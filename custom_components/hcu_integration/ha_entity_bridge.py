"""Bridge to expose HA devices (groups of entities) to the HCU as plugin devices."""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Awaitable
from uuid import uuid4

from homeassistant.const import (
    STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN,
    ATTR_FRIENDLY_NAME,
)
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_COLOR_TEMP, ATTR_RGB_COLOR,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir

from .const import (
    DOMAIN,
    HA_FEATURE_ON_OFF, HA_FEATURE_BRIGHTNESS, HA_FEATURE_COLOR_TEMP,
    HA_FEATURE_RGB_COLOR, HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY,
    HA_FEATURE_ILLUMINANCE, HA_FEATURE_CO2, HA_FEATURE_WIND_SPEED,
    HA_FEATURE_PRECIPITATION, HA_FEATURE_POWER, HA_FEATURE_ENERGY,
    HA_FEATURE_PM25, HA_FEATURE_PM10, HA_FEATURE_MOTION, HA_FEATURE_OCCUPANCY,
    HA_FEATURE_DOOR, HA_FEATURE_WINDOW, HA_FEATURE_SMOKE, HA_FEATURE_MOISTURE,
)

_LOGGER = logging.getLogger(__name__)

STATUS_EVENT_THROTTLE_SECONDS = 5.0

HA_DEVICE_ID_PREFIX = "ha."
HA_MODEL_TYPE = "HOME_ASSISTANT"
HA_FIRMWARE_VERSION = "1.0.0"

# Feature key → HCU feature descriptor (for DISCOVER_RESPONSE, no values)
_DISCOVER_FEATURE: dict[str, dict[str, Any]] = {
    HA_FEATURE_ON_OFF:        {"type": "switchState"},
    HA_FEATURE_BRIGHTNESS:    {"type": "dimming"},
    HA_FEATURE_COLOR_TEMP:    {"type": "colorTemperature"},
    HA_FEATURE_RGB_COLOR:     {"type": "color"},
    HA_FEATURE_TEMPERATURE:   {"type": "actualTemperature"},
    HA_FEATURE_HUMIDITY:      {"type": "humidity"},
    HA_FEATURE_ILLUMINANCE:   {"type": "illumination"},
    HA_FEATURE_CO2:           {"type": "co2Concentration"},
    HA_FEATURE_WIND_SPEED:    {"type": "windSpeed"},
    HA_FEATURE_PRECIPITATION: {"type": "rainCount"},
    HA_FEATURE_POWER:         {"type": "currentPower"},
    HA_FEATURE_ENERGY:        {"type": "energyCounter"},
    HA_FEATURE_PM25:          {"type": "particulateMassTwoPointFive"},
    HA_FEATURE_PM10:          {"type": "particulateMassTen"},
    HA_FEATURE_MOTION:        {"type": "motionDetected"},
    HA_FEATURE_OCCUPANCY:     {"type": "presence"},
    HA_FEATURE_DOOR:          {"type": "open"},
    HA_FEATURE_WINDOW:        {"type": "open"},
    HA_FEATURE_SMOKE:         {"type": "smokeDetected"},
    HA_FEATURE_MOISTURE:      {"type": "waterlevelDetected"},
}

# Device types the HCU plugin inbox accepts for discovery
_DISCOVERABLE_DEVICE_TYPES: set[str] = {"SWITCH", "LIGHT"}


def _determine_device_type(features: dict[str, str]) -> str:
    keys = set(features)
    if keys & {HA_FEATURE_BRIGHTNESS, HA_FEATURE_COLOR_TEMP, HA_FEATURE_RGB_COLOR}:
        return "LIGHT"
    if HA_FEATURE_ON_OFF in keys:
        return "LIGHT" if features[HA_FEATURE_ON_OFF].startswith("light.") else "SWITCH"
    if keys & {HA_FEATURE_POWER, HA_FEATURE_ENERGY}:
        return "ENERGY_METER"
    if keys & {HA_FEATURE_PM25, HA_FEATURE_PM10}:
        return "PARTICULATE_MATTER_SENSOR"
    if keys & {HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY, HA_FEATURE_ILLUMINANCE,
               HA_FEATURE_CO2, HA_FEATURE_WIND_SPEED, HA_FEATURE_PRECIPITATION}:
        return "CLIMATE_SENSOR"
    if keys & {HA_FEATURE_MOTION, HA_FEATURE_OCCUPANCY}:
        return "OCCUPANCY_SENSOR"
    if keys & {HA_FEATURE_DOOR, HA_FEATURE_WINDOW}:
        return "CONTACT_SENSOR"
    if HA_FEATURE_SMOKE in keys:
        return "SMOKE_ALARM"
    if HA_FEATURE_MOISTURE in keys:
        return "WATER_SENSOR"
    return "SWITCH"


def _feature_value(feature_key: str, state: State) -> dict[str, Any] | None:
    """Convert HA state to HCU feature value dict. Returns None if unavailable."""
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None

    try:
        if feature_key == HA_FEATURE_ON_OFF:
            return {"type": "switchState", "on": state.state == STATE_ON}

        if feature_key == HA_FEATURE_BRIGHTNESS:
            if state.state != STATE_ON:
                return None
            bri = state.attributes.get(ATTR_BRIGHTNESS)
            if bri is None:
                return None
            return {"type": "dimming", "dimLevel": round(bri / 255, 4)}

        if feature_key == HA_FEATURE_COLOR_TEMP:
            ct = state.attributes.get(ATTR_COLOR_TEMP)
            if ct is None:
                return None
            return {"type": "colorTemperature", "colorTemperature": int(ct)}

        if feature_key == HA_FEATURE_RGB_COLOR:
            rgb = state.attributes.get(ATTR_RGB_COLOR)
            if rgb is None:
                return None
            r, g, b = rgb
            return {"type": "color", "red": r, "green": g, "blue": b}

        if feature_key == HA_FEATURE_TEMPERATURE:
            return {"type": "actualTemperature", "actualTemperature": float(state.state)}

        if feature_key == HA_FEATURE_HUMIDITY:
            return {"type": "humidity", "humidity": int(round(float(state.state)))}

        if feature_key == HA_FEATURE_ILLUMINANCE:
            return {"type": "illumination", "illumination": float(state.state)}

        if feature_key == HA_FEATURE_CO2:
            return {"type": "co2Concentration", "co2Concentration": float(state.state)}

        if feature_key == HA_FEATURE_WIND_SPEED:
            return {"type": "windSpeed", "windSpeed": float(state.state)}

        if feature_key == HA_FEATURE_PRECIPITATION:
            return {"type": "rainCount", "rainCount": float(state.state)}

        if feature_key == HA_FEATURE_POWER:
            return {"type": "currentPower", "currentPower": float(state.state)}

        if feature_key == HA_FEATURE_ENERGY:
            return {"type": "energyCounter", "energyCounter": float(state.state)}

        if feature_key == HA_FEATURE_PM25:
            return {"type": "particulateMassTwoPointFive", "particulateMassTwoPointFive": float(state.state)}

        if feature_key == HA_FEATURE_PM10:
            return {"type": "particulateMassTen", "particulateMassTen": float(state.state)}

        if feature_key == HA_FEATURE_MOTION:
            return {"type": "motionDetected", "motionDetected": state.state == STATE_ON}

        if feature_key == HA_FEATURE_OCCUPANCY:
            return {"type": "presence", "presence": state.state == STATE_ON}

        if feature_key in (HA_FEATURE_DOOR, HA_FEATURE_WINDOW):
            return {"type": "open", "open": state.state == STATE_ON}

        if feature_key == HA_FEATURE_SMOKE:
            return {"type": "smokeDetected", "smokeDetected": state.state == STATE_ON}

        if feature_key == HA_FEATURE_MOISTURE:
            return {"type": "waterlevelDetected", "waterlevelDetected": state.state == STATE_ON}

    except (ValueError, TypeError):
        return None

    return None


class HaEntityBridge:
    """Bridges configured HA devices (with grouped entity features) to the HCU plugin protocol."""

    def __init__(
        self,
        hass: HomeAssistant,
        ha_devices: list[dict[str, Any]],
        send_message_fn: Callable[[dict[str, Any]], Awaitable[None]],
        plugin_id: str,
    ) -> None:
        self.hass = hass
        self._ha_devices: list[dict[str, Any]] = ha_devices
        self._send_message = send_message_fn
        self._plugin_id = plugin_id
        self._unsub: Callable | None = None
        self._last_sent: dict[str, float] = {}  # keyed by HCU device ID

        # Build lookup maps
        self._by_hcu_id: dict[str, dict[str, Any]] = {}
        self._entity_to_hcu_ids: dict[str, set[str]] = {}
        for device in ha_devices:
            hcu_id = self._make_hcu_id(device)
            self._by_hcu_id[hcu_id] = device
            for entity_id in device.get("features", {}).values():
                if entity_id:
                    self._entity_to_hcu_ids.setdefault(entity_id, set()).add(hcu_id)

    # --- ID helpers ---

    @staticmethod
    def _make_hcu_id(device: dict[str, Any]) -> str:
        return f"{HA_DEVICE_ID_PREFIX}{device['id']}"

    @staticmethod
    def _is_ha_device_id(device_id: str) -> bool:
        return device_id.startswith(HA_DEVICE_ID_PREFIX)

    def is_known_device(self, hcu_device_id: str) -> bool:
        return hcu_device_id in self._by_hcu_id

    # Backward-compat alias used by api.py
    def is_ha_device(self, device_id: str) -> bool:
        return self.is_known_device(device_id)

    @property
    def all_entity_ids(self) -> set[str]:
        return set(self._entity_to_hcu_ids.keys())

    # --- Descriptor helpers ---

    def _get_friendly_name(self, device: dict[str, Any]) -> str:
        name = device.get("name", "").strip()
        return name if name else device["id"]

    def _build_discover_features(self, features: dict[str, str]) -> list[dict[str, Any]]:
        result = []
        for key in features:
            desc = _DISCOVER_FEATURE.get(key)
            if desc:
                result.append(dict(desc))
        return result

    def _build_value_features(self, device: dict[str, Any]) -> list[dict[str, Any]] | None:
        features_conf: dict[str, str] = device.get("features", {})
        result = []
        for key, entity_id in features_conf.items():
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            val = _feature_value(key, state)
            if val is not None:
                result.append(val)
        return result if result else None

    def _build_device_object(
        self, device: dict[str, Any], include_values: bool
    ) -> dict[str, Any] | None:
        features_conf: dict[str, str] = device.get("features", {})
        if not features_conf:
            return None

        device_type = _determine_device_type(features_conf)
        hcu_id = self._make_hcu_id(device)

        obj: dict[str, Any] = {
            "deviceId": hcu_id,
            "friendlyName": self._get_friendly_name(device),
            "modelType": HA_MODEL_TYPE,
            "firmwareVersion": HA_FIRMWARE_VERSION,
            "deviceType": device_type,
        }

        if include_values:
            features = self._build_value_features(device)
            if features is None:
                return None
            obj["features"] = features
        else:
            obj["features"] = self._build_discover_features(features_conf)

        return obj

    # --- Discovery ---

    def build_discover_devices(self) -> list[dict[str, Any]]:
        devices = []
        for device in self._ha_devices:
            obj = self._build_device_object(device, include_values=False)
            if obj is None:
                continue
            if obj["deviceType"] in _DISCOVERABLE_DEVICE_TYPES:
                # Include current state values for discoverable devices
                val_features = self._build_value_features(device)
                if val_features:
                    obj["features"] = val_features
                devices.append(obj)
            else:
                _LOGGER.debug(
                    "Excluding device %s (%s) from DISCOVER_RESPONSE: type %s not accepted by HCU inbox",
                    obj["deviceId"], obj["friendlyName"], obj["deviceType"],
                )
        return devices

    # --- Status ---

    def build_status_devices(
        self, hcu_device_ids: list[str] | None = None
    ) -> list[dict[str, Any]]:
        targets = (
            [self._by_hcu_id[did] for did in hcu_device_ids if did in self._by_hcu_id]
            if hcu_device_ids is not None
            else self._ha_devices
        )
        result = []
        for device in targets:
            obj = self._build_device_object(device, include_values=True)
            if obj is not None:
                result.append(obj)
        return result

    # --- Control ---

    async def handle_control_request(self, body: dict[str, Any]) -> None:
        hcu_device_id = body.get("deviceId", "")
        device = self._by_hcu_id.get(hcu_device_id)
        if not device:
            return

        features_conf: dict[str, str] = device.get("features", {})
        self._last_sent[hcu_device_id] = time.monotonic()

        for feature in body.get("features", []):
            feature_type = feature.get("type")

            if feature_type == "switchState":
                entity_id = features_conf.get(HA_FEATURE_ON_OFF)
                if entity_id:
                    domain = entity_id.split(".")[0]
                    service = "turn_on" if feature.get("on") else "turn_off"
                    try:
                        await self.hass.services.async_call(
                            domain, service, {"entity_id": entity_id}, blocking=True
                        )
                    except Exception as err:
                        _LOGGER.error("Service %s.%s for %s failed: %s", domain, service, entity_id, err)

            elif feature_type == "dimming":
                entity_id = features_conf.get(HA_FEATURE_BRIGHTNESS) or features_conf.get(HA_FEATURE_ON_OFF)
                if entity_id and entity_id.startswith("light."):
                    dim_level = feature.get("dimLevel")
                    if dim_level is not None:
                        try:
                            brightness = int(float(dim_level) * 255)
                            await self.hass.services.async_call(
                                "light", "turn_on", {"entity_id": entity_id, "brightness": brightness}, blocking=True
                            )
                        except Exception as err:
                            _LOGGER.error("Dimming %s failed: %s", entity_id, err)

            elif feature_type == "colorTemperature":
                entity_id = features_conf.get(HA_FEATURE_COLOR_TEMP)
                if entity_id:
                    ct = feature.get("colorTemperature")
                    if ct is not None:
                        try:
                            await self.hass.services.async_call(
                                "light", "turn_on", {"entity_id": entity_id, "color_temp": int(ct)}, blocking=True
                            )
                        except Exception as err:
                            _LOGGER.error("Color temp %s failed: %s", entity_id, err)

            elif feature_type == "color":
                entity_id = features_conf.get(HA_FEATURE_RGB_COLOR)
                if entity_id:
                    r, g, b = feature.get("red", 0), feature.get("green", 0), feature.get("blue", 0)
                    try:
                        await self.hass.services.async_call(
                            "light", "turn_on", {"entity_id": entity_id, "rgb_color": [r, g, b]}, blocking=True
                        )
                    except Exception as err:
                        _LOGGER.error("RGB color %s failed: %s", entity_id, err)

    # --- Status Event ---

    async def send_status_event(self, hcu_device_ids: list[str] | None = None) -> None:
        targets = (
            [self._by_hcu_id[did] for did in hcu_device_ids if did in self._by_hcu_id]
            if hcu_device_ids is not None
            else self._ha_devices
        )
        for device in targets:
            features = self._build_value_features(device)
            if not features:
                continue
            hcu_id = self._make_hcu_id(device)
            try:
                await self._send_message({
                    "id": str(uuid4()),
                    "pluginId": self._plugin_id,
                    "type": "STATUS_EVENT",
                    "body": {
                        "deviceId": hcu_id,
                        "features": features,
                    },
                })
            except ConnectionError:
                pass

    # --- Stale device detection ---

    async def handle_stale_inclusion_devices(self, device_ids: list[str]) -> None:
        for device_id in device_ids:
            if not self._is_ha_device_id(device_id):
                continue
            if device_id in self._by_hcu_id:
                continue
            _LOGGER.info(
                "Device %s is still registered with HCU but no longer configured — creating repair issue",
                device_id,
            )
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                f"ha_entity_excluded_{device_id.replace('.', '_').replace('-', '_')}",
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="ha_entity_excluded",
                translation_placeholders={"entity_id": device_id},
            )

    # --- State listener ---

    def start_listening(self) -> None:
        all_ids = self.all_entity_ids
        if not all_ids:
            return

        @callback
        def _on_state_changed(event: Any) -> None:
            entity_id = event.data.get("entity_id")
            hcu_ids = self._entity_to_hcu_ids.get(entity_id)
            if not hcu_ids:
                return
            now = time.monotonic()
            for hcu_id in hcu_ids:
                if now - self._last_sent.get(hcu_id, 0) < STATUS_EVENT_THROTTLE_SECONDS:
                    continue
                self._last_sent[hcu_id] = now
                self.hass.async_create_task(
                    self.send_status_event([hcu_id]),
                    name=f"HCU status_event {hcu_id}",
                )

        self._unsub = self.hass.bus.async_listen("state_changed", _on_state_changed)
        _LOGGER.debug("HaEntityBridge: listening for %d entities across %d devices", len(all_ids), len(self._ha_devices))

    def stop_listening(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None

    # --- Config UI helper ---

    def get_device_summary(self) -> str:
        if not self._ha_devices:
            return ""
        lines = []
        for device in self._ha_devices:
            features_conf = device.get("features", {})
            device_type = _determine_device_type(features_conf) if features_conf else "?"
            n_features = len(features_conf)
            discoverable = device_type in _DISCOVERABLE_DEVICE_TYPES
            status = "controllable" if discoverable else "status events only"
            lines.append(
                f"• **{self._get_friendly_name(device)}** — {device_type} ({n_features} feature(s), {status})"
            )
        return "\n".join(lines)

    # --- Backward-compat shim (api.py still calls device_to_entity_id in one place) ---

    def device_to_entity_id(self, device_id: str) -> str | None:
        """Return None — new model uses device IDs, not entity IDs."""
        return None
