"""Tests for the HCU coordinator."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.hcu_integration import HcuCoordinator
from custom_components.hcu_integration.api import ProcessEventsResult
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    CONF_AUTH_TYPE,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    DOMAIN,
)


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


REMOVAL_EVENT = {"events": {"0": {"pushEventType": "DEVICE_REMOVED", "id": "dev-gone"}}}


def _coordinator_for_removal(
    hass: HomeAssistant, client: MagicMock, options: dict[str, Any]
) -> tuple[HcuCoordinator, MockConfigEntry]:
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "192.168.1.100"}, options=options
    )
    entry.add_to_hass(hass)
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    client.process_events.return_value = ProcessEventsResult(
        updated={"dev-kept"}, excluded={"dev-gone"}
    )
    return coordinator, entry


async def test_device_removal_without_auto_reload_only_updates_entities(
    hass: HomeAssistant, mock_hcu_client: MagicMock
):
    """With the option off, a removed device does not reload the entry."""
    coordinator, _ = _coordinator_for_removal(
        hass, mock_hcu_client, {CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: False}
    )

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload,
        patch.object(coordinator, "async_set_updated_data") as set_updated,
    ):
        coordinator._handle_event_message(REMOVAL_EVENT)
        await hass.async_block_till_done()

    mock_hcu_client.process_events.assert_called_once_with(REMOVAL_EVENT["events"])
    reload.assert_not_called()
    # The removed device is part of the update, so its entities show as gone.
    set_updated.assert_called_once_with({"dev-kept", "dev-gone"})


@pytest.mark.parametrize("options", [{}, {CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: True}])
async def test_device_removal_with_auto_reload_reloads_instead_of_updating(
    hass: HomeAssistant, mock_hcu_client: MagicMock, options: dict[str, Any]
):
    """By default and with the option on, a removed device reloads the entry."""
    coordinator, entry = _coordinator_for_removal(hass, mock_hcu_client, options)

    with (
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload,
        patch.object(coordinator, "async_set_updated_data") as set_updated,
    ):
        coordinator._handle_event_message(REMOVAL_EVENT)
        await hass.async_block_till_done()

    reload.assert_awaited_once_with(entry.entry_id)
    set_updated.assert_not_called()


@pytest.mark.parametrize(
    "home", [None, {}, {"id": ""}, {"id": None}, {"label": "no id"}, "missing"]
)
async def test_update_without_home_id_returns_devices_and_groups_only(
    hass: HomeAssistant, mock_hcu_client: MagicMock, home: Any
):
    """A state without a home id yields the device and group ids and nothing else."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.100"})
    entry.add_to_hass(hass)
    state: dict[str, Any] = {"devices": {"d1": {}}, "groups": {"g1": {}}}
    if home != "missing":
        state["home"] = home
    mock_hcu_client.state = state
    coordinator = HcuCoordinator(hass, mock_hcu_client, entry)

    assert await coordinator._async_update_data() == {"d1", "g1"}
    mock_hcu_client.get_system_state.assert_awaited_once_with()


@pytest.mark.parametrize(
    ("exc_factory", "expected_text"),
    [
        (TimeoutError, "TimeoutError"),
        (lambda: ConnectionError("socket closed"), "socket closed"),
    ],
)
async def test_listener_logs_class_name_for_empty_message_errors(
    hass: HomeAssistant,
    mock_hcu_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
    exc_factory: Any,
    expected_text: str,
) -> None:
    """Disconnect and retry logs include the exception class name when str(err) is empty."""
    import asyncio
    import logging

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_DUAL},
    )
    entry.add_to_hass(hass)
    coordinator = HcuCoordinator(hass, mock_hcu_client, entry)

    ws_step = 0

    async def fake_connect() -> None:
        nonlocal ws_step
        ws_step += 1
        if ws_step == 1:
            return
        if ws_step == 2:
            raise exc_factory()
        raise asyncio.CancelledError

    async def fake_listen() -> None:
        raise exc_factory()

    plugin_step = 0

    async def fake_connect_plugin() -> None:
        nonlocal plugin_step
        plugin_step += 1
        if plugin_step == 1:
            return
        if plugin_step == 2:
            raise exc_factory()
        raise asyncio.CancelledError

    async def fake_listen_plugin() -> None:
        raise exc_factory()

    mock_hcu_client.connect = AsyncMock(side_effect=fake_connect)
    mock_hcu_client.listen = AsyncMock(side_effect=fake_listen)
    mock_hcu_client.connect_plugin = AsyncMock(side_effect=fake_connect_plugin)
    mock_hcu_client.listen_plugin = AsyncMock(side_effect=fake_listen_plugin)

    with (
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_RECONNECT_INITIAL_DELAY",
            0,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_RECONNECT_JITTER_MAX",
            0,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        async with asyncio.timeout(1.0):
            await coordinator._listen_for_events()
            await coordinator._listen_for_plugin_events()

    messages = [r.message for r in caplog.records]
    assert f"WebSocket disconnected: {expected_text}. Reconnecting in 0s" in messages
    assert f"WebSocket reconnect failed: {expected_text}. Retrying in 0s" in messages
    assert (
        f"DualBridge Plugin WebSocket disconnected: {expected_text}. Reconnecting in 0s"
        in messages
    )
    assert (
        f"DualBridge Plugin WebSocket reconnect failed: {expected_text}. Retrying in 0s"
        in messages
    )


async def test_state_fetch_and_refresh_format_empty_timeout_errors(
    hass: HomeAssistant,
    mock_hcu_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Setup, coordinator updates, and reconnect state refreshes format bare TimeoutError."""
    import asyncio
    import logging

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_APP},
    )
    entry.add_to_hass(hass)
    coordinator = HcuCoordinator(hass, mock_hcu_client, entry)
    mock_hcu_client.get_system_state = AsyncMock(side_effect=TimeoutError())

    with (
        patch.object(coordinator, "_listen_for_events", AsyncMock()),
        caplog.at_level(logging.WARNING),
    ):
        assert await coordinator.async_setup() is False

    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"setup_failed_{entry.entry_id}")
    assert issue is not None
    assert issue.translation_placeholders is not None
    assert issue.translation_placeholders["reason"] == "TimeoutError"
    assert "Failed to get initial state: TimeoutError" in [
        r.message for r in caplog.records
    ]

    with pytest.raises(
        UpdateFailed, match="Error communicating with API: TimeoutError"
    ):
        await coordinator._async_update_data()

    caplog.clear()
    coordinator._connection_generation = 1
    mock_hcu_client.is_connected = True
    calls = 0

    async def fail_refresh_twice() -> dict[str, Any]:
        nonlocal calls
        calls += 1
        if calls == 2:
            mock_hcu_client.is_connected = False
        raise TimeoutError

    mock_hcu_client.get_system_state = AsyncMock(side_effect=fail_refresh_twice)

    with (
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_RECONNECT_INITIAL_DELAY",
            0,
        ),
        caplog.at_level(logging.WARNING),
    ):
        async with asyncio.timeout(1.0):
            await coordinator._async_refresh_state_after_reconnect()

    refresh_messages = [r.message for r in caplog.records]
    assert (
        "Could not refresh the HCU state after reconnecting: TimeoutError. Retrying in 0s"
        in refresh_messages
    )
    assert (
        "Could not refresh the HCU state after reconnecting: TimeoutError"
        in refresh_messages
    )
