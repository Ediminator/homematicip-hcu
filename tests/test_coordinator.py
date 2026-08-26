"""Tests for the HCU coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.hcu_integration import HcuCoordinator
from custom_components.hcu_integration.const import (
    CHANNEL_TYPE_MULTI_MODE_INPUT,
    CHANNEL_TYPE_MULTI_MODE_INPUT_TRANSMITTER,
    DOMAIN,
    EVENT_CHANNEL_TYPES,
)


@pytest.fixture
async def coordinator(hass: HomeAssistant, mock_hcu_client: MagicMock, mock_config_entry: ConfigEntry):
    """Create a coordinator instance."""
    coordinator = HcuCoordinator(hass, mock_hcu_client, mock_config_entry)
    coordinator._initial_state_loaded = True
    return coordinator


def test_coordinator_initialization(coordinator: HcuCoordinator, mock_hcu_client: MagicMock):
    """Test coordinator initialization."""
    assert coordinator.client == mock_hcu_client
    assert coordinator.entities == {}


def test_extract_event_channels(coordinator: HcuCoordinator):
    """Test extraction of event channels from events."""
    events = {
        "event1": {
            "pushEventType": "DEVICE_CHANGED",
            "device": {
                "id": "device1",
                "functionalChannels": {
                    "1": {"functionalChannelType": "WALL_MOUNTED_TRANSMITTER_CHANNEL"},
                    "2": {"functionalChannelType": "SWITCH_MEASURING"},
                },
            },
        },
    }

    result = coordinator._extract_event_channels(events)

    # WALL_MOUNTED_TRANSMITTER_CHANNEL should be extracted (it's an event channel type)
    assert ("device1", "1") in result
    # SWITCH_MEASURING should not be extracted (not an event channel type)
    assert ("device1", "2") not in result


def test_extract_event_channels_excludes_multi_mode_channels(coordinator: HcuCoordinator):
    """Test that multi-mode input channels are NOT extracted as event channels (Issue #183)."""
    events = {
        "event1": {
            "pushEventType": "DEVICE_CHANGED",
            "device": {
                "id": "device1",
                "functionalChannels": {
                    "1": {"functionalChannelType": CHANNEL_TYPE_MULTI_MODE_INPUT},
                    "2": {"functionalChannelType": CHANNEL_TYPE_MULTI_MODE_INPUT_TRANSMITTER},
                },
            },
        },
    }

    result = coordinator._extract_event_channels(events)

    # These channels should NOT be extracted because they are now in DEVICE_CHANNEL_EVENT_ONLY_TYPES
    # and should be excluded from timestamp-based detection
    assert ("device1", "1") not in result
    assert ("device1", "2") not in result



async def test_fire_button_event(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test firing a button event."""
    events_fired = []

    def capture_event(event):
        events_fired.append(event)

    hass.bus.async_listen(f"{DOMAIN}_event", capture_event)

    coordinator._fire_button_event("device1", "1", "press")
    await hass.async_block_till_done()

    assert len(events_fired) == 1
    event = events_fired[0]
    assert event.data["device_id"] == "device1"
    assert event.data["subtype"] == "1"
    assert event.data["type"] == "press"


async def test_handle_device_channel_events(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test handling DEVICE_CHANNEL_EVENT type events."""
    events_fired = []

    def capture_event(event):
        events_fired.append(event)

    hass.bus.async_listen(f"{DOMAIN}_event", capture_event)

    events = {
        "event1": {
            "pushEventType": "DEVICE_CHANNEL_EVENT",
            "channelEventType": "PRESS_SHORT",
            "deviceId": "device1",
            "channelIndex": "1",  # Changed from functionalChannelIndex to channelIndex
        },
    }

    coordinator._handle_device_channel_events(events)
    await hass.async_block_till_done()

    assert len(events_fired) == 1
    event = events_fired[0]
    assert event.data["device_id"] == "device1"
    assert event.data["subtype"] == "1"
    assert event.data["type"] == "press_short"


async def test_handle_event_message_full_flow(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test complete event message handling flow with DEVICE_CHANNEL_EVENT."""
    events_fired = []

    def capture_event(event):
        events_fired.append(event)

    hass.bus.async_listen(f"{DOMAIN}_event", capture_event)

    from custom_components.hcu_integration.api import ProcessEventsResult
    coordinator.client.process_events = MagicMock(return_value=ProcessEventsResult(updated={"device1"}))

    # Simulate receiving a DEVICE_CHANNEL_EVENT inside HMIP_SYSTEM_EVENT
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
    await hass.async_block_till_done()

    assert len(events_fired) == 1
    assert events_fired[0].data["type"] == "press_short"


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
