"""Unit tests for the HCU select platform."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

import aiohttp
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, State
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.select import (
    HcuAlarmSignalAcoustic,
    HcuAlarmSignalOptical,
    HcuPowerUpSwitchState,
    async_setup_entry,
)


def _make_power_up_entity(
    device_data: dict,
    channel_index: str = "1",
    feature: str = "powerUpSwitchState",
) -> tuple[HcuPowerUpSwitchState, MagicMock]:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_set_power_up_switch_state = AsyncMock()

    mapping = {"name": "Power Up State"}
    entity = HcuPowerUpSwitchState(
        coordinator, client, device_data, channel_index, feature, mapping
    )
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_alarm_acoustic_entity(
    group_data: dict,
) -> tuple[HcuAlarmSignalAcoustic, MagicMock]:
    gid = group_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {gid: group_data}

    client = MagicMock()
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.hcu_device_id = "hcu-1"
    client.async_test_alarm_signal_acoustic = AsyncMock()

    entity = HcuAlarmSignalAcoustic(coordinator, client, group_data)
    entity.platform_data = MagicMock(
        platform_name="hcu_integration",
        domain="select",
        platform_translations={},
    )
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_alarm_optical_entity(
    group_data: dict,
) -> tuple[HcuAlarmSignalOptical, MagicMock]:
    gid = group_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {gid: group_data}

    client = MagicMock()
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.hcu_device_id = "hcu-1"
    client.async_test_alarm_signal_optical = AsyncMock()

    entity = HcuAlarmSignalOptical(coordinator, client, group_data)
    entity.platform_data = MagicMock(
        platform_name="hcu_integration",
        domain="select",
        platform_translations={},
    )
    entity.async_write_ha_state = MagicMock()
    return entity, client


@pytest.mark.asyncio
async def test_select_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.SELECT: [mock_entity]}
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


def test_power_up_switch_state_properties() -> None:
    """Test powerUpSwitchState entity properties and option mapping."""
    device_data = {
        "id": "dev-psm-1",
        "label": "Coffee Plug",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "SWITCH_MEASURING",
                "label": "Plug",
                "powerUpSwitchState": "PERMANENT_ON",
            },
        },
    }
    entity, _ = _make_power_up_entity(device_data)

    assert entity.unique_id == "dev-psm-1_1_powerUpSwitchState"
    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.entity_registry_enabled_default is False
    assert entity.options == ["permanent_off", "permanent_on"]
    assert entity.current_option == "permanent_on"

    # Coordinator update calls write state
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_called_once()

    # When PERMANENT_OFF
    device_data["functionalChannels"]["1"]["powerUpSwitchState"] = "PERMANENT_OFF"
    assert entity.current_option == "permanent_off"

    # When missing or unknown
    device_data["functionalChannels"]["1"]["powerUpSwitchState"] = None
    assert entity.current_option is None
    device_data["functionalChannels"]["1"]["powerUpSwitchState"] = "UNKNOWN_VAL"
    assert entity.current_option is None


@pytest.mark.asyncio
async def test_power_up_switch_state_select_option_success() -> None:
    """Test selecting option calls API successfully."""
    device_data = {
        "id": "dev-psm-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "SWITCH_MEASURING"},
        },
    }
    entity, client = _make_power_up_entity(device_data)

    await entity.async_select_option("permanent_off")
    client.async_set_power_up_switch_state.assert_awaited_once_with(
        "dev-psm-1", 1, "PERMANENT_OFF"
    )

    client.async_set_power_up_switch_state.reset_mock()
    await entity.async_select_option("permanent_on")
    client.async_set_power_up_switch_state.assert_awaited_once_with(
        "dev-psm-1", 1, "PERMANENT_ON"
    )


@pytest.mark.asyncio
async def test_power_up_switch_state_select_option_errors(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test selecting option error handling (400, 500, HcuApiError, ConnectionError)."""
    device_data = {
        "id": "dev-psm-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "SWITCH_MEASURING"},
        },
    }
    entity, client = _make_power_up_entity(device_data)

    # 1. HTTP 400 error
    request_info = MagicMock()
    client.async_set_power_up_switch_state.side_effect = aiohttp.ClientResponseError(
        request_info=request_info, history=(), status=400, message="Bad Request"
    )
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("permanent_off")
    assert "The App User may not have sufficient permissions" in caplog.text

    # 2. HTTP 500 error
    caplog.clear()
    client.async_set_power_up_switch_state.side_effect = aiohttp.ClientResponseError(
        request_info=request_info, history=(), status=500, message="Server Error"
    )
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("permanent_off")
    assert "Failed to set powerUpSwitchState for dev-psm-1 channel 1" in caplog.text

    # 3. HcuApiError
    caplog.clear()
    client.async_set_power_up_switch_state.side_effect = HcuApiError("API failure")
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("permanent_off")
    assert (
        "Failed to set powerUpSwitchState for dev-psm-1 channel 1: API failure"
        in caplog.text
    )

    # 4. ConnectionError
    caplog.clear()
    client.async_set_power_up_switch_state.side_effect = ConnectionError("Net down")
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("permanent_off")
    assert (
        "Failed to set powerUpSwitchState for dev-psm-1 channel 1: Net down"
        in caplog.text
    )


def test_alarm_signal_base_device_info() -> None:
    """Test device_info renaming for SIREN vs other groups."""
    group_siren = {
        "id": "group-alarm-1",
        "type": "ALARM_SWITCHING",
        "label": "SIREN",
        "channels": [],
    }
    entity_siren, _ = _make_alarm_acoustic_entity(group_siren)
    assert entity_siren.device_info["name"] == "Indoor Sirene"

    group_other = {
        "id": "group-alarm-2",
        "type": "ALARM_SWITCHING",
        "label": "Other Alarm",
        "channels": [],
    }
    entity_other, _ = _make_alarm_acoustic_entity(group_other)
    assert entity_other.device_info["name"] == "Other Alarm"

    group_no_label = {
        "id": "group-alarm-3",
        "type": "ALARM_SWITCHING",
        "label": None,
        "channels": [],
    }
    entity_no_label, _ = _make_alarm_acoustic_entity(group_no_label)
    assert "name" in entity_no_label.device_info


@pytest.mark.asyncio
async def test_alarm_signal_acoustic_state_and_actions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test acoustic alarm signal restore state, selection, and error handling."""
    group_data = {
        "id": "group-alarm-1",
        "type": "ALARM_SWITCHING",
        "label": "Alarm Group",
        "channels": [],
    }
    entity, client = _make_alarm_acoustic_entity(group_data)

    assert entity.unique_id == "group-alarm-1_test_signal_acoustic"
    assert entity.translation_key == "alarm_test_signal_acoustic"
    assert "frequency_rising" in entity.options
    assert entity.current_option is None

    # Restoration with valid option
    entity.async_get_last_state = AsyncMock(
        return_value=State("select.alarm_acoustic", "frequency_rising")
    )
    await entity.async_added_to_hass()
    assert entity.current_option == "frequency_rising"

    # Restoration with invalid option
    entity.async_get_last_state = AsyncMock(
        return_value=State("select.alarm_acoustic", "non_existent_option")
    )
    await entity.async_added_to_hass()
    assert entity.current_option == "frequency_rising"  # remains previous

    # Restoration with None
    entity._current_option = None
    entity.async_get_last_state = AsyncMock(return_value=None)
    await entity.async_added_to_hass()
    assert entity.current_option is None

    # Coordinator update
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_called_once()
    entity.async_write_ha_state.reset_mock()

    # Successful select_option
    await entity.async_select_option("frequency_falling")
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "group-alarm-1", "FREQUENCY_FALLING"
    )
    assert entity.current_option == "disable_acoustic_signal"
    entity.async_write_ha_state.assert_called_once()

    # Error handling in select_option: HcuApiError
    caplog.clear()
    client.async_test_alarm_signal_acoustic.reset_mock()
    client.async_test_alarm_signal_acoustic.side_effect = HcuApiError(
        "Device unreachable"
    )
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("frequency_rising")
    assert "Failed to test acoustic signal" in caplog.text
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "group-alarm-1", "FREQUENCY_RISING"
    )

    # Error handling in select_option: ConnectionError
    caplog.clear()
    client.async_test_alarm_signal_acoustic.reset_mock()
    client.async_test_alarm_signal_acoustic.side_effect = ConnectionError("Offline")
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("frequency_rising")
    assert "Failed to test acoustic signal" in caplog.text
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "group-alarm-1", "FREQUENCY_RISING"
    )


@pytest.mark.asyncio
async def test_alarm_signal_optical_state_and_actions(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optical alarm signal restore state, selection, and error handling."""
    group_data = {
        "id": "group-alarm-2",
        "type": "ALARM_SWITCHING",
        "label": "Alarm Group Optical",
        "channels": [],
    }
    entity, client = _make_alarm_optical_entity(group_data)

    assert entity.unique_id == "group-alarm-2_test_signal_optical"
    assert entity.translation_key == "alarm_test_signal_optical"
    assert "blinking_both_repeating" in entity.options
    assert entity.current_option is None

    # Restoration with valid option
    entity.async_get_last_state = AsyncMock(
        return_value=State("select.alarm_optical", "blinking_both_repeating")
    )
    await entity.async_added_to_hass()
    assert entity.current_option == "blinking_both_repeating"

    # Restoration with invalid option
    entity.async_get_last_state = AsyncMock(
        return_value=State("select.alarm_optical", "invalid_choice")
    )
    await entity.async_added_to_hass()
    assert entity.current_option == "blinking_both_repeating"

    # Restoration with None
    entity._current_option = None
    entity.async_get_last_state = AsyncMock(return_value=None)
    await entity.async_added_to_hass()
    assert entity.current_option is None

    # Coordinator update
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_called_once()
    entity.async_write_ha_state.reset_mock()

    # Successful select_option
    await entity.async_select_option("double_flashing_repeating")
    client.async_test_alarm_signal_optical.assert_awaited_once_with(
        "group-alarm-2", "DOUBLE_FLASHING_REPEATING"
    )
    assert entity.current_option == "disable_optical_signal"
    entity.async_write_ha_state.assert_called_once()

    # Error handling in select_option: HcuApiError
    caplog.clear()
    client.async_test_alarm_signal_optical.reset_mock()
    client.async_test_alarm_signal_optical.side_effect = HcuApiError("Call failed")
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("confirmation_signal_0")
    assert "Failed to test optical signal" in caplog.text
    client.async_test_alarm_signal_optical.assert_awaited_once_with(
        "group-alarm-2", "CONFIRMATION_SIGNAL_0"
    )

    # Error handling in select_option: ConnectionError
    caplog.clear()
    client.async_test_alarm_signal_optical.reset_mock()
    client.async_test_alarm_signal_optical.side_effect = ConnectionError("Disconnected")
    with caplog.at_level(logging.ERROR):
        await entity.async_select_option("confirmation_signal_0")
    assert "Failed to test optical signal" in caplog.text
    client.async_test_alarm_signal_optical.assert_awaited_once_with(
        "group-alarm-2", "CONFIRMATION_SIGNAL_0"
    )
