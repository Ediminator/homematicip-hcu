"""Value conversion, special value, clamping, enum, and completeness tests."""

from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ATTR_MAX_COLOR_TEMP_KELVIN,
    ATTR_MIN_COLOR_TEMP_KELVIN,
)
from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)
import voluptuous as vol

from custom_components.hcu_integration.api import HcuApiClient
from custom_components.hcu_integration.const import (
    CONF_HA_DEVICES,
    CONTROL_ERROR_FAILED,
    CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
    DOMAIN,
    HA_DEVICE_TYPE_CLIMATE_SENSOR,
    HA_DEVICE_TYPE_CONTACT_SENSOR,
    HA_DEVICE_TYPE_ENERGY_METER,
    HA_DEVICE_TYPE_FEATURES,
    HA_DEVICE_TYPE_HEAT_PUMP,
    HA_DEVICE_TYPE_LIGHT,
    HA_DEVICE_TYPE_OCCUPANCY_SENSOR,
    HA_DEVICE_TYPE_SWITCH,
    HA_DEVICE_TYPE_SWITCH_INPUT,
    HA_DEVICE_TYPE_THERMOSTAT,
    HA_DEVICE_TYPE_WINDOW_COVERING,
    HA_FEATURE_BRIGHTNESS,
    HA_FEATURE_CLIMATE_OPERATION_MODE,
    HA_FEATURE_COLOR_TEMP,
    HA_FEATURE_DOOR,
    HA_FEATURE_ENERGY,
    HA_FEATURE_HEATING_TEMP_OFFSET,
    HA_FEATURE_HUMIDITY,
    HA_FEATURE_LOW_BAT,
    HA_FEATURE_MOISTURE_DETECTED,
    HA_FEATURE_MOTION,
    HA_FEATURE_ON_OFF,
    HA_FEATURE_ON_TIME,
    HA_FEATURE_POWER,
    HA_FEATURE_PRESENCE_MODE,
    HA_FEATURE_RGB_COLOR,
    HA_FEATURE_SHUTTER_DIRECTION,
    HA_FEATURE_SHUTTER_LEVEL,
    HA_FEATURE_SLATS_LEVEL,
    HA_FEATURE_TEMPERATURE,
    HA_FEATURE_VEHICLE_RANGE,
    HA_FEATURE_WIND_SPEED,
    HA_FEATURE_WINDOW,
    PLUGIN_ID,
)
from custom_components.hcu_integration.ha_entity_bridge import (
    _NUMERIC_FEATURES,
    HA_FIRMWARE_VERSION,
    HA_MODEL_TYPE,
    HaEntityBridge,
    _feature_value,
    _is_percent_scale,
    _level_to_brightness,
    _parse_finite_float,
    _position_to_level,
)
from custom_components.hcu_integration.light import HcuLight

_LIGHT: dict[str, Any] = {
    "id": "lt1",
    "name": "Desk Lamp",
    "type": HA_DEVICE_TYPE_LIGHT,
    "features": {
        HA_FEATURE_ON_OFF: "light.desk",
        HA_FEATURE_BRIGHTNESS: "light.desk",
        HA_FEATURE_COLOR_TEMP: "light.desk",
        HA_FEATURE_RGB_COLOR: "light.desk",
    },
}

_PUMP: dict[str, Any] = {
    "id": "sw1",
    "name": "Garden Pump",
    "type": HA_DEVICE_TYPE_SWITCH,
    "features": {
        HA_FEATURE_ON_OFF: "switch.pump",
        HA_FEATURE_ON_TIME: "number.run",
    },
}

_METER: dict[str, Any] = {
    "id": "em1",
    "name": "Meter",
    "type": HA_DEVICE_TYPE_ENERGY_METER,
    "features": {
        HA_FEATURE_POWER: "sensor.power",
        HA_FEATURE_ENERGY: "sensor.energy",
    },
}

_DESK_ENTITY = {"entity_id": "light.desk"}
_PUMP_ENTITY = {"entity_id": "switch.pump"}
_BRIDGE_LOGGER = "custom_components.hcu_integration.ha_entity_bridge"


@pytest.fixture
def options_flow_env(mock_async_zeroconf: MagicMock):
    """Set up zeroconf and patch async_setup_entry for options flow tests."""
    with patch(
        "custom_components.hcu_integration.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


def _make_state(
    value: str,
    attributes: dict[str, Any] | None = None,
    entity_id: str = "sensor.x",
) -> State:
    return State(entity_id, value, attributes or {})


def _setup_websocket(api_client: HcuApiClient) -> AsyncMock:
    ws = AsyncMock()
    ws.closed = False
    api_client._websocket = ws
    return ws


# ---------------------------------------------------------------------------
# 1. Finite float parser
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("21.5", 21.5),
        (" 7 ", 7.0),
        (3, 3.0),
        (-0.5, -0.5),
        ("1e3", 1000.0),
        ("nan", None),
        ("NaN", None),
        ("inf", None),
        ("-inf", None),
        ("Infinity", None),
        ("1e999", None),
        (float("nan"), None),
        (float("inf"), None),
        (float("-inf"), None),
        (10**400, None),
        (True, None),
        (False, None),
        (None, None),
        ("", None),
        ("abc", None),
        ([1], None),
        ({}, None),
    ],
)
def test_parse_finite_float(raw: Any, expected: float | None) -> None:
    """Reject booleans, unparsable values, and non-finite numbers."""
    result = _parse_finite_float(raw)
    if expected is None:
        assert result is None
    else:
        assert type(result) is float
        assert result == expected


# ---------------------------------------------------------------------------
# 2. Numeric status features: units, clamping, scaling, rounding, types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("feature_key", "raw", "attrs", "hcu_type", "field", "expected", "py_type"),
    [
        # temperature
        (
            "temperature",
            "21.54",
            {},
            "actualTemperature",
            "actualTemperature",
            21.54,
            float,
        ),
        (
            "temperature",
            "70",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "actualTemperature",
            "actualTemperature",
            21.1111,
            float,
        ),
        (
            "temperature",
            "293.15",
            {ATTR_UNIT_OF_MEASUREMENT: "K"},
            "actualTemperature",
            "actualTemperature",
            20.0,
            float,
        ),
        (
            "temperature",
            "21.5",
            {ATTR_UNIT_OF_MEASUREMENT: "°C"},
            "actualTemperature",
            "actualTemperature",
            21.5,
            float,
        ),
        (
            "temperature",
            "21.5",
            {ATTR_UNIT_OF_MEASUREMENT: "bananas"},
            "actualTemperature",
            "actualTemperature",
            21.5,
            float,
        ),
        (
            "temperature",
            "21.5",
            {ATTR_UNIT_OF_MEASUREMENT: None},
            "actualTemperature",
            "actualTemperature",
            21.5,
            float,
        ),
        (
            "temperature",
            "21.5",
            {ATTR_UNIT_OF_MEASUREMENT: ["°F"]},
            "actualTemperature",
            "actualTemperature",
            21.5,
            float,
        ),
        (
            "temperature",
            "21.5",
            {ATTR_UNIT_OF_MEASUREMENT: 5},
            "actualTemperature",
            "actualTemperature",
            21.5,
            float,
        ),
        (
            "temperature",
            "75",
            {},
            "actualTemperature",
            "actualTemperature",
            60.0,
            float,
        ),
        (
            "temperature",
            "-80",
            {},
            "actualTemperature",
            "actualTemperature",
            -50.0,
            float,
        ),
        (
            "temperature",
            "60",
            {},
            "actualTemperature",
            "actualTemperature",
            60.0,
            float,
        ),
        (
            "temperature",
            "-50",
            {},
            "actualTemperature",
            "actualTemperature",
            -50.0,
            float,
        ),
        (
            "temperature",
            "200",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "actualTemperature",
            "actualTemperature",
            60.0,
            float,
        ),
        (
            "temperature",
            "-100",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "actualTemperature",
            "actualTemperature",
            -50.0,
            float,
        ),
        (
            "temperature",
            "21.123456",
            {},
            "actualTemperature",
            "actualTemperature",
            21.1235,
            float,
        ),
        # supply_temperature
        (
            "supply_temperature",
            "118.4",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "supplyTemperature",
            "supplyTemperature",
            48.0,
            float,
        ),
        (
            "supply_temperature",
            "90",
            {},
            "supplyTemperature",
            "supplyTemperature",
            60.0,
            float,
        ),
        (
            "supply_temperature",
            "-60",
            {},
            "supplyTemperature",
            "supplyTemperature",
            -50.0,
            float,
        ),
        # set_point_temp
        (
            "set_point_temp",
            "68",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "setPointTemperature",
            "setPointTemperature",
            20.0,
            float,
        ),
        (
            "set_point_temp",
            "61",
            {},
            "setPointTemperature",
            "setPointTemperature",
            60.0,
            float,
        ),
        (
            "set_point_temp",
            "-51",
            {},
            "setPointTemperature",
            "setPointTemperature",
            -50.0,
            float,
        ),
        # cooling_temp_offset
        (
            "cooling_temp_offset",
            "9",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "coolingTemperatureOffset",
            "coolingTemperatureOffset",
            5.0,
            float,
        ),
        (
            "cooling_temp_offset",
            "-1.5",
            {},
            "coolingTemperatureOffset",
            "coolingTemperatureOffset",
            -1.5,
            float,
        ),
        (
            "cooling_temp_offset",
            "2",
            {ATTR_UNIT_OF_MEASUREMENT: "K"},
            "coolingTemperatureOffset",
            "coolingTemperatureOffset",
            2.0,
            float,
        ),
        (
            "cooling_temp_offset",
            "55",
            {},
            "coolingTemperatureOffset",
            "coolingTemperatureOffset",
            50.0,
            float,
        ),
        (
            "cooling_temp_offset",
            "-55",
            {},
            "coolingTemperatureOffset",
            "coolingTemperatureOffset",
            -50.0,
            float,
        ),
        # heating_temp_offset
        (
            "heating_temp_offset",
            "-4.5",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            "heatingTemperatureOffset",
            "heatingTemperatureOffset",
            -2.5,
            float,
        ),
        (
            "heating_temp_offset",
            "50.5",
            {},
            "heatingTemperatureOffset",
            "heatingTemperatureOffset",
            50.0,
            float,
        ),
        (
            "heating_temp_offset",
            "-50.5",
            {},
            "heatingTemperatureOffset",
            "heatingTemperatureOffset",
            -50.0,
            float,
        ),
        # wind_speed
        ("wind_speed", "12.3", {}, "windSpeed", "windSpeed", 12.3, float),
        (
            "wind_speed",
            "10",
            {ATTR_UNIT_OF_MEASUREMENT: "m/s"},
            "windSpeed",
            "windSpeed",
            36.0,
            float,
        ),
        (
            "wind_speed",
            "10",
            {ATTR_UNIT_OF_MEASUREMENT: "mph"},
            "windSpeed",
            "windSpeed",
            16.0934,
            float,
        ),
        (
            "wind_speed",
            "10",
            {ATTR_UNIT_OF_MEASUREMENT: "kn"},
            "windSpeed",
            "windSpeed",
            18.52,
            float,
        ),
        ("wind_speed", "500", {}, "windSpeed", "windSpeed", 400.0, float),
        ("wind_speed", "-3", {}, "windSpeed", "windSpeed", 0.0, float),
        (
            "wind_speed",
            "200",
            {ATTR_UNIT_OF_MEASUREMENT: "m/s"},
            "windSpeed",
            "windSpeed",
            400.0,
            float,
        ),
        (
            "wind_speed",
            "3",
            {ATTR_UNIT_OF_MEASUREMENT: "Beaufort"},
            "windSpeed",
            "windSpeed",
            15.6383,
            float,
        ),
        # power
        ("power", "250.75", {}, "currentPower", "currentPower", 250.75, float),
        (
            "power",
            "1.5",
            {ATTR_UNIT_OF_MEASUREMENT: "kW"},
            "currentPower",
            "currentPower",
            1500.0,
            float,
        ),
        (
            "power",
            "250",
            {ATTR_UNIT_OF_MEASUREMENT: "mW"},
            "currentPower",
            "currentPower",
            0.25,
            float,
        ),
        (
            "power",
            "-0.002",
            {ATTR_UNIT_OF_MEASUREMENT: "MW"},
            "currentPower",
            "currentPower",
            -2000.0,
            float,
        ),
        (
            "power",
            "-1200",
            {ATTR_UNIT_OF_MEASUREMENT: "W"},
            "currentPower",
            "currentPower",
            -1200.0,
            float,
        ),
        (
            "power",
            "5",
            {ATTR_UNIT_OF_MEASUREMENT: "w"},
            "currentPower",
            "currentPower",
            5.0,
            float,
        ),
        # energy
        ("energy", "1500.5", {}, "energyCounter", "in", 1500.5, float),
        (
            "energy",
            "1500.5",
            {ATTR_UNIT_OF_MEASUREMENT: "Wh"},
            "energyCounter",
            "in",
            1.5005,
            float,
        ),
        (
            "energy",
            "1.2",
            {ATTR_UNIT_OF_MEASUREMENT: "MWh"},
            "energyCounter",
            "in",
            1200.0,
            float,
        ),
        (
            "energy",
            "3.6",
            {ATTR_UNIT_OF_MEASUREMENT: "MJ"},
            "energyCounter",
            "in",
            1.0,
            float,
        ),
        (
            "energy",
            "7200",
            {ATTR_UNIT_OF_MEASUREMENT: "kJ"},
            "energyCounter",
            "in",
            2.0,
            float,
        ),
        ("energy", "-5", {}, "energyCounter", "in", 0.0, float),
        # precipitation
        ("precipitation", "3.2", {}, "rainCount", "rainCounter", 3.2, float),
        (
            "precipitation",
            "2",
            {ATTR_UNIT_OF_MEASUREMENT: "in"},
            "rainCount",
            "rainCounter",
            50.8,
            float,
        ),
        (
            "precipitation",
            "1.5",
            {ATTR_UNIT_OF_MEASUREMENT: "cm"},
            "rainCount",
            "rainCounter",
            15.0,
            float,
        ),
        (
            "precipitation",
            "0.25",
            {ATTR_UNIT_OF_MEASUREMENT: "m"},
            "rainCount",
            "rainCounter",
            250.0,
            float,
        ),
        ("precipitation", "-1", {}, "rainCount", "rainCounter", 0.0, float),
        (
            "precipitation",
            "4",
            {ATTR_UNIT_OF_MEASUREMENT: "mm/h"},
            "rainCount",
            "rainCounter",
            4.0,
            float,
        ),
        # vehicle_range
        ("vehicle_range", "310.2", {}, "vehicleRange", "travelRange", 310.2, float),
        (
            "vehicle_range",
            "100",
            {ATTR_UNIT_OF_MEASUREMENT: "mi"},
            "vehicleRange",
            "travelRange",
            160.9344,
            float,
        ),
        (
            "vehicle_range",
            "1500",
            {ATTR_UNIT_OF_MEASUREMENT: "m"},
            "vehicleRange",
            "travelRange",
            1.5,
            float,
        ),
        ("vehicle_range", "-10", {}, "vehicleRange", "travelRange", 0.0, float),
        # sunshine_duration
        (
            "sunshine_duration",
            "240.0",
            {},
            "sunshineDuration",
            "sunshineDuration",
            240,
            int,
        ),
        (
            "sunshine_duration",
            "7200",
            {ATTR_UNIT_OF_MEASUREMENT: "s"},
            "sunshineDuration",
            "sunshineDuration",
            2,
            int,
        ),
        (
            "sunshine_duration",
            "100",
            {ATTR_UNIT_OF_MEASUREMENT: "min"},
            "sunshineDuration",
            "sunshineDuration",
            2,
            int,
        ),
        (
            "sunshine_duration",
            "2",
            {ATTR_UNIT_OF_MEASUREMENT: "d"},
            "sunshineDuration",
            "sunshineDuration",
            48,
            int,
        ),
        (
            "sunshine_duration",
            "3.4",
            {ATTR_UNIT_OF_MEASUREMENT: "h"},
            "sunshineDuration",
            "sunshineDuration",
            3,
            int,
        ),
        (
            "sunshine_duration",
            "3.6",
            {},
            "sunshineDuration",
            "sunshineDuration",
            4,
            int,
        ),
        ("sunshine_duration", "-2", {}, "sunshineDuration", "sunshineDuration", 0, int),
        # illuminance
        ("illuminance", "120.5", {}, "illumination", "illumination", 120.5, float),
        ("illuminance", "85000", {}, "illumination", "illumination", 20000.0, float),
        ("illuminance", "-1", {}, "illumination", "illumination", 0.0, float),
        (
            "illuminance",
            "20000",
            {ATTR_UNIT_OF_MEASUREMENT: "lx"},
            "illumination",
            "illumination",
            20000.0,
            float,
        ),
        # wind_direction
        ("wind_direction", "180.5", {}, "windDirection", "windDirection", 180.5, float),
        ("wind_direction", "360", {}, "windDirection", "windDirection", 0.0, float),
        ("wind_direction", "-90", {}, "windDirection", "windDirection", 270.0, float),
        ("wind_direction", "720.5", {}, "windDirection", "windDirection", 0.5, float),
        ("wind_direction", "359", {}, "windDirection", "windDirection", 359.0, float),
        ("wind_direction", "359.6", {}, "windDirection", "windDirection", 359.0, float),
        ("wind_direction", "-0.4", {}, "windDirection", "windDirection", 359.0, float),
        (
            "wind_direction",
            "-1e-20",
            {},
            "windDirection",
            "windDirection",
            359.0,
            float,
        ),
        ("wind_direction", "0", {}, "windDirection", "windDirection", 0.0, float),
        # humidity
        ("humidity", "55.4", {}, "humidity", "humidity", 55, int),
        ("humidity", "55.6", {}, "humidity", "humidity", 56, int),
        ("humidity", "104", {}, "humidity", "humidity", 100, int),
        ("humidity", "-3", {}, "humidity", "humidity", 0, int),
        # co2
        ("co2", "450", {}, "co2", "co2", 450.0, float),
        ("co2", "-20", {}, "co2", "co2", 0.0, float),
        # battery
        ("battery", "85.0", {}, "batteryState", "batteryLevel", 0.85, float),
        ("battery", "150", {}, "batteryState", "batteryLevel", 1.0, float),
        ("battery", "-5", {}, "batteryState", "batteryLevel", 0.0, float),
        ("battery", "33.333", {}, "batteryState", "batteryLevel", 0.3333, float),
        # on_time
        ("on_time", "60.0", {}, "onTime", "onTime", 60.0, float),
        (
            "on_time",
            "2",
            {ATTR_UNIT_OF_MEASUREMENT: "min"},
            "onTime",
            "onTime",
            120.0,
            float,
        ),
        ("on_time", "-5", {}, "onTime", "onTime", 0.0, float),
        # pm1 / pm25 / pm10
        (
            "pm1",
            "2.1",
            {},
            "particulateMassOne",
            "particulateMassConcentrationOne",
            2.1,
            float,
        ),
        (
            "pm1",
            "-1",
            {},
            "particulateMassOne",
            "particulateMassConcentrationOne",
            0.0,
            float,
        ),
        (
            "pm25",
            "8.5",
            {},
            "particulateMassTwoPointFive",
            "particulateMassConcentrationTwoPointFive",
            8.5,
            float,
        ),
        (
            "pm25",
            "-1",
            {},
            "particulateMassTwoPointFive",
            "particulateMassConcentrationTwoPointFive",
            0.0,
            float,
        ),
        (
            "pm10",
            "14.0",
            {},
            "particulateMassTen",
            "particulateMassConcentrationTen",
            14.0,
            float,
        ),
        (
            "pm10",
            "-1",
            {},
            "particulateMassTen",
            "particulateMassConcentrationTen",
            0.0,
            float,
        ),
    ],
)
def test_numeric_feature_matrix(
    feature_key: str,
    raw: str,
    attrs: dict[str, Any],
    hcu_type: str,
    field: str,
    expected: float | int,
    py_type: type[float] | type[int],
) -> None:
    """Convert units, apply scaling, clamp to bounds, and round numeric features."""
    result = _feature_value(feature_key, _make_state(raw, attrs))
    assert result == {"type": hcu_type, field: expected}
    assert type(result[field]) is py_type


_NUMERIC_AND_SHADING_KEYS = (
    "temperature",
    "supply_temperature",
    "set_point_temp",
    "cooling_temp_offset",
    "heating_temp_offset",
    "wind_speed",
    "power",
    "energy",
    "precipitation",
    "vehicle_range",
    "sunshine_duration",
    "on_time",
    "illuminance",
    "humidity",
    "co2",
    "pm1",
    "pm25",
    "pm10",
    "wind_direction",
    "battery",
    "shutter_level",
    "slats_level",
)


@pytest.mark.parametrize("feature_key", _NUMERIC_AND_SHADING_KEYS)
@pytest.mark.parametrize(
    "bad_state",
    ["nan", "NaN", "inf", "-inf", "Infinity", "1e999", "abc", "", "True"],
)
def test_rejected_numeric_states_return_none(feature_key: str, bad_state: str) -> None:
    """Non-finite, boolean-like, empty, or non-numeric states yield None."""
    assert _feature_value(feature_key, _make_state(bad_state)) is None


def test_numeric_conversion_overflow_and_domain_errors_return_none() -> None:
    """Overflow during unit conversion and converter domain errors yield None."""
    assert (
        _feature_value(
            HA_FEATURE_POWER,
            _make_state("1e308", {ATTR_UNIT_OF_MEASUREMENT: "TW"}),
        )
        is None
    )
    assert (
        _feature_value(
            HA_FEATURE_WIND_SPEED,
            _make_state("-1", {ATTR_UNIT_OF_MEASUREMENT: "Beaufort"}),
        )
        is None
    )


def test_numeric_features_table_keys() -> None:
    """The numeric feature table contains the exact 20 expected keys."""
    expected_keys = [
        "battery",
        "co2",
        "cooling_temp_offset",
        "energy",
        "heating_temp_offset",
        "illuminance",
        "humidity",
        "on_time",
        "pm1",
        "pm10",
        "pm25",
        "power",
        "precipitation",
        "set_point_temp",
        "sunshine_duration",
        "supply_temperature",
        "temperature",
        "vehicle_range",
        "wind_direction",
        "wind_speed",
    ]
    assert sorted(_NUMERIC_FEATURES) == sorted(expected_keys)


# ---------------------------------------------------------------------------
# 3. Enum normalization and validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("feature_key", "raw", "hcu_type", "expected"),
    [
        (HA_FEATURE_CLIMATE_OPERATION_MODE, "AUTO", "climateOperationMode", "AUTO"),
        (
            HA_FEATURE_CLIMATE_OPERATION_MODE,
            "cooling",
            "climateOperationMode",
            "COOLING",
        ),
        (
            HA_FEATURE_CLIMATE_OPERATION_MODE,
            " Heating ",
            "climateOperationMode",
            "HEATING",
        ),
        (HA_FEATURE_PRESENCE_MODE, "AWAY", "presenceMode", "AWAY"),
        (HA_FEATURE_PRESENCE_MODE, "default", "presenceMode", "DEFAULT"),
        (HA_FEATURE_PRESENCE_MODE, "Home", "presenceMode", "HOME"),
        (HA_FEATURE_PRESENCE_MODE, "normal", "presenceMode", "NORMAL"),
        (HA_FEATURE_PRESENCE_MODE, "vacation\n", "presenceMode", "VACATION"),
        (HA_FEATURE_SHUTTER_DIRECTION, "darker", "shutterDirection", "DARKER"),
        (HA_FEATURE_SHUTTER_DIRECTION, "LIGHTER", "shutterDirection", "LIGHTER"),
    ],
)
def test_enum_valid_values(
    feature_key: str, raw: str, hcu_type: str, expected: str
) -> None:
    """Valid enum strings are stripped, uppercased, and accepted."""
    assert _feature_value(feature_key, _make_state(raw)) == {
        "type": hcu_type,
        hcu_type: expected,
    }


@pytest.mark.parametrize(
    ("feature_key", "raw", "hcu_type", "allowed"),
    [
        (
            HA_FEATURE_CLIMATE_OPERATION_MODE,
            "HEAT",
            "climateOperationMode",
            "AUTO, COOLING, HEATING",
        ),
        (
            HA_FEATURE_CLIMATE_OPERATION_MODE,
            "AWAY",
            "climateOperationMode",
            "AUTO, COOLING, HEATING",
        ),
        (
            HA_FEATURE_PRESENCE_MODE,
            "PARTY",
            "presenceMode",
            "AWAY, DEFAULT, HOME, NORMAL, VACATION",
        ),
        (
            HA_FEATURE_PRESENCE_MODE,
            "AUTO",
            "presenceMode",
            "AWAY, DEFAULT, HOME, NORMAL, VACATION",
        ),
        (HA_FEATURE_SHUTTER_DIRECTION, "UP", "shutterDirection", "DARKER, LIGHTER"),
        (HA_FEATURE_SHUTTER_DIRECTION, "", "shutterDirection", "DARKER, LIGHTER"),
    ],
)
def test_enum_invalid_values_logged_at_debug(
    caplog: pytest.LogCaptureFixture,
    feature_key: str,
    raw: str,
    hcu_type: str,
    allowed: str,
) -> None:
    """Invalid enum strings return None and emit one debug log record."""
    with caplog.at_level(logging.DEBUG, logger=_BRIDGE_LOGGER):
        result = _feature_value(feature_key, _make_state(raw, entity_id="select.mode"))
    assert result is None
    bridge_records = [r for r in caplog.records if r.name == _BRIDGE_LOGGER]
    assert len(bridge_records) == 1
    assert bridge_records[0].levelno == logging.DEBUG
    assert bridge_records[0].getMessage() == (
        f"Ignoring {hcu_type} value {raw!r} of select.mode: expected one of {allowed}"
    )


# ---------------------------------------------------------------------------
# 4. Shading levels and helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("feature_key", "hcu_type"),
    [
        (HA_FEATURE_SHUTTER_LEVEL, "shutterLevel"),
        (HA_FEATURE_SLATS_LEVEL, "slatsLevel"),
    ],
)
@pytest.mark.parametrize(
    ("raw", "attrs", "expected"),
    [
        ("0.65", {}, 0.65),
        ("0", {}, 0.0),
        ("1", {}, 1.0),
        ("1.5", {}, 1.0),
        ("-0.2", {}, 0.0),
        ("0.123456", {}, 0.1235),
        ("0.3", {"min": 0, "max": 1}, 0.3),
        ("0.3", {"max": 1.0, ATTR_UNIT_OF_MEASUREMENT: None}, 0.3),
        ("1.0", {"max": 1.01}, 1.0),
        ("0.3", {"max": "abc"}, 0.3),
        ("0.3", {"max": True}, 0.3),
        ("0.3", {"max": float("nan")}, 0.3),
        ("0.3", {"max": float("inf")}, 0.3),
        ("100", {"max": 100}, 0.0),
        ("0", {"max": 100}, 1.0),
        ("25", {"max": 100}, 0.75),
        ("25", {"max": 1.5}, 0.75),
        ("25", {ATTR_UNIT_OF_MEASUREMENT: "%"}, 0.75),
        ("25", {ATTR_UNIT_OF_MEASUREMENT: "%", "max": 1}, 0.75),
        ("130", {"max": 100}, 0.0),
        ("-20", {"max": 100}, 1.0),
        ("33.333", {"max": 100}, 0.6667),
        ("50", {"max": "100"}, 0.5),
        ("40", {"max": 255}, 0.6),
    ],
)
def test_shading_levels(
    feature_key: str,
    hcu_type: str,
    raw: str,
    attrs: dict[str, Any],
    expected: float,
) -> None:
    """Shading levels invert 0..100 or percent entities and clamp 0..1 fractions."""
    result = _feature_value(feature_key, _make_state(raw, attrs))
    assert result == {"type": hcu_type, hcu_type: expected}


@pytest.mark.parametrize(
    ("attrs", "expected"),
    [
        ({ATTR_UNIT_OF_MEASUREMENT: "%"}, True),
        ({"max": 1.02}, True),
        ({"max": 1.01}, False),
        ({"max": 1}, False),
        ({}, False),
        ({ATTR_UNIT_OF_MEASUREMENT: "percent"}, False),
    ],
)
def test_is_percent_scale(attrs: dict[str, Any], expected: bool) -> None:
    """Detect whether a shading entity uses a 0..100 position scale."""
    assert _is_percent_scale(_make_state("0", attrs)) is expected


@pytest.mark.parametrize(
    ("position", "expected"),
    [
        (0, 1.0),
        (100, 0.0),
        (25, 0.75),
        (150, 0.0),
        (-1, 1.0),
        (99.999, 0.0),
    ],
)
def test_position_to_level(position: float, expected: float) -> None:
    """Convert Home Assistant shading position to HCU level."""
    assert _position_to_level(position) == expected


# ---------------------------------------------------------------------------
# 5. Light status features
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("state_str", "attrs", "expected"),
    [
        (STATE_ON, {ATTR_BRIGHTNESS: 128}, {"type": "dimming", "dimLevel": 0.502}),
        (STATE_ON, {ATTR_BRIGHTNESS: 255}, {"type": "dimming", "dimLevel": 1.0}),
        (STATE_ON, {ATTR_BRIGHTNESS: 0}, {"type": "dimming", "dimLevel": 0.0}),
        (STATE_ON, {ATTR_BRIGHTNESS: 300}, {"type": "dimming", "dimLevel": 1.0}),
        (STATE_ON, {ATTR_BRIGHTNESS: -4}, {"type": "dimming", "dimLevel": 0.0}),
        (STATE_ON, {ATTR_BRIGHTNESS: "128"}, {"type": "dimming", "dimLevel": 0.502}),
        (STATE_ON, {ATTR_BRIGHTNESS: None}, None),
        (STATE_ON, {}, None),
        (STATE_ON, {ATTR_BRIGHTNESS: float("nan")}, None),
        (STATE_ON, {ATTR_BRIGHTNESS: float("inf")}, None),
        (STATE_ON, {ATTR_BRIGHTNESS: "bright"}, None),
        (STATE_ON, {ATTR_BRIGHTNESS: True}, None),
        (STATE_OFF, {ATTR_BRIGHTNESS: 200}, None),
    ],
)
def test_dimming_status(
    state_str: str, attrs: dict[str, Any], expected: dict[str, Any] | None
) -> None:
    """Dimming status clamps brightness, rejects invalid values, and skips off lights."""
    state = State("light.x", state_str, attrs)
    assert _feature_value(HA_FEATURE_BRIGHTNESS, state) == expected


@pytest.mark.parametrize(
    ("attrs", "expected_fields"),
    [
        ({ATTR_COLOR_TEMP_KELVIN: 3500}, {"colorTemperature": 3500}),
        ({"color_temp": 250}, {"colorTemperature": 4000}),
        ({"color_temp": 0}, None),
        ({"color_temp": -5}, None),
        ({"color_temp": "x"}, None),
        ({"color_temp": float("inf")}, None),
        ({"color_temp": 1e9}, None),
        ({}, None),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 3500,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "colorTemperature": 3500,
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 1500,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "colorTemperature": 2000,
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 9000,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "colorTemperature": 6500,
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 3000,
                ATTR_MIN_COLOR_TEMP_KELVIN: 6500,
                ATTR_MAX_COLOR_TEMP_KELVIN: 2000,
            },
            {
                "colorTemperature": 3000,
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: None,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 1500,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
            },
            {
                "colorTemperature": 2000,
                "minimalColorTemperature": 2000,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 9000,
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "colorTemperature": 6500,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 3000.6,
                ATTR_MIN_COLOR_TEMP_KELVIN: 2000.4,
                ATTR_MAX_COLOR_TEMP_KELVIN: "6500",
            },
            {
                "colorTemperature": 3001,
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: float("nan"),
                ATTR_MIN_COLOR_TEMP_KELVIN: float("inf"),
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "maximumColorTemperature": 6500,
            },
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: 0,
                ATTR_MIN_COLOR_TEMP_KELVIN: 0,
                ATTR_MAX_COLOR_TEMP_KELVIN: -1,
            },
            None,
        ),
        (
            {
                ATTR_COLOR_TEMP_KELVIN: True,
                ATTR_MIN_COLOR_TEMP_KELVIN: True,
                ATTR_MAX_COLOR_TEMP_KELVIN: False,
            },
            None,
        ),
        (
            {
                "color_temp": 250,
                ATTR_MIN_COLOR_TEMP_KELVIN: 4500,
                ATTR_MAX_COLOR_TEMP_KELVIN: 6500,
            },
            {
                "colorTemperature": 4500,
                "minimalColorTemperature": 4500,
                "maximumColorTemperature": 6500,
            },
        ),
        ({ATTR_COLOR_TEMP_KELVIN: 0.4}, None),
        ({ATTR_COLOR_TEMP_KELVIN: 0.6}, {"colorTemperature": 1}),
    ],
)
def test_color_temperature_status(
    attrs: dict[str, Any], expected_fields: dict[str, int] | None
) -> None:
    """Color temperature status includes integer Kelvin limits and clamps the value."""
    state = State("light.x", STATE_ON, attrs)
    result = _feature_value(HA_FEATURE_COLOR_TEMP, state)
    if expected_fields is None:
        assert result is None
    else:
        assert result == {"type": "colorTemperature", **expected_fields}
        for key in expected_fields:
            assert type(result[key]) is int


def test_color_temperature_status_off_light_keeps_limits() -> None:
    """An off light still reports minimal and maximal color temperature limits."""
    state = State(
        "light.x",
        STATE_OFF,
        {
            ATTR_COLOR_TEMP_KELVIN: None,
            ATTR_MIN_COLOR_TEMP_KELVIN: 2202,
            ATTR_MAX_COLOR_TEMP_KELVIN: 6535,
        },
    )
    assert _feature_value(HA_FEATURE_COLOR_TEMP, state) == {
        "type": "colorTemperature",
        "minimalColorTemperature": 2202,
        "maximumColorTemperature": 6535,
    }


@pytest.mark.parametrize(
    ("rgb", "expected"),
    [
        ((255, 0, 0), {"type": "color", "hue": 0, "saturationLevel": 1.0}),
        ((0, 255, 0), {"type": "color", "hue": 120, "saturationLevel": 1.0}),
        ((0, 0, 255), {"type": "color", "hue": 240, "saturationLevel": 1.0}),
        ((255, 0, 1), {"type": "color", "hue": 0, "saturationLevel": 1.0}),
        ((255, 0, 2), {"type": "color", "hue": 0, "saturationLevel": 1.0}),
        ((255, 0, 3), {"type": "color", "hue": 359, "saturationLevel": 1.0}),
        ((255, 255, 255), {"type": "color", "hue": 0, "saturationLevel": 0.0}),
        ((0, 0, 0), {"type": "color", "hue": 0, "saturationLevel": 0.0}),
        ((255, 128, 128), {"type": "color", "hue": 0, "saturationLevel": 0.498}),
        ([10, 20, 30], {"type": "color", "hue": 210, "saturationLevel": 0.6667}),
        ((300, 0, 0), {"type": "color", "hue": 0, "saturationLevel": 1.0}),
        ((-5, 0, 0), {"type": "color", "hue": 0, "saturationLevel": 0.0}),
        (("255", "0", "0"), {"type": "color", "hue": 0, "saturationLevel": 1.0}),
    ],
)
def test_color_status_valid(rgb: Any, expected: dict[str, Any]) -> None:
    """Convert valid rgb_color tuples to hue 0..359 and saturationLevel 0..1."""
    result = _feature_value(
        HA_FEATURE_RGB_COLOR, _make_state(STATE_ON, {"rgb_color": rgb})
    )
    assert result == expected
    assert type(result["hue"]) is int


@pytest.mark.parametrize(
    "rgb",
    [
        None,
        (255, 0),
        (255, 0, 0, 0),
        5,
        (float("nan"), 0, 0),
        (255, float("inf"), 0),
        (255, 0, None),
        ("x", 0, 0),
        (True, 0, 0),
        "123",
    ],
)
def test_color_status_invalid(rgb: Any) -> None:
    """Malformed or non-finite rgb_color values return None."""
    attrs = {} if rgb is None else {"rgb_color": rgb}
    if rgb is None:
        assert (
            _feature_value(
                HA_FEATURE_RGB_COLOR, _make_state(STATE_ON, {"rgb_color": None})
            )
            is None
        )
    assert _feature_value(HA_FEATURE_RGB_COLOR, _make_state(STATE_ON, attrs)) is None


def test_color_status_hue_sweep_bounds() -> None:
    """Hue stays within 0..359 and saturation within 0..1 across red/blue sweep."""
    for red in (255, 254, 200, 1):
        for blue in range(256):
            result = _feature_value(
                HA_FEATURE_RGB_COLOR,
                _make_state(STATE_ON, {"rgb_color": (red, 0, blue)}),
            )
            assert result is not None
            assert type(result["hue"]) is int
            assert 0 <= result["hue"] <= 359
            assert 0.0 <= result["saturationLevel"] <= 1.0


# ---------------------------------------------------------------------------
# 6. Dimming control
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("dim_level", "expected_on", "expected_off"),
    [
        (0.5, [{"entity_id": "light.desk", "brightness": 128}], []),
        (0.2, [{"entity_id": "light.desk", "brightness": 51}], []),
        (1.0, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1, [{"entity_id": "light.desk", "brightness": 255}], []),
        ("0.5", [{"entity_id": "light.desk", "brightness": 128}], []),
        (0.001, [{"entity_id": "light.desk", "brightness": 1}], []),
        (0.0039, [{"entity_id": "light.desk", "brightness": 1}], []),
        (0.0, [], [_DESK_ENTITY]),
        (0, [], [_DESK_ENTITY]),
        (-0.3, [], [_DESK_ENTITY]),
        (1.003, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1.02, [{"entity_id": "light.desk", "brightness": 255}], []),
        (2, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1.0049, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1.0051, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1.0099, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1.0101, [{"entity_id": "light.desk", "brightness": 255}], []),
        (1.01, [], []),
        (1.0100000001, [], []),
        ("1.01", [], []),
        (None, [], []),
        (1.005, [_DESK_ENTITY], []),
        (1.0050000001, [_DESK_ENTITY], []),
    ],
)
async def test_dimming_control_values(
    hass: HomeAssistant,
    dim_level: Any,
    expected_on: list[dict[str, Any]],
    expected_off: list[dict[str, Any]],
) -> None:
    """Dimming control honors special values, clamps bounds, and switches off at <= 0."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)

    feature: dict[str, Any] = {"type": "dimming", "dimLevel": dim_level}

    result = await bridge.handle_control_request(
        {"deviceId": "ha.lt1", "features": [feature]}
    )
    assert result is None
    assert [c.data for c in turn_on] == expected_on
    assert [c.data for c in turn_off] == expected_off


@pytest.mark.parametrize(
    ("features", "expected_on", "expected_off"),
    [
        (
            [
                {"type": "dimming", "dimLevel": 1.005},
                {"type": "switchState", "on": False},
            ],
            [],
            [_DESK_ENTITY],
        ),
        (
            [
                {"type": "switchState", "on": False},
                {"type": "dimming", "dimLevel": 1.005},
            ],
            [],
            [_DESK_ENTITY],
        ),
        (
            [
                {"type": "dimming", "dimLevel": 1.005},
                {"type": "switchState", "on": True},
            ],
            [_DESK_ENTITY],
            [],
        ),
        (
            [{"type": "dimming", "dimLevel": 1.005}, {"type": "switchState"}],
            [_DESK_ENTITY],
            [],
        ),
        (
            [
                {"type": "dimming", "dimLevel": 1.005},
                {"type": "switchState", "on": None},
            ],
            [_DESK_ENTITY],
            [],
        ),
        (
            [
                {"type": "dimming", "dimLevel": 1.005},
                {"type": "onTime", "on": True, "onTime": 5},
            ],
            [_DESK_ENTITY],
            [],
        ),
        (
            [
                {"type": "dimming", "dimLevel": 1.01},
                {"type": "switchState", "on": True},
            ],
            [_DESK_ENTITY],
            [],
        ),
    ],
)
async def test_dimming_control_with_sibling_features(
    hass: HomeAssistant,
    features: list[dict[str, Any]],
    expected_on: list[dict[str, Any]],
    expected_off: list[dict[str, Any]],
) -> None:
    """Last-value dimming defers to sibling switchState when on is present."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)

    result = await bridge.handle_control_request(
        {"deviceId": "ha.lt1", "features": features}
    )
    assert result is None
    assert [c.data for c in turn_on] == expected_on
    assert [c.data for c in turn_off] == expected_off


@pytest.mark.parametrize(
    "bad_dim",
    [float("nan"), float("inf"), float("-inf"), "nan", "abc", True, False, [0.5]],
)
async def test_dimming_control_invalid_values(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, bad_dim: Any
) -> None:
    """Invalid dimLevel values return CONTROL_REQUEST_FAILED and log an error."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)

    expected_msg = f"Dimming light.desk failed: invalid value {bad_dim!r}"
    with caplog.at_level(logging.ERROR, logger=_BRIDGE_LOGGER):
        result = await bridge.handle_control_request(
            {
                "deviceId": "ha.lt1",
                "features": [{"type": "dimming", "dimLevel": bad_dim}],
            }
        )
    assert result == {"code": CONTROL_ERROR_FAILED, "message": expected_msg}
    assert expected_msg in caplog.text
    assert turn_on == []
    assert turn_off == []


def test_level_to_brightness_round_trip() -> None:
    """Every brightness 1..255 round-trips through status rounding and clamps extremes."""
    for b in range(1, 256):
        assert _level_to_brightness(round(b / 255, 4)) == b
    assert _level_to_brightness(1e-9) == 1
    assert _level_to_brightness(7.0) == 255


# ---------------------------------------------------------------------------
# 7. Color temperature control
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw_ct", "attrs", "expected_kelvin"),
    [
        (3200, None, 3200),
        (3200.4, None, 3200),
        ("3200", None, 3200),
        (10075, None, 10075),
        (3200, {}, 3200),
        (
            1500,
            {ATTR_MIN_COLOR_TEMP_KELVIN: 2000, ATTR_MAX_COLOR_TEMP_KELVIN: 6500},
            2000,
        ),
        (
            9000,
            {ATTR_MIN_COLOR_TEMP_KELVIN: 2000, ATTR_MAX_COLOR_TEMP_KELVIN: 6500},
            6500,
        ),
        (
            3000,
            {ATTR_MIN_COLOR_TEMP_KELVIN: 6500, ATTR_MAX_COLOR_TEMP_KELVIN: 2000},
            3000,
        ),
        (9000, {ATTR_MIN_COLOR_TEMP_KELVIN: 2000}, 9000),
        (1000, {ATTR_MIN_COLOR_TEMP_KELVIN: 2000}, 2000),
    ],
)
async def test_color_temp_control_clamps_and_calls(
    hass: HomeAssistant,
    raw_ct: Any,
    attrs: dict[str, Any] | None,
    expected_kelvin: int,
) -> None:
    """Valid color temperatures are clamped to entity limits and sent as int."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)
    if attrs is not None:
        hass.states.async_set("light.desk", STATE_ON, attrs)

    result = await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "colorTemperature", "colorTemperature": raw_ct}],
        }
    )
    assert result is None
    assert len(turn_on) == 1
    assert turn_on[0].data == {
        "entity_id": "light.desk",
        "color_temp_kelvin": expected_kelvin,
    }
    assert type(turn_on[0].data["color_temp_kelvin"]) is int


@pytest.mark.parametrize(
    ("raw_ct", "attrs"),
    [
        (10050, None),
        (10100, None),
        (10050.0, None),
        ("10100", None),
        (10100.4, None),
        (None, None),
        (10050, {ATTR_MIN_COLOR_TEMP_KELVIN: 2000, ATTR_MAX_COLOR_TEMP_KELVIN: 6500}),
    ],
)
async def test_color_temp_control_no_op_special_values(
    hass: HomeAssistant, raw_ct: Any, attrs: dict[str, Any] | None
) -> None:
    """Last-value, ignore, and None colorTemperature values leave the light unchanged."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)
    if attrs is not None:
        hass.states.async_set("light.desk", STATE_ON, attrs)

    result = await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "colorTemperature", "colorTemperature": raw_ct}],
        }
    )
    assert result is None
    assert turn_on == []


@pytest.mark.parametrize(
    ("raw_ct", "expected_mode"),
    [
        (10150, 10150),
        (10200, 10200),
        (10150.0, 10150),
        ("10200", 10200),
        (10149.6, 10150),
    ],
)
async def test_color_temp_control_unsupported_modes(
    hass: HomeAssistant, raw_ct: Any, expected_mode: int
) -> None:
    """Dim2warm and dynamic daylight special values return FEATURE_NOT_SUPPORTED."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)
    hass.states.async_set(
        "light.desk",
        STATE_ON,
        {ATTR_MIN_COLOR_TEMP_KELVIN: 2000, ATTR_MAX_COLOR_TEMP_KELVIN: 6500},
    )

    result = await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "colorTemperature", "colorTemperature": raw_ct}],
        }
    )
    assert result == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": f"Color temperature mode {expected_mode} is not supported by ha.lt1",
    }
    assert turn_on == []


@pytest.mark.parametrize(
    "bad_ct",
    [0, -2700, 0.4, float("nan"), float("inf"), "warm", True],
)
async def test_color_temp_control_invalid_values(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, bad_ct: Any
) -> None:
    """Invalid colorTemperature values return CONTROL_REQUEST_FAILED and log an error."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)

    expected_msg = f"Color temp light.desk failed: invalid value {bad_ct!r}"
    with caplog.at_level(logging.ERROR, logger=_BRIDGE_LOGGER):
        result = await bridge.handle_control_request(
            {
                "deviceId": "ha.lt1",
                "features": [{"type": "colorTemperature", "colorTemperature": bad_ct}],
            }
        )
    assert result == {"code": CONTROL_ERROR_FAILED, "message": expected_msg}
    assert expected_msg in caplog.text
    assert turn_on == []


# ---------------------------------------------------------------------------
# 8. Color control
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hue", "sat", "expected_rgb"),
    [
        (120, 1.0, [0, 255, 0]),
        (240, 0.5, [128, 128, 255]),
        ("120", "1", [0, 255, 0]),
        (359, 1.0, [255, 0, 4]),
        (359.6, 1.0, [255, 0, 4]),
        (400, 1.0, [255, 0, 4]),
        (362, 1.0, [255, 0, 4]),
        (-20, 1.0, [255, 0, 0]),
        (120, 1.5, [0, 255, 0]),
        (120, 1.003, [0, 255, 0]),
        (120, -0.5, [255, 255, 255]),
        (120, 0, [255, 255, 255]),
    ],
)
async def test_color_control_without_state(
    hass: HomeAssistant, hue: Any, sat: Any, expected_rgb: list[int]
) -> None:
    """Complete color control requests clamp hue and saturation and send rgb_color."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)

    result = await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "color", "hue": hue, "saturationLevel": sat}],
        }
    )
    assert result is None
    assert [c.data for c in turn_on] == [
        {"entity_id": "light.desk", "rgb_color": expected_rgb}
    ]


@pytest.mark.parametrize(
    ("state_rgb", "feature", "expected_rgb"),
    [
        (
            (128, 128, 255),
            {"type": "color", "hue": 120, "saturationLevel": 1.01},
            [128, 255, 128],
        ),
        (
            (128, 128, 255),
            {"type": "color", "hue": 120, "saturationLevel": 1.005},
            [128, 255, 128],
        ),
        ((128, 128, 255), {"type": "color", "hue": 120}, [128, 255, 128]),
        (
            (128, 128, 255),
            {"type": "color", "hue": 120, "saturationLevel": None},
            [128, 255, 128],
        ),
        (
            (128, 128, 255),
            {"type": "color", "hue": 361, "saturationLevel": 1.0},
            [0, 0, 255],
        ),
        (
            (128, 128, 255),
            {"type": "color", "hue": 360, "saturationLevel": 1.0},
            [0, 0, 255],
        ),
        ((128, 128, 255), {"type": "color", "saturationLevel": 1.0}, [0, 0, 255]),
        (
            (128, 128, 255),
            {"type": "color", "hue": 361.0, "saturationLevel": 0.0},
            [255, 255, 255],
        ),
        (
            (128, 128, 255),
            {"type": "color", "hue": 0, "saturationLevel": 1.01},
            [255, 128, 128],
        ),
        (
            (255, 0, 0),
            {"type": "color", "hue": 360, "saturationLevel": 0.25},
            [255, 191, 191],
        ),
    ],
)
async def test_color_control_merges_kept_half_from_state(
    hass: HomeAssistant,
    state_rgb: tuple[int, int, int],
    feature: dict[str, Any],
    expected_rgb: list[int],
) -> None:
    """When one half of color is kept, fill it from the current light rgb_color."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)
    hass.states.async_set("light.desk", STATE_ON, {"rgb_color": state_rgb})

    result = await bridge.handle_control_request(
        {"deviceId": "ha.lt1", "features": [feature]}
    )
    assert result is None
    assert [c.data for c in turn_on] == [
        {"entity_id": "light.desk", "rgb_color": expected_rgb}
    ]


@pytest.mark.parametrize(
    ("attrs", "feature"),
    [
        ({"rgb_color": (255, 0, 0)}, {"type": "color"}),
        (
            {"rgb_color": (255, 0, 0)},
            {"type": "color", "hue": None, "saturationLevel": None},
        ),
        (
            {"rgb_color": (255, 0, 0)},
            {"type": "color", "hue": 361, "saturationLevel": 1.01},
        ),
        (
            {"rgb_color": (255, 0, 0)},
            {"type": "color", "hue": 360, "saturationLevel": 1.005},
        ),
        (
            {"rgb_color": (255, 0, 0)},
            {"type": "color", "hue": 361, "saturationLevel": 1.005},
        ),
        ({"rgb_color": (255, 0, 0)}, {"type": "color", "hue": 360}),
        ({"rgb_color": (255, 0, 0)}, {"type": "color", "saturationLevel": 1.01}),
        (None, {"type": "color", "hue": 120}),
        (None, {"type": "color", "hue": 120, "saturationLevel": 1.01}),
        (None, {"type": "color", "hue": 361, "saturationLevel": 0.5}),
        ({}, {"type": "color", "hue": 120}),
        ({"rgb_color": None}, {"type": "color", "hue": 120}),
        ({"rgb_color": (255, 0)}, {"type": "color", "saturationLevel": 0.5}),
        (
            {"rgb_color": (255, float("nan"), 0)},
            {"type": "color", "saturationLevel": 0.5},
        ),
    ],
)
async def test_color_control_no_op_cases(
    hass: HomeAssistant, attrs: dict[str, Any] | None, feature: dict[str, Any]
) -> None:
    """Both halves kept or missing current color sends no service call."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)
    if attrs is not None:
        hass.states.async_set("light.desk", STATE_ON, attrs)

    result = await bridge.handle_control_request(
        {"deviceId": "ha.lt1", "features": [feature]}
    )
    assert result is None
    assert turn_on == []


@pytest.mark.parametrize(
    ("feature", "bad_val"),
    [
        ({"type": "color", "hue": float("nan"), "saturationLevel": 1.0}, float("nan")),
        ({"type": "color", "hue": 120, "saturationLevel": float("inf")}, float("inf")),
        ({"type": "color", "hue": "red", "saturationLevel": 1.0}, "red"),
        ({"type": "color", "hue": True, "saturationLevel": 1.0}, True),
        ({"type": "color", "hue": 120, "saturationLevel": False}, False),
        ({"type": "color", "hue": float("nan")}, float("nan")),
        ({"type": "color", "saturationLevel": "x"}, "x"),
        (
            {"type": "color", "hue": 361, "saturationLevel": float("-inf")},
            float("-inf"),
        ),
    ],
)
async def test_color_control_invalid_values(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    feature: dict[str, Any],
    bad_val: Any,
) -> None:
    """Invalid hue or saturationLevel fails even if the other half is kept."""
    turn_on = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)
    hass.states.async_set("light.desk", STATE_ON, {"rgb_color": (255, 0, 0)})

    expected_msg = f"Color light.desk failed: invalid value {bad_val!r}"
    with caplog.at_level(logging.ERROR, logger=_BRIDGE_LOGGER):
        result = await bridge.handle_control_request(
            {"deviceId": "ha.lt1", "features": [feature]}
        )
    assert result == {"code": CONTROL_ERROR_FAILED, "message": expected_msg}
    assert expected_msg in caplog.text
    assert turn_on == []


# ---------------------------------------------------------------------------
# 9. Service failure error messages preserved
# ---------------------------------------------------------------------------


async def test_service_failures_keep_messages(hass: HomeAssistant) -> None:
    """Existing service failure messages are preserved across all light features."""

    async def _fail(call: ServiceCall) -> None:
        raise HomeAssistantError("Lamp offline")

    hass.services.async_register("light", "turn_on", _fail)
    hass.services.async_register("light", "turn_off", _fail)
    bridge = HaEntityBridge(hass, [_LIGHT], AsyncMock(), PLUGIN_ID)

    result = await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [
                {"type": "dimming", "dimLevel": 0},
                {"type": "dimming", "dimLevel": 1.005},
                {"type": "colorTemperature", "colorTemperature": 3000},
                {"type": "color", "hue": 1, "saturationLevel": 1},
            ],
        }
    )
    assert result == {
        "code": CONTROL_ERROR_FAILED,
        "message": (
            "Dimming light.desk failed: Lamp offline; "
            "Dimming light.desk failed: Lamp offline; "
            "Color temp light.desk failed: Lamp offline; "
            "Color light.desk failed: Lamp offline"
        ),
    }


# ---------------------------------------------------------------------------
# 10. On time resolution and invalid value rejection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("source", ["switch_feature", "on_time_feature", "entity"])
@pytest.mark.parametrize(
    "bad_on_time",
    [float("nan"), float("inf"), float("-inf"), "nan", "inf", True, False, "x", [5]],
)
async def test_control_on_time_rejects_invalid_sources(
    hass: HomeAssistant, source: str, bad_on_time: Any
) -> None:
    """Invalid onTime values from any source turn on without scheduling auto-off."""
    turn_on = async_mock_service(hass, "switch", "turn_on")
    turn_off = async_mock_service(hass, "switch", "turn_off")
    bridge = HaEntityBridge(hass, [_PUMP], AsyncMock(), PLUGIN_ID)

    features: list[dict[str, Any]] = [{"type": "switchState", "on": True}]
    if source == "switch_feature":
        features[0]["onTime"] = bad_on_time
    elif source == "on_time_feature":
        features.append({"type": "onTime", "onTime": bad_on_time})
    else:
        hass.states.async_set("number.run", str(bad_on_time))

    result = await bridge.handle_control_request(
        {"deviceId": "ha.sw1", "features": features}
    )
    assert result is None
    assert [c.data for c in turn_on] == [_PUMP_ENTITY]
    assert bridge._auto_off_tasks == {}
    await hass.async_block_till_done()
    assert turn_off == []


@pytest.mark.parametrize(
    ("body_features", "switch_feature", "entity_val", "entity_unit", "expected"),
    [
        ([], {}, "2", "min", 120.0),
        (
            [{"type": "onTime", "onTime": float("nan")}],
            {"onTime": float("inf")},
            "2",
            "min",
            120.0,
        ),
        ([{"type": "onTime", "onTime": 7}], {"onTime": True}, "2", "min", 7.0),
        (
            [{"type": "onTime", "onTime": "nan"}, {"type": "onTime", "onTime": 9}],
            {},
            "2",
            "min",
            9.0,
        ),
        ([{"type": "dimming", "onTime": 9}], {}, "2", "min", 120.0),
        ([], {"onTime": -3}, "2", "min", -3.0),
        ([], {}, "-4", None, 0.0),
        ([], {}, "inf", None, None),
        ([], {}, "1500", "ms", 1.5),
    ],
)
def test_get_control_on_time_direct(
    hass: HomeAssistant,
    body_features: list[dict[str, Any]],
    switch_feature: dict[str, Any],
    entity_val: str,
    entity_unit: str | None,
    expected: float | None,
) -> None:
    """Resolve onTime across request features and unit-converted entity state."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)
    attrs = {ATTR_UNIT_OF_MEASUREMENT: entity_unit} if entity_unit else {}
    hass.states.async_set("number.run", entity_val, attrs)
    features_conf = {HA_FEATURE_ON_TIME: "number.run"}

    assert (
        bridge._get_control_on_time(body_features, switch_feature, features_conf)
        == expected
    )


# ---------------------------------------------------------------------------
# 11. Required features and discovery completeness
# ---------------------------------------------------------------------------


def test_energy_meter_requires_power_constant() -> None:
    """ENERGY_METER requires power and keeps energy optional."""
    assert HA_DEVICE_TYPE_FEATURES[HA_DEVICE_TYPE_ENERGY_METER] == {
        "required": ["power"],
        "optional": ["energy"],
    }


@pytest.mark.parametrize("with_type", [True, False])
def test_incomplete_energy_meter_skipped_from_discover_with_single_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    with_type: bool,
) -> None:
    """Incomplete energy meter is omitted from discovery, logged once, and keeps status."""
    em_device: dict[str, Any] = {
        "id": "em1",
        "name": "Meter",
        "features": {HA_FEATURE_ENERGY: "sensor.energy"},
    }
    if with_type:
        em_device["type"] = HA_DEVICE_TYPE_ENERGY_METER

    sw_device: dict[str, Any] = {
        "id": "sw1",
        "name": "Pump",
        "type": HA_DEVICE_TYPE_SWITCH,
        "features": {HA_FEATURE_ON_OFF: "switch.pump"},
    }
    hass.states.async_set("sensor.energy", "12.5")
    hass.states.async_set("switch.pump", STATE_ON)

    bridge = HaEntityBridge(hass, [em_device, sw_device], AsyncMock(), PLUGIN_ID)

    with caplog.at_level(logging.WARNING, logger=_BRIDGE_LOGGER):
        first = bridge.build_discover_devices()
        second = bridge.build_discover_devices()

    assert [d["deviceId"] for d in first] == ["ha.sw1"]
    assert [d["deviceId"] for d in second] == ["ha.sw1"]
    assert bridge._discovered_hcu_ids == {"ha.sw1"}

    warnings = [
        r
        for r in caplog.records
        if r.name == _BRIDGE_LOGGER and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert warnings[0].getMessage() == (
        "Not offering device ha.em1 (Meter) to the HCU: type ENERGY_METER requires "
        "the feature currentPower. Edit the device in the integration options and "
        "select the missing entity"
    )

    status_devices = bridge.build_status_devices()
    assert [d["deviceId"] for d in status_devices] == ["ha.em1", "ha.sw1"]
    assert status_devices[0]["features"] == [
        {"type": "energyCounter", "in": 12.5},
        {"type": "maintenance", "unreach": False},
    ]

    included = bridge.handle_inclusion_event(["ha.em1"])
    assert [d["deviceId"] for d in included] == ["ha.em1"]
    assert bridge._discovered_hcu_ids == {"ha.sw1", "ha.em1"}


@pytest.mark.parametrize(
    ("power_state", "energy_state", "expected_before_maint", "expected_unreach"),
    [
        (
            "150",
            "12.5",
            [
                {"type": "currentPower", "currentPower": 150.0},
                {"type": "energyCounter", "in": 12.5},
            ],
            False,
        ),
        (
            STATE_UNAVAILABLE,
            "12.5",
            [{"type": "currentPower"}, {"type": "energyCounter", "in": 12.5}],
            True,
        ),
        (
            None,
            "12.5",
            [{"type": "currentPower"}, {"type": "energyCounter", "in": 12.5}],
            True,
        ),
        (
            "150",
            STATE_UNAVAILABLE,
            [
                {"type": "currentPower", "currentPower": 150.0},
                {"type": "energyCounter"},
            ],
            False,
        ),
        (
            STATE_UNKNOWN,
            STATE_UNAVAILABLE,
            [{"type": "currentPower"}, {"type": "energyCounter"}],
            False,
        ),
    ],
)
def test_complete_energy_meter_discover_and_unreach(
    hass: HomeAssistant,
    power_state: str | None,
    energy_state: str,
    expected_before_maint: list[dict[str, Any]],
    expected_unreach: bool,
) -> None:
    """Complete energy meter discovers and derives unreach from required power."""
    if power_state is not None:
        hass.states.async_set("sensor.power", power_state)
    hass.states.async_set("sensor.energy", energy_state)

    bridge = HaEntityBridge(hass, [_METER], AsyncMock(), PLUGIN_ID)
    discovered = bridge.build_discover_devices()
    assert len(discovered) == 1
    assert discovered[0]["features"] == [
        *expected_before_maint,
        {"type": "maintenance", "unreach": expected_unreach},
    ]


@pytest.mark.parametrize(
    ("energy_state", "expected_unreach"),
    [
        ("12.5", False),
        (STATE_UNAVAILABLE, True),
        (None, True),
        (STATE_UNKNOWN, False),
    ],
)
def test_energy_only_meter_status_unreach(
    hass: HomeAssistant, energy_state: str | None, expected_unreach: bool
) -> None:
    """Energy-only meter unreach falls back to all non-maintenance entities."""
    em_device = {
        "id": "em1",
        "name": "Meter",
        "type": HA_DEVICE_TYPE_ENERGY_METER,
        "features": {HA_FEATURE_ENERGY: "sensor.energy"},
    }
    if energy_state is not None:
        hass.states.async_set("sensor.energy", energy_state)

    bridge = HaEntityBridge(hass, [em_device], AsyncMock(), PLUGIN_ID)
    status = bridge.build_status_devices()
    assert len(status) == 1
    maint = next(f for f in status[0]["features"] if f["type"] == "maintenance")
    assert maint == {"type": "maintenance", "unreach": expected_unreach}


@pytest.mark.parametrize(
    ("device", "expected_type", "expected_feature"),
    [
        (
            {
                "id": "d1",
                "name": "Water",
                "features": {HA_FEATURE_MOISTURE_DETECTED: "binary_sensor.m"},
            },
            "WATER_SENSOR",
            "waterlevelDetected",
        ),
        (
            {
                "id": "d2",
                "name": "Car",
                "features": {HA_FEATURE_VEHICLE_RANGE: "sensor.r"},
            },
            "VEHICLE",
            "batteryState",
        ),
        (
            {
                "id": "d3",
                "name": "Bat",
                "features": {HA_FEATURE_LOW_BAT: "binary_sensor.b"},
            },
            "SWITCH",
            "switchState",
        ),
        (
            {
                "id": "d4",
                "name": "Room",
                "type": HA_DEVICE_TYPE_THERMOSTAT,
                "features": {HA_FEATURE_TEMPERATURE: "sensor.t"},
            },
            "THERMOSTAT",
            "setPointTemperature",
        ),
    ],
)
def test_other_incomplete_devices_skipped_with_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device: dict[str, Any],
    expected_type: str,
    expected_feature: str,
) -> None:
    """Any device lacking a required feature is skipped with a warning."""
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)
    with caplog.at_level(logging.WARNING, logger=_BRIDGE_LOGGER):
        discovered = bridge.build_discover_devices()

    assert discovered == []
    warnings = [
        r
        for r in caplog.records
        if r.name == _BRIDGE_LOGGER and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    assert warnings[0].getMessage() == (
        f"Not offering device ha.{device['id']} ({device['name']}) to the HCU: "
        f"type {expected_type} requires the feature {expected_feature}. Edit the "
        "device in the integration options and select the missing entity"
    )


@pytest.mark.parametrize(
    "device",
    [
        {
            "id": "l1",
            "name": "Motion",
            "features": {HA_FEATURE_MOTION: "binary_sensor.m"},
        },
        {"id": "l2", "name": "Door", "features": {HA_FEATURE_DOOR: "binary_sensor.d"}},
        {
            "id": "l3",
            "name": "Window",
            "features": {HA_FEATURE_WINDOW: "binary_sensor.w"},
        },
        {
            "id": "l4",
            "name": "Occ",
            "type": HA_DEVICE_TYPE_OCCUPANCY_SENSOR,
            "features": {HA_FEATURE_MOTION: "binary_sensor.m"},
        },
        {
            "id": "l5",
            "name": "Cont",
            "type": HA_DEVICE_TYPE_CONTACT_SENSOR,
            "features": {HA_FEATURE_WINDOW: "binary_sensor.w"},
        },
        {
            "id": "l6",
            "name": "Input",
            "type": HA_DEVICE_TYPE_SWITCH_INPUT,
            "features": {HA_FEATURE_LOW_BAT: "binary_sensor.b"},
        },
        {
            "id": "l7",
            "name": "Clim",
            "type": HA_DEVICE_TYPE_CLIMATE_SENSOR,
            "features": {HA_FEATURE_HUMIDITY: "sensor.h"},
        },
        {"id": "l8", "name": "Power", "features": {HA_FEATURE_POWER: "sensor.p"}},
    ],
)
def test_complete_and_legacy_devices_discovered_without_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    device: dict[str, Any],
) -> None:
    """Legacy equivalent keys and types without required features discover cleanly."""
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)
    with caplog.at_level(logging.WARNING, logger=_BRIDGE_LOGGER):
        discovered = bridge.build_discover_devices()

    assert [d["deviceId"] for d in discovered] == [f"ha.{device['id']}"]
    warnings = [
        r
        for r in caplog.records
        if r.name == _BRIDGE_LOGGER and r.levelno == logging.WARNING
    ]
    assert warnings == []


# ---------------------------------------------------------------------------
# 12. Options flow for ENERGY_METER
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("with_type", [True, False])
async def test_options_flow_edit_energy_only_meter(
    hass: HomeAssistant,
    options_flow_env: MagicMock,
    with_type: bool,
) -> None:
    """Editing an energy-only meter requires power, prefills energy, and saves cleanly."""
    meter_cfg: dict[str, Any] = {
        "id": "em1",
        "name": "Meter",
        "features": {HA_FEATURE_ENERGY: "sensor.energy"},
    }
    if with_type:
        meter_cfg["type"] = HA_DEVICE_TYPE_ENERGY_METER

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_HA_DEVICES: [meter_cfg]},
        unique_id="hcu-em-edit",
    )
    entry.add_to_hass(hass)

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices_edit"}
    )
    res_form = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"device_id": "em1"}
    )
    assert res_form["type"] is FlowResultType.FORM
    assert res_form["step_id"] == "ha_devices_edit"

    schema_keys = list(res_form["data_schema"].schema.keys())
    assert [k.schema for k in schema_keys] == [
        "name",
        "power",
        "energy",
        "low_bat",
        "sabotage",
        "unreach",
    ]
    power_marker = schema_keys[1]
    energy_marker = schema_keys[2]
    assert isinstance(power_marker, vol.Required)
    assert power_marker.default is vol.UNDEFINED
    assert isinstance(energy_marker, vol.Optional)
    assert energy_marker.description == {"suggested_value": "sensor.energy"}

    with pytest.raises(InvalidData) as exc_info:
        await hass.config_entries.options.async_configure(
            res_init["flow_id"],
            user_input={"name": "Meter", "energy": "sensor.energy"},
        )
    assert exc_info.value.schema_errors == {"power": "required key not provided"}
    assert entry.options == {CONF_HA_DEVICES: [meter_cfg]}

    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"],
        user_input={
            "name": "Meter",
            "power": "sensor.power",
            "energy": "sensor.energy",
        },
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    assert res_saved["data"][CONF_HA_DEVICES] == [
        {
            "id": "em1",
            "name": "Meter",
            "type": HA_DEVICE_TYPE_ENERGY_METER,
            "features": {
                HA_FEATURE_POWER: "sensor.power",
                HA_FEATURE_ENERGY: "sensor.energy",
            },
        }
    ]


async def test_options_flow_add_energy_meter(
    hass: HomeAssistant,
    options_flow_env: MagicMock,
) -> None:
    """Adding an ENERGY_METER requires power and saves with type ENERGY_METER."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_HA_DEVICES: []},
        unique_id="hcu-em-add",
    )
    entry.add_to_hass(hass)

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices_add"}
    )
    res_form = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"device_type": HA_DEVICE_TYPE_ENERGY_METER}
    )
    assert res_form["type"] is FlowResultType.FORM
    assert res_form["step_id"] == "ha_devices_add"

    schema_keys = list(res_form["data_schema"].schema.keys())
    assert [k.schema for k in schema_keys] == [
        "name",
        "power",
        "energy",
        "low_bat",
        "sabotage",
        "unreach",
    ]
    assert isinstance(schema_keys[1], vol.Required)
    assert schema_keys[1].default is vol.UNDEFINED
    assert isinstance(schema_keys[2], vol.Optional)

    with pytest.raises(InvalidData) as exc_info:
        await hass.config_entries.options.async_configure(
            res_init["flow_id"],
            user_input={"name": "Meter"},
        )
    assert exc_info.value.schema_errors == {"power": "required key not provided"}

    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"],
        user_input={"name": "Meter", "power": "sensor.power"},
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved) == 1
    assert saved[0]["name"] == "Meter"
    assert saved[0]["type"] == HA_DEVICE_TYPE_ENERGY_METER
    assert saved[0]["features"] == {HA_FEATURE_POWER: "sensor.power"}


# ---------------------------------------------------------------------------
# 13. Native light hue modulo 360
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("hue", "expected_sent"),
    [
        (360.0, 0),
        (359.9, 359),
        (0.0, 0),
        (180.0, 180),
        (359.0, 359),
        (360, 0),
        (720.0, 0),
        (361.5, 1),
    ],
)
async def test_native_light_hue_modulo_360(
    hass: HomeAssistant, hue: float | int, expected_sent: int
) -> None:
    """HcuLight normalizes hs_color hue modulo 360 as an integer."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}
    coordinator.data = {}

    client = MagicMock()
    client.is_connected = True
    client.async_set_hue_saturation = AsyncMock()

    dev_hs = {
        "id": "dev_hs",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "hue": 0,
                "saturationLevel": 1.0,
                "dimLevel": 0.5,
            }
        },
    }
    client.get_device_by_address.return_value = dev_hs

    light = HcuLight(coordinator, client, dev_hs, "1")
    light.hass = hass

    await light.async_turn_on(**{ATTR_HS_COLOR: (hue, 60.0), ATTR_BRIGHTNESS: 255})
    client.async_set_hue_saturation.assert_called_once_with(
        "dev_hs", 1, expected_sent, 0.6, 1.0, None
    )
    sent_hue = client.async_set_hue_saturation.call_args[0][2]
    assert type(sent_hue) is int


# ---------------------------------------------------------------------------
# 14. End-to-end whole messages and strict JSON
# ---------------------------------------------------------------------------


async def test_whole_messages_discover_and_status_event_for_light(
    hass: HomeAssistant, api_client: HcuApiClient
) -> None:
    """Verify full DISCOVER_RESPONSE and STATUS_EVENT payloads for a light."""
    ws = _setup_websocket(api_client)
    bridge = HaEntityBridge(hass, [_LIGHT], api_client._send_message, PLUGIN_ID)
    api_client.set_ha_entity_bridge(bridge)

    hass.states.async_set(
        "light.desk",
        STATE_OFF,
        {
            ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
            ATTR_MAX_COLOR_TEMP_KELVIN: 6535,
            ATTR_COLOR_TEMP_KELVIN: None,
            ATTR_BRIGHTNESS: None,
            "rgb_color": None,
        },
    )

    await api_client._send_discover_response("disc-1")
    assert ws.send_json.call_count == 1
    assert ws.send_json.call_args[0][0] == {
        "id": "disc-1",
        "pluginId": PLUGIN_ID,
        "type": "DISCOVER_RESPONSE",
        "body": {
            "success": True,
            "devices": [
                {
                    "deviceId": "ha.lt1",
                    "friendlyName": "Desk Lamp",
                    "modelType": HA_MODEL_TYPE,
                    "firmwareVersion": HA_FIRMWARE_VERSION,
                    "deviceType": HA_DEVICE_TYPE_LIGHT,
                    "features": [
                        {"type": "switchState", "on": False},
                        {"type": "dimming"},
                        {
                            "type": "colorTemperature",
                            "minimalColorTemperature": 2000,
                            "maximumColorTemperature": 6535,
                        },
                        {"type": "color"},
                        {"type": "maintenance", "unreach": False},
                    ],
                }
            ],
        },
    }

    ws.send_json.reset_mock()
    hass.states.async_set(
        "light.desk",
        STATE_ON,
        {
            ATTR_MIN_COLOR_TEMP_KELVIN: 2000,
            ATTR_MAX_COLOR_TEMP_KELVIN: 6535,
            ATTR_COLOR_TEMP_KELVIN: 7000,
            ATTR_BRIGHTNESS: 255,
            "rgb_color": (255, 0, 1),
        },
    )

    await bridge.send_status_event()
    assert ws.send_json.call_count == 1
    msg = ws.send_json.call_args[0][0]
    assert msg["pluginId"] == PLUGIN_ID
    assert msg["type"] == "STATUS_EVENT"
    assert isinstance(msg["id"], str) and msg["id"]
    assert msg["body"] == {
        "deviceId": "ha.lt1",
        "features": [
            {"type": "switchState", "on": True},
            {"type": "dimming", "dimLevel": 1.0},
            {
                "type": "colorTemperature",
                "colorTemperature": 6535,
                "minimalColorTemperature": 2000,
                "maximumColorTemperature": 6535,
            },
            {"type": "color", "hue": 0, "saturationLevel": 1.0},
            {"type": "maintenance", "unreach": False},
        ],
    }


def test_strict_json_never_emits_nan_across_all_feature_keys(
    hass: HomeAssistant,
) -> None:
    """All numeric and attribute nan/inf values are excluded so strict JSON succeeds."""
    all_keys: list[str] = []
    for spec in HA_DEVICE_TYPE_FEATURES.values():
        for key in spec["required"] + spec["optional"]:
            if key not in all_keys:
                all_keys.append(key)

    features_conf: dict[str, str] = {}
    bad_attrs = {
        ATTR_BRIGHTNESS: float("nan"),
        "rgb_color": (float("inf"), 0, 0),
        ATTR_COLOR_TEMP_KELVIN: float("nan"),
        ATTR_MIN_COLOR_TEMP_KELVIN: float("inf"),
        ATTR_MAX_COLOR_TEMP_KELVIN: float("nan"),
    }
    for idx, key in enumerate(all_keys):
        entity_id = f"sensor.all_{idx}"
        features_conf[key] = entity_id
        hass.states.async_set(entity_id, "nan", bad_attrs)

    device = {
        "id": "all1",
        "name": "Everything",
        "type": HA_DEVICE_TYPE_CLIMATE_SENSOR,
        "features": features_conf,
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)
    status_devices = bridge.build_status_devices()

    serialized = json.dumps(status_devices, allow_nan=False)
    assert "NaN" not in serialized
    assert len(status_devices) == 1
    assert status_devices[0]["features"] == [
        {"type": "switchState", "on": False},
        {"type": "storm", "storm": False},
        {"type": "sunshine", "sunshine": False},
        {"type": "raining", "raining": False},
        {"type": "presenceDetected", "presenceDetected": False},
        {"type": "contactSensorState", "triggered": False},
        {"type": "smokeAlarm", "smokeAlarm": False},
        {"type": "waterlevelDetected", "waterlevelDetected": False},
        {"type": "moistureDetected", "moistureDetected": False},
        {"type": "hotWaterBoost", "on": False},
        {"type": "maintenance", "unreach": False},
    ]


def test_heat_pump_and_window_covering_discover_and_status(
    hass: HomeAssistant,
) -> None:
    """Verify normalized enums, converted offsets, and inverted shading in full payloads."""
    heat_pump = {
        "id": "hp1",
        "name": "Heat Pump",
        "type": HA_DEVICE_TYPE_HEAT_PUMP,
        "features": {
            HA_FEATURE_CLIMATE_OPERATION_MODE: "select.hp_mode",
            HA_FEATURE_PRESENCE_MODE: "select.hp_presence",
            HA_FEATURE_HEATING_TEMP_OFFSET: "number.hp_offset",
        },
    }
    blind = {
        "id": "wc1",
        "name": "Blind",
        "type": HA_DEVICE_TYPE_WINDOW_COVERING,
        "features": {
            HA_FEATURE_SHUTTER_LEVEL: "number.blind_shutter",
            HA_FEATURE_SLATS_LEVEL: "number.blind_slats",
            HA_FEATURE_SHUTTER_DIRECTION: "select.blind_dir",
        },
    }

    hass.states.async_set("select.hp_mode", "heat")
    hass.states.async_set("select.hp_presence", "Home")
    hass.states.async_set("number.hp_offset", "9", {ATTR_UNIT_OF_MEASUREMENT: "°F"})
    hass.states.async_set(
        "number.blind_shutter",
        "25",
        {"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"},
    )
    hass.states.async_set("number.blind_slats", "0.4", {"min": 0, "max": 1})
    hass.states.async_set("select.blind_dir", "lighter")

    bridge = HaEntityBridge(hass, [heat_pump, blind], AsyncMock(), PLUGIN_ID)

    discovered = bridge.build_discover_devices()
    assert len(discovered) == 2
    assert discovered[0]["features"] == [
        {"type": "climateOperationMode"},
        {"type": "presenceMode", "presenceMode": "HOME"},
        {"type": "heatingTemperatureOffset", "heatingTemperatureOffset": 5.0},
        {"type": "maintenance", "unreach": False},
    ]
    assert discovered[1]["features"] == [
        {"type": "shutterLevel", "shutterLevel": 0.75},
        {"type": "slatsLevel", "slatsLevel": 0.4},
        {"type": "shutterDirection", "shutterDirection": "LIGHTER"},
        {"type": "maintenance", "unreach": False},
    ]

    status = bridge.build_status_devices()
    assert len(status) == 2
    assert status[0]["features"] == [
        {"type": "presenceMode", "presenceMode": "HOME"},
        {"type": "heatingTemperatureOffset", "heatingTemperatureOffset": 5.0},
        {"type": "maintenance", "unreach": False},
    ]
    assert status[1]["features"] == [
        {"type": "shutterLevel", "shutterLevel": 0.75},
        {"type": "slatsLevel", "slatsLevel": 0.4},
        {"type": "shutterDirection", "shutterDirection": "LIGHTER"},
        {"type": "maintenance", "unreach": False},
    ]
