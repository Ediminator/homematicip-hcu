"""Bridge to expose HA devices (groups of entities) to the HCU as plugin devices."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
import colorsys
from dataclasses import dataclass
import logging
import math
import time
from typing import Any
from uuid import uuid4

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, State, callback
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.unit_conversion import (
    BaseUnitConverter,
    DistanceConverter,
    DurationConverter,
    EnergyConverter,
    PowerConverter,
    SpeedConverter,
    TemperatureConverter,
    TemperatureDeltaConverter,
)

from .const import (
    CONTROL_ERROR_FAILED,
    CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
    CONTROL_ERROR_UNKNOWN_DEVICE,
    DOMAIN,
    HA_DEVICE_ID_PREFIX,
    HA_DEVICE_TYPE_FEATURES,
    HA_FEATURE_BATTERY,
    HA_FEATURE_BRIGHTNESS,
    HA_FEATURE_CLIMATE_OPERATION_MODE,
    HA_FEATURE_CO2,
    HA_FEATURE_COLOR_TEMP,
    HA_FEATURE_CONTACT_SENSOR,
    HA_FEATURE_COOLING_TEMP_OFFSET,
    HA_FEATURE_DOOR,
    HA_FEATURE_ENERGY,
    HA_FEATURE_HEATING_TEMP_OFFSET,
    HA_FEATURE_HOT_WATER_BOOST,
    HA_FEATURE_HUMIDITY,
    HA_FEATURE_ILLUMINANCE,
    HA_FEATURE_LOW_BAT,
    HA_FEATURE_MOISTURE,
    HA_FEATURE_MOISTURE_DETECTED,
    HA_FEATURE_MOTION,
    HA_FEATURE_OCCUPANCY,
    HA_FEATURE_ON_OFF,
    HA_FEATURE_ON_TIME,
    HA_FEATURE_PM1,
    HA_FEATURE_PM10,
    HA_FEATURE_PM25,
    HA_FEATURE_POWER,
    HA_FEATURE_PRECIPITATION,
    HA_FEATURE_PRESENCE_MODE,
    HA_FEATURE_RAINING,
    HA_FEATURE_RGB_COLOR,
    HA_FEATURE_SABOTAGE,
    HA_FEATURE_SET_POINT_TEMP,
    HA_FEATURE_SHUTTER_DIRECTION,
    HA_FEATURE_SHUTTER_LEVEL,
    HA_FEATURE_SLATS_LEVEL,
    HA_FEATURE_SMOKE,
    HA_FEATURE_STORM,
    HA_FEATURE_SUNSHINE,
    HA_FEATURE_SUNSHINE_DURATION,
    HA_FEATURE_SUPPLY_TEMPERATURE,
    HA_FEATURE_TEMPERATURE,
    HA_FEATURE_UNREACH,
    HA_FEATURE_VEHICLE_RANGE,
    HA_FEATURE_WIND_DIRECTION,
    HA_FEATURE_WIND_SPEED,
    HA_FEATURE_WINDOW,
    HA_MAINTENANCE_FEATURE_KEYS,
    determine_ha_device_type,
)

_LOGGER = logging.getLogger(__name__)

# Removed from homeassistant.components.light in newer HA versions
ATTR_COLOR_TEMP = "color_temp"
ATTR_RGB_COLOR = "rgb_color"

STATUS_EVENT_THROTTLE_SECONDS = 5.0

HA_MODEL_TYPE = "Homeassistant"
HA_FIRMWARE_VERSION = "0.0.0"

# Feature key → HCU feature descriptor (for DISCOVER_RESPONSE, no values).
# HA_MAINTENANCE_FEATURE_KEYS are handled separately as a single composite descriptor.
#
# Every "type" value here must be one of the Feature enum values from the
# official Connect API docs (section 6.6.6) — the HCU (or the app behind it)
# validates DISCOVER_RESPONSE against that schema, and an unrecognized "type"
# doesn't just get skipped, it appears to invalidate the *entire* response:
# none of the devices in that DISCOVER_RESPONSE show up in the app's inbox,
# not even otherwise-valid ones sent alongside it. See issue #306.
_DISCOVER_FEATURE: dict[str, dict[str, Any]] = {
    HA_FEATURE_ON_OFF: {"type": "switchState"},
    HA_FEATURE_BRIGHTNESS: {"type": "dimming"},
    HA_FEATURE_COLOR_TEMP: {"type": "colorTemperature"},
    HA_FEATURE_RGB_COLOR: {"type": "color"},
    HA_FEATURE_ON_TIME: {"type": "onTime"},
    HA_FEATURE_TEMPERATURE: {"type": "actualTemperature"},
    HA_FEATURE_HUMIDITY: {"type": "humidity"},
    HA_FEATURE_ILLUMINANCE: {"type": "illumination"},
    HA_FEATURE_CO2: {"type": "co2"},
    HA_FEATURE_WIND_SPEED: {"type": "windSpeed"},
    HA_FEATURE_PRECIPITATION: {"type": "rainCount"},
    HA_FEATURE_STORM: {"type": "storm"},
    HA_FEATURE_SUNSHINE: {"type": "sunshine"},
    HA_FEATURE_RAINING: {"type": "raining"},
    HA_FEATURE_WIND_DIRECTION: {"type": "windDirection"},
    HA_FEATURE_SUNSHINE_DURATION: {"type": "sunshineDuration"},
    HA_FEATURE_POWER: {"type": "currentPower"},
    HA_FEATURE_ENERGY: {"type": "energyCounter"},
    HA_FEATURE_PM1: {"type": "particulateMassOne"},
    HA_FEATURE_PM25: {"type": "particulateMassTwoPointFive"},
    HA_FEATURE_PM10: {"type": "particulateMassTen"},
    # The Connect API has no separate "motion" feature — PresenceDetected is
    # the only presence-related type, so both occupancy and motion map to it.
    HA_FEATURE_MOTION: {"type": "presenceDetected"},
    HA_FEATURE_OCCUPANCY: {"type": "presenceDetected"},
    HA_FEATURE_DOOR: {"type": "contactSensorState"},
    HA_FEATURE_WINDOW: {"type": "contactSensorState"},
    HA_FEATURE_CONTACT_SENSOR: {"type": "contactSensorState"},
    HA_FEATURE_SMOKE: {"type": "smokeAlarm"},
    HA_FEATURE_MOISTURE: {"type": "waterlevelDetected"},
    HA_FEATURE_MOISTURE_DETECTED: {"type": "moistureDetected"},
    HA_FEATURE_BATTERY: {"type": "batteryState"},
    HA_FEATURE_VEHICLE_RANGE: {"type": "vehicleRange"},
    HA_FEATURE_CLIMATE_OPERATION_MODE: {"type": "climateOperationMode"},
    HA_FEATURE_COOLING_TEMP_OFFSET: {"type": "coolingTemperatureOffset"},
    HA_FEATURE_HEATING_TEMP_OFFSET: {"type": "heatingTemperatureOffset"},
    HA_FEATURE_PRESENCE_MODE: {"type": "presenceMode"},
    HA_FEATURE_HOT_WATER_BOOST: {"type": "hotWaterBoost"},
    HA_FEATURE_SUPPLY_TEMPERATURE: {"type": "supplyTemperature"},
    HA_FEATURE_SET_POINT_TEMP: {"type": "setPointTemperature"},
    HA_FEATURE_SHUTTER_LEVEL: {"type": "shutterLevel"},
    HA_FEATURE_SLATS_LEVEL: {"type": "slatsLevel"},
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


_SPECIAL_TOLERANCE = 1e-6
_DIMMING_LAST_VALUE = 1.005
_DIMMING_IGNORE = 1.01
_HUE_LAST_VALUE = 360.0
_HUE_IGNORE = 361.0
_SAT_LAST_VALUE = 1.005
_SAT_IGNORE = 1.01
_COLOR_TEMP_KEEP_VALUES = frozenset({10050, 10100})
_COLOR_TEMP_UNSUPPORTED_MODES = frozenset({10150, 10200})

_ALLOWED_CLIMATE_OPERATION_MODES = frozenset({"AUTO", "COOLING", "HEATING"})
_ALLOWED_PRESENCE_MODES = frozenset({"AWAY", "DEFAULT", "HOME", "NORMAL", "VACATION"})
_ALLOWED_SHUTTER_DIRECTIONS = frozenset({"DARKER", "LIGHTER"})

_ENUM_FEATURES: dict[str, tuple[str, frozenset[str]]] = {
    HA_FEATURE_CLIMATE_OPERATION_MODE: (
        "climateOperationMode",
        _ALLOWED_CLIMATE_OPERATION_MODES,
    ),
    HA_FEATURE_PRESENCE_MODE: ("presenceMode", _ALLOWED_PRESENCE_MODES),
    HA_FEATURE_SHUTTER_DIRECTION: ("shutterDirection", _ALLOWED_SHUTTER_DIRECTIONS),
}


@dataclass(frozen=True)
class _NumericFeature:
    """Descriptor for converting, scaling, clamping, and rounding numeric features."""

    feature_type: str
    field: str
    converter: type[BaseUnitConverter] | None = None
    unit: str = ""
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False
    scale: Callable[[float], float] | None = None


_NUMERIC_FEATURES: dict[str, _NumericFeature] = {
    HA_FEATURE_TEMPERATURE: _NumericFeature(
        "actualTemperature",
        "actualTemperature",
        TemperatureConverter,
        UnitOfTemperature.CELSIUS,
        -50.0,
        60.0,
    ),
    HA_FEATURE_SUPPLY_TEMPERATURE: _NumericFeature(
        "supplyTemperature",
        "supplyTemperature",
        TemperatureConverter,
        UnitOfTemperature.CELSIUS,
        -50.0,
        60.0,
    ),
    HA_FEATURE_SET_POINT_TEMP: _NumericFeature(
        "setPointTemperature",
        "setPointTemperature",
        TemperatureConverter,
        UnitOfTemperature.CELSIUS,
        -50.0,
        60.0,
    ),
    HA_FEATURE_COOLING_TEMP_OFFSET: _NumericFeature(
        "coolingTemperatureOffset",
        "coolingTemperatureOffset",
        TemperatureDeltaConverter,
        UnitOfTemperature.CELSIUS,
        -50.0,
        50.0,
    ),
    HA_FEATURE_HEATING_TEMP_OFFSET: _NumericFeature(
        "heatingTemperatureOffset",
        "heatingTemperatureOffset",
        TemperatureDeltaConverter,
        UnitOfTemperature.CELSIUS,
        -50.0,
        50.0,
    ),
    HA_FEATURE_WIND_SPEED: _NumericFeature(
        "windSpeed",
        "windSpeed",
        SpeedConverter,
        UnitOfSpeed.KILOMETERS_PER_HOUR,
        0.0,
        400.0,
    ),
    HA_FEATURE_POWER: _NumericFeature(
        "currentPower",
        "currentPower",
        PowerConverter,
        UnitOfPower.WATT,
    ),
    # EnergyCounter has separate "in"/"out" fields (energy flowing into vs. out
    # of the device); a single HA energy sensor is reported as "in"
    # (consumption), the common case.
    HA_FEATURE_ENERGY: _NumericFeature(
        "energyCounter",
        "in",
        EnergyConverter,
        UnitOfEnergy.KILO_WATT_HOUR,
        0.0,
    ),
    HA_FEATURE_PRECIPITATION: _NumericFeature(
        "rainCount",
        "rainCounter",
        DistanceConverter,
        UnitOfLength.MILLIMETERS,
        0.0,
    ),
    HA_FEATURE_VEHICLE_RANGE: _NumericFeature(
        "vehicleRange",
        "travelRange",
        DistanceConverter,
        UnitOfLength.KILOMETERS,
        0.0,
    ),
    HA_FEATURE_SUNSHINE_DURATION: _NumericFeature(
        "sunshineDuration",
        "sunshineDuration",
        DurationConverter,
        UnitOfTime.HOURS,
        0.0,
        integer=True,
    ),
    HA_FEATURE_ON_TIME: _NumericFeature(
        "onTime",
        "onTime",
        DurationConverter,
        UnitOfTime.SECONDS,
        0.0,
    ),
    HA_FEATURE_ILLUMINANCE: _NumericFeature(
        "illumination",
        "illumination",
        minimum=0.0,
        maximum=20000.0,
    ),
    HA_FEATURE_HUMIDITY: _NumericFeature(
        "humidity",
        "humidity",
        minimum=0.0,
        maximum=100.0,
        integer=True,
    ),
    HA_FEATURE_CO2: _NumericFeature("co2", "co2", minimum=0.0),
    HA_FEATURE_PM1: _NumericFeature(
        "particulateMassOne",
        "particulateMassConcentrationOne",
        minimum=0.0,
    ),
    HA_FEATURE_PM25: _NumericFeature(
        "particulateMassTwoPointFive",
        "particulateMassConcentrationTwoPointFive",
        minimum=0.0,
    ),
    HA_FEATURE_PM10: _NumericFeature(
        "particulateMassTen",
        "particulateMassConcentrationTen",
        minimum=0.0,
    ),
    HA_FEATURE_WIND_DIRECTION: _NumericFeature(
        "windDirection",
        "windDirection",
        minimum=0.0,
        maximum=359.0,
        scale=lambda v: v % 360,
    ),
    # BatteryState.batteryLevel is a 0 to 1 fraction, not a raw percentage.
    HA_FEATURE_BATTERY: _NumericFeature(
        "batteryState",
        "batteryLevel",
        minimum=0.0,
        maximum=1.0,
        scale=lambda v: v / 100,
    ),
}


def _control_error(code: str, message: str) -> dict[str, str]:
    """Return an error object (Connect API 6.5.2) for a CONTROL_RESPONSE."""
    return {"code": code, "message": message}


def _parse_finite_float(value: Any) -> float | None:
    """Parse a non-boolean finite float, returning None for invalid inputs."""
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _require_finite_float(value: Any) -> float:
    """Parse a finite float or raise ValueError with the raw representation."""
    parsed = _parse_finite_float(value)
    if parsed is None:
        raise ValueError(f"invalid value {value!r}")
    return parsed


def _clamp(value: float, minimum: float | None, maximum: float | None) -> float:
    """Clamp value to any specified lower and upper bounds."""
    if minimum is not None and value < minimum:
        value = minimum
    if maximum is not None and value > maximum:
        value = maximum
    return value


def _numeric_value(state: State, feature: _NumericFeature) -> dict[str, Any] | None:
    """Convert, scale, clamp, and round a numeric entity state."""
    value = _parse_finite_float(state.state)
    if value is None:
        return None
    if feature.converter is not None:
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if isinstance(unit, str) and unit in feature.converter.VALID_UNITS:
            value = feature.converter.convert(value, unit, feature.unit)
    if feature.scale is not None:
        value = feature.scale(value)
    if not math.isfinite(value):
        return None
    value = _clamp(value, feature.minimum, feature.maximum)
    rounded: int | float = round(value) if feature.integer else round(value, 4)
    return {"type": feature.feature_type, feature.field: rounded}


def _enum_value(
    feature_type: str, state: State, allowed: frozenset[str]
) -> dict[str, Any] | None:
    """Normalize and validate an enum entity state."""
    normalized = state.state.strip().upper()
    if normalized in allowed:
        return {"type": feature_type, feature_type: normalized}
    _LOGGER.debug(
        "Ignoring %s value %r of %s: expected one of %s",
        feature_type,
        state.state,
        state.entity_id,
        ", ".join(sorted(allowed)),
    )
    return None


def _is_percent_scale(state: State) -> bool:
    """Return True if a shading entity uses a 0 to 100 position scale."""
    if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == PERCENTAGE:
        return True
    max_val = _parse_finite_float(state.attributes.get("max"))
    return max_val is not None and max_val > 1.01


def _position_to_level(position: float) -> float:
    """Convert a 0 to 100 HA position (100 open) to an HCU level (1 closed)."""
    return round(1 - _clamp(position, 0.0, 100.0) / 100.0, 4)


def _shading_value(feature_type: str, state: State) -> dict[str, Any] | None:
    """Convert shutter_level or slats_level state into an HCU feature dict."""
    value = _parse_finite_float(state.state)
    if value is None:
        return None
    level = (
        _position_to_level(value)
        if _is_percent_scale(state)
        else round(_clamp(value, 0.0, 1.0), 4)
    )
    return {"type": feature_type, feature_type: level}


def _rgb_to_hs_feature(rgb: Any) -> tuple[int, float] | None:
    """Convert an rgb_color sequence to HCU (hue, saturationLevel)."""
    if isinstance(rgb, str) or not isinstance(rgb, Sequence) or len(rgb) != 3:
        return None
    parsed: list[float] = []
    for part in rgb:
        num = _parse_finite_float(part)
        if num is None:
            return None
        parsed.append(_clamp(num, 0.0, 255.0))
    r, g, b = parsed
    # Connect API Color uses hue (0..359) and saturationLevel (0..1);
    # brightness is reported separately via Dimming.
    hue, saturation, _ = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    return round(hue * 360) % 360, round(saturation, 4)


def _parse_kelvin(value: Any) -> int | None:
    """Parse a positive integer Kelvin value, returning None if invalid or < 1."""
    num = _parse_finite_float(value)
    if num is None:
        return None
    kelvin = round(num)
    return kelvin if kelvin >= 1 else None


def _require_kelvin(value: Any) -> int:
    """Parse a positive integer Kelvin value or raise ValueError."""
    kelvin = _parse_kelvin(value)
    if kelvin is None:
        raise ValueError(f"invalid value {value!r}")
    return kelvin


def _color_temp_limits(state: State | None) -> tuple[int | None, int | None]:
    """Return (min_kelvin, max_kelvin) from an entity state, swapping if inverted."""
    if state is None:
        return None, None
    min_k = _parse_kelvin(state.attributes.get(ATTR_MIN_COLOR_TEMP_KELVIN))
    max_k = _parse_kelvin(state.attributes.get(ATTR_MAX_COLOR_TEMP_KELVIN))
    if min_k is not None and max_k is not None and min_k > max_k:
        return max_k, min_k
    return min_k, max_k


def _clamp_kelvin(kelvin: int, min_k: int | None, max_k: int | None) -> int:
    """Clamp a Kelvin temperature into any provided lower and upper bounds."""
    if min_k is not None and kelvin < min_k:
        kelvin = min_k
    if max_k is not None and kelvin > max_k:
        kelvin = max_k
    return kelvin


def _is_special(value: float, target: float) -> bool:
    """Return True if value matches a Connect API special float sentinel."""
    return abs(value - target) < _SPECIAL_TOLERANCE


def _level_to_brightness(level: float) -> int:
    """Convert an HCU dimming level (0 to 1) to HA brightness (1 to 255)."""
    return max(1, round(min(level, 1.0) * 255))


def _parse_color_part(raw: Any, last_val: float, ignore_val: float) -> float | None:
    """Return None if kept/special, parsed float if set, or raise on invalid."""
    if raw is None:
        return None
    val = _require_finite_float(raw)
    if _is_special(val, last_val) or _is_special(val, ignore_val):
        return None
    return val


def _feature_value(feature_key: str, state: State) -> dict[str, Any] | None:
    """Convert HA state to HCU feature value dict. Returns None if unavailable."""
    if state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        return None

    try:
        if numeric_feature := _NUMERIC_FEATURES.get(feature_key):
            return _numeric_value(state, numeric_feature)

        if enum_spec := _ENUM_FEATURES.get(feature_key):
            return _enum_value(enum_spec[0], state, enum_spec[1])

        if feature_key == HA_FEATURE_SHUTTER_LEVEL:
            return _shading_value("shutterLevel", state)

        if feature_key == HA_FEATURE_SLATS_LEVEL:
            return _shading_value("slatsLevel", state)

        if feature_key == HA_FEATURE_ON_OFF:
            return {"type": "switchState", "on": state.state == STATE_ON}

        if feature_key == HA_FEATURE_BRIGHTNESS:
            if state.state != STATE_ON:
                return None
            bri = _parse_finite_float(state.attributes.get(ATTR_BRIGHTNESS))
            if bri is None:
                return None
            return {
                "type": "dimming",
                "dimLevel": round(_clamp(bri / 255, 0.0, 1.0), 4),
            }

        if feature_key == HA_FEATURE_COLOR_TEMP:
            ct_kelvin = _parse_kelvin(state.attributes.get(ATTR_COLOR_TEMP_KELVIN))
            if ct_kelvin is None:
                ct_mireds = _parse_finite_float(state.attributes.get(ATTR_COLOR_TEMP))
                if ct_mireds is not None and ct_mireds > 0:
                    ct_kelvin = _parse_kelvin(1000000 / ct_mireds)
            min_k, max_k = _color_temp_limits(state)
            if ct_kelvin is None and min_k is None and max_k is None:
                return None
            feature_obj: dict[str, Any] = {"type": "colorTemperature"}
            if ct_kelvin is not None:
                feature_obj["colorTemperature"] = _clamp_kelvin(ct_kelvin, min_k, max_k)
            if min_k is not None:
                feature_obj["minimalColorTemperature"] = min_k
            if max_k is not None:
                feature_obj["maximumColorTemperature"] = max_k
            return feature_obj

        if feature_key == HA_FEATURE_RGB_COLOR:
            hs = _rgb_to_hs_feature(state.attributes.get(ATTR_RGB_COLOR))
            if hs is None:
                return None
            hue, saturation = hs
            return {"type": "color", "hue": hue, "saturationLevel": saturation}

        if feature_key == HA_FEATURE_STORM:
            return {"type": "storm", "storm": state.state == STATE_ON}

        if feature_key == HA_FEATURE_SUNSHINE:
            return {"type": "sunshine", "sunshine": state.state == STATE_ON}

        if feature_key == HA_FEATURE_RAINING:
            return {"type": "raining", "raining": state.state == STATE_ON}

        if feature_key == HA_FEATURE_MOTION:
            return {
                "type": "presenceDetected",
                "presenceDetected": state.state == STATE_ON,
            }

        if feature_key == HA_FEATURE_OCCUPANCY:
            return {
                "type": "presenceDetected",
                "presenceDetected": state.state == STATE_ON,
            }

        if feature_key in (
            HA_FEATURE_DOOR,
            HA_FEATURE_WINDOW,
            HA_FEATURE_CONTACT_SENSOR,
        ):
            return {"type": "contactSensorState", "triggered": state.state == STATE_ON}

        if feature_key == HA_FEATURE_SMOKE:
            return {"type": "smokeAlarm", "smokeAlarm": state.state == STATE_ON}

        if feature_key == HA_FEATURE_MOISTURE:
            return {
                "type": "waterlevelDetected",
                "waterlevelDetected": state.state == STATE_ON,
            }

        if feature_key == HA_FEATURE_MOISTURE_DETECTED:
            return {
                "type": "moistureDetected",
                "moistureDetected": state.state == STATE_ON,
            }

        if feature_key == HA_FEATURE_HOT_WATER_BOOST:
            return {"type": "hotWaterBoost", "on": state.state == STATE_ON}

    except (ValueError, TypeError):
        return None

    return None


def _build_maintenance_value(
    hass: HomeAssistant, features_conf: dict[str, str]
) -> dict[str, Any] | None:
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
        self._unsub: Callable[[], None] | None = None
        self._catch_up_task: asyncio.Task[Any] | None = None
        self._auto_off_tasks: dict[str, asyncio.Task[Any]] = {}
        self._last_sent: dict[str, float] = {}  # keyed by HCU device ID
        self._last_sent_features: dict[
            str, list[dict[str, Any]]
        ] = {}  # keyed by HCU device ID
        # HCU device IDs that may push state: reported in a DISCOVER_RESPONSE
        # or named in an INCLUSION_EVENT, and not excluded since. Proactive
        # STATUS_EVENT pushes are gated on this set, because sending state for
        # a device the HCU does not know would be a protocol violation.
        self._discovered_hcu_ids: set[str] = set()
        # HCU device IDs the HCU excluded (Connect API 6.4.8). Their state is
        # not reported until an INCLUSION_EVENT names them again.
        self._excluded_hcu_ids: set[str] = set()
        self._incomplete_warned: set[str] = set()

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

    def _build_discover_features(
        self, features: dict[str, str]
    ) -> list[dict[str, Any]]:
        # A few HA_FEATURE_* keys map onto the same Connect API feature type
        # (e.g. "door"/"window" both are contactSensorState) — the current
        # options flow no longer offers both for one device, but a device
        # saved before that change might still have both set. Sending the
        # same "type" twice is likely as invalid as an unrecognized one, so
        # only the first configured key for a given type is kept.
        result = []
        seen_types: set[str] = set()
        for key in features:
            if key in HA_MAINTENANCE_FEATURE_KEYS:
                continue
            desc = _DISCOVER_FEATURE.get(key)
            if desc and desc["type"] not in seen_types:
                seen_types.add(desc["type"])
                result.append(dict(desc))
        # Every device type supports Maintenance (Connect API 6.6.5); it
        # carries the reachability of the device.
        result.append({"type": "maintenance"})
        return result

    def _is_entity_unavailable(self, entity_id: str) -> bool:
        """Return True if the entity is missing or unavailable."""
        state = self.hass.states.get(entity_id)
        return state is None or state.state == STATE_UNAVAILABLE

    def _is_unreachable(self, device: dict[str, Any]) -> bool:
        """Return True if the entities behind a device cannot be reached.

        A device is unreachable when one of its required entities is missing
        or unavailable. A device without a configured required entity is
        unreachable when all of its entities are.
        """
        features_conf: dict[str, str] = device.get("features", {})
        device_type = device.get("type") or determine_ha_device_type(features_conf)
        required = HA_DEVICE_TYPE_FEATURES.get(device_type, {}).get("required", [])
        primary = [features_conf[key] for key in required if features_conf.get(key)]
        if primary:
            return any(self._is_entity_unavailable(entity) for entity in primary)
        entities = [
            entity
            for key, entity in features_conf.items()
            if key not in HA_MAINTENANCE_FEATURE_KEYS and entity
        ]
        return bool(entities) and all(
            self._is_entity_unavailable(entity) for entity in entities
        )

    def _build_value_features(self, device: dict[str, Any]) -> list[dict[str, Any]]:
        # Same "one entry per Connect API type" dedup as _build_discover_features.
        features_conf: dict[str, str] = device.get("features", {})
        result = []
        seen_types: set[str] = set()
        for key, entity_id in features_conf.items():
            if key in HA_MAINTENANCE_FEATURE_KEYS or not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            if state is None:
                continue
            val = _feature_value(key, state)
            if val is not None and val["type"] not in seen_types:
                seen_types.add(val["type"])
                result.append(val)
        # Maintenance is always reported: unreach is true while the entities
        # behind the device are unavailable, or while the configured unreach
        # entity is on.
        maintenance = _build_maintenance_value(self.hass, features_conf) or {
            "type": "maintenance"
        }
        maintenance["unreach"] = maintenance.get(
            "unreach", False
        ) or self._is_unreachable(device)
        result.append(maintenance)
        return result

    def _get_ha_device_info(
        self, features_conf: dict[str, str]
    ) -> tuple[str | None, str | None]:
        """Look up (model, sw_version) of the HA device the bridged entities belong to.

        Prefers the primary on_off entity (the one actually being controlled);
        falls back to the first configured entity otherwise. Many entities
        (helpers, templates) aren't attached to any device at all, in which
        case this returns (None, None) and the caller falls back to the
        generic HOME_ASSISTANT placeholder.
        """
        entity_id = features_conf.get(HA_FEATURE_ON_OFF) or next(
            (
                v
                for k, v in features_conf.items()
                if k not in HA_MAINTENANCE_FEATURE_KEYS and v
            ),
            None,
        )
        if not entity_id:
            return None, None

        entity_entry = er.async_get(self.hass).async_get(entity_id)
        if entity_entry is None or entity_entry.device_id is None:
            return None, None

        device_entry = dr.async_get(self.hass).async_get(entity_entry.device_id)
        # Child devices (Home Assistant 2026.10+) carry no model or firmware.
        if not isinstance(device_entry, dr.DeviceEntry):
            return None, None

        return device_entry.model, device_entry.sw_version

    def _build_device_object(
        self, device: dict[str, Any], include_values: bool
    ) -> dict[str, Any] | None:
        features_conf: dict[str, str] = device.get("features", {})
        if not features_conf:
            return None

        device_type = device.get("type") or determine_ha_device_type(features_conf)
        hcu_id = self._make_hcu_id(device)
        model, sw_version = self._get_ha_device_info(features_conf)

        obj: dict[str, Any] = {
            "deviceId": hcu_id,
            "friendlyName": self._get_friendly_name(device),
            "modelType": model or HA_MODEL_TYPE,
            "firmwareVersion": sw_version or HA_FIRMWARE_VERSION,
            "deviceType": device_type,
        }

        if include_values:
            obj["features"] = self._build_value_features(device)
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
            device_type = obj["deviceType"]
            if device_type not in _DISCOVERABLE_DEVICE_TYPES:
                _LOGGER.debug(
                    "Excluding device %s (%s) from DISCOVER_RESPONSE: type %s not accepted by HCU inbox",
                    obj["deviceId"],
                    obj["friendlyName"],
                    device_type,
                )
                continue
            present_types = {desc["type"] for desc in obj["features"]}
            required_keys = HA_DEVICE_TYPE_FEATURES[device_type]["required"]
            missing = [
                _DISCOVER_FEATURE[key]["type"]
                for key in required_keys
                if _DISCOVER_FEATURE[key]["type"] not in present_types
            ]
            if missing:
                if obj["deviceId"] not in self._incomplete_warned:
                    self._incomplete_warned.add(obj["deviceId"])
                    _LOGGER.warning(
                        "Not offering device %s (%s) to the HCU: type %s requires the feature %s. Edit the device in the integration options and select the missing entity",
                        obj["deviceId"],
                        obj["friendlyName"],
                        device_type,
                        ", ".join(missing),
                    )
                continue
            val_by_type = {f["type"]: f for f in self._build_value_features(device)}
            obj["features"] = [
                val_by_type.get(desc["type"], desc) for desc in obj["features"]
            ]
            devices.append(obj)
        # An excluded device is offered again, but stays silent until the HCU
        # includes it again.
        self._discovered_hcu_ids.update(
            d["deviceId"]
            for d in devices
            if d["deviceId"] not in self._excluded_hcu_ids
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
            if self._make_hcu_id(device) in self._excluded_hcu_ids:
                continue
            obj = self._build_device_object(device, include_values=True)
            if obj is not None:
                result.append(obj)
        return result

    # --- Inclusion and exclusion ---

    def handle_inclusion_event(self, device_ids: list[str]) -> list[dict[str, Any]]:
        """Activate the included devices and return their current status.

        The HCU expects a STATUS_RESPONSE with these devices (Connect API
        6.4.11). Device IDs that are not configured are ignored.
        """
        known = [did for did in dict.fromkeys(device_ids) if did in self._by_hcu_id]
        self._excluded_hcu_ids.difference_update(known)
        status_devices = self.build_status_devices(known)
        self._discovered_hcu_ids.update(d["deviceId"] for d in status_devices)
        return status_devices

    def handle_exclusion_event(self, device_ids: list[str]) -> None:
        """Stop reporting the state of excluded devices (Connect API 6.4.8).

        A pending on_time auto-off still runs, so the entity is not left on.
        """
        for device_id in device_ids:
            if self._is_ha_device_id(device_id):
                ir.async_delete_issue(
                    self.hass, DOMAIN, self._stale_issue_id(device_id)
                )
            if device_id not in self._by_hcu_id:
                continue
            self._excluded_hcu_ids.add(device_id)
            self._discovered_hcu_ids.discard(device_id)
            self._last_sent.pop(device_id, None)
            self._last_sent_features.pop(device_id, None)

    # --- Control ---

    async def handle_control_request(
        self, body: dict[str, Any]
    ) -> dict[str, str] | None:
        """Apply a CONTROL_REQUEST (Connect API 6.4.3) to the HA entities.

        Every feature is applied, even after one failed. Returns None on
        success, otherwise the error object (6.5.2) for the CONTROL_RESPONSE:
        the code of the first failure and the messages of all failures.
        """
        hcu_device_id = body.get("deviceId", "")
        device = self._by_hcu_id.get(hcu_device_id)
        if not device:
            return _control_error(
                CONTROL_ERROR_UNKNOWN_DEVICE, f"Unknown device {hcu_device_id}"
            )

        features_conf: dict[str, str] = device.get("features", {})
        body_features: list[dict[str, Any]] = body.get("features", [])
        errors: list[dict[str, str]] = []
        for feature in body_features:
            error = await self._apply_control_feature(
                hcu_device_id, feature, body_features, features_conf
            )
            if error is not None:
                errors.append(error)
        if not errors:
            return None
        return _control_error(
            errors[0]["code"], "; ".join(error["message"] for error in errors)
        )

    async def _apply_control_feature(
        self,
        hcu_device_id: str,
        feature: dict[str, Any],
        body_features: list[dict[str, Any]],
        features_conf: dict[str, str],
    ) -> dict[str, str] | None:
        """Apply one feature of a CONTROL_REQUEST; return an error object on failure."""
        feature_type = feature.get("type")
        unsupported = _control_error(
            CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
            f"Feature {feature_type} is not supported by {hcu_device_id}",
        )

        if feature_type == "onTime":
            # Only modifies a switchState in the same request (6.7.18).
            return None

        if feature_type == "switchState":
            entity_id = features_conf.get(HA_FEATURE_ON_OFF)
            if not entity_id:
                return unsupported
            on = feature.get("on")
            if on is None:
                return None
            domain = entity_id.split(".")[0]
            service = "turn_on" if on else "turn_off"
            try:
                await self.hass.services.async_call(
                    domain, service, {"entity_id": entity_id}, blocking=True
                )
            except Exception as err:  # noqa: BLE001 - errors from the target integration
                _LOGGER.error(
                    "Service %s.%s for %s failed: %s",
                    domain,
                    service,
                    entity_id,
                    err,
                )
                return _control_error(
                    CONTROL_ERROR_FAILED,
                    f"{domain}.{service} for {entity_id} failed: {err}",
                )

            self._cancel_auto_off_task(entity_id)
            if service == "turn_on":
                on_time_secs = self._get_control_on_time(
                    body_features, feature, features_conf
                )
                if on_time_secs and on_time_secs > 0:
                    task = self.hass.async_create_task(
                        self._auto_off_after(entity_id, domain, on_time_secs),
                        name=f"HCU on_time auto-off {entity_id}",
                    )
                    self._auto_off_tasks[entity_id] = task
            return None

        if feature_type == "dimming":
            entity_id = features_conf.get(HA_FEATURE_BRIGHTNESS) or features_conf.get(
                HA_FEATURE_ON_OFF
            )
            if not entity_id or not entity_id.startswith("light."):
                return unsupported
            dim_level = feature.get("dimLevel")
            if dim_level is None:
                return None
            try:
                level = _require_finite_float(dim_level)
                if _is_special(level, _DIMMING_IGNORE):
                    return None
                if _is_special(level, _DIMMING_LAST_VALUE):
                    if any(
                        other.get("type") == "switchState"
                        and other.get("on") is not None
                        for other in body_features
                    ):
                        return None
                    await self.hass.services.async_call(
                        "light",
                        "turn_on",
                        {"entity_id": entity_id},
                        blocking=True,
                    )
                elif level <= 0:
                    await self.hass.services.async_call(
                        "light",
                        "turn_off",
                        {"entity_id": entity_id},
                        blocking=True,
                    )
                else:
                    await self.hass.services.async_call(
                        "light",
                        "turn_on",
                        {
                            "entity_id": entity_id,
                            "brightness": _level_to_brightness(level),
                        },
                        blocking=True,
                    )
            except Exception as err:  # noqa: BLE001 - errors from the target integration
                _LOGGER.error("Dimming %s failed: %s", entity_id, err)
                return _control_error(
                    CONTROL_ERROR_FAILED, f"Dimming {entity_id} failed: {err}"
                )
            return None

        if feature_type == "colorTemperature":
            entity_id = features_conf.get(HA_FEATURE_COLOR_TEMP)
            if not entity_id:
                return unsupported
            ct = feature.get("colorTemperature")
            if ct is None:
                return None
            try:
                kelvin = _require_kelvin(ct)
                if kelvin in _COLOR_TEMP_KEEP_VALUES:
                    return None
                if kelvin in _COLOR_TEMP_UNSUPPORTED_MODES:
                    return _control_error(
                        CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
                        f"Color temperature mode {kelvin} is not supported by {hcu_device_id}",
                    )
                min_k, max_k = _color_temp_limits(self.hass.states.get(entity_id))
                kelvin = _clamp_kelvin(kelvin, min_k, max_k)
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": entity_id, ATTR_COLOR_TEMP_KELVIN: kelvin},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001 - errors from the target integration
                _LOGGER.error("Color temp %s failed: %s", entity_id, err)
                return _control_error(
                    CONTROL_ERROR_FAILED, f"Color temp {entity_id} failed: {err}"
                )
            return None

        if feature_type == "color":
            entity_id = features_conf.get(HA_FEATURE_RGB_COLOR)
            if not entity_id:
                return unsupported
            try:
                hue = _parse_color_part(
                    feature.get("hue"), _HUE_LAST_VALUE, _HUE_IGNORE
                )
                saturation = _parse_color_part(
                    feature.get("saturationLevel"), _SAT_LAST_VALUE, _SAT_IGNORE
                )
                if hue is None and saturation is None:
                    return None
                if hue is None or saturation is None:
                    state = self.hass.states.get(entity_id)
                    current = (
                        _rgb_to_hs_feature(state.attributes.get(ATTR_RGB_COLOR))
                        if state is not None
                        else None
                    )
                    if current is None:
                        return None
                    if hue is None:
                        hue = current[0]
                    if saturation is None:
                        saturation = current[1]
                clamped_hue = max(0, min(359, round(hue)))
                clamped_sat = _clamp(saturation, 0.0, 1.0)
                r, g, b = colorsys.hsv_to_rgb(clamped_hue / 360, clamped_sat, 1.0)
                rgb_color = [round(r * 255), round(g * 255), round(b * 255)]
                await self.hass.services.async_call(
                    "light",
                    "turn_on",
                    {"entity_id": entity_id, "rgb_color": rgb_color},
                    blocking=True,
                )
            except Exception as err:  # noqa: BLE001 - errors from the target integration
                _LOGGER.error("Color %s failed: %s", entity_id, err)
                return _control_error(
                    CONTROL_ERROR_FAILED, f"Color {entity_id} failed: {err}"
                )
            return None

        return unsupported

    def _get_control_on_time(
        self,
        body_features: list[dict[str, Any]],
        switch_feature: dict[str, Any],
        features_conf: dict[str, str],
    ) -> float | None:
        """Resolve the auto-off delay for a switchState turn-on.

        Priority: value on the switchState feature itself > a sibling "onTime"
        feature in the same CONTROL_REQUEST > the configured on_time entity.
        """
        if (value := _parse_finite_float(switch_feature.get("onTime"))) is not None:
            return value

        for other in body_features:
            if other.get("type") == "onTime":
                if (parsed := _parse_finite_float(other.get("onTime"))) is not None:
                    return parsed

        entity_id = features_conf.get(HA_FEATURE_ON_TIME)
        if entity_id:
            state = self.hass.states.get(entity_id)
            if state is not None and state.state not in (
                STATE_UNAVAILABLE,
                STATE_UNKNOWN,
            ):
                feat = _numeric_value(state, _NUMERIC_FEATURES[HA_FEATURE_ON_TIME])
                return feat["onTime"] if feat is not None else None

        return None

    def _cancel_auto_off_task(self, entity_id: str) -> None:
        """Cancel any active on_time auto-off timer task for an entity."""
        task = self._auto_off_tasks.pop(entity_id, None)
        if task is not None and not task.done():
            task.cancel()

    async def _auto_off_after(
        self, entity_id: str, domain: str, delay_secs: float
    ) -> None:
        try:
            await asyncio.sleep(delay_secs)
        finally:
            # Stop tracking once the timer has elapsed or was cancelled, so the
            # off state caused by the auto-off below can't cancel this task.
            if self._auto_off_tasks.get(entity_id) is asyncio.current_task():
                self._auto_off_tasks.pop(entity_id, None)
        try:
            await self.hass.services.async_call(
                domain, "turn_off", {"entity_id": entity_id}, blocking=True
            )
        except Exception as err:  # noqa: BLE001 - errors from the target integration
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
                # The HCU does not know this device, or it excluded it. Pushing
                # state for it would be a protocol violation.
                continue
            features = self._build_value_features(device)
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
                await self._send_message(
                    {
                        "id": str(uuid4()),
                        "pluginId": self._plugin_id,
                        "type": "STATUS_EVENT",
                        "body": {
                            "deviceId": hcu_id,
                            "features": features,
                        },
                    }
                )
            except ConnectionError:
                if self._last_sent_features.get(hcu_id) is features:
                    self._last_sent.pop(hcu_id, None)
                    self._last_sent_features.pop(hcu_id, None)

    # --- Stale device detection ---

    @staticmethod
    def _stale_issue_id(device_id: str) -> str:
        return f"ha_entity_excluded_{device_id.replace('.', '_').replace('-', '_')}"

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
                self._stale_issue_id(device_id),
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="ha_entity_excluded",
                translation_placeholders={"entity_id": device_id},
            )

    # --- State listener ---

    def _cancel_catch_up_task(self) -> None:
        """Cancel any pending listener-start catch-up task."""
        task = self._catch_up_task
        self._catch_up_task = None
        if task is not None and not task.done():
            task.cancel()

    async def _send_catch_up(self) -> None:
        """Yield once so stop_listening can cancel before any state is sent."""
        send_status = self.send_status_event
        await asyncio.sleep(0)
        await send_status()

    def start_listening(self) -> None:
        all_ids = self.all_entity_ids
        if not all_ids:
            return

        @callback
        def _on_state_changed(event: Any) -> None:
            entity_id = event.data.get("entity_id")
            new_state = event.data.get("new_state")
            # An entity turned off by any means (HA UI, automation, device) ends
            # a pending on_time auto-off, so a later manual turn-on isn't cut short.
            if (
                new_state is not None
                and new_state.state == STATE_OFF
                and entity_id in self._auto_off_tasks
            ):
                self._cancel_auto_off_task(entity_id)
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

        if self._unsub:
            self._unsub()
            self._unsub = None
        self._cancel_catch_up_task()
        self._unsub = async_track_state_change_event(
            self.hass, list(all_ids), _on_state_changed
        )
        # Report the current state once, so a change that happened before the
        # listener was running is not missed.
        self._catch_up_task = self.hass.async_create_task(
            self._send_catch_up(), name="HCU status_event catch-up"
        )
        _LOGGER.debug(
            "HaEntityBridge: listening for %d entities across %d devices",
            len(all_ids),
            len(self._ha_devices),
        )

    def stop_listening(self) -> None:
        self._cancel_catch_up_task()
        if self._unsub:
            self._unsub()
            self._unsub = None
        for task in list(self._auto_off_tasks.values()):
            if not task.done():
                task.cancel()
        self._auto_off_tasks.clear()

    # --- Config UI helper ---

    def get_device_summary(self) -> str:
        if not self._ha_devices:
            return ""
        lines = []
        for device in self._ha_devices:
            features_conf = device.get("features", {})
            device_type = device.get("type") or (
                determine_ha_device_type(features_conf) if features_conf else "?"
            )
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
