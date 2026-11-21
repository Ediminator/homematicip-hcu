"""Control and status tests for thermostat, window covering, and heat pump bridge devices."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_CLOSED,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
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
    HA_DEVICE_TYPE_HEAT_PUMP,
    HA_DEVICE_TYPE_THERMOSTAT,
    HA_DEVICE_TYPE_WINDOW_COVERING,
    HA_FEATURE_CLIMATE_OPERATION_MODE,
    HA_FEATURE_CO2,
    HA_FEATURE_COOLING_TEMP_OFFSET,
    HA_FEATURE_DOMAINS,
    HA_FEATURE_HEATING_TEMP_OFFSET,
    HA_FEATURE_HOT_WATER_BOOST,
    HA_FEATURE_HUMIDITY,
    HA_FEATURE_ON_OFF,
    HA_FEATURE_ON_TIME,
    HA_FEATURE_PRESENCE_MODE,
    HA_FEATURE_SET_POINT_TEMP,
    HA_FEATURE_SHUTTER_DIRECTION,
    HA_FEATURE_SHUTTER_LEVEL,
    HA_FEATURE_SLATS_LEVEL,
    HA_FEATURE_SUPPLY_TEMPERATURE,
    HA_FEATURE_TEMPERATURE,
    PLUGIN_ID,
)
from custom_components.hcu_integration.ha_entity_bridge import (
    _CONTROLLABLE_DEVICE_TYPES,
    HaEntityBridge,
    _feature_value,
    _level_to_position,
    _position_to_level,
)

_ABSENT = object()

_TH: dict[str, Any] = {
    "id": "th1",
    "name": "Living Room",
    "type": HA_DEVICE_TYPE_THERMOSTAT,
    "features": {
        HA_FEATURE_SET_POINT_TEMP: "climate.room",
        HA_FEATURE_TEMPERATURE: "climate.room",
        HA_FEATURE_HUMIDITY: "climate.room",
    },
}

_TH2: dict[str, Any] = {
    "id": "th2",
    "name": "Office",
    "type": HA_DEVICE_TYPE_THERMOSTAT,
    "features": {
        HA_FEATURE_SET_POINT_TEMP: "number.office_target",
    },
}

_WC: dict[str, Any] = {
    "id": "wc1",
    "name": "Blind",
    "type": HA_DEVICE_TYPE_WINDOW_COVERING,
    "features": {
        HA_FEATURE_SHUTTER_LEVEL: "cover.blind",
        HA_FEATURE_SLATS_LEVEL: "cover.blind",
        HA_FEATURE_SHUTTER_DIRECTION: "select.blind_dir",
    },
}

_WC2: dict[str, Any] = {
    "id": "wc2",
    "name": "Roller",
    "type": HA_DEVICE_TYPE_WINDOW_COVERING,
    "features": {
        HA_FEATURE_SHUTTER_LEVEL: "number.roller",
        HA_FEATURE_SLATS_LEVEL: "input_number.roller_slats",
    },
}

_HP: dict[str, Any] = {
    "id": "hp1",
    "name": "Heat Pump",
    "type": HA_DEVICE_TYPE_HEAT_PUMP,
    "features": {
        HA_FEATURE_CLIMATE_OPERATION_MODE: "select.hp_mode",
        HA_FEATURE_PRESENCE_MODE: "input_select.hp_presence",
        HA_FEATURE_COOLING_TEMP_OFFSET: "number.hp_cool",
        HA_FEATURE_HEATING_TEMP_OFFSET: "input_number.hp_heat",
        HA_FEATURE_HOT_WATER_BOOST: "switch.hp_boost",
        HA_FEATURE_SUPPLY_TEMPERATURE: "sensor.hp_supply",
    },
}

_ALL_CONTROL_SERVICES: tuple[tuple[str, str], ...] = (
    ("climate", "set_temperature"),
    ("cover", "set_cover_position"),
    ("cover", "set_cover_tilt_position"),
    ("cover", "open_cover"),
    ("cover", "close_cover"),
    ("cover", "open_cover_tilt"),
    ("cover", "close_cover_tilt"),
    ("number", "set_value"),
    ("input_number", "set_value"),
    ("select", "select_option"),
    ("input_select", "select_option"),
    ("switch", "turn_on"),
    ("switch", "turn_off"),
    ("input_boolean", "turn_on"),
    ("input_boolean", "turn_off"),
)

_BRIDGE_LOGGER = "custom_components.hcu_integration.ha_entity_bridge"


@pytest.fixture
def options_flow_env(mock_async_zeroconf: MagicMock):
    """Set up zeroconf and patch async_setup_entry for options flow tests."""
    with patch(
        "custom_components.hcu_integration.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


def _register_control_mocks(
    hass: HomeAssistant,
    extra: tuple[tuple[str, str], ...] = (),
) -> dict[tuple[str, str], list[ServiceCall]]:
    """Register mock handlers for all bridge control services."""
    services: dict[tuple[str, str], list[ServiceCall]] = {}
    for domain, service in (*_ALL_CONTROL_SERVICES, *extra):
        services[(domain, service)] = async_mock_service(hass, domain, service)
    return services


def _assert_calls(
    services: dict[tuple[str, str], list[ServiceCall]],
    expected: list[tuple[str, str, dict[str, Any]]],
) -> None:
    """Assert exact domain, service, and data for expected calls and none elsewhere."""
    expected_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for domain, service, data in expected:
        expected_by_key.setdefault((domain, service), []).append(data)

    for key, calls in services.items():
        expected_data_list = expected_by_key.get(key, [])
        assert len(calls) == len(expected_data_list), (
            f"Unexpected call count for {key}: {calls!r}"
        )
        for call, expected_data in zip(calls, expected_data_list, strict=True):
            assert call.domain == key[0]
            assert call.service == key[1]
            assert dict(call.data) == expected_data
            for field in ("temperature", "value"):
                if field in expected_data:
                    assert type(call.data[field]) is float
            for field in ("position", "tilt_position"):
                if field in expected_data:
                    assert type(call.data[field]) is int


def _make_bridge(
    hass: HomeAssistant,
    devices: list[dict[str, Any]] | None = None,
) -> HaEntityBridge:
    """Construct a HaEntityBridge with the default test devices."""
    if devices is None:
        devices = [_TH, _TH2, _WC, _WC2, _HP]
    return HaEntityBridge(hass, devices, AsyncMock(), PLUGIN_ID)


def _control_request(
    device_id: str,
    features: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "pluginId": PLUGIN_ID,
        "id": "ctrl-1",
        "type": "CONTROL_REQUEST",
        "body": {"deviceId": device_id, "features": features},
    }


def _setup_websocket(api_client: HcuApiClient) -> AsyncMock:
    ws = AsyncMock()
    ws.closed = False
    api_client._websocket = ws
    return ws


# ---------------------------------------------------------------------------
# 1. Constants and device summary
# ---------------------------------------------------------------------------


def test_feature_domains_and_controllable_types(hass: HomeAssistant) -> None:
    """Verify updated domain lists, unchanged neighbors, and device summary."""
    assert HA_FEATURE_DOMAINS[HA_FEATURE_TEMPERATURE] == ["sensor", "climate"]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_HUMIDITY] == ["sensor", "climate"]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_CLIMATE_OPERATION_MODE] == [
        "select",
        "input_select",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_PRESENCE_MODE] == [
        "select",
        "input_select",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_SET_POINT_TEMP] == [
        "climate",
        "number",
        "input_number",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_SHUTTER_LEVEL] == [
        "cover",
        "number",
        "input_number",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_SLATS_LEVEL] == [
        "cover",
        "number",
        "input_number",
    ]

    assert HA_FEATURE_DOMAINS[HA_FEATURE_CO2] == ["sensor"]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_SUPPLY_TEMPERATURE] == ["sensor"]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_SHUTTER_DIRECTION] == ["sensor", "select"]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_COOLING_TEMP_OFFSET] == [
        "number",
        "input_number",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_HEATING_TEMP_OFFSET] == [
        "number",
        "input_number",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_ON_TIME] == ["number", "input_number"]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_HOT_WATER_BOOST] == [
        "switch",
        "input_boolean",
    ]
    assert HA_FEATURE_DOMAINS[HA_FEATURE_ON_OFF] == ["switch", "light"]

    expected_controllable = {
        "SWITCH",
        "LIGHT",
        "THERMOSTAT",
        "WINDOW_COVERING",
        "HEAT_PUMP",
    }
    assert expected_controllable == _CONTROLLABLE_DEVICE_TYPES

    climate_sensor = {
        "id": "c1",
        "name": "Weather",
        "type": HA_DEVICE_TYPE_CLIMATE_SENSOR,
        "features": {HA_FEATURE_TEMPERATURE: "climate.room"},
    }
    bridge = _make_bridge(hass, [_TH, _WC, _HP, climate_sensor])
    expected_summary = (
        "• **Living Room** — THERMOSTAT (3 feature(s), controllable)\n"
        "• **Blind** — WINDOW_COVERING (3 feature(s), controllable)\n"
        "• **Heat Pump** — HEAT_PUMP (6 feature(s), controllable)\n"
        "• **Weather** — CLIMATE_SENSOR (1 feature(s), status events only)"
    )
    assert bridge.get_device_summary() == expected_summary


# ---------------------------------------------------------------------------
# 2. Climate status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    (
        "feature_key",
        "entity_id",
        "state_val",
        "attrs",
        "unit",
        "expected",
        "py_type",
    ),
    [
        # set_point_temp on climate
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": 21.5},
            None,
            {"type": "setPointTemperature", "setPointTemperature": 21.5},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "off",
            {"temperature": 21},
            None,
            {"type": "setPointTemperature", "setPointTemperature": 21.0},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": "21.5"},
            None,
            {"type": "setPointTemperature", "setPointTemperature": 21.5},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": 70},
            "°F",
            {"type": "setPointTemperature", "setPointTemperature": 21.1111},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": 293.15},
            "K",
            {"type": "setPointTemperature", "setPointTemperature": 20.0},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": 75},
            None,
            {"type": "setPointTemperature", "setPointTemperature": 60.0},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": -80},
            None,
            {"type": "setPointTemperature", "setPointTemperature": -50.0},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": 70, ATTR_UNIT_OF_MEASUREMENT: "°F"},
            None,
            {"type": "setPointTemperature", "setPointTemperature": 60.0},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": None},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": "nan"},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": float("nan")},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": float("inf")},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": True},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": "abc"},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            "heat",
            {"temperature": [21]},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            STATE_UNAVAILABLE,
            {"temperature": 21},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "climate.room",
            STATE_UNKNOWN,
            {"temperature": 21},
            None,
            None,
            None,
        ),
        # temperature on climate
        (
            HA_FEATURE_TEMPERATURE,
            "climate.room",
            "heat",
            {"current_temperature": 20.4},
            None,
            {"type": "actualTemperature", "actualTemperature": 20.4},
            float,
        ),
        (
            HA_FEATURE_TEMPERATURE,
            "climate.room",
            "heat",
            {"current_temperature": 68},
            "°F",
            {"type": "actualTemperature", "actualTemperature": 20.0},
            float,
        ),
        (
            HA_FEATURE_TEMPERATURE,
            "climate.room",
            "heat",
            {"temperature": 21},
            None,
            None,
            None,
        ),
        # humidity on climate
        (
            HA_FEATURE_HUMIDITY,
            "climate.room",
            "heat",
            {"current_humidity": 55.4},
            None,
            {"type": "humidity", "humidity": 55},
            int,
        ),
        (
            HA_FEATURE_HUMIDITY,
            "climate.room",
            "heat",
            {"current_humidity": 55.6},
            "°F",
            {"type": "humidity", "humidity": 56},
            int,
        ),
        (
            HA_FEATURE_HUMIDITY,
            "climate.room",
            "heat",
            {"current_humidity": 104},
            None,
            {"type": "humidity", "humidity": 100},
            int,
        ),
        (
            HA_FEATURE_HUMIDITY,
            "climate.room",
            "heat",
            {"humidity": 50},
            None,
            None,
            None,
        ),
        # other keys on climate
        (
            HA_FEATURE_CO2,
            "climate.room",
            "heat",
            {"co2": 500},
            None,
            None,
            None,
        ),
        (
            HA_FEATURE_SUPPLY_TEMPERATURE,
            "climate.room",
            "heat",
            {"temperature": 30, "current_temperature": 31},
            None,
            None,
            None,
        ),
        # non-climate entities ignore climate attribute extraction and unit arg
        (
            HA_FEATURE_TEMPERATURE,
            "sensor.x",
            "19.5",
            {"current_temperature": 30},
            None,
            {"type": "actualTemperature", "actualTemperature": 19.5},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "number.x",
            "68",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            None,
            {"type": "setPointTemperature", "setPointTemperature": 20.0},
            float,
        ),
        (
            HA_FEATURE_SET_POINT_TEMP,
            "number.x",
            "68",
            {},
            "°F",
            {"type": "setPointTemperature", "setPointTemperature": 60.0},
            float,
        ),
    ],
)
def test_climate_status_feature_values(
    feature_key: str,
    entity_id: str,
    state_val: str,
    attrs: dict[str, Any],
    unit: str | None,
    expected: dict[str, Any] | None,
    py_type: type | None,
) -> None:
    """Climate entities read target temperature, current temperature, and humidity."""
    state = State(entity_id, state_val, attrs)
    result = (
        _feature_value(feature_key, state)
        if unit is None
        else _feature_value(feature_key, state, unit)
    )
    assert result == expected
    if expected is not None and py_type is not None:
        assert result is not None
        value_field = next(k for k in expected if k != "type")
        assert type(result[value_field]) is py_type


def test_climate_status_keyword_temperature_unit() -> None:
    """_feature_value accepts temperature_unit as a keyword argument."""
    state = State("climate.room", "heat", {"temperature": 70})
    result = _feature_value(HA_FEATURE_SET_POINT_TEMP, state, temperature_unit="°F")
    assert result == {"type": "setPointTemperature", "setPointTemperature": 21.1111}
    assert result is not None
    assert type(result["setPointTemperature"]) is float


# ---------------------------------------------------------------------------
# 3. Cover status
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("feature_key", "entity_id", "state_val", "attrs", "expected"),
    [
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 25},
            {"type": "shutterLevel", "shutterLevel": 0.75},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 100},
            {"type": "shutterLevel", "shutterLevel": 0.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 0},
            {"type": "shutterLevel", "shutterLevel": 1.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 130},
            {"type": "shutterLevel", "shutterLevel": 0.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": -20},
            {"type": "shutterLevel", "shutterLevel": 1.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 33.333},
            {"type": "shutterLevel", "shutterLevel": 0.6667},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": "40"},
            {"type": "shutterLevel", "shutterLevel": 0.6},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            "closing",
            {"current_position": 40},
            {"type": "shutterLevel", "shutterLevel": 0.6},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_CLOSED,
            {},
            {"type": "shutterLevel", "shutterLevel": 1.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {},
            {"type": "shutterLevel", "shutterLevel": 0.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_CLOSED,
            {"current_position": None},
            {"type": "shutterLevel", "shutterLevel": 1.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": "abc"},
            {"type": "shutterLevel", "shutterLevel": 0.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_CLOSED,
            {"current_position": float("nan")},
            {"type": "shutterLevel", "shutterLevel": 1.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": True},
            {"type": "shutterLevel", "shutterLevel": 0.0},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            "opening",
            {},
            None,
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            "closing",
            {},
            None,
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            "stopped",
            {},
            None,
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_UNAVAILABLE,
            {"current_position": 40},
            None,
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 25, "max": 1, ATTR_UNIT_OF_MEASUREMENT: "x"},
            {"type": "shutterLevel", "shutterLevel": 0.75},
        ),
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "cover.x",
            "40",
            {},
            None,
        ),
        # slats_level on cover
        (
            HA_FEATURE_SLATS_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_position": 25, "current_tilt_position": 70},
            {"type": "slatsLevel", "slatsLevel": 0.3},
        ),
        (
            HA_FEATURE_SLATS_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_tilt_position": 0},
            {"type": "slatsLevel", "slatsLevel": 1.0},
        ),
        (
            HA_FEATURE_SLATS_LEVEL,
            "cover.blind",
            STATE_CLOSED,
            {"current_tilt_position": 100},
            {"type": "slatsLevel", "slatsLevel": 0.0},
        ),
        (
            HA_FEATURE_SLATS_LEVEL,
            "cover.blind",
            STATE_CLOSED,
            {"current_position": 0},
            None,
        ),
        (
            HA_FEATURE_SLATS_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {},
            None,
        ),
        (
            HA_FEATURE_SLATS_LEVEL,
            "cover.blind",
            STATE_OPEN,
            {"current_tilt_position": "x"},
            None,
        ),
        # non-cover entity keeps reading state.state
        (
            HA_FEATURE_SHUTTER_LEVEL,
            "number.x",
            "0.4",
            {"current_position": 90},
            {"type": "shutterLevel", "shutterLevel": 0.4},
        ),
    ],
)
def test_cover_status_feature_values(
    feature_key: str,
    entity_id: str,
    state_val: str,
    attrs: dict[str, Any],
    expected: dict[str, Any] | None,
) -> None:
    """Cover entities read current_position and current_tilt_position with open/closed fallback."""
    state = State(entity_id, state_val, attrs)
    assert _feature_value(feature_key, state) == expected


# ---------------------------------------------------------------------------
# 4. Level to position conversion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("level", "expected"),
    [
        (0, 100),
        (1, 0),
        (0.5, 50),
        (0.333, 67),
        (0.004, 100),
        (0.996, 0),
        (-1, 100),
        (7, 0),
        (0.125, 88),
        (0.375, 62),
    ],
)
def test_level_to_position_values(level: float, expected: int) -> None:
    """Convert HCU level (0 open, 1 closed) to HA position integer (0 closed, 100 open)."""
    pos = _level_to_position(level)
    assert pos == expected
    assert type(pos) is int


def test_level_to_position_roundtrip_all_percentages() -> None:
    """Every integer percentage 0..100 roundtrips through _position_to_level."""
    for p in range(101):
        roundtrip = _level_to_position(_position_to_level(p))
        assert roundtrip == p
        assert type(roundtrip) is int


# ---------------------------------------------------------------------------
# 5. Device status and discovery with HA unit system
# ---------------------------------------------------------------------------


def test_device_status_with_us_unit_system_and_unreach(hass: HomeAssistant) -> None:
    """Status builder uses hass.config.units for climate and reports unreach when unavailable."""
    hass.config.units = US_CUSTOMARY_SYSTEM
    hass.states.async_set(
        "climate.room",
        "heat",
        {
            "temperature": 70,
            "current_temperature": 68,
            "current_humidity": 41.6,
            "min_temp": 45,
            "max_temp": 95,
        },
    )
    hass.states.async_set(
        "cover.blind",
        STATE_OPEN,
        {
            "current_position": 25,
            "current_tilt_position": 70,
            "supported_features": 255,
        },
    )
    hass.states.async_set("select.blind_dir", "lighter")

    bridge = _make_bridge(hass, [_TH, _WC])
    status = {d["deviceId"]: d["features"] for d in bridge.build_status_devices()}
    assert status["ha.th1"] == [
        {"type": "setPointTemperature", "setPointTemperature": 21.1111},
        {"type": "actualTemperature", "actualTemperature": 20.0},
        {"type": "humidity", "humidity": 42},
        {"type": "maintenance", "unreach": False},
    ]
    assert status["ha.wc1"] == [
        {"type": "shutterLevel", "shutterLevel": 0.75},
        {"type": "slatsLevel", "slatsLevel": 0.3},
        {"type": "shutterDirection", "shutterDirection": "LIGHTER"},
        {"type": "maintenance", "unreach": False},
    ]

    hass.states.async_set("climate.room", STATE_UNAVAILABLE)
    hass.states.async_set("cover.blind", STATE_UNAVAILABLE)
    status_unavail = {
        d["deviceId"]: d["features"] for d in bridge.build_status_devices()
    }
    assert status_unavail["ha.th1"] == [{"type": "maintenance", "unreach": True}]
    assert status_unavail["ha.wc1"] == [
        {"type": "shutterDirection", "shutterDirection": "LIGHTER"},
        {"type": "maintenance", "unreach": True},
    ]


def test_device_discovery_metric_with_climate_and_cover(hass: HomeAssistant) -> None:
    """Discovery merges current values for known features and descriptors for missing ones."""
    hass.states.async_set(
        "climate.room",
        "heat",
        {
            "temperature": 21,
            "current_temperature": 20.4,
            "current_humidity": 41.6,
        },
    )
    hass.states.async_set(
        "cover.blind",
        STATE_CLOSED,
        {"supported_features": 3},
    )

    bridge = _make_bridge(hass, [_TH, _WC])
    discovered = {d["deviceId"]: d["features"] for d in bridge.build_discover_devices()}
    assert discovered["ha.th1"] == [
        {"type": "setPointTemperature", "setPointTemperature": 21.0},
        {"type": "actualTemperature", "actualTemperature": 20.4},
        {"type": "humidity", "humidity": 42},
        {"type": "maintenance", "unreach": False},
    ]
    assert discovered["ha.wc1"] == [
        {"type": "shutterLevel", "shutterLevel": 1.0},
        {"type": "slatsLevel"},
        {"type": "shutterDirection"},
        {"type": "maintenance", "unreach": False},
    ]


async def test_listener_attribute_only_change_sends_status_event(
    hass: HomeAssistant,
) -> None:
    """Attribute-only updates on climate and cover entities emit STATUS_EVENT."""
    send = AsyncMock()
    hass.states.async_set(
        "climate.room", "heat", {"temperature": 21, "current_temperature": 20}
    )
    hass.states.async_set("cover.blind", STATE_OPEN, {"current_position": 100})
    bridge = HaEntityBridge(hass, [_TH, _WC], send, PLUGIN_ID)
    bridge.build_discover_devices()
    bridge.start_listening()
    try:
        await hass.async_block_till_done()
        send.reset_mock()

        hass.states.async_set(
            "climate.room", "heat", {"temperature": 22.5, "current_temperature": 20}
        )
        await hass.async_block_till_done()
        assert [c.args[0]["type"] for c in send.call_args_list] == ["STATUS_EVENT"]
        assert send.call_args_list[0].args[0]["body"] == {
            "deviceId": "ha.th1",
            "features": [
                {"type": "setPointTemperature", "setPointTemperature": 22.5},
                {"type": "actualTemperature", "actualTemperature": 20.0},
                {"type": "maintenance", "unreach": False},
            ],
        }
        send.reset_mock()

        hass.states.async_set("cover.blind", STATE_OPEN, {"current_position": 40})
        await hass.async_block_till_done()
        assert [c.args[0]["type"] for c in send.call_args_list] == ["STATUS_EVENT"]
        assert send.call_args_list[0].args[0]["body"] == {
            "deviceId": "ha.wc1",
            "features": [
                {"type": "shutterLevel", "shutterLevel": 0.6},
                {"type": "maintenance", "unreach": False},
            ],
        }
    finally:
        bridge.stop_listening()


# ---------------------------------------------------------------------------
# 6. Set point temperature control (climate, number, input_number)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("use_us_units", "state_attrs", "raw_target", "expected_temp"),
    [
        # No state (state_attrs is None)
        (False, None, 21.5, 21.5),
        (False, None, 21, 21.0),
        (False, None, "21.5", 21.5),
        (False, None, 75, 60.0),
        (False, None, -80, -50.0),
        (False, None, None, None),
        # With min_temp / max_temp
        (False, {"min_temp": 5, "max_temp": 30}, 21.5, 21.5),
        (False, {"min_temp": 5, "max_temp": 30}, 35, 30.0),
        (False, {"min_temp": 5, "max_temp": 30}, 2, 5.0),
        (False, {"min_temp": 5, "max_temp": 30}, -80, 5.0),
        (False, {"min_temp": 5, "max_temp": 30}, 30, 30.0),
        (False, {"min_temp": 5, "max_temp": 30}, 5, 5.0),
        (False, {"min_temp": 5.12345, "max_temp": 30}, 2, 5.12345),
        # Swapped limits
        (False, {"min_temp": 30, "max_temp": 5}, 35, 30.0),
        (False, {"min_temp": 30, "max_temp": 5}, 2, 5.0),
        (False, {"min_temp": 30, "max_temp": 5}, 20, 20.0),
        # Non-numeric limits ignored
        (False, {"min_temp": "abc", "max_temp": float("nan")}, 35, 35.0),
        # One-sided limits
        (False, {"min_temp": 7}, 2, 7.0),
        (False, {"min_temp": 7}, 35, 35.0),
        (False, {"max_temp": 28}, 35, 28.0),
        (False, {"max_temp": 28}, 2, 2.0),
        # unit_of_measurement attribute ignored on climate
        (False, {ATTR_UNIT_OF_MEASUREMENT: "°F"}, 21.5, 21.5),
        # US customary unit system
        (True, {"min_temp": 45, "max_temp": 95}, 21.5, 70.7),
        (True, {"min_temp": 45, "max_temp": 95}, 20, 68.0),
        (True, {"min_temp": 45, "max_temp": 95}, 60, 95.0),
        (True, {"min_temp": 45, "max_temp": 95}, -50, 45.0),
        (True, {"min_temp": 45, "max_temp": 95}, 7.3, 45.14),
        (True, {"min_temp": 45, "max_temp": 95}, 21.123456, 70.0222),
        (True, {}, 21.5, 70.7),
    ],
)
async def test_control_set_point_climate(
    hass: HomeAssistant,
    use_us_units: bool,
    state_attrs: dict[str, Any] | None,
    raw_target: Any,
    expected_temp: float | None,
) -> None:
    """Apply setPointTemperature to a climate entity using HA unit system and limits."""
    if use_us_units:
        hass.config.units = US_CUSTOMARY_SYSTEM
    if state_attrs is not None:
        hass.states.async_set("climate.room", "heat", state_attrs)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_TH])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.th1",
            "features": [
                {"type": "setPointTemperature", "setPointTemperature": raw_target}
            ],
        }
    )
    assert err is None
    if expected_temp is None:
        _assert_calls(services, [])
    else:
        _assert_calls(
            services,
            [
                (
                    "climate",
                    "set_temperature",
                    {"entity_id": "climate.room", "temperature": expected_temp},
                )
            ],
        )


async def test_control_set_point_climate_missing_field_is_noop(
    hass: HomeAssistant,
) -> None:
    """setPointTemperature without a value field does nothing and returns None."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_TH])

    err = await bridge.handle_control_request(
        {"deviceId": "ha.th1", "features": [{"type": "setPointTemperature"}]}
    )
    assert err is None
    _assert_calls(services, [])


@pytest.mark.parametrize(
    "bad_value",
    [float("nan"), float("inf"), "abc", True, [21], {}],
)
async def test_control_set_point_climate_invalid_values(
    hass: HomeAssistant,
    bad_value: Any,
) -> None:
    """Invalid setPointTemperature values fail with CONTROL_REQUEST_FAILED and no call."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_TH])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.th1",
            "features": [
                {"type": "setPointTemperature", "setPointTemperature": bad_value}
            ],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": f"Setting setPointTemperature of climate.room failed: invalid value {bad_value!r}",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    ("use_us_units", "state_attrs", "raw_target", "expected_val"),
    [
        (False, None, 21.5, 21.5),
        (
            False,
            {"min": 5, "max": 30, ATTR_UNIT_OF_MEASUREMENT: "°C"},
            21.5,
            21.5,
        ),
        (
            False,
            {"min": 5, "max": 30, ATTR_UNIT_OF_MEASUREMENT: "°C"},
            35,
            30.0,
        ),
        (
            False,
            {"min": 5, "max": 30, ATTR_UNIT_OF_MEASUREMENT: "°C"},
            2,
            5.0,
        ),
        (
            False,
            {"min": 41, "max": 86, ATTR_UNIT_OF_MEASUREMENT: "°F"},
            21.5,
            70.7,
        ),
        (
            False,
            {"min": 41, "max": 86, ATTR_UNIT_OF_MEASUREMENT: "°F"},
            35,
            86.0,
        ),
        (
            False,
            {"min": 41, "max": 86, ATTR_UNIT_OF_MEASUREMENT: "°F"},
            2,
            41.0,
        ),
        (False, {ATTR_UNIT_OF_MEASUREMENT: "K"}, 21.5, 294.65),
        (False, {ATTR_UNIT_OF_MEASUREMENT: "bananas"}, 21.5, 21.5),
        (False, {ATTR_UNIT_OF_MEASUREMENT: ["°F"]}, 21.5, 21.5),
        (False, {ATTR_UNIT_OF_MEASUREMENT: None}, 21.5, 21.5),
        (False, {"min": "5", "max": "30"}, 35, 30.0),
        (True, {"min": 5, "max": 30}, 21.5, 21.5),
    ],
)
async def test_control_set_point_number(
    hass: HomeAssistant,
    use_us_units: bool,
    state_attrs: dict[str, Any] | None,
    raw_target: Any,
    expected_val: float,
) -> None:
    """Apply setPointTemperature to a number entity using unit_of_measurement and min/max."""
    if use_us_units:
        hass.config.units = US_CUSTOMARY_SYSTEM
    if state_attrs is not None:
        hass.states.async_set("number.office_target", "20", state_attrs)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_TH2])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.th2",
            "features": [
                {"type": "setPointTemperature", "setPointTemperature": raw_target}
            ],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [
            (
                "number",
                "set_value",
                {"entity_id": "number.office_target", "value": expected_val},
            )
        ],
    )


async def test_control_set_point_input_number(hass: HomeAssistant) -> None:
    """Apply setPointTemperature to an input_number entity."""
    hass.states.async_set("input_number.target", "20", {"min": 5, "max": 30})
    services = _register_control_mocks(hass)
    bridge = _make_bridge(
        hass,
        [
            {
                "id": "th3",
                "name": "Hall",
                "type": HA_DEVICE_TYPE_THERMOSTAT,
                "features": {HA_FEATURE_SET_POINT_TEMP: "input_number.target"},
            }
        ],
    )

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.th3",
            "features": [{"type": "setPointTemperature", "setPointTemperature": 21.5}],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [
            (
                "input_number",
                "set_value",
                {"entity_id": "input_number.target", "value": 21.5},
            )
        ],
    )


# ---------------------------------------------------------------------------
# 7. Cooling and heating temperature offsets
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("feature_type", "entity_id", "domain", "state_attrs", "raw_val", "expected_val"),
    [
        ("coolingTemperatureOffset", "number.hp_cool", "number", None, 2.5, 2.5),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            2.5,
            4.5,
        ),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            55,
            90.0,
        ),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            -55,
            -90.0,
        ),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            0.123456,
            0.2222,
        ),
        ("coolingTemperatureOffset", "number.hp_cool", "number", {}, 55, 50.0),
        ("coolingTemperatureOffset", "number.hp_cool", "number", {}, -55, -50.0),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {ATTR_UNIT_OF_MEASUREMENT: "K"},
            2.5,
            2.5,
        ),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {"min": -5, "max": 5},
            7,
            5.0,
        ),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {"min": -5, "max": 5},
            -7,
            -5.0,
        ),
        (
            "coolingTemperatureOffset",
            "number.hp_cool",
            "number",
            {"min": -9, "max": 9, ATTR_UNIT_OF_MEASUREMENT: "°F"},
            7,
            9.0,
        ),
        (
            "heatingTemperatureOffset",
            "input_number.hp_heat",
            "input_number",
            None,
            -1.5,
            -1.5,
        ),
        (
            "heatingTemperatureOffset",
            "input_number.hp_heat",
            "input_number",
            None,
            "1.5",
            1.5,
        ),
        (
            "heatingTemperatureOffset",
            "input_number.hp_heat",
            "input_number",
            None,
            None,
            None,
        ),
        (
            "heatingTemperatureOffset",
            "input_number.hp_heat",
            "input_number",
            {ATTR_UNIT_OF_MEASUREMENT: "°F"},
            1.5,
            2.7,
        ),
    ],
)
async def test_control_temperature_offsets(
    hass: HomeAssistant,
    feature_type: str,
    entity_id: str,
    domain: str,
    state_attrs: dict[str, Any] | None,
    raw_val: Any,
    expected_val: float | None,
) -> None:
    """Apply coolingTemperatureOffset and heatingTemperatureOffset using delta conversion."""
    if state_attrs is not None:
        hass.states.async_set(entity_id, "0", state_attrs)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": feature_type, feature_type: raw_val}],
        }
    )
    assert err is None
    if expected_val is None:
        _assert_calls(services, [])
    else:
        _assert_calls(
            services,
            [(domain, "set_value", {"entity_id": entity_id, "value": expected_val})],
        )


@pytest.mark.parametrize(
    ("feature_type", "entity_id", "bad_val"),
    [
        ("coolingTemperatureOffset", "number.hp_cool", True),
        ("heatingTemperatureOffset", "input_number.hp_heat", float("nan")),
    ],
)
async def test_control_temperature_offsets_invalid(
    hass: HomeAssistant,
    feature_type: str,
    entity_id: str,
    bad_val: Any,
) -> None:
    """Invalid offset values fail with CONTROL_REQUEST_FAILED and no call."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": feature_type, feature_type: bad_val}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": f"Setting {feature_type} of {entity_id} failed: invalid value {bad_val!r}",
    }
    _assert_calls(services, [])


# ---------------------------------------------------------------------------
# 8. Shutter and slats level control (cover, number, input_number)
# ---------------------------------------------------------------------------

_DEFAULT_COVER_ATTRS: dict[str, Any] = {
    "supported_features": 255,
    "current_position": 40,
    "current_tilt_position": 60,
}


@pytest.mark.parametrize(
    ("feature_type", "raw_level", "expected_service", "expected_data"),
    [
        ("shutterLevel", 0.75, "set_cover_position", {"position": 25}),
        ("shutterLevel", 0, "set_cover_position", {"position": 100}),
        ("shutterLevel", 1, "set_cover_position", {"position": 0}),
        ("shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        ("shutterLevel", 0.333, "set_cover_position", {"position": 67}),
        ("shutterLevel", "0.75", "set_cover_position", {"position": 25}),
        ("shutterLevel", 0.004, "set_cover_position", {"position": 100}),
        ("shutterLevel", 0.996, "set_cover_position", {"position": 0}),
        ("shutterLevel", 1.003, "set_cover_position", {"position": 0}),
        ("shutterLevel", 2, "set_cover_position", {"position": 0}),
        ("shutterLevel", -0.2, "set_cover_position", {"position": 100}),
        ("shutterLevel", 1.0049, "set_cover_position", {"position": 0}),
        ("shutterLevel", 1.0051, "set_cover_position", {"position": 0}),
        ("shutterLevel", 1.0099, "set_cover_position", {"position": 0}),
        ("shutterLevel", 1.0101, "set_cover_position", {"position": 0}),
        ("shutterLevel", 1.01, None, None),
        ("shutterLevel", 1.0100000001, None, None),
        ("shutterLevel", "1.01", None, None),
        ("shutterLevel", 1.005, None, None),
        ("shutterLevel", 1.0050000001, None, None),
        ("shutterLevel", None, None, None),
        ("slatsLevel", 0.3, "set_cover_tilt_position", {"tilt_position": 70}),
        ("slatsLevel", 0, "set_cover_tilt_position", {"tilt_position": 100}),
        ("slatsLevel", 1, "set_cover_tilt_position", {"tilt_position": 0}),
        ("slatsLevel", 0.555, "set_cover_tilt_position", {"tilt_position": 44}),
        ("slatsLevel", 1.01, None, None),
        ("slatsLevel", 1.005, None, None),
    ],
)
async def test_control_cover_levels_with_position_support(
    hass: HomeAssistant,
    feature_type: str,
    raw_level: Any,
    expected_service: str | None,
    expected_data: dict[str, Any] | None,
) -> None:
    """Cover entities with position support invert level and handle special sentinels."""
    hass.states.async_set("cover.blind", STATE_OPEN, _DEFAULT_COVER_ATTRS)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc1",
            "features": [{"type": feature_type, feature_type: raw_level}],
        }
    )
    assert err is None
    if expected_service is None or expected_data is None:
        _assert_calls(services, [])
    else:
        _assert_calls(
            services,
            [
                (
                    "cover",
                    expected_service,
                    {"entity_id": "cover.blind", **expected_data},
                )
            ],
        )


async def test_control_cover_missing_level_field_is_noop(hass: HomeAssistant) -> None:
    """shutterLevel without a value field does nothing and returns None."""
    hass.states.async_set("cover.blind", STATE_OPEN, _DEFAULT_COVER_ATTRS)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC])

    err = await bridge.handle_control_request(
        {"deviceId": "ha.wc1", "features": [{"type": "shutterLevel"}]}
    )
    assert err is None
    _assert_calls(services, [])


@pytest.mark.parametrize(
    (
        "supported_features",
        "feature_type",
        "raw_level",
        "expected_service",
        "expected_data",
    ),
    [
        # sf=3 (open/close only)
        (3, "shutterLevel", 0, "open_cover", {}),
        (3, "shutterLevel", 0.004, "open_cover", {}),
        (3, "shutterLevel", -1, "open_cover", {}),
        (3, "shutterLevel", 1, "close_cover", {}),
        (3, "shutterLevel", 0.996, "close_cover", {}),
        (3, "shutterLevel", 2, "close_cover", {}),
        (3, "shutterLevel", 0.5, "ERROR", None),
        (3, "shutterLevel", 1.01, None, None),
        (3, "shutterLevel", 1.005, None, None),
        (3, "slatsLevel", 0, "open_cover_tilt", {}),
        (3, "slatsLevel", 1, "close_cover_tilt", {}),
        (3, "slatsLevel", 0.5, "ERROR", None),
        # sf=15 (open/close/set_position/stop, no tilt position)
        (15, "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        (15, "slatsLevel", 0, "open_cover_tilt", {}),
        (15, "slatsLevel", 1, "close_cover_tilt", {}),
        (15, "slatsLevel", 0.5, "ERROR", None),
        # sf=4 (SET_POSITION only)
        (4, "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        (4, "slatsLevel", 0.5, "ERROR", None),
        # sf=128 (SET_TILT_POSITION only)
        (128, "slatsLevel", 0.5, "set_cover_tilt_position", {"tilt_position": 50}),
        (128, "shutterLevel", 0.5, "ERROR", None),
        # sf=0
        (0, "shutterLevel", 0.5, "ERROR", None),
        (0, "shutterLevel", 1, "close_cover", {}),
        # Non-integer or missing supported_features falls back to set_cover_position
        (_ABSENT, "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        (None, "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        ("abc", "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        (True, "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        (3.0, "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
        ("3", "shutterLevel", 0.5, "set_cover_position", {"position": 50}),
    ],
)
async def test_control_cover_supported_features_fallback(
    hass: HomeAssistant,
    supported_features: Any,
    feature_type: str,
    raw_level: float,
    expected_service: str | None,
    expected_data: dict[str, Any] | None,
) -> None:
    """Covers without set_position open/close at extremes and fail intermediate positions."""
    attrs: dict[str, Any] = {}
    if supported_features is not _ABSENT:
        attrs["supported_features"] = supported_features
    hass.states.async_set("cover.blind", STATE_OPEN, attrs)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc1",
            "features": [{"type": feature_type, feature_type: raw_level}],
        }
    )
    if expected_service == "ERROR":
        assert err == {
            "code": CONTROL_ERROR_FAILED,
            "message": f"Setting {feature_type} of cover.blind failed: the cover can only be fully opened or closed",
        }
        _assert_calls(services, [])
    else:
        assert err is None
        if expected_service is None or expected_data is None:
            _assert_calls(services, [])
        else:
            _assert_calls(
                services,
                [
                    (
                        "cover",
                        expected_service,
                        {"entity_id": "cover.blind", **expected_data},
                    )
                ],
            )


async def test_control_cover_missing_supported_features_attr_and_no_state(
    hass: HomeAssistant,
) -> None:
    """Cover without supported_features attribute or without state calls set position."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC])

    # No state at all for cover.blind
    err1 = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc1",
            "features": [{"type": "shutterLevel", "shutterLevel": 0.5}],
        }
    )
    err2 = await bridge.handle_control_request(
        {"deviceId": "ha.wc1", "features": [{"type": "slatsLevel", "slatsLevel": 0.5}]}
    )
    assert err1 is None
    assert err2 is None
    _assert_calls(
        services,
        [
            (
                "cover",
                "set_cover_position",
                {"entity_id": "cover.blind", "position": 50},
            ),
            (
                "cover",
                "set_cover_tilt_position",
                {"entity_id": "cover.blind", "tilt_position": 50},
            ),
        ],
    )

    # State present with no supported_features attribute at all
    services2 = _register_control_mocks(hass)
    hass.states.async_set("cover.blind", STATE_OPEN, {})
    err3 = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc1",
            "features": [{"type": "shutterLevel", "shutterLevel": 0.5}],
        }
    )
    assert err3 is None
    _assert_calls(
        services2,
        [("cover", "set_cover_position", {"entity_id": "cover.blind", "position": 50})],
    )


@pytest.mark.parametrize(
    ("feature_type", "bad_val"),
    [
        ("shutterLevel", float("nan")),
        ("shutterLevel", float("inf")),
        ("shutterLevel", "abc"),
        ("shutterLevel", True),
        ("shutterLevel", [0.5]),
        ("slatsLevel", "x"),
    ],
)
async def test_control_cover_invalid_level_values(
    hass: HomeAssistant,
    feature_type: str,
    bad_val: Any,
) -> None:
    """Invalid shutterLevel or slatsLevel values fail with CONTROL_REQUEST_FAILED."""
    hass.states.async_set("cover.blind", STATE_OPEN, _DEFAULT_COVER_ATTRS)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc1",
            "features": [{"type": feature_type, feature_type: bad_val}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": f"Setting {feature_type} of cover.blind failed: invalid value {bad_val!r}",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    ("state_attrs", "raw_level", "expected_val"),
    [
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 0.75, 25.0),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 0, 100.0),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 1, 0.0),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 0.333, 66.7),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 0.123456, 87.6544),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 1.003, 0.0),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, -0.2, 100.0),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 2, 0.0),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 1.01, None),
        ({"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"}, 1.005, None),
        ({"min": 0, "max": 100}, 0.75, 25.0),
        ({ATTR_UNIT_OF_MEASUREMENT: "%"}, 0.75, 25.0),
        ({"min": 0, "max": 255}, 0.6, 40.0),
        ({"min": 0, "max": 1}, 0.75, 0.75),
        ({"min": 0, "max": 1}, 0, 0.0),
        ({"min": 0, "max": 1}, 1, 1.0),
        ({"min": 0, "max": 1}, 0.123456, 0.1235),
        ({"min": 0, "max": 1}, 1.5, 1.0),
        ({"min": 0, "max": 1}, -1, 0.0),
        ({}, 0.75, 0.75),
        (None, 0.75, 0.75),
        ({"min": 10, "max": 90}, 1, 10.0),
        ({"min": 10, "max": 90}, 0, 90.0),
        ({"min": 10, "max": 90}, 0.5, 50.0),
        ({"min": 0.2, "max": 0.8}, 1, 0.8),
        ({"min": 0.2, "max": 0.8}, 0, 0.2),
        ({"min": 0.33333, "max": 0.8}, 0, 0.33333),
        (None, 2, 1.0),
        (None, -0.2, 0.0),
        ({ATTR_UNIT_OF_MEASUREMENT: "%"}, 2, 0.0),
        ({ATTR_UNIT_OF_MEASUREMENT: "%"}, -0.2, 100.0),
    ],
)
async def test_control_number_shutter_level(
    hass: HomeAssistant,
    state_attrs: dict[str, Any] | None,
    raw_level: float,
    expected_val: float | None,
) -> None:
    """Number shutterLevel uses percent inversion when scaled and 0..1 otherwise."""
    if state_attrs is not None:
        hass.states.async_set("number.roller", "0", state_attrs)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC2])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc2",
            "features": [{"type": "shutterLevel", "shutterLevel": raw_level}],
        }
    )
    assert err is None
    if expected_val is None:
        _assert_calls(services, [])
    else:
        _assert_calls(
            services,
            [
                (
                    "number",
                    "set_value",
                    {"entity_id": "number.roller", "value": expected_val},
                )
            ],
        )


async def test_control_input_number_slats_level(hass: HomeAssistant) -> None:
    """input_number slatsLevel handles percent scale, 0..1 scale, and invalid nan."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_WC2])

    hass.states.async_set(
        "input_number.roller_slats",
        "50",
        {"min": 0, "max": 100, ATTR_UNIT_OF_MEASUREMENT: "%"},
    )
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.wc2",
                "features": [{"type": "slatsLevel", "slatsLevel": 0.3}],
            }
        )
        is None
    )
    _assert_calls(
        services,
        [
            (
                "input_number",
                "set_value",
                {"entity_id": "input_number.roller_slats", "value": 70.0},
            )
        ],
    )

    services2 = _register_control_mocks(hass)
    hass.states.async_set("input_number.roller_slats", "0.5", {"min": 0, "max": 1})
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.wc2",
                "features": [{"type": "slatsLevel", "slatsLevel": 0.3}],
            }
        )
        is None
    )
    _assert_calls(
        services2,
        [
            (
                "input_number",
                "set_value",
                {"entity_id": "input_number.roller_slats", "value": 0.3},
            )
        ],
    )

    services3 = _register_control_mocks(hass)
    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.wc2",
            "features": [{"type": "slatsLevel", "slatsLevel": float("nan")}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Setting slatsLevel of input_number.roller_slats failed: invalid value nan",
    }
    _assert_calls(services3, [])


# ---------------------------------------------------------------------------
# 9. Enum controls (climateOperationMode and presenceMode)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("options_attr", "has_state", "expected_option"),
    [
        (["AUTO", "COOLING", "HEATING"], True, "HEATING"),
        (["auto", "cooling", "heating"], True, "heating"),
        (["Auto", " Heating "], True, " Heating "),
        (["heating", "HEATING"], True, "heating"),
        (["HEATING", "heating"], True, "HEATING"),
        ([1, None, "HEATING"], True, "HEATING"),
        (("auto", "heating"), True, "heating"),
        ("AUTO,HEATING", True, "HEATING"),
        (None, True, "HEATING"),
        ({"HEATING": 1}, True, "HEATING"),
        ("MISSING_ATTR", True, "HEATING"),
        (None, False, "HEATING"),
    ],
)
async def test_control_climate_operation_mode_options_matching(
    hass: HomeAssistant,
    options_attr: Any,
    has_state: bool,
    expected_option: str,
) -> None:
    """Enum control preserves exact case/whitespace from entity options or sends uppercase."""
    if has_state:
        attrs: dict[str, Any] = {}
        if options_attr != "MISSING_ATTR":
            attrs["options"] = options_attr
        hass.states.async_set("select.hp_mode", "auto", attrs)
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": "HEATING"}
            ],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [
            (
                "select",
                "select_option",
                {"entity_id": "select.hp_mode", "option": expected_option},
            )
        ],
    )


async def test_control_climate_operation_mode_fallback_sends_upper_case(
    hass: HomeAssistant,
) -> None:
    """When state is absent, enum control sends stripped uppercase option."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": " heating "}
            ],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [
            (
                "select",
                "select_option",
                {"entity_id": "select.hp_mode", "option": "HEATING"},
            )
        ],
    )


@pytest.mark.parametrize("options_attr", [[], ["heat", "cool"]])
async def test_control_climate_operation_mode_missing_option_fails(
    hass: HomeAssistant,
    options_attr: list[str],
) -> None:
    """Missing target option in entity options attribute fails with CONTROL_REQUEST_FAILED."""
    hass.states.async_set("select.hp_mode", "heat", {"options": options_attr})
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": "HEATING"}
            ],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Setting climateOperationMode of select.hp_mode failed: HEATING is not an option of the entity",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    ("raw_val", "expected_option"),
    [
        ("heating", "heating"),
        (" Cooling ", "cooling"),
        ("AUTO", "auto"),
        ("auto\n", "auto"),
    ],
)
async def test_control_climate_operation_mode_normalization(
    hass: HomeAssistant,
    raw_val: str,
    expected_option: str,
) -> None:
    """Incoming enum strings are stripped and uppercased before matching options."""
    hass.states.async_set(
        "select.hp_mode", "auto", {"options": ["auto", "cooling", "heating"]}
    )
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": raw_val}
            ],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [
            (
                "select",
                "select_option",
                {"entity_id": "select.hp_mode", "option": expected_option},
            )
        ],
    )


@pytest.mark.parametrize(
    "bad_val",
    ["HEAT", "AWAY", "", 5, True, ["HEATING"], 1.5],
)
async def test_control_climate_operation_mode_invalid_values(
    hass: HomeAssistant,
    bad_val: Any,
) -> None:
    """Invalid or non-string enum values fail with CONTROL_REQUEST_FAILED."""
    hass.states.async_set(
        "select.hp_mode", "AUTO", {"options": ["AUTO", "COOLING", "HEATING"]}
    )
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": bad_val}
            ],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": f"Setting climateOperationMode of select.hp_mode failed: invalid value {bad_val!r}",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    "feature",
    [
        {"type": "climateOperationMode"},
        {"type": "climateOperationMode", "climateOperationMode": None},
    ],
)
async def test_control_climate_operation_mode_noop(
    hass: HomeAssistant,
    feature: dict[str, Any],
) -> None:
    """Missing or None enum value field does nothing and returns None."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    assert (
        await bridge.handle_control_request(
            {"deviceId": "ha.hp1", "features": [feature]}
        )
        is None
    )
    _assert_calls(services, [])


@pytest.mark.parametrize(
    ("raw_val", "expected_option"),
    [
        ("AWAY", "Away"),
        ("DEFAULT", "Default"),
        ("HOME", "Home"),
        ("NORMAL", "Normal"),
        ("VACATION", "Vacation"),
    ],
)
async def test_control_presence_mode_input_select(
    hass: HomeAssistant,
    raw_val: str,
    expected_option: str,
) -> None:
    """presenceMode calls input_select.select_option with the matched entity option."""
    hass.states.async_set(
        "input_select.hp_presence",
        "Home",
        {"options": ["Home", "Away", "Vacation", "Normal", "Default"]},
    )
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": "presenceMode", "presenceMode": raw_val}],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [
            (
                "input_select",
                "select_option",
                {"entity_id": "input_select.hp_presence", "option": expected_option},
            )
        ],
    )


@pytest.mark.parametrize("bad_val", ["PARTY", "AUTO", "HEATING"])
async def test_control_presence_mode_invalid_values(
    hass: HomeAssistant,
    bad_val: str,
) -> None:
    """Invalid presenceMode values fail with CONTROL_REQUEST_FAILED."""
    hass.states.async_set(
        "input_select.hp_presence",
        "Home",
        {"options": ["Home", "Away", "Vacation", "Normal", "Default"]},
    )
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": "presenceMode", "presenceMode": bad_val}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": f"Setting presenceMode of input_select.hp_presence failed: invalid value {bad_val!r}",
    }
    _assert_calls(services, [])


async def test_control_presence_mode_missing_option_fails(hass: HomeAssistant) -> None:
    """Valid presenceMode absent from entity options fails with CONTROL_REQUEST_FAILED."""
    hass.states.async_set(
        "input_select.hp_presence", "Home", {"options": ["Home", "Away"]}
    )
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": "presenceMode", "presenceMode": "VACATION"}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Setting presenceMode of input_select.hp_presence failed: VACATION is not an option of the entity",
    }
    _assert_calls(services, [])


# ---------------------------------------------------------------------------
# 10. Hot water boost control
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("on_val", "expected_service"),
    [
        (True, "turn_on"),
        (False, "turn_off"),
    ],
)
async def test_control_hot_water_boost_switch(
    hass: HomeAssistant,
    on_val: bool,
    expected_service: str,
) -> None:
    """hotWaterBoost controls switch entities on strict booleans."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": "hotWaterBoost", "on": on_val}],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [("switch", expected_service, {"entity_id": "switch.hp_boost"})],
    )


@pytest.mark.parametrize(
    "feature",
    [{"type": "hotWaterBoost"}, {"type": "hotWaterBoost", "on": None}],
)
async def test_control_hot_water_boost_noop(
    hass: HomeAssistant,
    feature: dict[str, Any],
) -> None:
    """hotWaterBoost without on or with None does nothing and succeeds."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    assert (
        await bridge.handle_control_request(
            {"deviceId": "ha.hp1", "features": [feature]}
        )
        is None
    )
    _assert_calls(services, [])


@pytest.mark.parametrize(
    "bad_on",
    ["true", "false", 1, 0, "on", [True]],
)
async def test_control_hot_water_boost_rejects_non_bool(
    hass: HomeAssistant,
    bad_on: Any,
) -> None:
    """hotWaterBoost rejects strings, integers, and other non-boolean values."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [{"type": "hotWaterBoost", "on": bad_on}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": f"Setting hotWaterBoost of switch.hp_boost failed: invalid value {bad_on!r}",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    ("on_val", "expected_service"),
    [
        (True, "turn_on"),
        (False, "turn_off"),
    ],
)
async def test_control_hot_water_boost_input_boolean(
    hass: HomeAssistant,
    on_val: bool,
    expected_service: str,
) -> None:
    """hotWaterBoost controls input_boolean entities."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(
        hass,
        [
            {
                "id": "hp2",
                "name": "Boost",
                "type": HA_DEVICE_TYPE_HEAT_PUMP,
                "features": {HA_FEATURE_HOT_WATER_BOOST: "input_boolean.boost"},
            }
        ],
    )

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp2",
            "features": [{"type": "hotWaterBoost", "on": on_val}],
        }
    )
    assert err is None
    _assert_calls(
        services,
        [("input_boolean", expected_service, {"entity_id": "input_boolean.boost"})],
    )


# ---------------------------------------------------------------------------
# 11. Unsupported features, foreign domains, empty entities, malformed types
# ---------------------------------------------------------------------------

_ALL_8_CONTROL_FEATURES: list[dict[str, Any]] = [
    {"type": "setPointTemperature", "setPointTemperature": 21.0},
    {"type": "coolingTemperatureOffset", "coolingTemperatureOffset": 1.0},
    {"type": "heatingTemperatureOffset", "heatingTemperatureOffset": 1.0},
    {"type": "climateOperationMode", "climateOperationMode": "HEATING"},
    {"type": "presenceMode", "presenceMode": "HOME"},
    {"type": "hotWaterBoost", "on": True},
    {"type": "shutterLevel", "shutterLevel": 0.5},
    {"type": "slatsLevel", "slatsLevel": 0.5},
]

_MISSING_VALUE_CONTROL_FEATURES: list[dict[str, Any]] = [
    {"type": "setPointTemperature"},
    {"type": "hotWaterBoost", "on": None},
    {"type": "shutterLevel"},
    {"type": "climateOperationMode", "climateOperationMode": None},
]


@pytest.mark.parametrize(
    "feature", [*_ALL_8_CONTROL_FEATURES, *_MISSING_VALUE_CONTROL_FEATURES]
)
async def test_control_missing_configured_feature_is_unsupported(
    hass: HomeAssistant,
    feature: dict[str, Any],
) -> None:
    """Each control feature returns FEATURE_NOT_SUPPORTED when unconfigured."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(
        hass,
        [
            {
                "id": "hp_min",
                "name": "HP Minimal",
                "type": HA_DEVICE_TYPE_HEAT_PUMP,
                "features": {HA_FEATURE_SUPPLY_TEMPERATURE: "sensor.s"},
            }
        ],
    )

    err = await bridge.handle_control_request(
        {"deviceId": "ha.hp_min", "features": [feature]}
    )
    assert err == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": f"Feature {feature['type']} is not supported by ha.hp_min",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    "feature", [*_ALL_8_CONTROL_FEATURES, *_MISSING_VALUE_CONTROL_FEATURES]
)
async def test_control_foreign_domain_is_unsupported(
    hass: HomeAssistant,
    feature: dict[str, Any],
) -> None:
    """Entities from unsupported domains are rejected before any service call."""
    services = _register_control_mocks(
        hass,
        extra=(
            ("sensor", "set_value"),
            ("sensor", "select_option"),
            ("climate", "set_value"),
            ("climate", "select_option"),
            ("light", "turn_on"),
        ),
    )
    bridge = _make_bridge(
        hass,
        [
            {
                "id": "foreign",
                "name": "Foreign",
                "type": HA_DEVICE_TYPE_HEAT_PUMP,
                "features": {
                    HA_FEATURE_SET_POINT_TEMP: "sensor.t",
                    HA_FEATURE_COOLING_TEMP_OFFSET: "climate.c",
                    HA_FEATURE_HEATING_TEMP_OFFSET: "sensor.h",
                    HA_FEATURE_CLIMATE_OPERATION_MODE: "sensor.mode",
                    HA_FEATURE_PRESENCE_MODE: "climate.c",
                    HA_FEATURE_HOT_WATER_BOOST: "light.l",
                    HA_FEATURE_SHUTTER_LEVEL: "sensor.pos",
                    HA_FEATURE_SLATS_LEVEL: "climate.c",
                },
            }
        ],
    )

    err = await bridge.handle_control_request(
        {"deviceId": "ha.foreign", "features": [feature]}
    )
    assert err == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": f"Feature {feature['type']} is not supported by ha.foreign",
    }
    _assert_calls(services, [])


async def test_control_empty_entity_id_is_unsupported(hass: HomeAssistant) -> None:
    """An empty string entity id returns FEATURE_NOT_SUPPORTED."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(
        hass,
        [
            {
                "id": "hp_empty",
                "name": "HP Empty",
                "type": HA_DEVICE_TYPE_HEAT_PUMP,
                "features": {HA_FEATURE_HOT_WATER_BOOST: ""},
            }
        ],
    )

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp_empty",
            "features": [{"type": "hotWaterBoost", "on": True}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": "Feature hotWaterBoost is not supported by ha.hp_empty",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    "feature_type",
    [
        "actualTemperature",
        "humidity",
        "co2",
        "supplyTemperature",
        "shutterDirection",
        "maintenance",
        "bogus",
        None,
        5,
    ],
)
async def test_control_non_controllable_and_unknown_feature_types(
    hass: HomeAssistant,
    feature_type: Any,
) -> None:
    """Status-only and unknown feature types return FEATURE_NOT_SUPPORTED."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {"deviceId": "ha.hp1", "features": [{"type": feature_type}]}
    )
    assert err == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": f"Feature {feature_type} is not supported by ha.hp1",
    }
    _assert_calls(services, [])


@pytest.mark.parametrize(
    ("feature", "expected_label"),
    [
        ({"type": ["shutterLevel"]}, "['shutterLevel']"),
        ({"type": {"a": 1}}, "{'a': 1}"),
        ({}, "None"),
    ],
)
async def test_control_unhashable_and_missing_feature_type(
    hass: HomeAssistant,
    feature: dict[str, Any],
    expected_label: str,
) -> None:
    """Unhashable or missing feature type returns FEATURE_NOT_SUPPORTED without raising."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {"deviceId": "ha.hp1", "features": [feature]}
    )
    assert err == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": f"Feature {expected_label} is not supported by ha.hp1",
    }
    _assert_calls(services, [])


# ---------------------------------------------------------------------------
# 12. Multiple features, partial failures, service errors, logging
# ---------------------------------------------------------------------------


async def test_control_heat_pump_multiple_features_all_succeed(
    hass: HomeAssistant,
) -> None:
    """All five controllable heat pump features execute in request order."""
    recorded: list[tuple[str, str, dict[str, Any]]] = []

    async def _record(call: ServiceCall) -> None:
        recorded.append((call.domain, call.service, dict(call.data)))
        if "value" in call.data:
            assert type(call.data["value"]) is float

    for domain, service in _ALL_CONTROL_SERVICES:
        hass.services.async_register(domain, service, _record)

    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": "COOLING"},
                {"type": "presenceMode", "presenceMode": "AWAY"},
                {"type": "coolingTemperatureOffset", "coolingTemperatureOffset": 2.5},
                {"type": "heatingTemperatureOffset", "heatingTemperatureOffset": -1},
                {"type": "hotWaterBoost", "on": True},
            ],
        }
    )
    assert err is None
    assert recorded == [
        (
            "select",
            "select_option",
            {"entity_id": "select.hp_mode", "option": "COOLING"},
        ),
        (
            "input_select",
            "select_option",
            {"entity_id": "input_select.hp_presence", "option": "AWAY"},
        ),
        (
            "number",
            "set_value",
            {"entity_id": "number.hp_cool", "value": 2.5},
        ),
        (
            "input_number",
            "set_value",
            {"entity_id": "input_number.hp_heat", "value": -1.0},
        ),
        (
            "switch",
            "turn_on",
            {"entity_id": "switch.hp_boost"},
        ),
    ]


async def test_control_partial_failure_continues_and_joins_messages(
    hass: HomeAssistant,
) -> None:
    """Valid features still apply when other features in the same request fail."""
    services = _register_control_mocks(hass)
    bridge = _make_bridge(hass, [_HP])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp1",
            "features": [
                {"type": "climateOperationMode", "climateOperationMode": "HEAT"},
                {"type": "hotWaterBoost", "on": True},
                {"type": "supplyTemperature", "supplyTemperature": 40},
                {"type": "coolingTemperatureOffset", "coolingTemperatureOffset": "x"},
            ],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": (
            "Setting climateOperationMode of select.hp_mode failed: invalid value 'HEAT'; "
            "Feature supplyTemperature is not supported by ha.hp1; "
            "Setting coolingTemperatureOffset of number.hp_cool failed: invalid value 'x'"
        ),
    }
    _assert_calls(
        services,
        [("switch", "turn_on", {"entity_id": "switch.hp_boost"})],
    )


async def test_control_service_exceptions_log_and_return_errors(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """HomeAssistantError from target services logs one ERROR per failure and joins messages."""

    async def _fail(call: ServiceCall) -> None:
        raise HomeAssistantError("Valve stuck")

    for domain, service in _ALL_CONTROL_SERVICES:
        hass.services.async_register(domain, service, _fail)

    hass.states.async_set("cover.blind", STATE_OPEN, _DEFAULT_COVER_ATTRS)
    bridge = _make_bridge(hass, [_TH, _WC, _HP])

    with caplog.at_level(logging.ERROR, logger=_BRIDGE_LOGGER):
        caplog.clear()
        err_th = await bridge.handle_control_request(
            {
                "deviceId": "ha.th1",
                "features": [
                    {"type": "setPointTemperature", "setPointTemperature": 21}
                ],
            }
        )
        assert err_th == {
            "code": CONTROL_ERROR_FAILED,
            "message": "Setting setPointTemperature of climate.room failed: Valve stuck",
        }
        assert [r.message for r in caplog.records if r.levelno == logging.ERROR] == [
            "Setting setPointTemperature of climate.room failed: Valve stuck"
        ]

        caplog.clear()
        err_wc = await bridge.handle_control_request(
            {
                "deviceId": "ha.wc1",
                "features": [
                    {"type": "shutterLevel", "shutterLevel": 0.5},
                    {"type": "slatsLevel", "slatsLevel": 0.5},
                ],
            }
        )
        assert err_wc == {
            "code": CONTROL_ERROR_FAILED,
            "message": (
                "Setting shutterLevel of cover.blind failed: Valve stuck; "
                "Setting slatsLevel of cover.blind failed: Valve stuck"
            ),
        }
        assert [r.message for r in caplog.records if r.levelno == logging.ERROR] == [
            "Setting shutterLevel of cover.blind failed: Valve stuck",
            "Setting slatsLevel of cover.blind failed: Valve stuck",
        ]

        caplog.clear()
        err_hp = await bridge.handle_control_request(
            {
                "deviceId": "ha.hp1",
                "features": [
                    {"type": "climateOperationMode", "climateOperationMode": "COOLING"},
                    {"type": "presenceMode", "presenceMode": "AWAY"},
                    {
                        "type": "coolingTemperatureOffset",
                        "coolingTemperatureOffset": 2.5,
                    },
                    {
                        "type": "heatingTemperatureOffset",
                        "heatingTemperatureOffset": -1,
                    },
                    {"type": "hotWaterBoost", "on": True},
                ],
            }
        )
        expected_hp_messages = [
            "Setting climateOperationMode of select.hp_mode failed: Valve stuck",
            "Setting presenceMode of input_select.hp_presence failed: Valve stuck",
            "Setting coolingTemperatureOffset of number.hp_cool failed: Valve stuck",
            "Setting heatingTemperatureOffset of input_number.hp_heat failed: Valve stuck",
            "Setting hotWaterBoost of switch.hp_boost failed: Valve stuck",
        ]
        assert err_hp == {
            "code": CONTROL_ERROR_FAILED,
            "message": "; ".join(expected_hp_messages),
        }
        assert [
            r.message for r in caplog.records if r.levelno == logging.ERROR
        ] == expected_hp_messages


async def test_control_unregistered_service_reports_not_found(
    hass: HomeAssistant,
) -> None:
    """Missing target service surfaces ServiceNotFound in CONTROL_REQUEST_FAILED."""
    bridge = _make_bridge(hass, [_TH])

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.th1",
            "features": [{"type": "setPointTemperature", "setPointTemperature": 21}],
        }
    )
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Setting setPointTemperature of climate.room failed: Action climate.set_temperature not found",
    }


# ---------------------------------------------------------------------------
# 13. API client roundtrip (CONTROL_REQUEST -> CONTROL_RESPONSE + STATUS_EVENT)
# ---------------------------------------------------------------------------


async def test_api_client_control_request_roundtrip(
    hass: HomeAssistant,
    api_client: HcuApiClient,
) -> None:
    """API client sends CONTROL_RESPONSE followed by STATUS_EVENT on success."""
    ws = _setup_websocket(api_client)
    hass.states.async_set(
        "climate.room",
        "heat",
        {
            "temperature": 21,
            "current_temperature": 20.4,
            "current_humidity": 41.6,
            "min_temp": 5,
            "max_temp": 30,
        },
    )
    services = _register_control_mocks(hass)
    bridge = HaEntityBridge(hass, [_TH], api_client._send_message, PLUGIN_ID)
    api_client.set_ha_entity_bridge(bridge)
    bridge.build_discover_devices()

    await api_client._handle_control_request(
        _control_request(
            "ha.th1", [{"type": "setPointTemperature", "setPointTemperature": 22.5}]
        )
    )
    _assert_calls(
        services,
        [
            (
                "climate",
                "set_temperature",
                {"entity_id": "climate.room", "temperature": 22.5},
            )
        ],
    )
    sent_ok = [call.args[0] for call in ws.send_json.call_args_list]
    assert [msg["type"] for msg in sent_ok] == ["CONTROL_RESPONSE", "STATUS_EVENT"]
    assert sent_ok[0]["id"] == "ctrl-1"
    assert sent_ok[0]["pluginId"] == PLUGIN_ID
    assert sent_ok[0]["body"] == {"deviceId": "ha.th1", "success": True}
    assert sent_ok[1]["body"] == {
        "deviceId": "ha.th1",
        "features": [
            {"type": "setPointTemperature", "setPointTemperature": 21.0},
            {"type": "actualTemperature", "actualTemperature": 20.4},
            {"type": "humidity", "humidity": 42},
            {"type": "maintenance", "unreach": False},
        ],
    }


async def test_api_client_control_request_failure_roundtrip(
    hass: HomeAssistant,
    api_client: HcuApiClient,
) -> None:
    """API client sends failure CONTROL_RESPONSE followed by STATUS_EVENT."""
    ws = _setup_websocket(api_client)
    hass.states.async_set(
        "climate.room",
        "heat",
        {
            "temperature": 21,
            "current_temperature": 20.4,
            "current_humidity": 41.6,
            "min_temp": 5,
            "max_temp": 30,
        },
    )
    services = _register_control_mocks(hass)
    bridge = HaEntityBridge(hass, [_TH], api_client._send_message, PLUGIN_ID)
    api_client.set_ha_entity_bridge(bridge)
    bridge.build_discover_devices()

    await api_client._handle_control_request(
        _control_request(
            "ha.th1", [{"type": "setPointTemperature", "setPointTemperature": "warm"}]
        )
    )
    _assert_calls(services, [])
    sent_err = [call.args[0] for call in ws.send_json.call_args_list]
    assert [msg["type"] for msg in sent_err] == ["CONTROL_RESPONSE", "STATUS_EVENT"]
    assert sent_err[0]["id"] == "ctrl-1"
    assert sent_err[0]["pluginId"] == PLUGIN_ID
    assert sent_err[0]["body"] == {
        "deviceId": "ha.th1",
        "success": False,
        "error": {
            "code": CONTROL_ERROR_FAILED,
            "message": "Setting setPointTemperature of climate.room failed: invalid value 'warm'",
        },
    }
    assert sent_err[1]["body"] == {
        "deviceId": "ha.th1",
        "features": [
            {"type": "setPointTemperature", "setPointTemperature": 21.0},
            {"type": "actualTemperature", "actualTemperature": 20.4},
            {"type": "humidity", "humidity": 42},
            {"type": "maintenance", "unreach": False},
        ],
    }


# ---------------------------------------------------------------------------
# 14. Options flow selector domains and validation
# ---------------------------------------------------------------------------


async def _open_add_device_form(
    hass: HomeAssistant,
    device_type: str,
    unique_id: str,
) -> tuple[MockConfigEntry, dict[str, Any]]:
    """Navigate the options flow to the ha_devices_add form for device_type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_HA_DEVICES: []},
        unique_id=unique_id,
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
        res_init["flow_id"], user_input={"device_type": device_type}
    )
    assert res_form["type"] is FlowResultType.FORM
    assert res_form["step_id"] == "ha_devices_add"
    return entry, res_form


async def test_options_flow_thermostat_domains_and_validation(
    hass: HomeAssistant,
    options_flow_env: MagicMock,
) -> None:
    """Thermostat form offers climate/number/input_number and validates domains."""
    _entry, res_form = await _open_add_device_form(
        hass, HA_DEVICE_TYPE_THERMOSTAT, "hcu-add-th"
    )
    schema = res_form["data_schema"].schema
    markers = {m.schema: m for m in schema}
    assert list(markers) == [
        "name",
        "set_point_temp",
        "temperature",
        "humidity",
        "co2",
        "low_bat",
        "sabotage",
        "unreach",
    ]
    assert isinstance(markers["set_point_temp"], vol.Required)
    assert schema[markers["set_point_temp"]].config["domain"] == [
        "climate",
        "number",
        "input_number",
    ]
    assert schema[markers["temperature"]].config["domain"] == ["sensor", "climate"]
    assert schema[markers["humidity"]].config["domain"] == ["sensor", "climate"]
    assert schema[markers["co2"]].config["domain"] == ["sensor"]
    for m_key in ("low_bat", "sabotage", "unreach"):
        assert schema[markers[m_key]].config["domain"] == ["binary_sensor"]

    with pytest.raises(InvalidData) as exc_info:
        await hass.config_entries.options.async_configure(
            res_form["flow_id"],
            user_input={"name": "T", "set_point_temp": "sensor.x"},
        )
    assert exc_info.value.schema_errors == {
        "set_point_temp": "Entity sensor.x belongs to domain sensor, expected ['climate', 'number', 'input_number']"
    }

    res_saved = await hass.config_entries.options.async_configure(
        res_form["flow_id"],
        user_input={
            "name": "T",
            "set_point_temp": "climate.room",
            "temperature": "climate.room",
            "humidity": "climate.room",
            "co2": "sensor.co2",
        },
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved) == 1
    assert saved[0]["name"] == "T"
    assert saved[0]["type"] == HA_DEVICE_TYPE_THERMOSTAT
    assert saved[0]["features"] == {
        HA_FEATURE_TEMPERATURE: "climate.room",
        HA_FEATURE_HUMIDITY: "climate.room",
        HA_FEATURE_CO2: "sensor.co2",
        HA_FEATURE_SET_POINT_TEMP: "climate.room",
    }


async def test_options_flow_window_covering_domains_and_validation(
    hass: HomeAssistant,
    options_flow_env: MagicMock,
) -> None:
    """Window covering form offers cover/number/input_number and validates domains."""
    _entry, res_form = await _open_add_device_form(
        hass, HA_DEVICE_TYPE_WINDOW_COVERING, "hcu-add-wc"
    )
    schema = res_form["data_schema"].schema
    markers = {m.schema: m for m in schema}
    assert list(markers) == [
        "name",
        "shutter_level",
        "slats_level",
        "shutter_direction",
        "low_bat",
        "sabotage",
        "unreach",
    ]
    assert isinstance(markers["shutter_level"], vol.Required)
    assert schema[markers["shutter_level"]].config["domain"] == [
        "cover",
        "number",
        "input_number",
    ]
    assert schema[markers["slats_level"]].config["domain"] == [
        "cover",
        "number",
        "input_number",
    ]
    assert schema[markers["shutter_direction"]].config["domain"] == ["sensor", "select"]
    for m_key in ("low_bat", "sabotage", "unreach"):
        assert schema[markers[m_key]].config["domain"] == ["binary_sensor"]

    with pytest.raises(InvalidData) as exc_info:
        await hass.config_entries.options.async_configure(
            res_form["flow_id"],
            user_input={
                "name": "B",
                "shutter_level": "cover.blind",
                "shutter_direction": "cover.blind",
            },
        )
    assert exc_info.value.schema_errors == {
        "shutter_direction": "Entity cover.blind belongs to domain cover, expected ['sensor', 'select']"
    }

    res_saved = await hass.config_entries.options.async_configure(
        res_form["flow_id"],
        user_input={
            "name": "B",
            "shutter_level": "cover.blind",
            "slats_level": "cover.blind",
            "shutter_direction": "select.dir",
        },
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved) == 1
    assert saved[0]["name"] == "B"
    assert saved[0]["type"] == HA_DEVICE_TYPE_WINDOW_COVERING
    assert saved[0]["features"] == {
        HA_FEATURE_SHUTTER_LEVEL: "cover.blind",
        HA_FEATURE_SLATS_LEVEL: "cover.blind",
        HA_FEATURE_SHUTTER_DIRECTION: "select.dir",
    }


async def test_options_flow_heat_pump_domains_and_validation(
    hass: HomeAssistant,
    options_flow_env: MagicMock,
) -> None:
    """Heat pump form offers select and input_select and validates domains."""
    _entry, res_form = await _open_add_device_form(
        hass, HA_DEVICE_TYPE_HEAT_PUMP, "hcu-add-hp"
    )
    schema = res_form["data_schema"].schema
    markers = {m.schema: m for m in schema}
    assert list(markers) == [
        "name",
        "climate_operation_mode",
        "cooling_temp_offset",
        "heating_temp_offset",
        "presence_mode",
        "hot_water_boost",
        "supply_temperature",
        "low_bat",
        "sabotage",
        "unreach",
    ]
    assert isinstance(markers["climate_operation_mode"], vol.Required)
    assert schema[markers["climate_operation_mode"]].config["domain"] == [
        "select",
        "input_select",
    ]
    assert schema[markers["cooling_temp_offset"]].config["domain"] == [
        "number",
        "input_number",
    ]
    assert schema[markers["heating_temp_offset"]].config["domain"] == [
        "number",
        "input_number",
    ]
    assert schema[markers["presence_mode"]].config["domain"] == [
        "select",
        "input_select",
    ]
    assert schema[markers["hot_water_boost"]].config["domain"] == [
        "switch",
        "input_boolean",
    ]
    assert schema[markers["supply_temperature"]].config["domain"] == ["sensor"]
    for m_key in ("low_bat", "sabotage", "unreach"):
        assert schema[markers[m_key]].config["domain"] == ["binary_sensor"]

    with pytest.raises(InvalidData) as exc_info:
        await hass.config_entries.options.async_configure(
            res_form["flow_id"],
            user_input={"name": "H", "climate_operation_mode": "climate.x"},
        )
    assert exc_info.value.schema_errors == {
        "climate_operation_mode": "Entity climate.x belongs to domain climate, expected ['select', 'input_select']"
    }

    res_saved = await hass.config_entries.options.async_configure(
        res_form["flow_id"],
        user_input={
            "name": "H",
            "climate_operation_mode": "input_select.mode",
            "presence_mode": "input_select.presence",
            "hot_water_boost": "input_boolean.boost",
        },
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved) == 1
    assert saved[0]["name"] == "H"
    assert saved[0]["type"] == HA_DEVICE_TYPE_HEAT_PUMP
    assert saved[0]["features"] == {
        HA_FEATURE_CLIMATE_OPERATION_MODE: "input_select.mode",
        HA_FEATURE_PRESENCE_MODE: "input_select.presence",
        HA_FEATURE_HOT_WATER_BOOST: "input_boolean.boost",
    }


# ---------------------------------------------------------------------------
# 15. End-to-end tests against real Home Assistant entities
# ---------------------------------------------------------------------------


async def test_real_ha_helper_entities_control(hass: HomeAssistant) -> None:
    """Control real input_number, input_select, and input_boolean entities."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass,
        "input_number",
        {
            "input_number": {
                "target": {
                    "min": 41,
                    "max": 86,
                    "step": 0.1,
                    "unit_of_measurement": "°F",
                    "initial": 68,
                },
                "roller": {
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "unit_of_measurement": "%",
                    "initial": 100,
                },
                "slats": {
                    "min": 0,
                    "max": 1,
                    "step": 0.01,
                    "initial": 0,
                },
                "heat": {
                    "min": -5,
                    "max": 5,
                    "step": 0.5,
                    "initial": 0,
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        "input_select",
        {
            "input_select": {
                "mode": {
                    "options": ["auto", "cooling", "heating"],
                    "initial": "auto",
                },
                "presence": {
                    "options": ["Home", "Away", "Vacation"],
                    "initial": "Home",
                },
            }
        },
    )
    assert await async_setup_component(
        hass,
        "input_boolean",
        {"input_boolean": {"boost": {}}},
    )
    await hass.async_block_till_done()

    devices = [
        {
            "id": "th",
            "name": "Target",
            "type": HA_DEVICE_TYPE_THERMOSTAT,
            "features": {HA_FEATURE_SET_POINT_TEMP: "input_number.target"},
        },
        {
            "id": "wc",
            "name": "Roller",
            "type": HA_DEVICE_TYPE_WINDOW_COVERING,
            "features": {
                HA_FEATURE_SHUTTER_LEVEL: "input_number.roller",
                HA_FEATURE_SLATS_LEVEL: "input_number.slats",
            },
        },
        {
            "id": "hp",
            "name": "Heat Pump",
            "type": HA_DEVICE_TYPE_HEAT_PUMP,
            "features": {
                HA_FEATURE_CLIMATE_OPERATION_MODE: "input_select.mode",
                HA_FEATURE_PRESENCE_MODE: "input_select.presence",
                HA_FEATURE_HEATING_TEMP_OFFSET: "input_number.heat",
                HA_FEATURE_HOT_WATER_BOOST: "input_boolean.boost",
            },
        },
    ]
    bridge = _make_bridge(hass, devices)

    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.th",
                "features": [
                    {"type": "setPointTemperature", "setPointTemperature": 21.5}
                ],
            }
        )
        is None
    )
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.wc",
                "features": [
                    {"type": "shutterLevel", "shutterLevel": 0.75},
                    {"type": "slatsLevel", "slatsLevel": 0.3},
                ],
            }
        )
        is None
    )
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.hp",
                "features": [
                    {"type": "climateOperationMode", "climateOperationMode": "HEATING"},
                    {"type": "presenceMode", "presenceMode": "VACATION"},
                    {"type": "heatingTemperatureOffset", "heatingTemperatureOffset": 7},
                    {"type": "hotWaterBoost", "on": True},
                ],
            }
        )
        is None
    )
    await hass.async_block_till_done()

    for entity_id, expected_state in (
        ("input_number.target", "70.7"),
        ("input_number.roller", "25.0"),
        ("input_number.slats", "0.3"),
        ("input_select.mode", "heating"),
        ("input_select.presence", "Vacation"),
        ("input_number.heat", "5.0"),
        ("input_boolean.boost", "on"),
    ):
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state

    err = await bridge.handle_control_request(
        {
            "deviceId": "ha.hp",
            "features": [
                {"type": "presenceMode", "presenceMode": "NORMAL"},
                {"type": "hotWaterBoost", "on": False},
            ],
        }
    )
    await hass.async_block_till_done()
    assert err == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Setting presenceMode of input_select.presence failed: NORMAL is not an option of the entity",
    }
    presence_state = hass.states.get("input_select.presence")
    boost_state = hass.states.get("input_boolean.boost")
    assert presence_state is not None
    assert boost_state is not None
    assert presence_state.state == "Vacation"
    assert boost_state.state == "off"


async def test_real_ha_cover_and_climate_entities(hass: HomeAssistant) -> None:
    """Control and read real template cover and generic_thermostat climate entities."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(
        hass,
        "input_number",
        {
            "input_number": {
                "pos": {"min": 0, "max": 100, "step": 1, "initial": 100},
                "tilt": {"min": 0, "max": 100, "step": 1, "initial": 100},
            }
        },
    )
    assert await async_setup_component(
        hass,
        "input_boolean",
        {
            "input_boolean": {
                "gar": {"initial": True},
                "heater": {},
            }
        },
    )
    assert await async_setup_component(
        hass,
        "template",
        {
            "template": [
                {
                    "cover": [
                        {
                            "name": "Garage",
                            "state": "{{ 'open' if is_state('input_boolean.gar','on') else 'closed' }}",
                            "open_cover": [
                                {
                                    "action": "input_boolean.turn_on",
                                    "target": {"entity_id": "input_boolean.gar"},
                                }
                            ],
                            "close_cover": [
                                {
                                    "action": "input_boolean.turn_off",
                                    "target": {"entity_id": "input_boolean.gar"},
                                }
                            ],
                        },
                        {
                            "name": "Blind",
                            "position": "{{ states('input_number.pos') | int }}",
                            "tilt": "{{ states('input_number.tilt') | int }}",
                            "set_cover_position": [
                                {
                                    "action": "input_number.set_value",
                                    "target": {"entity_id": "input_number.pos"},
                                    "data": {"value": "{{ position }}"},
                                }
                            ],
                            "set_cover_tilt_position": [
                                {
                                    "action": "input_number.set_value",
                                    "target": {"entity_id": "input_number.tilt"},
                                    "data": {"value": "{{ tilt }}"},
                                }
                            ],
                        },
                    ]
                }
            ]
        },
    )
    hass.states.async_set("sensor.t", "20.4", {ATTR_UNIT_OF_MEASUREMENT: "°C"})
    assert await async_setup_component(
        hass,
        "climate",
        {
            "climate": [
                {
                    "platform": "generic_thermostat",
                    "name": "Room",
                    "heater": "input_boolean.heater",
                    "target_sensor": "sensor.t",
                    "min_temp": 5,
                    "max_temp": 30,
                    "target_temp": 21,
                    "initial_hvac_mode": "heat",
                }
            ]
        },
    )
    await hass.async_block_till_done()

    garage_state = hass.states.get("cover.garage")
    assert garage_state is not None
    assert garage_state.attributes["supported_features"] == 3

    devices = [
        {
            "id": "g",
            "name": "Garage",
            "type": HA_DEVICE_TYPE_WINDOW_COVERING,
            "features": {HA_FEATURE_SHUTTER_LEVEL: "cover.garage"},
        },
        {
            "id": "b",
            "name": "Blind",
            "type": HA_DEVICE_TYPE_WINDOW_COVERING,
            "features": {
                HA_FEATURE_SHUTTER_LEVEL: "cover.blind",
                HA_FEATURE_SLATS_LEVEL: "cover.blind",
            },
        },
        {
            "id": "t",
            "name": "Room",
            "type": HA_DEVICE_TYPE_THERMOSTAT,
            "features": {
                HA_FEATURE_SET_POINT_TEMP: "climate.room",
                HA_FEATURE_TEMPERATURE: "climate.room",
            },
        },
    ]
    bridge = _make_bridge(hass, devices)

    before = {d["deviceId"]: d["features"] for d in bridge.build_status_devices()}
    assert before["ha.g"] == [
        {"type": "shutterLevel", "shutterLevel": 0.0},
        {"type": "maintenance", "unreach": False},
    ]
    assert before["ha.b"] == [
        {"type": "shutterLevel", "shutterLevel": 0.0},
        {"type": "slatsLevel", "slatsLevel": 0.0},
        {"type": "maintenance", "unreach": False},
    ]
    assert before["ha.t"] == [
        {"type": "setPointTemperature", "setPointTemperature": 21.0},
        {"type": "actualTemperature", "actualTemperature": 20.4},
        {"type": "maintenance", "unreach": False},
    ]

    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.g",
                "features": [{"type": "shutterLevel", "shutterLevel": 1}],
            }
        )
        is None
    )
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.b",
                "features": [
                    {"type": "shutterLevel", "shutterLevel": 0.75},
                    {"type": "slatsLevel", "slatsLevel": 0.3},
                ],
            }
        )
        is None
    )
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.t",
                "features": [
                    {"type": "setPointTemperature", "setPointTemperature": 22.5}
                ],
            }
        )
        is None
    )
    await hass.async_block_till_done()

    after = {d["deviceId"]: d["features"] for d in bridge.build_status_devices()}
    assert after["ha.g"] == [
        {"type": "shutterLevel", "shutterLevel": 1.0},
        {"type": "maintenance", "unreach": False},
    ]
    assert after["ha.b"] == [
        {"type": "shutterLevel", "shutterLevel": 0.75},
        {"type": "slatsLevel", "slatsLevel": 0.3},
        {"type": "maintenance", "unreach": False},
    ]
    assert after["ha.t"] == [
        {"type": "setPointTemperature", "setPointTemperature": 22.5},
        {"type": "actualTemperature", "actualTemperature": 20.4},
        {"type": "maintenance", "unreach": False},
    ]
    garage_after = hass.states.get("cover.garage")
    assert garage_after is not None
    assert garage_after.state == STATE_CLOSED

    err_mid = await bridge.handle_control_request(
        {
            "deviceId": "ha.g",
            "features": [{"type": "shutterLevel", "shutterLevel": 0.5}],
        }
    )
    assert err_mid == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Setting shutterLevel of cover.garage failed: the cover can only be fully opened or closed",
    }

    err_slats = await bridge.handle_control_request(
        {
            "deviceId": "ha.g",
            "features": [{"type": "slatsLevel", "slatsLevel": 0.5}],
        }
    )
    assert err_slats == {
        "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
        "message": "Feature slatsLevel is not supported by ha.g",
    }

    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.t",
                "features": [
                    {"type": "setPointTemperature", "setPointTemperature": 55}
                ],
            }
        )
        is None
    )
    await hass.async_block_till_done()
    clamped = {d["deviceId"]: d["features"] for d in bridge.build_status_devices()}
    assert clamped["ha.t"] == [
        {"type": "setPointTemperature", "setPointTemperature": 30.0},
        {"type": "actualTemperature", "actualTemperature": 20.4},
        {"type": "maintenance", "unreach": False},
    ]
