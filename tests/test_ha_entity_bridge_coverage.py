"""Comprehensive coverage tests for HaEntityBridge (ha_entity_bridge.py)."""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_COLOR_TEMP_KELVIN
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
)

from custom_components.hcu_integration.const import (
    DOMAIN,
    HA_DEVICE_TYPE_CLIMATE_SENSOR,
    HA_DEVICE_TYPE_LIGHT,
    HA_DEVICE_TYPE_SWITCH,
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
    PLUGIN_ID,
)
from custom_components.hcu_integration.ha_entity_bridge import (
    HA_FIRMWARE_VERSION,
    HA_MODEL_TYPE,
    HaEntityBridge,
    _build_maintenance_value,
    _feature_value,
)


def _make_state(
    state_str: str,
    attributes: dict[str, Any] | None = None,
    entity_id: str = "sensor.test",
) -> State:
    return State(entity_id, state_str, attributes or {})


# ---------------------------------------------------------------------------
# 1. _feature_value tests
# ---------------------------------------------------------------------------


def test_feature_value_unavailable_unknown() -> None:
    """Unavailable or unknown states return None for any feature."""
    for bad_state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
        st = _make_state(bad_state)
        assert _feature_value(HA_FEATURE_ON_OFF, st) is None
        assert _feature_value(HA_FEATURE_TEMPERATURE, st) is None


def test_feature_value_on_off() -> None:
    """Test switchState feature conversion for on and off."""
    assert _feature_value(HA_FEATURE_ON_OFF, _make_state(STATE_ON)) == {
        "type": "switchState",
        "on": True,
    }
    assert _feature_value(HA_FEATURE_ON_OFF, _make_state(STATE_OFF)) == {
        "type": "switchState",
        "on": False,
    }


def test_feature_value_brightness() -> None:
    """Test dimming feature conversion and edge cases."""
    # When state is off, dimming is None
    assert (
        _feature_value(
            HA_FEATURE_BRIGHTNESS, _make_state(STATE_OFF, {ATTR_BRIGHTNESS: 200})
        )
        is None
    )

    # When brightness attribute is missing, returns None
    assert _feature_value(HA_FEATURE_BRIGHTNESS, _make_state(STATE_ON, {})) is None

    # Normal dimming calculation
    val = _feature_value(
        HA_FEATURE_BRIGHTNESS, _make_state(STATE_ON, {ATTR_BRIGHTNESS: 128})
    )
    assert val == {"type": "dimming", "dimLevel": round(128 / 255, 4)}


def test_feature_value_color_temp() -> None:
    """Test colorTemperature with kelvin, legacy mireds, and missing attribute."""
    # Kelvin attribute
    assert _feature_value(
        HA_FEATURE_COLOR_TEMP, _make_state(STATE_ON, {ATTR_COLOR_TEMP_KELVIN: 3500})
    ) == {"type": "colorTemperature", "colorTemperature": 3500}

    # Legacy mireds attribute
    assert _feature_value(
        HA_FEATURE_COLOR_TEMP, _make_state(STATE_ON, {"color_temp": 250})
    ) == {"type": "colorTemperature", "colorTemperature": 4000}

    # Legacy mireds <= 0 or invalid
    assert (
        _feature_value(HA_FEATURE_COLOR_TEMP, _make_state(STATE_ON, {"color_temp": 0}))
        is None
    )

    # Missing attributes
    assert _feature_value(HA_FEATURE_COLOR_TEMP, _make_state(STATE_ON, {})) is None


def test_feature_value_rgb_color() -> None:
    """Test color feature conversion from RGB to HSV hue and saturation."""
    # Missing rgb_color attribute
    assert _feature_value(HA_FEATURE_RGB_COLOR, _make_state(STATE_ON, {})) is None

    # Pure Red: rgb (255, 0, 0) -> hue 0, saturation 1.0
    val_red = _feature_value(
        HA_FEATURE_RGB_COLOR, _make_state(STATE_ON, {"rgb_color": (255, 0, 0)})
    )
    assert val_red == {"type": "color", "hue": 0, "saturationLevel": 1.0}

    # Pure Green: rgb (0, 255, 0) -> hue 120, saturation 1.0
    val_green = _feature_value(
        HA_FEATURE_RGB_COLOR, _make_state(STATE_ON, {"rgb_color": (0, 255, 0)})
    )
    assert val_green == {"type": "color", "hue": 120, "saturationLevel": 1.0}


def test_feature_value_sensors_and_meters() -> None:
    """Test conversion of environmental and metering sensors."""
    assert _feature_value(HA_FEATURE_TEMPERATURE, _make_state("21.54")) == {
        "type": "actualTemperature",
        "actualTemperature": 21.54,
    }
    assert _feature_value(HA_FEATURE_HUMIDITY, _make_state("55.4")) == {
        "type": "humidity",
        "humidity": 55,
    }
    assert _feature_value(HA_FEATURE_ILLUMINANCE, _make_state("120.5")) == {
        "type": "illumination",
        "illumination": 120.5,
    }
    assert _feature_value(HA_FEATURE_CO2, _make_state("450")) == {
        "type": "co2",
        "co2": 450.0,
    }
    assert _feature_value(HA_FEATURE_WIND_SPEED, _make_state("12.3")) == {
        "type": "windSpeed",
        "windSpeed": 12.3,
    }
    assert _feature_value(HA_FEATURE_PRECIPITATION, _make_state("3.2")) == {
        "type": "rainCount",
        "rainCounter": 3.2,
    }
    assert _feature_value(HA_FEATURE_WIND_DIRECTION, _make_state("180.5")) == {
        "type": "windDirection",
        "windDirection": 180.5,
    }
    assert _feature_value(HA_FEATURE_SUNSHINE_DURATION, _make_state("240.0")) == {
        "type": "sunshineDuration",
        "sunshineDuration": 240.0,
    }
    assert _feature_value(HA_FEATURE_POWER, _make_state("250.75")) == {
        "type": "currentPower",
        "currentPower": 250.75,
    }
    assert _feature_value(HA_FEATURE_ENERGY, _make_state("1500.5")) == {
        "type": "energyCounter",
        "in": 1500.5,
    }
    assert _feature_value(HA_FEATURE_PM1, _make_state("2.1")) == {
        "type": "particulateMassOne",
        "particulateMassConcentrationOne": 2.1,
    }
    assert _feature_value(HA_FEATURE_PM25, _make_state("8.5")) == {
        "type": "particulateMassTwoPointFive",
        "particulateMassConcentrationTwoPointFive": 8.5,
    }
    assert _feature_value(HA_FEATURE_PM10, _make_state("14.0")) == {
        "type": "particulateMassTen",
        "particulateMassConcentrationTen": 14.0,
    }
    assert _feature_value(HA_FEATURE_BATTERY, _make_state("85.0")) == {
        "type": "batteryState",
        "batteryLevel": 0.85,
    }
    assert _feature_value(HA_FEATURE_VEHICLE_RANGE, _make_state("310.2")) == {
        "type": "vehicleRange",
        "travelRange": 310.2,
    }
    assert _feature_value(HA_FEATURE_ON_TIME, _make_state("60.0")) == {
        "type": "onTime",
        "onTime": 60.0,
    }


def test_feature_value_binary_flags() -> None:
    """Test boolean/binary flags for storms, sunshine, rain, motion, contact, moisture, smoke."""
    assert _feature_value(HA_FEATURE_STORM, _make_state(STATE_ON)) == {
        "type": "storm",
        "storm": True,
    }
    assert _feature_value(HA_FEATURE_SUNSHINE, _make_state(STATE_OFF)) == {
        "type": "sunshine",
        "sunshine": False,
    }
    assert _feature_value(HA_FEATURE_RAINING, _make_state(STATE_ON)) == {
        "type": "raining",
        "raining": True,
    }
    assert _feature_value(HA_FEATURE_MOTION, _make_state(STATE_ON)) == {
        "type": "presenceDetected",
        "presenceDetected": True,
    }
    assert _feature_value(HA_FEATURE_OCCUPANCY, _make_state(STATE_OFF)) == {
        "type": "presenceDetected",
        "presenceDetected": False,
    }
    assert _feature_value(HA_FEATURE_DOOR, _make_state(STATE_ON)) == {
        "type": "contactSensorState",
        "triggered": True,
    }
    assert _feature_value(HA_FEATURE_WINDOW, _make_state(STATE_OFF)) == {
        "type": "contactSensorState",
        "triggered": False,
    }
    assert _feature_value(HA_FEATURE_CONTACT_SENSOR, _make_state(STATE_ON)) == {
        "type": "contactSensorState",
        "triggered": True,
    }
    assert _feature_value(HA_FEATURE_SMOKE, _make_state(STATE_ON)) == {
        "type": "smokeAlarm",
        "smokeAlarm": True,
    }
    assert _feature_value(HA_FEATURE_MOISTURE, _make_state(STATE_ON)) == {
        "type": "waterlevelDetected",
        "waterlevelDetected": True,
    }
    assert _feature_value(HA_FEATURE_MOISTURE_DETECTED, _make_state(STATE_OFF)) == {
        "type": "moistureDetected",
        "moistureDetected": False,
    }


def test_feature_value_climate_and_shutter() -> None:
    """Test climate offsets, operation mode, hot water, and shutter features."""
    assert _feature_value(HA_FEATURE_CLIMATE_OPERATION_MODE, _make_state("HEAT")) == {
        "type": "climateOperationMode",
        "climateOperationMode": "HEAT",
    }
    assert _feature_value(HA_FEATURE_COOLING_TEMP_OFFSET, _make_state("-1.5")) == {
        "type": "coolingTemperatureOffset",
        "coolingTemperatureOffset": -1.5,
    }
    assert _feature_value(HA_FEATURE_HEATING_TEMP_OFFSET, _make_state("2.0")) == {
        "type": "heatingTemperatureOffset",
        "heatingTemperatureOffset": 2.0,
    }
    assert _feature_value(HA_FEATURE_PRESENCE_MODE, _make_state("AWAY")) == {
        "type": "presenceMode",
        "presenceMode": "AWAY",
    }
    assert _feature_value(HA_FEATURE_HOT_WATER_BOOST, _make_state(STATE_ON)) == {
        "type": "hotWaterBoost",
        "on": True,
    }
    assert _feature_value(HA_FEATURE_SUPPLY_TEMPERATURE, _make_state("48.5")) == {
        "type": "supplyTemperature",
        "supplyTemperature": 48.5,
    }
    assert _feature_value(HA_FEATURE_SET_POINT_TEMP, _make_state("21.0")) == {
        "type": "setPointTemperature",
        "setPointTemperature": 21.0,
    }
    assert _feature_value(HA_FEATURE_SHUTTER_LEVEL, _make_state("0.65")) == {
        "type": "shutterLevel",
        "shutterLevel": 0.65,
    }
    assert _feature_value(HA_FEATURE_SLATS_LEVEL, _make_state("0.4")) == {
        "type": "slatsLevel",
        "slatsLevel": 0.4,
    }
    assert _feature_value(HA_FEATURE_SHUTTER_DIRECTION, _make_state("UP")) == {
        "type": "shutterDirection",
        "shutterDirection": "UP",
    }


def test_feature_value_errors_and_unknown() -> None:
    """Test handling of invalid float values and unknown feature keys."""
    # ValueError handled
    assert _feature_value(HA_FEATURE_TEMPERATURE, _make_state("not_a_number")) is None
    # Unknown feature key
    assert _feature_value("non_existent_key", _make_state("123")) is None


# ---------------------------------------------------------------------------
# 2. _build_maintenance_value tests
# ---------------------------------------------------------------------------


def test_build_maintenance_value(hass: HomeAssistant) -> None:
    """Test combining lowBat, sabotage, and unreach into a maintenance feature object."""
    # 1. No maintenance keys configured
    assert _build_maintenance_value(hass, {HA_FEATURE_ON_OFF: "switch.test"}) is None

    # 2. Configured maintenance entities not in hass states or unavailable
    conf = {
        HA_FEATURE_LOW_BAT: "binary_sensor.low_bat",
        HA_FEATURE_SABOTAGE: "binary_sensor.sabotage",
        HA_FEATURE_UNREACH: "binary_sensor.unreach",
    }
    assert _build_maintenance_value(hass, conf) is None

    hass.states.async_set("binary_sensor.low_bat", STATE_UNAVAILABLE)
    hass.states.async_set("binary_sensor.sabotage", STATE_UNKNOWN)
    assert _build_maintenance_value(hass, conf) is None

    # 3. Known states populated
    hass.states.async_set("binary_sensor.low_bat", STATE_ON)
    hass.states.async_set("binary_sensor.sabotage", STATE_OFF)
    hass.states.async_set("binary_sensor.unreach", STATE_ON)

    assert _build_maintenance_value(hass, conf) == {
        "type": "maintenance",
        "lowBat": True,
        "sabotage": False,
        "unreach": True,
    }


# ---------------------------------------------------------------------------
# 3. HaEntityBridge helper methods & discovery
# ---------------------------------------------------------------------------


def test_bridge_id_and_lookup_helpers(hass: HomeAssistant) -> None:
    """Test _make_hcu_id, _is_ha_device_id, is_known_device, is_ha_device, and all_entity_ids."""
    ha_devices = [
        {
            "id": "switch1",
            "name": " Living Room Switch ",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {
                HA_FEATURE_ON_OFF: "switch.living_room",
                HA_FEATURE_LOW_BAT: "binary_sensor.switch_bat",
            },
        },
        {
            "id": "switch2",
            "name": "",
            "features": {HA_FEATURE_ON_OFF: "switch.bedroom"},
        },
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    assert bridge._make_hcu_id(ha_devices[0]) == "ha.switch1"
    assert bridge._is_ha_device_id("ha.switch1") is True
    assert bridge._is_ha_device_id("0001D8A9999") is False

    assert bridge.is_known_device("ha.switch1") is True
    assert bridge.is_known_device("ha.unknown") is False
    assert bridge.is_ha_device("ha.switch1") is True
    assert bridge.is_ha_device("ha.unknown") is False

    assert bridge.all_entity_ids == {
        "switch.living_room",
        "binary_sensor.switch_bat",
        "switch.bedroom",
    }
    assert bridge._get_friendly_name(ha_devices[0]) == "Living Room Switch"
    assert bridge._get_friendly_name(ha_devices[1]) == "switch2"
    assert bridge.device_to_entity_id("ha.switch1") is None


def test_build_discover_features_dedup_and_maintenance(hass: HomeAssistant) -> None:
    """Test deduplication of duplicate Connect API types and maintenance addition."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    # Both door and window map to contactSensorState; only one is kept
    features = {
        HA_FEATURE_DOOR: "binary_sensor.door",
        HA_FEATURE_WINDOW: "binary_sensor.window",
        HA_FEATURE_LOW_BAT: "binary_sensor.bat",
    }
    discover_features = bridge._build_discover_features(features)
    assert discover_features == [
        {"type": "contactSensorState"},
        {"type": "maintenance"},
    ]


def test_build_value_features_edge_cases(hass: HomeAssistant) -> None:
    """Test _build_value_features handling of empty entity IDs, missing states, and maintenance."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    # Config with empty entity_id string, unrecorded entity, and valid entity + maintenance
    hass.states.async_set("switch.valid", STATE_ON)
    hass.states.async_set("binary_sensor.low_bat", STATE_ON)
    device = {
        "id": "dev1",
        "features": {
            HA_FEATURE_ON_OFF: "switch.valid",
            HA_FEATURE_BRIGHTNESS: "",  # empty entity_id
            HA_FEATURE_COLOR_TEMP: "light.non_existent",  # state is None
            HA_FEATURE_LOW_BAT: "binary_sensor.low_bat",
        },
    }
    features = bridge._build_value_features(device)
    assert features == [
        {"type": "switchState", "on": True},
        {"type": "maintenance", "lowBat": True},
    ]


def test_get_ha_device_info(hass: HomeAssistant) -> None:
    """Test looking up device model and firmware version from entity and device registry."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    # 1. No primary entity or only maintenance
    assert bridge._get_ha_device_info({}) == (None, None)
    assert bridge._get_ha_device_info({HA_FEATURE_LOW_BAT: "sensor.bat"}) == (
        None,
        None,
    )

    # 2. Entity not in entity registry
    assert bridge._get_ha_device_info({HA_FEATURE_ON_OFF: "switch.not_registered"}) == (
        None,
        None,
    )

    # 3. Entity in registry without device_id
    ent_reg = er.async_get(hass)
    ent_reg.async_get_or_create("switch", "test_domain", "switch_no_device")
    assert bridge._get_ha_device_info(
        {HA_FEATURE_ON_OFF: "switch.test_domain_switch_no_device"}
    ) == (None, None)

    # 4. Entity attached to registered parent device
    config_entry = MockConfigEntry(domain="test_domain")
    config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    dev_entry = dev_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("test_domain", "dev123")},
        model="SuperSwitch 2000",
        sw_version="3.1.4",
    )
    ent_with_dev = ent_reg.async_get_or_create(
        "switch",
        "test_domain",
        "switch_with_dev",
        device_id=dev_entry.id,
    )
    assert bridge._get_ha_device_info({HA_FEATURE_ON_OFF: ent_with_dev.entity_id}) == (
        "SuperSwitch 2000",
        "3.1.4",
    )

    # 5. Entity lookup fallback when ON_OFF not present (uses first non-maintenance feature)
    ent_sensor = ent_reg.async_get_or_create(
        "sensor",
        "test_domain",
        "temp_sensor",
        device_id=dev_entry.id,
    )
    assert bridge._get_ha_device_info(
        {HA_FEATURE_TEMPERATURE: ent_sensor.entity_id}
    ) == (
        "SuperSwitch 2000",
        "3.1.4",
    )

    # 6. Child device (ChildDeviceEntry) carries no model or firmware
    child_dev = dev_reg.async_get_or_create_child(
        config_entry_id=config_entry.entry_id,
        identifiers={("test_domain", "child123")},
        parent_device_id=dev_entry.id,
    )
    ent_child = ent_reg.async_get_or_create(
        "switch",
        "test_domain",
        "switch_child",
        device_id=child_dev.id,
    )
    assert bridge._get_ha_device_info({HA_FEATURE_ON_OFF: ent_child.entity_id}) == (
        None,
        None,
    )


def test_build_device_object_include_values(hass: HomeAssistant) -> None:
    """Test _build_device_object with include_values=True and False, handling empty features."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    # Device with no features
    assert bridge._build_device_object({"id": "empty", "features": {}}, False) is None

    # Device with discover values
    dev = {
        "id": "switch1",
        "name": "Porch Switch",
        "type": HA_DEVICE_TYPE_SWITCH,
        "features": {HA_FEATURE_ON_OFF: "switch.porch"},
    }
    obj_no_vals = bridge._build_device_object(dev, include_values=False)
    assert obj_no_vals is not None
    assert obj_no_vals["deviceId"] == "ha.switch1"
    assert obj_no_vals["friendlyName"] == "Porch Switch"
    assert obj_no_vals["modelType"] == HA_MODEL_TYPE
    assert obj_no_vals["firmwareVersion"] == HA_FIRMWARE_VERSION
    assert obj_no_vals["features"] == [{"type": "switchState"}]

    # When include_values=True but state is unavailable -> returns None
    hass.states.async_set("switch.porch", STATE_UNAVAILABLE)
    assert bridge._build_device_object(dev, include_values=True) is None

    # When include_values=True and state is valid -> returns obj with value features
    hass.states.async_set("switch.porch", STATE_ON)
    obj_with_vals = bridge._build_device_object(dev, include_values=True)
    assert obj_with_vals is not None
    assert obj_with_vals["features"] == [{"type": "switchState", "on": True}]


def test_build_discover_devices(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test build_discover_devices handles empty, valid, and non-discoverable devices."""
    ha_devices = [
        # Empty features -> skipped
        {"id": "empty", "features": {}},
        # Valid switch with current state -> values overlaid
        {
            "id": "sw1",
            "name": "Hallway",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.hallway"},
        },
        # Non-discoverable device type -> excluded and logged
        {
            "id": "custom",
            "name": "Custom Unsupported",
            "type": "NON_EXISTENT_TYPE",
            "features": {HA_FEATURE_ON_OFF: "switch.custom"},
        },
    ]
    hass.states.async_set("switch.hallway", STATE_ON)
    hass.states.async_set("switch.custom", STATE_ON)

    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)
    with caplog.at_level(logging.DEBUG):
        devices = bridge.build_discover_devices()

    assert len(devices) == 1
    assert devices[0]["deviceId"] == "ha.sw1"
    assert devices[0]["features"] == [{"type": "switchState", "on": True}]
    assert "ha.sw1" in bridge._discovered_hcu_ids

    # Verify debug log for excluded device
    assert (
        "Excluding device ha.custom (Custom Unsupported) from DISCOVER_RESPONSE"
        in caplog.text
    )


def test_build_status_devices(hass: HomeAssistant) -> None:
    """Test build_status_devices with all devices and filtered device IDs."""
    ha_devices = [
        {
            "id": "sw1",
            "name": "Kitchen",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.kitchen"},
        },
        {
            "id": "sw2",
            "name": "Pantry",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.pantry"},
        },
    ]
    hass.states.async_set("switch.kitchen", STATE_ON)
    hass.states.async_set("switch.pantry", STATE_UNAVAILABLE)

    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    # 1. hcu_device_ids=None -> sw1 is returned, sw2 skipped because state unavailable
    status_all = bridge.build_status_devices(None)
    assert len(status_all) == 1
    assert status_all[0]["deviceId"] == "ha.sw1"

    # 2. hcu_device_ids specified with known and unknown IDs
    status_filtered = bridge.build_status_devices(["ha.sw1", "ha.unknown"])
    assert len(status_filtered) == 1
    assert status_filtered[0]["deviceId"] == "ha.sw1"


# ---------------------------------------------------------------------------
# 4. Control requests & auto-off timers
# ---------------------------------------------------------------------------


async def test_control_request_unknown_device(hass: HomeAssistant) -> None:
    """Control request for unknown device ID is ignored safely."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)
    # Should not raise or call any service
    await bridge.handle_control_request(
        {
            "deviceId": "ha.unknown",
            "features": [{"type": "switchState", "on": True}],
        }
    )


async def test_control_request_service_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Service failures are caught and logged without raising exceptions."""
    ha_devices = [
        {
            "id": "sw1",
            "name": "Switch 1",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.broken"},
        }
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    async def _failing_switch(call: Any) -> None:
        raise HomeAssistantError("Service exploded")

    hass.services.async_register("switch", "turn_on", _failing_switch)

    with caplog.at_level(logging.ERROR):
        await bridge.handle_control_request(
            {
                "deviceId": "ha.sw1",
                "features": [{"type": "switchState", "on": True}],
            }
        )

    assert (
        "Service switch.turn_on for switch.broken failed: Service exploded"
        in caplog.text
    )


async def test_control_request_dimming(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test dimming control on light entity, ignoring non-light entity, and error handling."""
    ha_devices = [
        {
            "id": "lt1",
            "name": "Light 1",
            "type": HA_DEVICE_TYPE_LIGHT,
            "features": {HA_FEATURE_BRIGHTNESS: "light.living_room"},
        },
        {
            "id": "sw1",
            "name": "Switch 1",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.fan"},
        },
    ]
    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    # 1. Normal dimming: dimLevel = 0.5 -> brightness = 127
    await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "dimming", "dimLevel": 0.5}],
        }
    )
    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data == {
        "entity_id": "light.living_room",
        "brightness": 127,
    }

    # 2. Dimming on a non-light entity is skipped
    await bridge.handle_control_request(
        {
            "deviceId": "ha.sw1",
            "features": [{"type": "dimming", "dimLevel": 0.5}],
        }
    )
    assert len(turn_on_calls) == 1

    # 3. Dimming service call failure logged
    async def _failing_dim(call: Any) -> None:
        raise HomeAssistantError("Dimming failed")

    hass.services.async_register("light", "turn_on", _failing_dim)

    with caplog.at_level(logging.ERROR):
        await bridge.handle_control_request(
            {
                "deviceId": "ha.lt1",
                "features": [{"type": "dimming", "dimLevel": 0.5}],
            }
        )
    assert "Dimming light.living_room failed: Dimming failed" in caplog.text


async def test_control_request_color_temp_and_rgb(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test colorTemperature and color feature handling, missing values, and error logs."""
    ha_devices = [
        {
            "id": "lt1",
            "name": "Color Light",
            "type": HA_DEVICE_TYPE_LIGHT,
            "features": {
                HA_FEATURE_COLOR_TEMP: "light.color_light",
                HA_FEATURE_RGB_COLOR: "light.color_light",
            },
        }
    ]
    turn_on_calls = async_mock_service(hass, "light", "turn_on")
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    # 1. RGB Color: hue=120, saturationLevel=1.0 -> green (0, 255, 0)
    await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "color", "hue": 120, "saturationLevel": 1.0}],
        }
    )
    assert len(turn_on_calls) == 1
    assert turn_on_calls[0].data == {
        "entity_id": "light.color_light",
        "rgb_color": [0, 255, 0],
    }

    # 2. Missing hue or saturation is ignored
    await bridge.handle_control_request(
        {
            "deviceId": "ha.lt1",
            "features": [{"type": "color", "hue": 120}],
        }
    )
    assert len(turn_on_calls) == 1

    # 3. Color and Color temperature service call errors logged
    async def _failing_light(call: Any) -> None:
        raise HomeAssistantError("Light call failed")

    hass.services.async_register("light", "turn_on", _failing_light)

    with caplog.at_level(logging.ERROR):
        await bridge.handle_control_request(
            {
                "deviceId": "ha.lt1",
                "features": [{"type": "color", "hue": 120, "saturationLevel": 1.0}],
            }
        )
    assert "Color light.color_light failed: Light call failed" in caplog.text

    with caplog.at_level(logging.ERROR):
        await bridge.handle_control_request(
            {
                "deviceId": "ha.lt1",
                "features": [{"type": "colorTemperature", "colorTemperature": 4000}],
            }
        )
    assert "Color temp light.color_light failed: Light call failed" in caplog.text


def test_get_control_on_time_priority(hass: HomeAssistant) -> None:
    """Test resolution order and fallbacks for on_time."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    features_conf = {HA_FEATURE_ON_TIME: "input_number.timer"}
    hass.states.async_set("input_number.timer", "30.0")

    # Priority 1: on switchState feature itself
    assert (
        bridge._get_control_on_time(
            body_features=[{"type": "onTime", "onTime": 15}],
            switch_feature={"onTime": 45},
            features_conf=features_conf,
        )
        == 45.0
    )

    # Priority 1 with invalid value falls through
    assert (
        bridge._get_control_on_time(
            body_features=[{"type": "onTime", "onTime": 15}],
            switch_feature={"onTime": "invalid"},
            features_conf=features_conf,
        )
        == 15.0
    )

    # Priority 2: sibling onTime feature in body_features
    assert (
        bridge._get_control_on_time(
            body_features=[{"type": "onTime", "onTime": 25}],
            switch_feature={},
            features_conf=features_conf,
        )
        == 25.0
    )

    # Priority 2 with invalid value falls through
    assert (
        bridge._get_control_on_time(
            body_features=[{"type": "onTime", "onTime": "bad"}],
            switch_feature={},
            features_conf=features_conf,
        )
        == 30.0
    )

    # Priority 3: configured HA_FEATURE_ON_TIME entity
    assert (
        bridge._get_control_on_time(
            body_features=[],
            switch_feature={},
            features_conf=features_conf,
        )
        == 30.0
    )

    # Configured entity state unavailable / invalid
    hass.states.async_set("input_number.timer", STATE_UNAVAILABLE)
    assert (
        bridge._get_control_on_time(
            body_features=[],
            switch_feature={},
            features_conf=features_conf,
        )
        is None
    )

    hass.states.async_set("input_number.timer", "not_a_number")
    assert (
        bridge._get_control_on_time(
            body_features=[],
            switch_feature={},
            features_conf=features_conf,
        )
        is None
    )

    # No on_time sources available
    assert (
        bridge._get_control_on_time(
            body_features=[],
            switch_feature={},
            features_conf={},
        )
        is None
    )


async def test_auto_off_after_service_call_failure(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Auto-off task failure is logged without crashing."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    async def _failing_turn_off(call: Any) -> None:
        raise HomeAssistantError("Turn off failed")

    hass.services.async_register("switch", "turn_off", _failing_turn_off)

    with caplog.at_level(logging.ERROR):
        await bridge._auto_off_after("switch.test", "switch", 0)

    assert "on_time auto-off for switch.test failed: Turn off failed" in caplog.text


# ---------------------------------------------------------------------------
# 5. Status events & throttling
# ---------------------------------------------------------------------------


async def test_send_status_event_gating_and_throttling(hass: HomeAssistant) -> None:
    """Test that status events require discovery, are throttled when identical, and handle ConnectionError."""
    ha_devices = [
        {
            "id": "sw1",
            "name": "Switch 1",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.sw1"},
        }
    ]
    hass.states.async_set("switch.sw1", STATE_ON)
    send_fn = AsyncMock()
    bridge = HaEntityBridge(hass, ha_devices, send_fn, PLUGIN_ID)

    # 1. Device NOT yet discovered -> sending is skipped to prevent protocol violation
    await bridge.send_status_event()
    send_fn.assert_not_called()

    # Discover device
    bridge.build_discover_devices()
    send_fn.reset_mock()

    # 2. First send -> successfully sent
    await bridge.send_status_event()
    assert send_fn.call_count == 1
    msg = send_fn.call_args[0][0]
    assert msg["pluginId"] == PLUGIN_ID
    assert msg["type"] == "STATUS_EVENT"
    assert msg["body"]["deviceId"] == "ha.sw1"
    assert msg["body"]["features"] == [{"type": "switchState", "on": True}]

    # 3. Second send immediately with same state -> throttled (skipped)
    await bridge.send_status_event()
    assert send_fn.call_count == 1

    # 4. State changed -> sent immediately even within throttle interval
    hass.states.async_set("switch.sw1", STATE_OFF)
    await bridge.send_status_event()
    assert send_fn.call_count == 2
    assert send_fn.call_args[0][0]["body"]["features"] == [
        {"type": "switchState", "on": False}
    ]

    # 5. Same state but throttle interval elapsed (> 5.0 seconds) -> sent
    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.time.monotonic",
        return_value=bridge._last_sent["ha.sw1"] + 6.0,
    ):
        await bridge.send_status_event()
    assert send_fn.call_count == 3

    # 6. ConnectionError during send_message is suppressed
    send_fn.side_effect = ConnectionError("HCU connection lost")
    hass.states.async_set("switch.sw1", STATE_ON)
    # Should not raise exception
    await bridge.send_status_event()


async def test_send_status_event_no_features_skipped(hass: HomeAssistant) -> None:
    """send_status_event skips devices when features evaluate to empty/None."""
    ha_devices = [
        {
            "id": "sw1",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.sw1"},
        }
    ]
    hass.states.async_set("switch.sw1", STATE_ON)
    send_fn = AsyncMock()
    bridge = HaEntityBridge(hass, ha_devices, send_fn, PLUGIN_ID)
    bridge.build_discover_devices()
    send_fn.reset_mock()

    # Make entity state unavailable -> features evaluates to None
    hass.states.async_set("switch.sw1", STATE_UNAVAILABLE)
    await bridge.send_status_event()
    send_fn.assert_not_called()


# ---------------------------------------------------------------------------
# 6. Stale device repairs
# ---------------------------------------------------------------------------


async def test_handle_stale_inclusion_devices(hass: HomeAssistant) -> None:
    """Test repair issues are created for orphaned/stale HA devices."""
    ha_devices = [
        {
            "id": "active_dev",
            "name": "Active Switch",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.active"},
        }
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    stale_device_ids = [
        "0001D8A9999",  # Not an HA device -> ignored
        "ha.active_dev",  # Active configured device -> ignored
        "ha.stale_lamp",  # Stale HA device -> repair issue created
    ]

    await bridge.handle_stale_inclusion_devices(stale_device_ids)

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, "ha_entity_excluded_ha_stale_lamp")
    assert issue is not None
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.is_fixable is False
    assert issue.translation_key == "ha_entity_excluded"
    assert issue.translation_placeholders == {"entity_id": "ha.stale_lamp"}


# ---------------------------------------------------------------------------
# 7. State listener edge cases & device summary
# ---------------------------------------------------------------------------


def test_start_listening_no_entities(hass: HomeAssistant) -> None:
    """Calling start_listening with no configured entities returns immediately."""
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)
    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.async_track_state_change_event"
    ) as track_mock:
        bridge.start_listening()
        track_mock.assert_not_called()


def test_start_listening_resubscribes(hass: HomeAssistant) -> None:
    """Calling start_listening when already listening cancels previous subscription."""
    ha_devices = [
        {
            "id": "sw1",
            "features": {HA_FEATURE_ON_OFF: "switch.test"},
        }
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)
    unsub_mock1 = MagicMock()
    unsub_mock2 = MagicMock()

    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.async_track_state_change_event",
        side_effect=[unsub_mock1, unsub_mock2],
    ):
        bridge.start_listening()
        assert bridge._unsub is unsub_mock1

        bridge.start_listening()
        unsub_mock1.assert_called_once()
        assert bridge._unsub is unsub_mock2

    bridge.stop_listening()
    unsub_mock2.assert_called_once()


async def test_state_change_unknown_entity(hass: HomeAssistant) -> None:
    """State change callback ignores entities not mapped to any HCU device."""
    ha_devices = [
        {
            "id": "sw1",
            "features": {HA_FEATURE_ON_OFF: "switch.known"},
        }
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)
    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.async_track_state_change_event"
    ) as track_mock:
        bridge.start_listening()
        callback_fn = track_mock.call_args[0][2]

    # Callback with an unknown entity id
    event = MagicMock(
        data={"entity_id": "switch.unknown", "new_state": _make_state(STATE_ON)}
    )
    with patch.object(bridge.hass, "async_create_task") as task_mock:
        callback_fn(event)
        task_mock.assert_not_called()

    bridge.stop_listening()


def test_get_device_summary(hass: HomeAssistant) -> None:
    """Test get_device_summary markdown generation for empty, controllable, and sensor devices."""
    # 1. Empty devices
    bridge_empty = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)
    assert bridge_empty.get_device_summary() == ""

    # 2. Devices with controllable and non-controllable types
    ha_devices = [
        {
            "id": "sw1",
            "name": "Kitchen Light",
            "type": HA_DEVICE_TYPE_LIGHT,
            "features": {HA_FEATURE_ON_OFF: "light.kitchen"},
        },
        {
            "id": "sens1",
            "name": "Weather Station",
            "type": HA_DEVICE_TYPE_CLIMATE_SENSOR,
            "features": {
                HA_FEATURE_TEMPERATURE: "sensor.temp",
                HA_FEATURE_HUMIDITY: "sensor.hum",
            },
        },
        {
            "id": "dev_inferred",
            "features": {},  # no type, no features -> '?'
        },
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)
    summary = bridge.get_device_summary()

    lines = summary.split("\n")
    assert len(lines) == 3
    assert lines[0] == "• **Kitchen Light** — LIGHT (1 feature(s), controllable)"
    assert (
        lines[1]
        == "• **Weather Station** — CLIMATE_SENSOR (2 feature(s), status events only)"
    )
    assert lines[2] == "• **dev_inferred** — ? (0 feature(s), status events only)"
