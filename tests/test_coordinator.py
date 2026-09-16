"""Tests for the HCU coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform

from custom_components.hcu_integration import HcuCoordinator
from custom_components.hcu_integration.api import ProcessEventsResult
from custom_components.hcu_integration.const import DOMAIN


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_hcu_client: MagicMock, mock_config_entry: ConfigEntry):
    """Create a coordinator instance."""
    coordinator = HcuCoordinator(hass, mock_hcu_client, mock_config_entry)
    return coordinator


def test_coordinator_initialization(coordinator: HcuCoordinator, mock_hcu_client: MagicMock):
    """Test coordinator initialization."""
    assert coordinator.client == mock_hcu_client
    assert coordinator.entities == {}


async def test_fire_button_event(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test firing a button event."""
    coordinator._fire_button_event("device1", "1", "press")

    hass.bus.async_fire.assert_called_once_with(
        f"{DOMAIN}_event",
        {"device_id": "device1", "subtype": "1", "type": "press"},
    )


async def test_handle_device_channel_events(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test handling DEVICE_CHANNEL_EVENT type events."""
    mock_event_entity = MagicMock()
    mock_event_entity._device_id = "device1"
    mock_event_entity._channel_index_str = "1"
    mock_event_entity.handle_trigger = MagicMock()
    coordinator.entities[Platform.EVENT] = [mock_event_entity]

    events = {
        "event1": {
            "pushEventType": "DEVICE_CHANNEL_EVENT",
            "channelEventType": "PRESS_SHORT",
            "deviceId": "device1",
            "channelIndex": "1",
        },
    }

    updated_ids = coordinator._handle_device_channel_events(events)

    assert updated_ids == {"device1"}
    hass.bus.async_fire.assert_called_once_with(
        f"{DOMAIN}_event",
        {"device_id": "device1", "subtype": "1", "type": "press_short"},
    )
    mock_event_entity.handle_trigger.assert_called_once_with("press_short")


async def test_handle_device_channel_events_normalization(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test normalization of channel event types (KEY_ prefix and doorbell events)."""
    mock_event_entity = MagicMock()
    mock_event_entity._device_id = "device1"
    mock_event_entity._channel_index_str = "1"
    mock_event_entity.handle_trigger = MagicMock()
    coordinator.entities[Platform.EVENT] = [mock_event_entity]

    # Test KEY_PRESS_LONG -> press_long
    events_key = {
        "event1": {
            "pushEventType": "DEVICE_CHANNEL_EVENT",
            "channelEventType": "KEY_PRESS_LONG",
            "deviceId": "device1",
            "channelIndex": "1",
        },
    }
    updated_ids = coordinator._handle_device_channel_events(events_key)
    assert updated_ids == {"device1"}
    hass.bus.async_fire.assert_called_with(
        f"{DOMAIN}_event",
        {"device_id": "device1", "subtype": "1", "type": "press_long"},
    )
    mock_event_entity.handle_trigger.assert_called_with("press_long")

    # Test DOOR_BELL_SENSOR_EVENT -> ring
    hass.bus.async_fire.reset_mock()
    mock_event_entity.handle_trigger.reset_mock()
    events_doorbell = {
        "event1": {
            "pushEventType": "DEVICE_CHANNEL_EVENT",
            "channelEventType": "DOOR_BELL_SENSOR_EVENT",
            "deviceId": "device1",
            "channelIndex": "1",
        },
    }
    updated_ids = coordinator._handle_device_channel_events(events_doorbell)
    assert updated_ids == {"device1"}
    hass.bus.async_fire.assert_called_with(
        f"{DOMAIN}_event",
        {"device_id": "device1", "subtype": "1", "type": "ring"},
    )
    mock_event_entity.handle_trigger.assert_called_with("ring")

    # Test unknown channel event type is ignored
    hass.bus.async_fire.reset_mock()
    mock_event_entity.handle_trigger.reset_mock()
    events_unknown = {
        "event1": {
            "pushEventType": "DEVICE_CHANNEL_EVENT",
            "channelEventType": "UNKNOWN_EVENT_TYPE",
            "deviceId": "device1",
            "channelIndex": "1",
        },
    }
    updated_ids = coordinator._handle_device_channel_events(events_unknown)
    assert updated_ids == set()
    hass.bus.async_fire.assert_not_called()
    mock_event_entity.handle_trigger.assert_not_called()


async def test_handle_event_message_full_flow(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test complete event message handling flow."""
    mock_event_entity = MagicMock()
    mock_event_entity._device_id = "device1"
    mock_event_entity._channel_index_str = "1"
    mock_event_entity.handle_trigger = MagicMock()
    coordinator.entities[Platform.EVENT] = [mock_event_entity]
    coordinator._initial_state_loaded = True

    coordinator.client.process_events = MagicMock(return_value=ProcessEventsResult(updated={"device1"}))
    coordinator.async_set_updated_data = MagicMock()

    message = {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {
                    "event1": {
                        "pushEventType": "DEVICE_CHANNEL_EVENT",
                        "channelEventType": "PRESS_SHORT",
                        "deviceId": "device1",
                        "channelIndex": "1",
                    },
                },
            },
        },
    }

    coordinator._handle_event_message(message)

    hass.bus.async_fire.assert_called_once_with(
        f"{DOMAIN}_event",
        {"device_id": "device1", "subtype": "1", "type": "press_short"},
    )
    mock_event_entity.handle_trigger.assert_called_once_with("press_short")
    coordinator.async_set_updated_data.assert_called_once_with({"device1"})


def test_handle_event_message_ignores_non_event_types(coordinator: HcuCoordinator):
    """Test that non-HMIP_SYSTEM_EVENT messages are ignored."""
    message = {"type": "OTHER_TYPE", "body": {}}

    # Should not raise an error
    coordinator._handle_event_message(message)


def test_handle_event_message_empty_events(coordinator: HcuCoordinator):
    """Test handling message with no events."""
    message = {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {},
            },
        },
    }

    # Should not raise an error
    coordinator._handle_event_message(message)
