"""Unit tests for the HCU sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import (
    DOMAIN,
    HMIP_ON_TIME_INFINITE,
)
from custom_components.hcu_integration.sensor import (
    HcuGenericSensor,
    HcuGroupOnTimeSensor,
    HcuHomeSensor,
    HcuTemperatureSensor,
    HcuTimestampSensor,
    HcuWindowStateSensor,
    async_setup_entry,
)


def _make_generic_sensor(
    device_data: dict,
    channel_index: str = "1",
    feature: str = "actualTemperature",
    mapping: dict | None = None,
    cls: type[HcuGenericSensor] = HcuGenericSensor,
) -> HcuGenericSensor:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    m = mapping or {
        "name": "Temperature",
        "device_class": SensorDeviceClass.TEMPERATURE,
    }
    entity = cls(coordinator, client, device_data, channel_index, feature, m)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_sensor_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.SENSOR: [mock_entity]}
    entry.runtime_data = mock_coordinator

    added = []

    def mock_add_entities(entities: list) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == [mock_entity]

    # Empty list
    mock_coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == []


def test_home_sensor() -> None:
    """Test HcuHomeSensor for carrierSense, dutyCycle, and other attributes."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {}

    client = MagicMock()
    client.hcu_device_id = "hcu-home"
    client.state = {
        "home": {
            "id": "home-1",
            "carrierSense": 3.456,
            "dutyCycle": 12.789,
            "version": "2.4.0",
        }
    }

    mapping_cs = {
        "name": "Carrier Sense",
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal",
        "entity_registry_enabled_default": True,
    }
    sensor_cs = HcuHomeSensor(coordinator, client, "carrierSense", mapping_cs)
    assert sensor_cs.unique_id == "hcu-home_carrierSense"
    assert sensor_cs.name == "Carrier Sense"
    assert sensor_cs.native_value == 3.5

    mapping_dc = {"name": "Duty Cycle"}
    sensor_dc = HcuHomeSensor(coordinator, client, "dutyCycle", mapping_dc)
    assert sensor_dc.native_value == 12.8

    mapping_ver = {"name": "Version"}
    sensor_ver = HcuHomeSensor(coordinator, client, "version", mapping_ver)
    assert sensor_ver.native_value == "2.4.0"

    # Missing value
    client.state["home"]["carrierSense"] = None
    assert sensor_cs.native_value is None


def test_group_on_time_sensor() -> None:
    """Test HcuGroupOnTimeSensor values including infinite on-time."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {}

    group_data = {
        "id": "group-ext-1",
        "type": "EXTENDED_LINKED_SWITCHING",
        "label": "Staircase",
        "onTime": 180.2,
        "channels": [],
    }
    client = MagicMock()
    client.hcu_device_id = "hcu-1"
    client.get_group_by_id = MagicMock(return_value=group_data)

    entity = HcuGroupOnTimeSensor(coordinator, client, group_data)
    assert entity.unique_id == "group-ext-1_on_time"
    assert entity.device_class == SensorDeviceClass.DURATION
    assert entity.native_unit_of_measurement == "s"
    assert entity.suggested_display_precision == 0
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.entity_registry_enabled_default is False
    assert entity.native_value == 180.0

    # Infinite on-time -> 0
    group_data["onTime"] = HMIP_ON_TIME_INFINITE
    assert entity.native_value == 0

    # Missing onTime -> None
    group_data["onTime"] = None
    assert entity.native_value is None


def test_generic_sensor_properties_and_values() -> None:
    """Test HcuGenericSensor mapping, overlays, and feature special calculations."""
    device_data = {
        "id": "dev-valve-1",
        "label": "Radiator Thermostat",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "HEATING_THERMOSTAT_CHANNEL",
                "label": "Heater Channel",
                "valvePosition": 0.425,
                "vaporAmount": 5.6789,
                "dutyCycleLevel": 8.23,
                "onTime": 30.2,
                "genericMetric": 100,
                "internalLinkConfiguration": {
                    "overlayMetric": 42,
                },
            },
        },
    }
    mapping = {
        "name": "Valve Position",
        "device_class": None,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 1,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": True,
    }
    sensor_valve = _make_generic_sensor(
        device_data, "1", "valvePosition", mapping, HcuGenericSensor
    )
    assert sensor_valve.unique_id == "dev-valve-1_1_valvePosition"
    # valvePosition is multiplied by 100.0 and rounded to 1 decimal
    assert sensor_valve.native_value == 42.5

    # vaporAmount rounded to 2 decimals
    sensor_vapor = _make_generic_sensor(
        device_data, "1", "vaporAmount", {"name": "Vapor"}, HcuGenericSensor
    )
    assert sensor_vapor.native_value == 5.68

    # dutyCycleLevel rounded to 1 decimal
    sensor_dc = _make_generic_sensor(
        device_data, "1", "dutyCycleLevel", {"name": "Duty Cycle"}, HcuGenericSensor
    )
    assert sensor_dc.native_value == 8.2

    # onTime rounded to 0 decimals
    sensor_ontime = _make_generic_sensor(
        device_data, "1", "onTime", {"name": "On Time"}, HcuGenericSensor
    )
    assert sensor_ontime.native_value == 30.0

    # onTime infinite -> 0
    device_data["functionalChannels"]["1"]["onTime"] = HMIP_ON_TIME_INFINITE
    assert sensor_ontime.native_value == 0

    # overlay metric from internalLinkConfiguration
    sensor_overlay = _make_generic_sensor(
        device_data, "1", "overlayMetric", {"name": "Overlay"}, HcuGenericSensor
    )
    assert sensor_overlay.native_value == 42

    # genericMetric unchanged
    sensor_generic = _make_generic_sensor(
        device_data, "1", "genericMetric", {"name": "Metric"}, HcuGenericSensor
    )
    assert sensor_generic.native_value == 100

    # None metric
    sensor_none = _make_generic_sensor(
        device_data, "1", "nonExistent", {"name": "None"}, HcuGenericSensor
    )
    assert sensor_none.native_value is None

    # Translation key branch
    sensor_trans = _make_generic_sensor(
        device_data,
        "1",
        "genericMetric",
        {"name": "Key", "translation_key": "custom_key"},
        HcuGenericSensor,
    )
    assert sensor_trans.translation_key == "custom_key"


def test_smart_energy_counter_names() -> None:
    """Test smart naming for various energyCounter types."""
    channel_data = {
        "functionalChannelType": "ENERGY_COUNTER_CHANNEL",
        "label": "Electricity Meter",
        "energyCounterUsage": 123.4,
    }
    device_data = {
        "id": "dev-meter-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": channel_data,
        },
    }

    types_and_expected = [
        ("ENERGY_COUNTER_USAGE_HIGH_TARIFF", "Energy Usage (High Tariff)"),
        ("ENERGY_COUNTER_USAGE_LOW_TARIFF", "Energy Usage (Low Tariff)"),
        ("ENERGY_COUNTER_INPUT_SINGLE_TARIFF", "Energy Feed-in"),
        ("ENERGY_COUNTER_INPUT_HIGH_TARIFF", "Energy Feed-in (High Tariff)"),
        ("ENERGY_COUNTER_INPUT_LOW_TARIFF", "Energy Feed-in (Low Tariff)"),
        ("UNKNOWN", "Base Energy"),
        ("OTHER_UNMAPPED_TYPE", "Base Energy"),
    ]

    for c_type, expected_feature_name in types_and_expected:
        channel_data["energyCounterUsageType"] = c_type
        sensor = _make_generic_sensor(
            device_data,
            "1",
            "energyCounterUsage",
            {"name": "Base Energy"},
            HcuGenericSensor,
        )
        assert expected_feature_name in str(sensor.name)


def test_temperature_sensor() -> None:
    """Test HcuTemperatureSensor native value reading."""
    device_data = {
        "id": "dev-temp-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "WALL_MOUNTED_THERMOSTAT_PRO_CHANNEL",
                "actualTemperature": 21.8,
            },
        },
    }
    entity = _make_generic_sensor(
        device_data,
        "1",
        "actualTemperature",
        {"name": "Room Temp"},
        HcuTemperatureSensor,
    )
    assert entity.native_value == 21.8


def test_window_state_sensor() -> None:
    """Test HcuWindowStateSensor states and options."""
    device_data = {
        "id": "dev-srh-1",
        "label": "Window Handle Sensor",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "ROTARY_HANDLE_SENSOR",
                "windowState": "OPEN",
            },
        },
    }
    # With default mapping=None
    dev_id = "dev-srh-1"
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}
    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuWindowStateSensor(coordinator, client, device_data, "1")
    assert entity.unique_id == "dev-srh-1_1_windowState_state"
    assert entity.translation_key == "hcu_tiltwindow"
    assert entity.options == ["open", "tilted", "closed"]
    assert entity.native_value == "open"

    device_data["functionalChannels"]["1"]["windowState"] = "TILTED"
    assert entity.native_value == "tilted"

    device_data["functionalChannels"]["1"]["windowState"] = "CLOSED"
    assert entity.native_value == "closed"

    # Other / None state
    device_data["functionalChannels"]["1"]["windowState"] = "UNKNOWN_STATE"
    assert entity.native_value == "UNKNOWN_STATE"

    device_data["functionalChannels"]["1"]["windowState"] = None
    assert entity.native_value is None

    # Custom mapping
    custom_entity = HcuWindowStateSensor(
        coordinator, client, device_data, "1", "windowState", {"name": "Custom State"}
    )
    assert custom_entity.options == ["open", "tilted", "closed"]


def test_timestamp_sensor() -> None:
    """Test HcuTimestampSensor millisecond conversions and boundary checks."""
    device_data = {
        "id": "dev-ts-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DEVICE_BASE",
                "lastStatusUpdate": 1700000000000,
            },
        },
    }
    entity = _make_generic_sensor(
        device_data,
        "1",
        "lastStatusUpdate",
        {"name": "Last Update"},
        HcuTimestampSensor,
    )
    assert entity.native_value == "2023-11-14T22:13:20+00:00"

    # None value
    device_data["functionalChannels"]["1"]["lastStatusUpdate"] = None
    assert entity.native_value is None

    # Zero or negative timestamp
    device_data["functionalChannels"]["1"]["lastStatusUpdate"] = 0
    assert entity.native_value is None
    device_data["functionalChannels"]["1"]["lastStatusUpdate"] = -5000
    assert entity.native_value is None

    # Timestamp beyond year 9999 (> 253402300799000)
    device_data["functionalChannels"]["1"]["lastStatusUpdate"] = 300000000000000
    assert entity.native_value is None

    # Non-numeric string / ValueError
    device_data["functionalChannels"]["1"]["lastStatusUpdate"] = "not-a-number"
    assert entity.native_value is None

    # Overflow / huge number
    device_data["functionalChannels"]["1"]["lastStatusUpdate"] = "1e400"
    assert entity.native_value is None
