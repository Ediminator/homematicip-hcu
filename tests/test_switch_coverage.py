"""Comprehensive coverage tests for custom_components/hcu_integration/switch.py."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    API_PATHS,
    DOMAIN,
    HMIP_ON_TIME_INFINITE,
)
from custom_components.hcu_integration.switch import (
    HcuConfigUseInternalOnTime,
    HcuSwitch,
    HcuSwitchGroup,
    HcuWateringGroup,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}
    coordinator.data = {}
    return coordinator


@pytest.fixture
def mock_hcu_client():
    """Create a mock HCU client."""
    client = MagicMock()
    client.is_connected = True
    client.hcu_device_id = "hcu_main"
    client.hcu_part_device_ids = set()
    client.async_set_switch_state = AsyncMock()
    client.async_set_sound_file = AsyncMock()
    client.async_group_control = AsyncMock()
    return client


async def test_async_setup_entry_with_entities():
    """Test async_setup_entry registers entities when present."""
    hass = MagicMock()
    mock_entity = MagicMock()
    coordinator = MagicMock()
    coordinator.entities = {Platform.SWITCH: [mock_entity]}

    config_entry = MagicMock()
    config_entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)
    async_add_entities.assert_called_once_with([mock_entity])


async def test_async_setup_entry_without_entities():
    """Test async_setup_entry does nothing when switch entities are absent."""
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.entities = {}

    config_entry = MagicMock()
    config_entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)
    async_add_entities.assert_not_called()


def test_hcu_switch_visualization_device_classes(mock_coordinator, mock_hcu_client):
    """Test device_class determination from switchVisualization and fallback map."""
    dev_outlet = {
        "id": "dev_outlet",
        "type": "OTHER_TYPE",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "switchVisualization": "OUTLET",
                "on": False,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_outlet
    sw_outlet = HcuSwitch(mock_coordinator, mock_hcu_client, dev_outlet, "1")
    assert sw_outlet.device_class == SwitchDeviceClass.OUTLET

    dev_switch = {
        "id": "dev_switch",
        "type": "OTHER_TYPE",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "switchVisualization": "SWITCH",
                "on": False,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_switch
    sw_switch = HcuSwitch(mock_coordinator, mock_hcu_client, dev_switch, "1")
    assert sw_switch.device_class == SwitchDeviceClass.SWITCH

    # Multi-channel unlabeled switch sets translation key and channel index placeholder
    dev_multi = {
        "id": "dev_multi",
        "type": "OTHER_TYPE",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False},
            "2": {"functionalChannelType": "SWITCH_CHANNEL", "on": False},
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_multi
    sw_multi = HcuSwitch(mock_coordinator, mock_hcu_client, dev_multi, "2")
    assert sw_multi.translation_key == "hcu_switch"
    assert sw_multi.translation_placeholders == {"channel_index": " 2"}


def test_hcu_switch_coordinator_update_syncs_state(mock_coordinator, mock_hcu_client):
    """Test _handle_coordinator_update syncs switch state and writes HA state."""
    device = {
        "id": "dev_sw_1",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    mock_coordinator.data = {"dev_sw_1": {}}

    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")
    switch.async_write_ha_state = MagicMock()

    assert switch.is_on is False

    device["functionalChannels"]["1"]["on"] = True
    switch._handle_coordinator_update()

    assert switch.is_on is True
    switch.async_write_ha_state.assert_called_once()


async def test_hcu_switch_turn_on_and_off(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test normal async_turn_on and async_turn_off without internal on_time."""
    device = {
        "id": "dev_sw_1",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    # Turn on
    await switch.async_turn_on()
    mock_hcu_client.async_set_switch_state.assert_called_once_with("dev_sw_1", 1, True)
    assert switch.is_on is True

    # Turn off
    mock_hcu_client.async_set_switch_state.reset_mock()
    await switch.async_turn_off()
    mock_hcu_client.async_set_switch_state.assert_called_once_with("dev_sw_1", 1, False)
    assert switch.is_on is False


async def test_hcu_switch_turn_on_with_internal_on_time(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test async_turn_on delegates to async_turn_on_with_time when companion switch is on."""
    device = {
        "id": "dev_sw_timer",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "on": False,
                "onTime": 45.0,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")
    switch.hass = hass
    switch.async_write_ha_state = MagicMock()

    # Create companion switch and set to ON
    reg = er.async_get(hass)
    comp = reg.async_get_or_create(
        "switch",
        DOMAIN,
        "dev_sw_timer_1_use_internal_on_time",
        suggested_object_id="timer_sw",
    )
    hass.states.async_set(comp.entity_id, STATE_ON)

    await switch.async_turn_on()
    mock_hcu_client.async_set_switch_state.assert_called_once_with(
        "dev_sw_timer", 1, True, on_time=45.0
    )
    assert switch.is_on is True
    switch.async_write_ha_state.assert_called_once()

    # Direct call to async_turn_on_with_time verifies optimistic state and API dispatch
    switch.async_write_ha_state.reset_mock()
    mock_hcu_client.async_set_switch_state.reset_mock()
    await switch.async_turn_on_with_time(20.0)
    mock_hcu_client.async_set_switch_state.assert_called_once_with(
        "dev_sw_timer", 1, True, on_time=20.0
    )
    assert switch.is_on is True
    switch.async_write_ha_state.assert_called_once()


async def test_hcu_switch_turn_on_with_time_error_rollback(
    mock_coordinator, mock_hcu_client, caplog: pytest.LogCaptureFixture
):
    """Test async_turn_on_with_time rollback on HcuApiError and ConnectionError."""
    device = {
        "id": "dev_sw_err",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")
    switch.async_write_ha_state = MagicMock()

    mock_hcu_client.async_set_switch_state.side_effect = HcuApiError(
        "Device unreachable"
    )

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await switch.async_turn_on_with_time(30.0)
    assert exc_info.value.translation_key == "command_failed"

    assert switch.is_on is False  # Restored to previous False
    assert "Failed to turn on" in caplog.text
    assert switch.async_write_ha_state.call_count == 2


async def test_hcu_switch_play_sound(mock_coordinator, mock_hcu_client):
    """Test async_play_sound service call handler on HcuSwitch."""
    device = {
        "id": "dev_sw_mp3",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")

    await switch.async_play_sound("sound_01.mp3", 0.8, 10.5)
    mock_hcu_client.async_set_sound_file.assert_called_once_with(
        device_id="dev_sw_mp3",
        channel_index=1,
        sound_file="sound_01.mp3",
        volume=0.8,
        duration=10.5,
    )


async def test_hcu_config_use_internal_on_time_lifecycle(
    mock_coordinator,
    mock_hcu_client,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
):
    """Test HcuConfigUseInternalOnTime initialization, state restoration, and switching."""
    device = {
        "id": "dev_cfg",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "onTime": 30.0,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device

    entity = HcuConfigUseInternalOnTime(mock_coordinator, mock_hcu_client, device, "1")
    entity.hass = hass
    entity._attr_name = "Use Internal On Time"

    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.entity_registry_enabled_default is False
    assert entity.unique_id == "dev_cfg_1_use_internal_on_time"
    assert entity.is_on is False
    assert entity.translation_key == "hcu_use_internal_on_time"
    assert entity._base_translation_key == "hcu_use_internal_on_time"
    entity._resolve_translation_prefix(has_siblings=True)
    assert entity.translation_placeholders == {"channel": ""}

    # Resolved on_time helper
    assert entity._resolved_on_time() == 30.0

    # Test wateringOnTime fallback
    device["functionalChannels"]["1"]["onTime"] = 0
    device["functionalChannels"]["1"]["wateringOnTime"] = 40.0
    assert entity._resolved_on_time() == 40.0

    # Test internalLinkConfiguration fallback
    device["functionalChannels"]["1"]["wateringOnTime"] = 0
    device["functionalChannels"]["1"]["internalLinkConfiguration"] = {"onTime": 50.0}
    assert entity._resolved_on_time() == 50.0

    # Turn on success
    entity.async_write_ha_state = MagicMock()
    await entity.async_turn_on()
    assert entity.is_on is True
    entity.async_write_ha_state.assert_called_once()

    # Turn off success
    entity.async_write_ha_state.reset_mock()
    await entity.async_turn_off()
    assert entity.is_on is False
    entity.async_write_ha_state.assert_called_once()

    # Cannot turn on when on_time is 0
    device["functionalChannels"]["1"]["internalLinkConfiguration"]["onTime"] = 0
    entity.async_write_ha_state.reset_mock()
    with caplog.at_level(logging.DEBUG):
        await entity.async_turn_on()
    assert entity.is_on is False
    assert "Cannot enable 'Use Internal On Time'" in caplog.text
    entity.async_write_ha_state.assert_not_called()

    # Cannot turn on when on_time is HMIP_ON_TIME_INFINITE
    device["functionalChannels"]["1"]["onTime"] = HMIP_ON_TIME_INFINITE
    with caplog.at_level(logging.DEBUG):
        await entity.async_turn_on()
    assert entity.is_on is False

    # State restoration in async_added_to_hass
    # Case 1: Restored state is ON but on_time is infinite -> disabled on startup
    entity.async_get_last_state = AsyncMock(return_value=MagicMock(state=STATE_ON))
    with caplog.at_level(logging.DEBUG):
        await entity.async_added_to_hass()
    assert entity.is_on is False
    assert "Disabling 'Use Internal On Time'" in caplog.text

    # Case 2: Restored state is ON and on_time is valid -> stays ON
    device["functionalChannels"]["1"]["onTime"] = 15.0
    await entity.async_added_to_hass()
    assert entity.is_on is True

    # Case 3: Restored state is OFF -> stays OFF
    entity.async_get_last_state = AsyncMock(return_value=MagicMock(state=STATE_OFF))
    await entity.async_added_to_hass()
    assert entity.is_on is False

    # Case 4: No restored state -> stays False
    entity.async_get_last_state = AsyncMock(return_value=None)
    await entity.async_added_to_hass()
    assert entity.is_on is False

    # _handle_coordinator_update is no-op
    entity._handle_coordinator_update()


def test_hcu_switch_group_platform(mock_coordinator, mock_hcu_client):
    """Test HcuSwitchGroup platform and basic initialization."""
    group_data = {"id": "grp_sw", "label": "Switch Group", "on": True}
    mock_hcu_client.get_group_by_id.return_value = group_data

    group = HcuSwitchGroup(mock_coordinator, mock_hcu_client, group_data)
    assert group.PLATFORM == Platform.SWITCH
    assert group._attr_is_on is True


async def test_hcu_watering_group_lifecycle_and_actions(
    mock_coordinator, mock_hcu_client, caplog: pytest.LogCaptureFixture
):
    """Test HcuWateringGroup is_on, async_turn_on, async_turn_off, and async_turn_on_with_time."""
    group_data = {
        "id": "grp_water",
        "label": "Garden Watering",
        "wateringActive": False,
    }
    mock_hcu_client.get_group_by_id.return_value = group_data

    group = HcuWateringGroup(mock_coordinator, mock_hcu_client, group_data)
    group.async_write_ha_state = MagicMock()

    assert group.is_on is False

    # Turn on
    await group.async_turn_on()
    mock_hcu_client.async_group_control.assert_called_once_with(
        API_PATHS["SET_GROUP_WATERING_SWITCH_STATE"],
        "grp_water",
        {"wateringActive": True},
    )

    # Turn off
    mock_hcu_client.async_group_control.reset_mock()
    await group.async_turn_off()
    mock_hcu_client.async_group_control.assert_called_once_with(
        API_PATHS["SET_GROUP_WATERING_SWITCH_STATE"],
        "grp_water",
        {"wateringActive": False},
    )

    # Turn on with time - success
    mock_hcu_client.async_group_control.reset_mock()
    await group.async_turn_on_with_time(120.0)
    mock_hcu_client.async_group_control.assert_called_once_with(
        API_PATHS["SET_GROUP_WATERING_SWITCH_STATE_WITH_TIME"],
        "grp_water",
        {"wateringActive": True, "wateringTime": 120.0},
    )

    # Turn on with time - error rollback
    mock_hcu_client.async_group_control.side_effect = ConnectionError("Network lost")
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await group.async_turn_on_with_time(60.0)
    assert exc_info.value.translation_key == "command_failed"
    assert "Failed to turn on" in caplog.text
