"""Bridge to expose HA devices (groups of entities) to the HCU as plugin devices."""
from __future__ import annotations

import asyncio
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
from homeassistant.helpers import issue_registry as ir

from .const import (
    DOMAIN,
    HA_FEATURE_ON_OFF, HA_FEATURE_BRIGHTNESS, HA_FEATURE_COLOR_TEMP,
    HA_FEATURE_RGB_COLOR, HA_FEATURE_ON_TIME, HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY,
    HA_FEATURE_ILLUMINANCE, HA_FEATURE_CO2, HA_FEATURE_WIND_SPEED,
    HA_FEATURE_PRECIPITATION, HA_FEATURE_STORM, HA_FEATURE_SUNSHINE, HA_FEATURE_RAINING,
    HA_FEATURE_WIND_DIRECTION, HA_FEATURE_SUNSHINE_DURATION,
    HA_FEATURE_POWER, HA_FEATURE_ENERGY,
    HA_FEATURE_PM1, HA_FEATURE_PM25, HA_FEATURE_PM10, HA_FEATURE_MOTION, HA_FEATURE_OCCUPANCY,
    HA_FEATURE_DOOR, HA_FEATURE_WINDOW, HA_FEATURE_SMOKE,
    HA_FEATURE_MOISTURE, HA_FEATURE_MOISTURE_DETECTED,
    HA_FEATURE_BATTERY, HA_FEATURE_VEHICLE_RANGE, HA_FEATURE_CLIMATE_OPERATION_MODE,
    HA_FEATURE_COOLING_TEMP_OFFSET, HA_FEATURE_HEATING_TEMP_OFFSET, HA_FEATURE_PRESENCE_MODE,
    HA_FEATURE_HOT_WATER_BOOST, HA_FEATURE_SUPPLY_TEMPERATURE, HA_FEATURE_SET_POINT_TEMP,
    HA_FEATURE_SHUTTER_LEVEL, HA_FEATURE_SLATS_LEVEL, HA_FEATURE_SHUTTER_DIRECTION,
    HA_FEATURE_LOW_BAT, HA_FEATURE_SABOTAGE, HA_FEATURE_UNREACH, HA_MAINTENANCE_FEATURE_KEYS,
    HA_DEVICE_TYPE_FEATURES,
    HA_DEVICE_ID_PREFIX,
    determine_ha_device_type,
)

_LOGGER = logging.getLogger(__name__)

# Removed from homeassistant.components.light in newer HA versions
ATTR_COLOR_TEMP = "color_temp"
ATTR_RGB_COLOR = "rgb_color"

STATUS_EVENT_THROTTLE_SECONDS = 5.0

HA_MODEL_TYPE = "HOME_ASSISTANT"
HA_FIRMWARE_VERSION = "1.0.0"

# Feature key → HCU feature descriptor (for DISCOVER_RESPONSE, no values).
# HA_MAINTENANCE_FEATURE_KEYS are handled separately as a single composite descriptor.
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
    HA_FEATURE_STORM:         {"type": "storm"},
    HA_FEATURE_SUNSHINE:      {"type": "sunshine"},
    HA_FEATURE_RAINING:       {"type": "raining"},
    HA_FEATURE_WIND_DIRECTION: {"type": "windDirection"},
    HA_FEATURE_SUNSHINE_DURATION: {"type": "sunshineDuration"},
    HA_FEATURE_POWER:         {"type": "currentPower"},
    HA_FEATURE_ENERGY:        {"type": "energyCounter"},
    HA_FEATURE_PM1:           {"type": "particulateMassOne"},
    HA_FEATURE_PM25:          {"type": "particulateMassTwoPointFive"},
    HA_FEATURE_PM10:          {"type": "particulateMassTen"},
    HA_FEATURE_MOTION:        {"type": "motionDetected"},
    HA_FEATURE_OCCUPANCY:     {"type": "presence"},
    HA_FEATURE_DOOR:          {"type": "open"},
    HA_FEATURE_WINDOW:        {"type": "open"},
    HA_FEATURE_SMOKE:         {"type": "smokeDetected"},
    HA_FEATURE_MOISTURE:      {"type": "waterlevelDetected"},
    HA_FEATURE_MOISTURE_DETECTED: {"type": "moistureDetected"},
    HA_FEATURE_BATTERY:       {"type": "batteryLevel"},
    HA_FEATURE_VEHICLE_RANGE: {"type": "vehicleRange"},
    HA_FEATURE_CLIMATE_OPERATION_MODE: {"type": "climateOperationMode"},
    HA_FEATURE_COOLING_TEMP_OFFSET: {"type": "coolingTemperatureOffset"},
    HA_FEATURE_HEATING_TEMP_OFFSET: {"type": "heatingTemperatureOffset"},
    HA_FEATURE_PRESENCE_MODE: {"type": "presenceMode"},
    HA_FEATURE_HOT_WATER_BOOST: {"type": "hotWaterBoost"},
    HA_FEATURE_SUPPLY_TEMPERATURE: {"type": "supplyTemperature"},
    HA_FEATURE_SET_POINT_TEMP: {"type": "setPointTemperature"},
    HA_FEATURE_SHUTTER_LEVEL: {"type": "shutterLevel"},
    HA_FEATURE_SLATS_LEVEL:   {"type": "slatsLevel"},
    HA_FEATURE_SHUTTER_DIRECTION: {"type": "shutterDirection"},
}

# HA_FEATURE_* key → HCU field name used inside the combined "maintenance" object
_MAINTENANCE_FIELD: dict[str, str] = {
    HA_FEATURE_LOW_BAT: "lowBat",
    HA_FEATURE_SABOTAGE: "sabotage",
    HA_FEATURE_UNREACH: "unreach",
}

# Device types the HCU plugin inbox accepts for discovery — currently all
# documented types (see .docs/flows/ha_entity_bridge_flow.md)
_DISCOVERABLE_DEVICE_TYPES: set[str] = set(HA_DEVICE_TYPE_FEATURES)

# Device types the HCU can send CONTROL_REQUEST for; all other types are
# status/discovery only (sensors, meters, …).
_CONTROLLABLE_DEVICE_TYPES: set[str] = {"SWITCH", "LIGHT"}


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

        if feature_key == HA_FEATURE_STORM:
            return {"type": "storm", "storm": state.state == STATE_ON}

        if feature_key == HA_FEATURE_SUNSHINE:
            return {"type": "sunshine", "sunshine": state.state == STATE_ON}

        if feature_key == HA_FEATURE_RAINING:
            return {"type": "raining", "raining": state.state == STATE_ON}

        if feature_key == HA_FEATURE_WIND_DIRECTION:
            return {"type": "windDirection", "windDirection": float(state.state)}

        if feature_key == HA_FEATURE_SUNSHINE_DURATION:
            return {"type": "sunshineDuration", "sunshineDuration": float(state.state)}

        if feature_key == HA_FEATURE_POWER:
            return {"type": "currentPower", "currentPower": float(state.state)}

        if feature_key == HA_FEATURE_ENERGY:
            return {"type": "energyCounter", "energyCounter": float(state.state)}

        if feature_key == HA_FEATURE_PM1:
            return {"type": "particulateMassOne", "particulateMassOne": float(state.state)}

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

        if feature_key == HA_FEATURE_MOISTURE_DETECTED:
            return {"type": "moistureDetected", "moistureDetected": state.state == STATE_ON}

        if feature_key == HA_FEATURE_BATTERY:
            return {"type": "batteryLevel", "batteryLevel": int(round(float(state.state)))}

        if feature_key == HA_FEATURE_VEHICLE_RANGE:
            return {"type": "vehicleRange", "vehicleRange": float(state.state)}

        if feature_key == HA_FEATURE_CLIMATE_OPERATION_MODE:
            return {"type": "climateOperationMode", "climateOperationMode": state.state}

        if feature_key == HA_FEATURE_COOLING_TEMP_OFFSET:
            return {"type": "coolingTemperatureOffset", "coolingTemperatureOffset": float(state.state)}

        if feature_key == HA_FEATURE_HEATING_TEMP_OFFSET:
            return {"type": "heatingTemperatureOffset", "heatingTemperatureOffset": float(state.state)}

        if feature_key == HA_FEATURE_PRESENCE_MODE:
            return {"type": "presenceMode", "presenceMode": state.state}

        if feature_key == HA_FEATURE_HOT_WATER_BOOST:
            return {"type": "hotWaterBoost", "hotWaterBoost": state.state == STATE_ON}

        if feature_key == HA_FEATURE_SUPPLY_TEMPERATURE:
            return {"type": "supplyTemperature", "supplyTemperature": float(state.state)}

        if feature_key == HA_FEATURE_SET_POINT_TEMP:
            return {"type": "setPointTemperature", "setPointTemperature": float(state.state)}

        if feature_key == HA_FEATURE_SHUTTER_LEVEL:
            return {"type": "shutterLevel", "shutterLevel": float(state.state)}

        if feature_key == HA_FEATURE_SLATS_LEVEL:
            return {"type": "slatsLevel", "slatsLevel": float(state.state)}

        if feature_key == HA_FEATURE_SHUTTER_DIRECTION:
            return {"type": "shutterDirection", "shutterDirection": state.state}

    except (ValueError, TypeError):
        return None

    return None


def _build_maintenance_value(hass: HomeAssistant, features_conf: dict[str, str]) -> dict[str, Any] | None:
    """Combine the up-to-3 configured maintenance entities into one HCU object.

    Only included fields have a known, non-unavailable state; the object is
    omitted entirely if none of the configured entities currently have a value.
    """
    obj: dict[str, Any] = {}
    for feature_key, hcu_field in _MAINTENANCE_FIELD.items():
        entity_id = features_conf.get(feature_key)
        if not entity_id:
            continue
        state = hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            continue
        obj[hcu_field] = state.state == STATE_ON
    if not obj:
        return None
    return {"type": "maintenance", **obj}


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
        self._last_sent_features: dict[str, list[dict[str, Any]]] = {}  # keyed by HCU device ID
        # HCU device IDs the HCU has actually been told about via DISCOVER_RESPONSE.
        # Proactive STATUS_EVENT pushes are gated on this — sending state for a
        # device the HCU never discovered would be a protocol violation.
        self._discovered_hcu_ids: set[str] = set()

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
            if key in HA_MAINTENANCE_FEATURE_KEYS:
                continue
            desc = _DISCOVER_FEATURE.get(key)
            if desc:
                result.append(dict(desc))
        if any(key in features for key in HA_MAINTENANCE_FEATURE_KEYS):
            result.append({"type": "maintenance"})
        return result

    def _build_value_features(self, device: dict[str, Any]) -> list[dict[str, Any]] | None:
        features_conf: dict[str, str] = device.get("features", {})
        result = []
        for key, entity_id in features_conf.items():
            if key in HA_MAINTENANCE_FEATURE_KEYS or not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            val = _feature_value(key, state)
            if val is not None:
                result.append(val)
        maintenance = _build_maintenance_value(self.hass, features_conf)
        if maintenance is not None:
            result.append(maintenance)
        return result if result else None

    def _build_device_object(
        self, device: dict[str, Any], include_values: bool
    ) -> dict[str, Any] | None:
        features_conf: dict[str, str] = device.get("features", {})
        if not features_conf:
            return None

        device_type = device.get("type") or determine_ha_device_type(features_conf)
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
                val_features = self._build_value_features(device)
                if val_features:
                    obj["features"] = val_features
                devices.append(obj)
            else:
                _LOGGER.debug(
                    "Excluding device %s (%s) from DISCOVER_RESPONSE: type %s not accepted by HCU inbox",
                    obj["deviceId"], obj["friendlyName"], obj["deviceType"],
                )
        self._discovered_hcu_ids.update(d["deviceId"] for d in devices)
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
                        continue

                    if service == "turn_on":
                        on_time_secs = self._get_control_on_time(body.get("features", []), feature, features_conf)
                        if on_time_secs and on_time_secs > 0:
                            self.hass.async_create_task(
                                self._auto_off_after(entity_id, domain, on_time_secs),
                                name=f"HCU on_time auto-off {entity_id}",
                            )

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

    def _get_control_on_time(
        self, body_features: list[dict[str, Any]], switch_feature: dict[str, Any], features_conf: dict[str, str]
    ) -> float | None:
        """Resolve the auto-off delay for a switchState turn-on.

        Priority: value on the switchState feature itself > a sibling "onTime"
        feature in the same CONTROL_REQUEST > the configured on_time entity.
        """
        if (value := switch_feature.get("onTime")) is not None:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass

        for other in body_features:
            if other.get("type") == "onTime" and other.get("onTime") is not None:
                try:
                    return float(other["onTime"])
                except (ValueError, TypeError):
                    pass

        entity_id = features_conf.get(HA_FEATURE_ON_TIME)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN):
                try:
                    return float(state.state)
                except (ValueError, TypeError):
                    pass

        return None

    async def _auto_off_after(self, entity_id: str, domain: str, delay_secs: float) -> None:
        await asyncio.sleep(delay_secs)
        try:
            await self.hass.services.async_call(domain, "turn_off", {"entity_id": entity_id}, blocking=True)
        except Exception as err:
            _LOGGER.error("on_time auto-off for %s failed: %s", entity_id, err)

    # --- Status Event ---

    async def send_status_event(self, hcu_device_ids: list[str] | None = None) -> None:
        targets = (
            [self._by_hcu_id[did] for did in hcu_device_ids if did in self._by_hcu_id]
            if hcu_device_ids is not None
            else self._ha_devices
        )
        now = time.monotonic()
        for device in targets:
            hcu_id = self._make_hcu_id(device)
            if hcu_id not in self._discovered_hcu_ids:
                # HCU has never been told about this device via DISCOVER_RESPONSE —
                # pushing state for it would be a protocol violation.
                continue
            features = self._build_value_features(device)
            if not features:
                continue
            if (
                features == self._last_sent_features.get(hcu_id)
                and now - self._last_sent.get(hcu_id, 0) < STATUS_EVENT_THROTTLE_SECONDS
            ):
                # Same value we already reported, reported recently — skip to
                # avoid flooding the HCU with redundant updates (e.g. a fast
                # sensor). An actually *different* value is never skipped here,
                # no matter how soon after the last send: it may be the real,
                # confirmed state arriving shortly after a CONTROL_REQUEST's
                # optimistic report, and must not be dropped.
                continue
            self._last_sent[hcu_id] = now
            self._last_sent_features[hcu_id] = features
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
            # Throttling/dedup against redundant sends happens centrally in
            # send_status_event(), based on whether the reported value actually
            # changed — not just on elapsed time.
            self.hass.async_create_task(
                self.send_status_event(list(hcu_ids)),
                name=f"HCU status_event {entity_id}",
            )

        self._unsub = self.hass.bus.async_listen("state_changed", _on_state_changed)
        _LOGGER.debug(
            "HaEntityBridge: listening for %d entities across %d devices",
            len(all_ids), len(self._ha_devices),
        )

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
            device_type = device.get("type") or (determine_ha_device_type(features_conf) if features_conf else "?")
            n_features = len(features_conf)
            controllable = device_type in _CONTROLLABLE_DEVICE_TYPES
            status = "controllable" if controllable else "status events only"
            lines.append(
                f"• **{self._get_friendly_name(device)}** — {device_type} ({n_features} feature(s), {status})"
            )
        return "\n".join(lines)

    def device_to_entity_id(self, device_id: str) -> str | None:
        """Return None — new model uses device IDs, not entity IDs."""
        return None
