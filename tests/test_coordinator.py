"""Tests for the HCU coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import async_capture_events

from custom_components.hcu_integration import HcuCoordinator
from custom_components.hcu_integration.api import ProcessEventsResult
from custom_components.hcu_integration.const import DOMAIN


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, mock_hcu_client: MagicMock, mock_config_entry: ConfigEntry
):
    """Create a coordinator instance."""
    return HcuCoordinator(hass, mock_hcu_client, mock_config_entry)


def test_coordinator_initialization(
    coordinator: HcuCoordinator, mock_hcu_client: MagicMock
):
    """Test coordinator initialization."""
    assert coordinator.client == mock_hcu_client
    assert coordinator.entities == {}


async def test_fire_button_event(coordinator: HcuCoordinator, hass: HomeAssistant):
    """Test firing a button event."""
    events = async_capture_events(hass, f"{DOMAIN}_event")
    coordinator._fire_button_event("device1", "1", "press")
    await hass.async_block_till_done()

    assert [e.data for e in events] == [
        {"device_id": "device1", "subtype": "1", "type": "press"}
    ]


async def test_handle_device_channel_events(
    coordinator: HcuCoordinator, hass: HomeAssistant
):
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

    fired = async_capture_events(hass, f"{DOMAIN}_event")
    updated_ids = coordinator._handle_device_channel_events(events)
    await hass.async_block_till_done()

    assert updated_ids == {"device1"}
    assert [e.data for e in fired] == [
        {"device_id": "device1", "subtype": "1", "type": "press_short"}
    ]
    mock_event_entity.handle_trigger.assert_called_once_with("press_short")


async def test_handle_device_channel_events_normalization(
    coordinator: HcuCoordinator, hass: HomeAssistant
):
    """Test normalization of channel event types (KEY_ prefix and doorbell events)."""
    mock_event_entity = MagicMock()
    mock_event_entity._device_id = "device1"
    mock_event_entity._channel_index_str = "1"
    mock_event_entity.handle_trigger = MagicMock()
    coordinator.entities[Platform.EVENT] = [mock_event_entity]

    fired = async_capture_events(hass, f"{DOMAIN}_event")

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
    await hass.async_block_till_done()
    assert updated_ids == {"device1"}
    assert fired[-1].data == {
        "device_id": "device1",
        "subtype": "1",
        "type": "press_long",
    }
    mock_event_entity.handle_trigger.assert_called_with("press_long")

    # Test DOOR_BELL_SENSOR_EVENT -> ring
    fired.clear()
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
    await hass.async_block_till_done()
    assert updated_ids == {"device1"}
    assert fired[-1].data == {"device_id": "device1", "subtype": "1", "type": "ring"}
    mock_event_entity.handle_trigger.assert_called_with("ring")

    # Test unknown channel event type is ignored
    fired.clear()
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
    await hass.async_block_till_done()
    assert updated_ids == set()
    assert fired == []
    mock_event_entity.handle_trigger.assert_not_called()


async def test_handle_event_message_full_flow(
    coordinator: HcuCoordinator, hass: HomeAssistant
):
    """Test complete event message handling flow."""
    mock_event_entity = MagicMock()
    mock_event_entity._device_id = "device1"
    mock_event_entity._channel_index_str = "1"
    mock_event_entity.handle_trigger = MagicMock()
    coordinator.entities[Platform.EVENT] = [mock_event_entity]
    coordinator._initial_state_loaded = True

    coordinator.client.process_events = MagicMock(
        return_value=ProcessEventsResult(updated={"device1"})
    )
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

    fired = async_capture_events(hass, f"{DOMAIN}_event")
    coordinator._handle_event_message(message)
    await hass.async_block_till_done()

    assert [e.data for e in fired] == [
        {"device_id": "device1", "subtype": "1", "type": "press_short"}
    ]
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


async def test_async_setup_entry_raises_config_entry_not_ready_and_cleans_up(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
):
    """Test failed setup cleans up client/hass.data, does not start bridge early, and raises ConfigEntryNotReady."""
    from unittest.mock import patch

    from homeassistant.exceptions import ConfigEntryNotReady

    from custom_components.hcu_integration import async_setup_entry

    mock_client = MagicMock()
    mock_client.plugin_id = "de.homematic.homeassistant"
    mock_client._send_message = AsyncMock()
    mock_client.set_ha_entity_bridge = MagicMock()
    mock_client.disconnect = AsyncMock()
    mock_client.disconnect_plugin = AsyncMock()

    mock_bridge = MagicMock()
    mock_bridge.start_listening = MagicMock()
    mock_bridge.stop_listening = MagicMock()

    with (
        patch(
            "custom_components.hcu_integration.HcuApiClient", return_value=mock_client
        ),
        patch(
            "custom_components.hcu_integration.HaEntityBridge", return_value=mock_bridge
        ),
        patch.object(HcuCoordinator, "async_setup", new=AsyncMock(return_value=False)),
        pytest.raises(ConfigEntryNotReady),
    ):
        await async_setup_entry(hass, mock_config_entry)

    mock_bridge.start_listening.assert_not_called()
    mock_client.disconnect.assert_awaited_once()
    mock_client.disconnect_plugin.assert_awaited_once()
    assert getattr(mock_config_entry, "runtime_data", None) is None


async def test_listen_for_events_logs_unavailable_once_and_recovery(
    coordinator: HcuCoordinator, caplog: pytest.LogCaptureFixture
):
    """Test Silver rule log-when-unavailable: warn once on disconnect, debug on retries, info on recovery."""
    import asyncio
    import logging
    from unittest.mock import patch

    attempts = 0

    async def side_effect_connect():
        nonlocal attempts
        attempts += 1
        if attempts <= 3:
            raise ConnectionError(f"Offline attempt {attempts}")
        if attempts == 4:
            return
        raise asyncio.CancelledError

    coordinator.client.connect = AsyncMock(side_effect=side_effect_connect)
    coordinator.client.listen = AsyncMock(
        side_effect=[ConnectionError("Dropped after connect"), asyncio.CancelledError()]
    )
    coordinator.client.is_connected = False
    coordinator.client.register_event_callback = MagicMock()
    coordinator.client.announce_plugin_ready = AsyncMock()

    with (
        patch(
            "custom_components.hcu_integration.coordinator.asyncio.sleep",
            new=AsyncMock(),
        ),
        caplog.at_level(logging.DEBUG),
    ):
        await coordinator._listen_for_events()

    warnings = [
        r.message
        for r in caplog.records
        if r.levelname == "WARNING" and "WebSocket disconnected" in r.message
    ]
    # Should warn once for the initial 3 consecutive failures, then once again after attempt 4 connected and dropped
    assert len(warnings) == 2


async def test_repairs_async_create_fix_flow_handles_none_data(hass: HomeAssistant):
    """Test repairs.async_create_fix_flow does not crash when data is None."""
    from custom_components.hcu_integration.repairs import (
        AccessAuthorizationRepairFlow,
        InvalidPinNotificationFlow,
        SetupFailedRepairFlow,
        async_create_fix_flow,
    )

    flow_setup = await async_create_fix_flow(hass, "setup_failed_entry1", None)
    assert isinstance(flow_setup, SetupFailedRepairFlow)

    flow_pin = await async_create_fix_flow(hass, "pin_failed_dev1", None)
    assert isinstance(flow_pin, InvalidPinNotificationFlow)

    flow_auth = await async_create_fix_flow(hass, "access_authorization_dev1_1", None)
    assert isinstance(flow_auth, AccessAuthorizationRepairFlow)
