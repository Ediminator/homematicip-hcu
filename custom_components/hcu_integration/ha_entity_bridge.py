"""Bridge to expose selected Home Assistant entities to the HCU as plugin devices."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Awaitable
from uuid import uuid4

from homeassistant.const import (
    STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN,
    ATTR_FRIENDLY_NAME,
)
from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er

_LOGGER = logging.getLogger(__name__)

STATUS_EVENT_THROTTLE_SECONDS = 5.0

HA_MODEL_TYPE = "HOME_ASSISTANT"
HA_FIRMWARE_VERSION = "1.0.0"

# Maps HA sensor device_class → (HCU deviceType, HCU feature type)
SENSOR_CLASS_TO_DEVICE: dict[str, tuple[str, str]] = {
    "temperature":    ("CLIMATE_SENSOR",              "actualTemperature"),
    "humidity":       ("CLIMATE_SENSOR",              "humidity"),
    "moisture":       ("CLIMATE_SENSOR",              "humidity"),
    "illuminance":    ("CLIMATE_SENSOR",              "illumination"),
    "co2":            ("CLIMATE_SENSOR",              "co2Concentration"),
    "carbon_dioxide": ("CLIMATE_SENSOR",              "co2Concentration"),
    "wind_speed":     ("CLIMATE_SENSOR",              "windSpeed"),
    "precipitation":  ("CLIMATE_SENSOR",              "rainCount"),
    "power":          ("ENERGY_METER",                "currentPower"),
    "energy":         ("ENERGY_METER",                "energyCounter"),
    "pm25":           ("PARTICULATE_MATTER_SENSOR",   "particulateMassTwoPointFive"),
    "pm10":           ("PARTICULATE_MATTER_SENSOR",   "particulateMassTen"),
}

# Maps HA binary_sensor device_class → (HCU deviceType, HCU feature type)
BINARY_SENSOR_CLASS_TO_DEVICE: dict[str, tuple[str, str]] = {
    "door":       ("CONTACT_SENSOR",   "open"),
    "window":     ("CONTACT_SENSOR",   "open"),
    "opening":    ("CONTACT_SENSOR",   "open"),
    "motion":     ("OCCUPANCY_SENSOR", "motionDetected"),
    "occupancy":  ("OCCUPANCY_SENSOR", "presence"),
    "presence":   ("OCCUPANCY_SENSOR", "presence"),
    "smoke":      ("SMOKE_ALARM",      "smokeDetected"),
    "moisture":   ("WATER_SENSOR",     "waterlevelDetected"),
}

HA_ENTITY_PREFIX = "ha."


class HaEntityBridge:
    """Bridges selected HA entities to the HCU plugin protocol."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_ids: list[str],
        send_message_fn: Callable[[dict[str, Any]], Awaitable[None]],
        plugin_id: str,
    ) -> None:
        self.hass = hass
        self.entity_ids: set[str] = set(entity_ids)
        self._send_message = send_message_fn
        self._plugin_id = plugin_id
        self._unsub: Callable | None = None
        self._last_sent: dict[str, float] = {}

    # --- Device ID helpers ---

    @staticmethod
    def entity_to_device_id(entity_id: str) -> str:
        return f"{HA_ENTITY_PREFIX}{entity_id}"

    @staticmethod
    def device_to_entity_id(device_id: str) -> str | None:
        if device_id.startswith(HA_ENTITY_PREFIX):
            return device_id[len(HA_ENTITY_PREFIX):]
        return None

    def is_ha_device(self, device_id: str) -> bool:
        entity_id = self.device_to_entity_id(device_id)
        return entity_id is not None and entity_id in self.entity_ids

    # --- Device info helpers ---

    def _get_device_descriptor(self, entity_id: str, state: State | None) -> dict[str, Any] | None:
        """Return a Device object (without current feature values) for discovery."""
        domain = entity_id.split(".")[0]
        friendly_name = (state.attributes.get(ATTR_FRIENDLY_NAME) if state else None)
        if not friendly_name:
            reg = er.async_get(self.hass)
            entry = reg.async_get(entity_id)
            friendly_name = (entry.name or entry.original_name if entry else None) or entity_id

        base = {
            "deviceId": self.entity_to_device_id(entity_id),
            "friendlyName": friendly_name,
            "modelType": HA_MODEL_TYPE,
            "firmwareVersion": HA_FIRMWARE_VERSION,
        }

        if domain == "switch":
            vis = (state.attributes.get("switchVisualization") if state else None) or "SWITCH"
            if vis == "LIGHT":
                return {**base, "deviceType": "LIGHT",
                        "features": [{"type": "switchState"}, {"type": "dimming"}]}
            return {**base, "deviceType": "SWITCH", "features": [{"type": "switchState"}]}

        if domain == "light":
            return {**base, "deviceType": "LIGHT",
                    "features": [{"type": "switchState"}, {"type": "dimming"}]}

        if domain in ("sensor", "binary_sensor"):
            mapping_table = SENSOR_CLASS_TO_DEVICE if domain == "sensor" else BINARY_SENSOR_CLASS_TO_DEVICE
            device_class = (state.attributes.get("device_class") if state else None)
            if device_class is None:
                reg = er.async_get(self.hass)
                entry = reg.async_get(entity_id)
                if entry:
                    device_class = entry.device_class or entry.original_device_class
            device_class = device_class or ""
            mapping = mapping_table.get(device_class)
            if not mapping:
                return None
            device_type, feature_type = mapping
            return {**base, "deviceType": device_type, "features": [{"type": feature_type}]}

        return None

    # --- Discovery ---

    # Device types the HCU plugin inbox accepts. Read-only sensor types
    # (ENERGY_METER, CLIMATE_SENSOR, etc.) are rejected by the HCU and
    # cause the entire DISCOVER_RESPONSE to be silently dropped.
    _DISCOVERABLE_DEVICE_TYPES: set[str] = {"SWITCH", "LIGHT"}

    def build_discover_devices(self) -> list[dict[str, Any]]:
        """Build the device list for DISCOVER_RESPONSE, including current feature values."""
        devices = []
        for entity_id in sorted(self.entity_ids):
            state = self.hass.states.get(entity_id)
            descriptor = self._get_device_descriptor(entity_id, state)
            if descriptor and descriptor["deviceType"] in self._DISCOVERABLE_DEVICE_TYPES:
                if state is not None:
                    domain = entity_id.split(".")[0]
                    features = self._state_to_features(domain, state)
                    if features:
                        descriptor["features"] = features
                devices.append(descriptor)
            elif descriptor:
                _LOGGER.debug(
                    "Excluding %s (%s) from DISCOVER_RESPONSE: deviceType %s not accepted by HCU inbox",
                    entity_id, descriptor["friendlyName"], descriptor["deviceType"],
                )
        return devices

    # --- Status ---

    def build_status_devices(
        self, entity_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Build full Device objects with current feature values for STATUS_RESPONSE."""
        targets = entity_ids if entity_ids is not None else sorted(self.entity_ids)
        result = []
        for entity_id in targets:
            if entity_id not in self.entity_ids:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            domain = entity_id.split(".")[0]
            features = self._state_to_features(domain, state)
            if features is None:
                continue
            descriptor = self._get_device_descriptor(entity_id, state)
            if not descriptor:
                continue
            descriptor["features"] = features
            result.append(descriptor)
        return result

    def _state_to_features(
        self, domain: str, state: State
    ) -> list[dict[str, Any]] | None:
        """Convert HA state to HCU IFeature objects."""
        if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None

        if domain == "switch":
            return [{"type": "switchState", "on": state.state == STATE_ON}]

        if domain == "light":
            is_on = state.state == STATE_ON
            features: list[dict[str, Any]] = [{"type": "switchState", "on": is_on}]
            if is_on:
                brightness = state.attributes.get(ATTR_BRIGHTNESS)
                if brightness is not None:
                    features.append({"type": "dimming", "dimLevel": round(brightness / 255, 4)})
            return features

        if domain == "sensor":
            device_class = state.attributes.get("device_class") or ""
            mapping = SENSOR_CLASS_TO_DEVICE.get(device_class)
            if not mapping:
                return None
            _, feature_type = mapping
            try:
                value: int | float = float(state.state)
            except (ValueError, TypeError):
                return None
            if feature_type == "humidity":
                value = int(round(value))
            return [{"type": feature_type, feature_type: value}]

        if domain == "binary_sensor":
            device_class = state.attributes.get("device_class") or ""
            mapping = BINARY_SENSOR_CLASS_TO_DEVICE.get(device_class)
            if not mapping:
                return None
            _, feature_type = mapping
            return [{"type": feature_type, feature_type: state.state == STATE_ON}]

        return None

    # --- Control ---

    async def handle_control_request(self, body: dict[str, Any]) -> None:
        """Execute a ControlRequest targeting an HA entity."""
        device_id = body.get("deviceId", "")
        entity_id = self.device_to_entity_id(device_id)
        if not entity_id or entity_id not in self.entity_ids:
            return

        domain = entity_id.split(".")[0]
        features: list[dict[str, Any]] = body.get("features", [])

        # Set throttle before the service call so the state_changed listener
        # doesn't fire a duplicate STATUS_EVENT while we await blocking=True.
        self._last_sent[entity_id] = time.monotonic()

        for feature in features:
            feature_type = feature.get("type")

            if feature_type == "switchState":
                service = "turn_on" if feature.get("on") else "turn_off"
                _LOGGER.debug("Switching %s → %s", entity_id, "ON" if feature.get("on") else "OFF")
                try:
                    await self.hass.services.async_call(
                        domain, service, {"entity_id": entity_id}, blocking=True
                    )
                    _LOGGER.debug("Switched %s successfully", entity_id)
                except Exception as err:
                    _LOGGER.error("Service call %s.%s for %s failed: %s", domain, service, entity_id, err)
            elif feature_type == "dimming" and domain == "light":
                dim_level = feature.get("dimLevel")
                if dim_level is not None:
                    try:
                        brightness = int(float(dim_level) * 255)
                        _LOGGER.debug("Dimming %s → %.1f%% (brightness %d)", entity_id, float(dim_level) * 100, brightness)
                        await self.hass.services.async_call(
                            "light",
                            "turn_on",
                            {"entity_id": entity_id, "brightness": brightness},
                            blocking=True,
                        )
                        _LOGGER.debug("Dimmed %s successfully", entity_id)
                    except (ValueError, TypeError):
                        _LOGGER.warning("Invalid dimLevel value: %s", dim_level)
                    except Exception as err:
                        _LOGGER.error("Service call light.turn_on for %s failed: %s", entity_id, err)

    # --- Status Event ---

    async def send_status_event(self, entity_ids: list[str] | None = None) -> None:
        """Push current HA entity states to the HCU as STATUS_EVENTs (one per device)."""
        targets = entity_ids if entity_ids is not None else sorted(self.entity_ids)
        for entity_id in targets:
            if entity_id not in self.entity_ids:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            domain = entity_id.split(".")[0]
            features = self._state_to_features(domain, state)
            if not features:
                continue
            try:
                await self._send_message({
                    "id": str(uuid4()),
                    "pluginId": self._plugin_id,
                    "type": "STATUS_EVENT",
                    "body": {
                        "deviceId": self.entity_to_device_id(entity_id),
                        "features": features,
                    },
                })
            except ConnectionError:
                pass

    # --- State listener ---

    def start_listening(self) -> None:
        """Subscribe to HA state_changed events for managed entities."""
        if not self.entity_ids:
            return

        @callback
        def _on_state_changed(event: Any) -> None:
            entity_id = event.data.get("entity_id")
            if entity_id not in self.entity_ids:
                return
            now = time.monotonic()
            if now - self._last_sent.get(entity_id, 0) < STATUS_EVENT_THROTTLE_SECONDS:
                return
            self._last_sent[entity_id] = now
            self.hass.async_create_task(
                self.send_status_event([entity_id]),
                name=f"HCU status_event {entity_id}",
            )

        self._unsub = self.hass.bus.async_listen("state_changed", _on_state_changed)
        _LOGGER.debug("HaEntityBridge: listening to %d entities", len(self.entity_ids))

    def stop_listening(self) -> None:
        """Unsubscribe from HA state changes."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    # --- Config UI helper ---

    def get_entity_type_summary(self) -> str:
        """Return a human-readable summary of entity → HCU device type mapping."""
        if not self.entity_ids:
            return ""
        lines = []
        for entity_id in sorted(self.entity_ids):
            state = self.hass.states.get(entity_id)
            descriptor = self._get_device_descriptor(entity_id, state)
            if descriptor:
                device_type = descriptor["deviceType"]
                status = "discoverable" if device_type in self._DISCOVERABLE_DEVICE_TYPES else "status events only"
                lines.append(f"• {entity_id} → {device_type} ({status})")
            else:
                lines.append(f"• {entity_id} → (unsupported type)")
        return "\n".join(lines)
