"""Coverage tests for HCU valve platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.valve import ValveDeviceClass, ValveEntityFeature
from homeassistant.const import STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import DOMAIN, HMIP_ON_TIME_INFINITE
from custom_components.hcu_integration.valve import HcuWateringSwitch, async_setup_entry


def _create_valve(
    hass: HomeAssistant,
    *,
    device_id: str = "valve-dev-1",
    channel_index: str = "1",
    channel_data: dict | None = None,
    device_channels: dict | None = None,
) -> tuple[HcuWateringSwitch, MagicMock, MagicMock]:
    """Create an HcuWateringSwitch test entity with mocks."""
    ch_data = {
        "functionalChannelType": "WATERING_ACTUATOR_CHANNEL",
        "label": "Garden Valve",
        "wateringActive": False,
        "wateringOnTime": 600,
    }
    if channel_data:
        ch_data.update(channel_data)

    func_channels = {
        "0": {"functionalChannelType": "DEVICE_BASE"},
        channel_index: ch_data,
    }
    if device_channels:
        func_channels.update(device_channels)

    device = {
        "id": device_id,
        "label": "Watering Valve",
        "type": "WATERING_COMPUTER",
        "functionalChannels": func_channels,
    }

    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {device_id: device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_set_watering_switch_state = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {device_id: device}
    coordinator.client = client
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}

    valve = HcuWateringSwitch(coordinator, client, device, channel_index)
    valve.hass = hass
    return valve, coordinator, client


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test platform setup with and without valve entities."""
    entry = MagicMock()
    coordinator = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    # Case 1: No valve entities
    coordinator.entities = {}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

    # Case 2: Valve entities present
    valve_entity = MagicMock()
    coordinator.entities = {Platform.VALVE: [valve_entity]}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([valve_entity])


def test_valve_initialization_and_naming(hass: HomeAssistant) -> None:
    """Test valve initialization and naming when no label and multiple channels."""
    device_channels = {
        "1": {"functionalChannelType": "WATERING_ACTUATOR_CHANNEL", "label": None},
        "2": {"functionalChannelType": "WATERING_ACTUATOR_CHANNEL", "label": None},
    }
    valve, _, _ = _create_valve(
        hass,
        channel_index="1",
        channel_data={"label": None},
        device_channels=device_channels,
    )
    assert valve.unique_id == "valve-dev-1_1_watering"
    assert valve.device_class == ValveDeviceClass.WATER
    assert valve.reports_position is False
    assert (
        valve.supported_features == ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    )


def test_valve_states_and_coordinator_update(hass: HomeAssistant) -> None:
    """Test is_closed and coordinator updates."""
    valve_active, _, _ = _create_valve(hass, channel_data={"wateringActive": True})
    assert valve_active.is_closed is False

    valve_inactive, _, _ = _create_valve(hass, channel_data={"wateringActive": False})
    assert valve_inactive.is_closed is True

    valve_inactive.async_write_ha_state = MagicMock()
    valve_inactive._channel["wateringActive"] = True
    valve_inactive._handle_coordinator_update()
    assert valve_inactive.is_closed is False
    assert valve_inactive.assumed_state is False


def test_get_internal_on_time(hass: HomeAssistant) -> None:
    """Test _get_internal_on_time under various conditions."""
    valve, _, _ = _create_valve(
        hass,
        device_id="valve-dev-1",
        channel_index="1",
        channel_data={"wateringOnTime": 300},
    )
    registry = er.async_get(hass)
    companion_uid = "valve-dev-1_1_use_internal_on_time"

    # 1. Companion entity not in registry
    assert valve._get_internal_on_time() is None

    # 2. Companion entity registered, but state is None
    entry = registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id=companion_uid,
    )
    assert valve._get_internal_on_time() is None

    # 3. Companion entity state is OFF
    hass.states.async_set(entry.entity_id, STATE_OFF)
    assert valve._get_internal_on_time() is None

    # 4. Companion entity state is ON, but on_time is 0
    valve._channel["wateringOnTime"] = 0
    hass.states.async_set(entry.entity_id, STATE_ON)
    assert valve._get_internal_on_time() is None

    # 5. Companion entity state is ON, but on_time is HMIP_ON_TIME_INFINITE
    valve._channel["wateringOnTime"] = HMIP_ON_TIME_INFINITE
    assert valve._get_internal_on_time() is None

    # 6. Companion entity state is ON, on_time is valid
    valve._channel["wateringOnTime"] = 300
    assert valve._get_internal_on_time() == 300.0


async def test_async_open_valve_without_internal_on_time(hass: HomeAssistant) -> None:
    """Test opening valve without companion internal on time."""
    valve, _, client = _create_valve(hass)
    valve.async_write_ha_state = MagicMock()

    valve.async_write_ha_state.reset_mock()
    await valve.async_open_valve()
    valve.async_write_ha_state.assert_called()
    assert valve.assumed_state is True
    client.async_set_watering_switch_state.assert_awaited_once_with(
        "valve-dev-1", 1, True
    )
    assert valve.is_closed is False

    # Test error handling (HcuApiError) reverts is_closed to True
    client.async_set_watering_switch_state.side_effect = HcuApiError("Command failed")
    with pytest.raises(HomeAssistantError) as exc_info:
        await valve.async_open_valve()
    assert exc_info.value.translation_key == "command_failed"
    assert valve.is_closed is True
    assert valve.assumed_state is False

    # Test error handling (ConnectionError)
    client.async_set_watering_switch_state.side_effect = ConnectionError("Disconnected")
    with pytest.raises(HomeAssistantError) as exc_info:
        await valve.async_open_valve()
    assert exc_info.value.translation_key == "command_failed"
    assert valve.is_closed is True
    assert valve.assumed_state is False


async def test_async_open_valve_with_internal_on_time(hass: HomeAssistant) -> None:
    """Test opening valve when internal on-time switch is active."""
    valve, _, client = _create_valve(
        hass,
        device_id="valve-dev-2",
        channel_index="1",
        channel_data={"wateringOnTime": 450},
    )
    valve.async_write_ha_state = MagicMock()
    registry = er.async_get(hass)
    entry = registry.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id="valve-dev-2_1_use_internal_on_time",
    )
    hass.states.async_set(entry.entity_id, STATE_ON)

    # Success call delegates to async_turn_on_with_time
    valve.async_write_ha_state.reset_mock()
    await valve.async_open_valve()
    valve.async_write_ha_state.assert_called()
    assert valve.assumed_state is True
    assert valve.is_closed is False
    client.async_set_watering_switch_state.assert_awaited_once_with(
        "valve-dev-2", 1, True, on_time=450.0
    )

    # Error call in async_open_valve with internal on time
    client.async_set_watering_switch_state.side_effect = HcuApiError("Timed error")
    with pytest.raises(HomeAssistantError) as exc_info:
        await valve.async_open_valve()
    assert exc_info.value.translation_key == "command_failed"
    assert valve.is_closed is True


async def test_async_close_valve(hass: HomeAssistant) -> None:
    """Test closing valve and error recovery."""
    valve, _, client = _create_valve(hass, channel_data={"wateringActive": True})
    valve.async_write_ha_state = MagicMock()

    # Success call
    valve.async_write_ha_state.reset_mock()
    await valve.async_close_valve()
    valve.async_write_ha_state.assert_called()
    assert valve.assumed_state is True
    client.async_set_watering_switch_state.assert_awaited_once_with(
        "valve-dev-1", 1, False
    )
    assert valve.is_closed is True

    # Error handling (ConnectionError) reverts is_closed to False
    client.async_set_watering_switch_state.side_effect = ConnectionError("Network down")
    valve.async_write_ha_state.reset_mock()
    with pytest.raises(HomeAssistantError) as exc_info:
        await valve.async_close_valve()
    assert exc_info.value.translation_key == "command_failed"
    assert valve.async_write_ha_state.call_count == 2
    assert valve.is_closed is False
    assert valve.assumed_state is False


async def test_async_turn_on_with_time(hass: HomeAssistant) -> None:
    """Test async_turn_on_with_time success and failure raising error."""
    valve, _, client = _create_valve(hass)
    valve.async_write_ha_state = MagicMock()

    valve.async_write_ha_state.reset_mock()
    await valve.async_turn_on_with_time(on_time=120.0)
    valve.async_write_ha_state.assert_called()
    assert valve.assumed_state is True
    client.async_set_watering_switch_state.assert_awaited_once_with(
        "valve-dev-1", 1, True, on_time=120.0
    )
    assert valve.is_closed is False

    # Failure reverts state and raises
    client.async_set_watering_switch_state.side_effect = HcuApiError(
        "Set on time failed"
    )
    with pytest.raises(HomeAssistantError) as exc_info:
        await valve.async_turn_on_with_time(on_time=120.0)
    assert exc_info.value.translation_key == "command_failed"
    assert valve.is_closed is True
    assert valve.assumed_state is False
