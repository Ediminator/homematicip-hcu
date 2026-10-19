"""Unit tests for the HCU binary_sensor platform."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.binary_sensor import (
    HcuBinarySensor,
    HcuDoorBinarySensor,
    HcuHeatDemandBinarySensorGroup,
    HcuSecurityAlarmBinarySensor,
    HcuSmokeBinarySensor,
    HcuUnreachBinarySensor,
    HcuVacationModeBinarySensor,
    HcuWindowBinarySensor,
    async_setup_entry,
)
from custom_components.hcu_integration.const import (
    ABSENCE_TYPE_PARTY,
    ABSENCE_TYPE_PERIOD,
    ABSENCE_TYPE_VACATION,
    DOMAIN,
)


def _make_binary_sensor(
    device_data: dict,
    channel_index: str = "1",
    feature: str = "state",
    mapping: dict | None = None,
    cls: type[HcuBinarySensor] = HcuBinarySensor,
) -> HcuBinarySensor:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    m = mapping or {"name": "Test Binary Sensor"}
    entity = cls(coordinator, client, device_data, channel_index, feature, m)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_binary_sensor_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.BINARY_SENSOR: [mock_entity]}
    entry.runtime_data = mock_coordinator

    added = []

    def mock_add_entities(entities: list) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == [mock_entity]

    mock_coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == []


def test_generic_binary_sensor_properties_and_mapping() -> None:
    """Test HcuBinarySensor mapping, custom on_state, and boolean conversion."""
    device_data = {
        "id": "dev-sensor-1",
        "label": "Motion Detector",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "MOTION_DETECTION_CHANNEL",
                "label": "Hallway Motion",
                "motion": True,
            },
        },
    }
    mapping = {
        "name": "Motion",
        "device_class": BinarySensorDeviceClass.MOTION,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "on_state": True,
    }
    entity = _make_binary_sensor(device_data, "1", "motion", mapping, HcuBinarySensor)

    assert entity.unique_id == "dev-sensor-1_1_motion"
    assert entity.device_class == BinarySensorDeviceClass.MOTION
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.entity_registry_enabled_default is False
    assert entity.is_on is True

    # on_state mismatch
    device_data["functionalChannels"]["1"]["motion"] = False
    assert entity.is_on is False

    # Value is None -> is_on is None
    device_data["functionalChannels"]["1"]["motion"] = None
    assert entity.is_on is None

    # Without on_state (fallback to bool(value))
    mapping_no_on_state = {"name": "Presence"}
    entity2 = _make_binary_sensor(
        device_data, "1", "motion", mapping_no_on_state, HcuBinarySensor
    )
    device_data["functionalChannels"]["1"]["motion"] = "non-empty-string"
    assert entity2.is_on is True
    device_data["functionalChannels"]["1"]["motion"] = ""
    assert entity2.is_on is False


def test_window_and_door_binary_sensor() -> None:
    """Test window and door binary sensor OPEN/TILTED states."""
    device_data = {
        "id": "dev-contact-1",
        "label": "Window Contact",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "SHUTTER_CONTACT_CHANNEL",
                "windowState": "OPEN",
            },
        },
    }
    window_entity = _make_binary_sensor(
        device_data, "1", "windowState", {"name": "Window"}, HcuWindowBinarySensor
    )
    assert window_entity.translation_key == "hcu_window"
    assert window_entity.is_on is True

    device_data["functionalChannels"]["1"]["windowState"] = "TILTED"
    assert window_entity.is_on is True

    device_data["functionalChannels"]["1"]["windowState"] = "CLOSED"
    assert window_entity.is_on is False

    door_entity = _make_binary_sensor(
        device_data, "1", "windowState", {"name": "Door"}, HcuDoorBinarySensor
    )
    assert door_entity.translation_key == "hcu_door"
    assert door_entity.is_on is False


def test_smoke_binary_sensor() -> None:
    """Test smoke detector primary and secondary alarms."""
    device_data = {
        "id": "dev-smoke-1",
        "label": "Smoke Detector",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "SMOKE_DETECTOR_CHANNEL",
                "smokeDetectorAlarmType": "PRIMARY_ALARM",
            },
        },
    }
    smoke_entity = _make_binary_sensor(
        device_data,
        "1",
        "smokeDetectorAlarmType",
        {"name": "Smoke"},
        HcuSmokeBinarySensor,
    )
    assert smoke_entity.is_on is True

    device_data["functionalChannels"]["1"]["smokeDetectorAlarmType"] = "SECONDARY_ALARM"
    assert smoke_entity.is_on is True

    device_data["functionalChannels"]["1"]["smokeDetectorAlarmType"] = "IDLE_OFF"
    assert smoke_entity.is_on is False


def test_unreach_binary_sensor() -> None:
    """Test unreach sensor connection inverted logic."""
    device_data = {
        "id": "dev-unreach-1",
        "label": "Battery Device",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "unreach": False,
            },
        },
    }
    entity = _make_binary_sensor(
        device_data, "0", "unreach", {"name": "Connected"}, HcuUnreachBinarySensor
    )
    # unreach is False -> device is connected -> is_on is True (not value)
    assert entity.is_on is True

    # unreach is True -> device unreachable -> is_on is False
    device_data["functionalChannels"]["0"]["unreach"] = True
    assert entity.is_on is False

    # unreach is None -> is_on is False
    device_data["functionalChannels"]["0"]["unreach"] = None
    assert entity.is_on is False


def test_security_alarm_binary_sensor() -> None:
    """Test HcuSecurityAlarmBinarySensor for safety and intrusion alarms."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {}

    client = MagicMock()
    client.hcu_device_id = "hcu-home"
    client.state = {
        "home": {
            "functionalHomes": {
                "SECURITY_AND_ALARM_ID": {
                    "solution": "SECURITY_AND_ALARM",
                    "safetyAlarmActive": True,
                    "alarmActive": False,
                }
            }
        }
    }

    sensor_safety = HcuSecurityAlarmBinarySensor(
        coordinator, client, flag="safetyAlarmActive", key="safety_alarm"
    )
    assert sensor_safety.unique_id == "hcu-home_safety_alarm"
    assert sensor_safety.translation_key == "hcu_safety_alarm"
    assert sensor_safety.device_class == BinarySensorDeviceClass.SAFETY
    assert sensor_safety.is_on is True

    sensor_intrusion = HcuSecurityAlarmBinarySensor(
        coordinator, client, flag="alarmActive", key="intrusion_alarm"
    )
    assert sensor_intrusion.is_on is False

    # Missing security home returns None
    client.state = {"home": {}}
    assert sensor_safety.is_on is None


def test_vacation_mode_binary_sensor_absence_types(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test vacation mode sensor under various absence types and datetime parsing."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {"hcu-main": {}}

    client = MagicMock()
    client.hcu_device_id = "hcu-main"
    client.get_device_by_address = MagicMock(return_value={"id": "hcu-main"})

    # 1. VACATION mode with valid dates
    client.state = {
        "home": {
            "functionalHomes": {
                "INDOOR_CLIMATE": {
                    "absenceType": ABSENCE_TYPE_VACATION,
                    "absenceStartTime": "2026_01_01 10:00",
                    "absenceEndTime": "2026_01_10 18:00",
                    "lastVacationTemperature": 17.0,
                }
            }
        }
    }
    vacation_sensor = HcuVacationModeBinarySensor(coordinator, client)
    vacation_sensor.async_write_ha_state = MagicMock()

    assert vacation_sensor.unique_id == "hcu-main_vacation_mode"
    assert vacation_sensor.icon == "mdi:palm-tree"
    assert vacation_sensor.translation_key == "hcu_vacation_mode"

    attrs = vacation_sensor.extra_state_attributes
    assert attrs["type"] == ABSENCE_TYPE_VACATION
    assert attrs["target_temperature"] == 17.0
    assert "2026-01-01T10:00" in attrs["start_time"]
    # Because start time is in the past, is_on should be True
    assert vacation_sensor.is_on is True

    # Future start time -> is_on is False
    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"]["absenceStartTime"] = (
        "2099_01_01 10:00"
    )
    vacation_sensor._handle_coordinator_update()
    assert vacation_sensor.is_on is False

    # Missing absenceStartTime (tests if not time_str -> None)
    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"]["absenceStartTime"] = None
    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"]["absenceEndTime"] = None
    vacation_sensor._handle_coordinator_update()
    assert vacation_sensor.extra_state_attributes["start_time"] is None
    assert vacation_sensor.is_on is False

    # Invalid start time string -> logs warning, is_on is False
    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"]["absenceStartTime"] = (
        "invalid_format"
    )
    with caplog.at_level(logging.WARNING):
        vacation_sensor._handle_coordinator_update()
    assert "Could not parse HCU start time" in caplog.text

    # Manually corrupted extra_state_attributes start_time -> logs warning in is_on
    vacation_sensor._attr_extra_state_attributes["start_time"] = "bad-iso"
    with caplog.at_level(logging.WARNING):
        assert vacation_sensor.is_on is False
    assert "Invalid start_time format" in caplog.text

    # Missing start time in attributes -> is_on is False
    vacation_sensor._attr_extra_state_attributes["start_time"] = None
    assert vacation_sensor.is_on is False

    # 2. PERIOD or PERMANENT mode
    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"] = {
        "absenceType": ABSENCE_TYPE_PERIOD,
        "absenceStartTime": "2026_02_01 08:00",
        "absenceEndTime": "2026_02_05 18:00",
        "ecoTemperature": 18.5,
    }
    vacation_sensor._handle_coordinator_update()
    attrs = vacation_sensor.extra_state_attributes
    assert attrs["type"] == ABSENCE_TYPE_PERIOD
    assert attrs["target_temperature"] == 18.5
    # Since type is not VACATION, is_on is False
    assert vacation_sensor.is_on is False

    # 3. PARTY or NOT_ABSENT mode resets attributes
    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"] = {
        "absenceType": ABSENCE_TYPE_PARTY,
    }
    vacation_sensor._handle_coordinator_update()
    attrs = vacation_sensor.extra_state_attributes
    assert attrs["type"] is None
    assert attrs["start_time"] is None
    assert attrs["target_temperature"] is None


def test_heat_demand_group_binary_sensor() -> None:
    """Test boiler and pump heat demand group binary sensors."""
    groups = {
        "group-boiler-1": {
            "id": "group-boiler-1",
            "type": "HEATING_COOLING_DEMAND_BOILER",
            "label": "Boiler",
            "heatDemand": True,
            "channels": [],
        },
        "group-pump-1": {
            "id": "group-pump-1",
            "type": "HEATING_COOLING_DEMAND_PUMP",
            "label": "Pump",
            "heatDemand": False,
            "channels": [],
        },
        "group-demand-1": {
            "id": "group-demand-1",
            "type": "OTHER_HEAT_DEMAND",
            "heatDemand": False,
            "channels": [],
        },
    }

    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = groups
    client = MagicMock()
    client.hcu_device_id = "hcu-1"
    client.get_group_by_id = MagicMock(side_effect=groups.get)

    sensor_boiler = HcuHeatDemandBinarySensorGroup(
        coordinator, client, groups["group-boiler-1"]
    )
    assert sensor_boiler.device_class == BinarySensorDeviceClass.HEAT
    assert sensor_boiler.is_on is True

    sensor_pump = HcuHeatDemandBinarySensorGroup(
        coordinator, client, groups["group-pump-1"]
    )
    assert sensor_pump.is_on is False

    sensor_other = HcuHeatDemandBinarySensorGroup(
        coordinator, client, groups["group-demand-1"]
    )
    assert sensor_other.is_on is False
