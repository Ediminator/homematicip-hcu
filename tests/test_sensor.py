"""Unit tests for the HCU sensor platform."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, ProcessEventsResult
from custom_components.hcu_integration.const import (
    DOMAIN,
    HMIP_FEATURE_TO_ENTITY,
    HMIP_ON_TIME_INFINITE,
)
from custom_components.hcu_integration.sensor import (
    HcuGenericSensor,
    HcuGroupOnTimeSensor,
    HcuHomeSensor,
    HcuTemperatureSensor,
    HcuTimestampSensor,
    HcuValveStateSensor,
    HcuWindowStateSensor,
    async_setup_entry,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")


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
        "device_class": SensorDeviceClass.POWER_FACTOR,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:signal",
        "entity_registry_enabled_default": True,
    }
    sensor_cs = HcuHomeSensor(coordinator, client, "carrierSense", mapping_cs)
    assert sensor_cs.unique_id == "hcu-home_carrierSense"
    assert sensor_cs.name == "Carrier Sense"
    assert sensor_cs.native_value == 3.5
    assert sensor_cs.device_class == SensorDeviceClass.POWER_FACTOR
    assert sensor_cs.native_unit_of_measurement == "%"
    assert sensor_cs.state_class == SensorStateClass.MEASUREMENT
    assert sensor_cs.entity_registry_enabled_default is True

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
        "device_class": SensorDeviceClass.BATTERY,
        "unit": "%",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:valve",
        "suggested_display_precision": 1,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": True,
    }
    sensor_valve = _make_generic_sensor(
        device_data, "1", "valvePosition", mapping, HcuGenericSensor
    )
    assert sensor_valve.unique_id == "dev-valve-1_1_valvePosition"
    assert sensor_valve.has_entity_name is True
    assert sensor_valve.name == "Heater Channel Valve Position"
    assert sensor_valve.device_class == SensorDeviceClass.BATTERY
    assert sensor_valve.native_unit_of_measurement == "%"
    assert sensor_valve.state_class == SensorStateClass.MEASUREMENT
    assert sensor_valve.suggested_display_precision == 1
    assert sensor_valve.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor_valve.entity_registry_enabled_default is True
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
    """Test smart naming and translation keys for various energyCounter types."""
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
        ("ENERGY_COUNTER_USAGE_HIGH_TARIFF", "energy_usage_high_tariff"),
        ("ENERGY_COUNTER_USAGE_LOW_TARIFF", "energy_usage_low_tariff"),
        ("ENERGY_COUNTER_INPUT_SINGLE_TARIFF", "energy_feed_in"),
        ("ENERGY_COUNTER_INPUT_HIGH_TARIFF", "energy_feed_in_high_tariff"),
        ("ENERGY_COUNTER_INPUT_LOW_TARIFF", "energy_feed_in_low_tariff"),
    ]

    for c_type, expected_trans_key in types_and_expected:
        channel_data["energyCounterUsageType"] = c_type
        sensor = _make_generic_sensor(
            device_data,
            "1",
            "energyCounterUsage",
            {"name": "Base Energy", "translation_key": "energy_counter"},
            HcuGenericSensor,
        )
        assert sensor.translation_key == expected_trans_key
        assert sensor.translation_placeholders == {
            "channel": "Electricity Meter ",
            "channel_index": "",
        }

    # Fallback to base translation_key when unknown or unmapped
    for c_type in ("UNKNOWN", "OTHER_UNMAPPED_TYPE"):
        channel_data["energyCounterUsageType"] = c_type
        sensor = _make_generic_sensor(
            device_data,
            "1",
            "energyCounterUsage",
            {"name": "Base Energy", "translation_key": "energy_counter"},
            HcuGenericSensor,
        )
        assert sensor.translation_key == "energy_counter"


@pytest.mark.parametrize(
    ("tariff_type", "expected_en", "expected_de"),
    [
        (
            "ENERGY_COUNTER_USAGE_HIGH_TARIFF",
            "Electricity Meter Energy Usage (High Tariff)",
            "Electricity Meter Energieverbrauch (Hochtarif)",
        ),
        (
            "ENERGY_COUNTER_USAGE_LOW_TARIFF",
            "Electricity Meter Energy Usage (Low Tariff)",
            "Electricity Meter Energieverbrauch (Niedertarif)",
        ),
        (
            "ENERGY_COUNTER_INPUT_SINGLE_TARIFF",
            "Electricity Meter Energy Feed-in",
            "Electricity Meter Energieeinspeisung",
        ),
        (
            "ENERGY_COUNTER_INPUT_HIGH_TARIFF",
            "Electricity Meter Energy Feed-in (High Tariff)",
            "Electricity Meter Energieeinspeisung (Hochtarif)",
        ),
        (
            "ENERGY_COUNTER_INPUT_LOW_TARIFF",
            "Electricity Meter Energy Feed-in (Low Tariff)",
            "Electricity Meter Energieeinspeisung (Niedertarif)",
        ),
    ],
)
@pytest.mark.asyncio
async def test_energy_counter_tariff_translations_en_and_de(
    hass: HomeAssistant,
    tariff_type: str,
    expected_en: str,
    expected_de: str,
) -> None:
    """Test energy counter tariff names are translated into English and German."""
    channel_data = {
        "functionalChannelType": "ENERGY_COUNTER_CHANNEL",
        "energyCounter": 123.4,
        "energyCounterType": tariff_type,
    }
    device_data = {
        "id": "dev-meter-1",
        "label": "Electricity Meter",
        "modelType": "HmIP-ESI",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": channel_data,
        },
    }

    client = MagicMock(spec=HcuApiClient)
    client._auth_type = "app"
    client.plugin_id = "plugin-1"
    client.hcu_device_id = "hcu-1"
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.state = {"devices": {"dev-meter-1": device_data}, "groups": {}, "home": {}}
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.get_group_by_id = MagicMock(return_value=None)
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()

    for lang, expected_name in [("en", expected_en), ("de", expected_de)]:
        hass.config.language = lang
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Homematic IP HCU",
            version=7,
            data={"host": "192.0.2.10", "auth_type": "app"},
            unique_id=f"hcu-test-{tariff_type}-{lang}",
        )
        entry.add_to_hass(hass)

        with (
            patch(
                "custom_components.hcu_integration.HcuApiClient", return_value=client
            ),
            patch(
                "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
                AsyncMock(return_value=True),
            ),
        ):
            assert await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        reg = er.async_get(hass)
        entries = er.async_entries_for_config_entry(reg, entry.entry_id)
        usage_entries = [e for e in entries if e.unique_id.endswith("_energyCounter")]
        assert len(usage_entries) == 1
        state = hass.states.get(usage_entries[0].entity_id)
        assert state is not None
        assert state.attributes.get("friendly_name") == expected_name

        await hass.config_entries.async_unload(entry.entry_id)
        await hass.async_block_till_done()


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
    assert entity.device_class == SensorDeviceClass.ENUM
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
        {"name": "Last Update", "device_class": SensorDeviceClass.TIMESTAMP},
        HcuTimestampSensor,
    )
    assert entity.device_class == SensorDeviceClass.TIMESTAMP
    assert entity.native_value == datetime(2023, 11, 14, 22, 13, 20, tzinfo=UTC)
    assert entity.state == "2023-11-14T22:13:20+00:00"

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


@pytest.mark.parametrize(
    "feature",
    [
        "carrierSense",
        "dutyCycle",
        "accelerationSensorValueX",
        "accelerationSensorValueY",
        "accelerationSensorValueZ",
        "accelerationSensorEventCounter",
        "absoluteAngle",
    ],
)
def test_technical_sensors_are_diagnostic(feature: str) -> None:
    """Radio traffic, duty cycle and raw acceleration values are diagnostic entities."""
    from custom_components.hcu_integration.const import HMIP_FEATURE_TO_ENTITY

    mapping = HMIP_FEATURE_TO_ENTITY[feature]
    assert mapping["entity_category"] == EntityCategory.DIAGNOSTIC

    if mapping["class"] == "HcuHomeSensor":
        coordinator = MagicMock()
        client = MagicMock()
        client.hcu_device_id = "hcu-home"
        client.state = {"home": {"id": "home-1", feature: 1.0}}
        sensor = HcuHomeSensor(coordinator, client, feature, mapping)
        assert sensor.entity_category == EntityCategory.DIAGNOSTIC


def test_valve_state_sensor() -> None:
    """Test HcuValveStateSensor maps HCU values to its enum options."""
    device_data = {
        "id": "dev-etrv-1",
        "label": "Radiator",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_OPERATIONLOCK"},
            "1": {
                "functionalChannelType": "HEATING_THERMOSTAT_CHANNEL",
                "valveState": "ADAPTION_DONE",
            },
        },
    }
    coordinator = MagicMock()
    coordinator.data = {"dev-etrv-1": device_data}
    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuValveStateSensor(
        coordinator,
        client,
        device_data,
        "1",
        "valveState",
        HMIP_FEATURE_TO_ENTITY["valveState"],
    )
    assert entity.unique_id == "dev-etrv-1_1_valveState"
    assert entity.translation_key == "valve_state"
    assert entity.device_class == SensorDeviceClass.ENUM
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.native_value == "adaption_done"

    channel = device_data["functionalChannels"]["1"]
    channel["valveState"] = "ADJUSTMENT_TOO_BIG"
    assert entity.native_value == "adjustment_too_big"
    channel["valveState"] = "SOMETHING_NEW"
    assert entity.native_value is None
    channel["valveState"] = None
    assert entity.native_value is None
