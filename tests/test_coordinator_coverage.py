"""Comprehensive coverage tests for coordinator.py."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_capture_events,
)

from custom_components.hcu_integration import event
from custom_components.hcu_integration.api import HcuApiError, ProcessEventsResult
from custom_components.hcu_integration.const import (
    ATTR_USER_MESSAGE_ACKNOWLEDGEMENT_TYPE,
    ATTR_USER_MESSAGE_ID,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_TYPE,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    CONF_ZEROCONF_NAME,
    CONF_ZEROCONF_TYPE,
    DOMAIN,
    EVENT_USER_MESSAGE_ACKNOWLEDGEMENT,
    MSG_TYPE_USER_MESSAGE_ACK,
    WEBSOCKET_RECONNECT_JITTER_MAX,
)
from custom_components.hcu_integration.coordinator import HcuCoordinator


@pytest.fixture
def base_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create a mock config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={},
        entry_id="test_entry_coord_1",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock HcuApiClient."""
    client = MagicMock()
    client.hcu_device_id = "3014F711A000000000000001"
    client.state = {
        "devices": {
            "3014F711A000000000000001": {
                "id": "3014F711A000000000000001",
                "oem": "eQ-3",
                "modelType": "HCU",
                "label": "My HCU",
                "firmwareVersion": "1.0.0",
                "functionalChannels": {
                    "1": {"visibleChannelIndex": 10},
                    "2": {},
                },
            },
            "dev2": {
                "id": "dev2",
                "functionalChannels": {
                    "1": {},
                },
            },
        },
        "groups": {
            "group1": {"id": "group1"},
        },
        "home": {"id": "home1"},
    }
    client.is_connected = True
    client.is_plugin_connected = True
    client.connect = AsyncMock()
    client.connect_plugin = AsyncMock()
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    client.get_system_state = AsyncMock(return_value=client.state)
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.announce_plugin_ready = AsyncMock()
    client.register_event_callback = MagicMock()
    client.listen = AsyncMock()
    client.listen_plugin = AsyncMock()
    return client


class TestCoordinatorIssues:
    def test_create_and_delete_setup_issue_plugin(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test creating and deleting setup issue with plugin auth."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        coordinator._create_setup_issue("Connection refused")

        issue_reg = ir.async_get(hass)
        issue = issue_reg.async_get_issue(
            DOMAIN, f"setup_failed_{base_config_entry.entry_id}"
        )
        assert issue is not None
        assert issue.severity == ir.IssueSeverity.ERROR
        assert issue.translation_placeholders["auth_mode"] == "Plugin User"
        assert issue.translation_placeholders["reason"] == "Connection refused"
        assert issue.data == {"entry_id": base_config_entry.entry_id}

        coordinator._delete_setup_issue()
        assert (
            issue_reg.async_get_issue(
                DOMAIN, f"setup_failed_{base_config_entry.entry_id}"
            )
            is None
        )

    def test_create_setup_issue_app_and_dual_and_custom(
        self, hass: HomeAssistant, mock_client: MagicMock
    ):
        """Test auth_mode labels in setup issue for app, dual, and unknown auth types."""
        issue_reg = ir.async_get(hass)

        for auth_type, expected_label in [
            (AUTH_TYPE_APP, "App User"),
            (AUTH_TYPE_DUAL, "DualBridge (App + Plugin)"),
            ("CUSTOM_MODE", "CUSTOM_MODE"),
        ]:
            entry = MockConfigEntry(
                domain=DOMAIN,
                data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: auth_type},
                entry_id=f"entry_{auth_type}",
            )
            entry.add_to_hass(hass)
            coord = HcuCoordinator(hass, mock_client, entry)
            coord._create_setup_issue("Failed")

            issue = issue_reg.async_get_issue(DOMAIN, f"setup_failed_entry_{auth_type}")
            assert issue is not None
            assert issue.translation_placeholders["auth_mode"] == expected_label


class TestCoordinatorSetup:
    async def test_async_setup_plugin_timeout_waiting_for_websocket(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test async_setup fails when waiting for WebSocket times out."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)

        async def fake_wait_for(fut, *args, **kwargs):
            fut.close()
            raise TimeoutError

        with (
            patch.object(coordinator, "_listen_for_events", AsyncMock()),
            patch(
                "custom_components.hcu_integration.coordinator.asyncio.wait_for",
                side_effect=fake_wait_for,
            ),
        ):
            res = await coordinator.async_setup()
            assert res is False

        issue = ir.async_get(hass).async_get_issue(
            DOMAIN, f"setup_failed_{base_config_entry.entry_id}"
        )
        assert issue is not None
        assert "timed out" in issue.translation_placeholders["reason"]

    async def test_async_setup_no_devices_in_initial_state(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test async_setup fails when get_system_state returns empty devices."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        coordinator._connected_event.set()
        mock_client.get_system_state.return_value = {"devices": {}}

        with (
            patch.object(coordinator, "_listen_for_events", AsyncMock()),
            caplog.at_level(logging.ERROR),
        ):
            res = await coordinator.async_setup()
            assert res is False

        assert any(
            "Connected but failed to get valid initial state" in r.message
            for r in caplog.records
        )
        issue = ir.async_get(hass).async_get_issue(
            DOMAIN, f"setup_failed_{base_config_entry.entry_id}"
        )
        assert issue is not None
        assert "no devices found" in issue.translation_placeholders["reason"]

    async def test_async_setup_client_error(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test async_setup fails when get_system_state raises HcuApiError."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        coordinator._connected_event.set()
        mock_client.get_system_state.side_effect = HcuApiError("API Error 500")

        with patch.object(coordinator, "_listen_for_events", AsyncMock()):
            res = await coordinator.async_setup()
            assert res is False

        issue = ir.async_get(hass).async_get_issue(
            DOMAIN, f"setup_failed_{base_config_entry.entry_id}"
        )
        assert issue is not None
        assert "API Error 500" in issue.translation_placeholders["reason"]

    async def test_async_setup_dual_success(
        self, hass: HomeAssistant, mock_client: MagicMock
    ):
        """Test async_setup with DualBridge starts plugin listener and succeeds."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_DUAL},
            entry_id="dual_entry",
        )
        entry.add_to_hass(hass)
        coordinator = HcuCoordinator(hass, mock_client, entry)

        with (
            patch.object(coordinator, "_listen_for_events", AsyncMock()),
            patch.object(
                coordinator, "_listen_for_plugin_events", AsyncMock()
            ) as mock_plugin_listen,
            patch.object(
                coordinator, "_register_hcu_device", AsyncMock()
            ) as mock_reg_hcu,
        ):
            res = await coordinator.async_setup()
            assert res is True
            mock_plugin_listen.assert_called_once()
            mock_reg_hcu.assert_awaited_once()

        assert coordinator._initial_state_loaded is True
        assert coordinator.data == {
            "3014F711A000000000000001",
            "dev2",
            "group1",
            "home1",
        }


class TestCoordinatorDataUpdate:
    async def test_async_update_data_success(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test _async_update_data fetches state and extracts all ids."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        res = await coordinator._async_update_data()
        assert res == {"3014F711A000000000000001", "dev2", "group1", "home1"}

    async def test_async_update_data_failure_raises_update_failed(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test _async_update_data wraps errors in UpdateFailed."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        mock_client.get_system_state.side_effect = HcuApiError("Timeout")

        with pytest.raises(UpdateFailed, match="Error communicating with API: Timeout"):
            await coordinator._async_update_data()


class TestCoordinatorKnownHosts:
    async def test_async_known_hosts_with_zeroconf(
        self, hass: HomeAssistant, mock_client: MagicMock
    ):
        """Test _async_known_hosts returns configured host and zeroconf resolved addresses."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "192.168.1.100",
                CONF_ZEROCONF_NAME: "hcu._homematic._tcp.local.",
                CONF_ZEROCONF_TYPE: "_homematic._tcp.local.",
            },
            entry_id="zc_entry",
        )
        entry.add_to_hass(hass)
        coordinator = HcuCoordinator(hass, mock_client, entry)

        mock_info = MagicMock()
        mock_info.parsed_addresses.return_value = ["192.168.1.101"]
        mock_aiozc = MagicMock()
        mock_aiozc.async_get_service_info = AsyncMock(return_value=mock_info)

        with patch(
            "homeassistant.components.zeroconf.async_get_async_instance",
            AsyncMock(return_value=mock_aiozc),
        ):
            hosts = await coordinator._async_known_hosts()

        assert hosts == {"192.168.1.100", "192.168.1.101"}

    async def test_async_known_hosts_zeroconf_exception_handled(
        self, hass: HomeAssistant, mock_client: MagicMock
    ):
        """Test zeroconf query failure is handled gracefully."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: "192.168.1.100",
                CONF_ZEROCONF_NAME: "hcu._homematic._tcp.local.",
                CONF_ZEROCONF_TYPE: "_homematic._tcp.local.",
            },
            entry_id="zc_entry_err",
        )
        entry.add_to_hass(hass)
        coordinator = HcuCoordinator(hass, mock_client, entry)

        mock_aiozc = MagicMock()
        mock_aiozc.async_get_service_info = AsyncMock(
            side_effect=Exception("Zeroconf timeout")
        )

        with patch(
            "homeassistant.components.zeroconf.async_get_async_instance",
            AsyncMock(return_value=mock_aiozc),
        ):
            hosts = await coordinator._async_known_hosts()

        assert hosts == {"192.168.1.100"}


class TestRegisterHcuDevice:
    async def test_register_hcu_device_missing_id_warns_and_returns(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test _register_hcu_device logs warning when hcu_device_id is None."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        mock_client.hcu_device_id = None

        with caplog.at_level(logging.WARNING):
            await coordinator._register_hcu_device()

        assert any(
            "Could not determine HCU device ID" in r.message for r in caplog.records
        )
        assert coordinator.hcu_device_entry_id is None

    async def test_register_hcu_device_with_valid_and_null_mac(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test _register_hcu_device resolves MAC, ignores null MAC, and registers device."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)

        async def fake_known_hosts():
            return {"192.168.1.100", "192.168.1.101", "192.168.1.102"}

        def fake_get_mac_address(ip):
            if ip == "192.168.1.100":
                return "AA:BB:CC:DD:EE:FF"
            if ip == "192.168.1.101":
                return "00:00:00:00:00:00"  # Null MAC placeholder
            raise OSError("Arp lookup failed")

        with (
            patch.object(
                coordinator, "_async_known_hosts", side_effect=fake_known_hosts
            ),
            patch("getmac.get_mac_address", side_effect=fake_get_mac_address),
        ):
            await coordinator._register_hcu_device()

        assert coordinator.hcu_device_entry_id is not None
        device_reg = dr.async_get(hass)
        device = device_reg.async_get(coordinator.hcu_device_entry_id)
        assert device is not None
        assert (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff") in device.connections
        assert len(device.connections) == 1
        assert device.name == "My HCU"
        assert device.sw_version == "1.0.0"


class TestEventMessageHandling:
    def test_handle_user_message_ack(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test _handle_user_message_ack fires event on bus and strips quotes."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        captured = async_capture_events(hass, EVENT_USER_MESSAGE_ACKNOWLEDGEMENT)

        # Message missing id should be ignored
        coordinator._handle_event_message(
            {"type": MSG_TYPE_USER_MESSAGE_ACK, "body": {}}
        )
        assert len(captured) == 0

        # Valid ack with quoted ackType
        coordinator._handle_event_message(
            {
                "type": MSG_TYPE_USER_MESSAGE_ACK,
                "body": {
                    "userMessageId": "msg_123",
                    "ackType": '"CONFIRM"',
                },
            }
        )
        assert len(captured) == 1
        assert captured[0].data == {
            ATTR_USER_MESSAGE_ID: "msg_123",
            ATTR_USER_MESSAGE_ACKNOWLEDGEMENT_TYPE: "CONFIRM",
        }

    def test_handle_event_message_app_user_format_and_advanced_debug(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test handling App User format events with advanced debugging."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        coordinator.advanced_debugging = True
        coordinator._initial_state_loaded = True
        mock_client.process_events.return_value = ProcessEventsResult(updated={"dev2"})

        with caplog.at_level(logging.DEBUG):
            coordinator._handle_event_message(
                {"events": {"0": {"pushEventType": "DEVICE_CHANGED"}}}
            )

        assert any("HMIP_SYSTEM_EVENT:" in r.message for r in caplog.records)
        assert any("process_events result" in r.message for r in caplog.records)

    def test_handle_event_message_advanced_debug_json_error(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test handling advanced debugging fallback when json.dumps fails."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        coordinator.advanced_debugging = True
        coordinator._initial_state_loaded = True

        with (
            patch("json.dumps", side_effect=TypeError("Not JSON serializable")),
            caplog.at_level(logging.DEBUG),
        ):
            coordinator._handle_event_message(
                {"events": {"0": {"pushEventType": "DEVICE_CHANGED"}}}
            )

        assert any("HMIP_SYSTEM_EVENT: (repr):" in r.message for r in caplog.records)

    def test_handle_event_message_before_initial_state_loaded(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test events before initial state is loaded only update cache without triggering entities."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        coordinator._initial_state_loaded = False
        coordinator.async_set_updated_data = MagicMock()

        coordinator._handle_event_message(
            {"events": {"0": {"pushEventType": "DEVICE_CHANGED"}}}
        )

        mock_client.process_events.assert_called_once()
        coordinator.async_set_updated_data.assert_not_called()

    async def test_handle_event_message_device_excluded_reloads(
        self, hass: HomeAssistant, mock_client: MagicMock
    ):
        """Test integration reloads when a device is removed (excluded)."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100"},
            options={CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: True},
            entry_id="reload_entry_excluded",
        )
        entry.add_to_hass(hass)
        coordinator = HcuCoordinator(hass, mock_client, entry)
        coordinator._initial_state_loaded = True
        mock_client.process_events.return_value = ProcessEventsResult(
            excluded={"dev_removed"}
        )

        with patch.object(
            hass.config_entries, "async_reload", AsyncMock()
        ) as mock_reload:
            coordinator._handle_event_message(
                {"events": {"0": {"pushEventType": "DEVICE_REMOVED"}}}
            )
            await hass.async_block_till_done()
            mock_reload.assert_called_once_with(entry.entry_id)

    async def test_handle_event_message_reload_required_delayed(
        self, hass: HomeAssistant, mock_client: MagicMock
    ):
        """Test reload_required triggers delayed reload."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100"},
            options={CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: True},
            entry_id="reload_entry_delayed",
        )
        entry.add_to_hass(hass)
        coordinator = HcuCoordinator(hass, mock_client, entry)
        coordinator._initial_state_loaded = True
        mock_client.process_events.return_value = ProcessEventsResult(
            reload_required={"dev_changed"}
        )

        real_sleep = asyncio.sleep

        async def fake_sleep(duration):
            await real_sleep(0)

        with (
            patch("asyncio.sleep", side_effect=fake_sleep),
            patch.object(
                hass.config_entries, "async_reload", AsyncMock()
            ) as mock_reload,
        ):
            coordinator._handle_event_message(
                {"events": {"0": {"pushEventType": "DEVICE_CHANGED"}}}
            )
            assert coordinator._pending_device_reload_task is not None
            await coordinator._pending_device_reload_task
            assert coordinator._pending_device_reload_task is None
            mock_reload.assert_awaited_once_with(entry.entry_id)

    def test_handle_device_channel_events_skips_malformed(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test skipping non-dict events, wrong pushEventType, or missing fields."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        events = {
            "e1": "not a dict",
            "e2": {"pushEventType": "OTHER_EVENT"},
            "e3": {"pushEventType": "DEVICE_CHANNEL_EVENT"},  # missing deviceId, etc.
        }
        res = coordinator._handle_device_channel_events(events)
        assert res == set()

    def test_get_visible_channel_idx(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
    ):
        """Test visibleChannelIndex lookup."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        # Device has visibleChannelIndex: 10 on channel 1
        assert (
            coordinator._get_visible_channel_idx("3014F711A000000000000001", "1")
            == "10"
        )
        # Device has channel 2 with no visibleChannelIndex -> returns original
        assert (
            coordinator._get_visible_channel_idx("3014F711A000000000000001", "2") == "2"
        )
        # Unknown device -> returns original
        assert coordinator._get_visible_channel_idx("unknown_device", "1") == "1"

    def test_trigger_event_entity_fallback_and_missing(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test _trigger_event_entity visible channel lookup and not found warning."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)

        mock_event_entity = MagicMock(spec=event.TriggerableEvent)
        mock_event_entity._device_id = "3014F711A000000000000001"
        mock_event_entity._channel_index_str = "1"
        coordinator.entities[Platform.EVENT] = [mock_event_entity]

        # Trigger by visible channel idx ("10" maps to channel "1")
        coordinator._trigger_event_entity(
            "3014F711A000000000000001", "10", "press_short"
        )
        mock_event_entity.handle_trigger.assert_called_once_with("press_short")
        assert ("3014F711A000000000000001", "10") in coordinator._event_entities

        # Trigger entity that doesn't exist logs warning
        with caplog.at_level(logging.WARNING):
            coordinator._trigger_event_entity("nonexistent_device", "1", "press_short")

        assert any(
            "Event entity not found: device=nonexistent_device" in r.message
            for r in caplog.records
        )


class TestListeners:
    async def test_listen_for_events_reconnect_lifecycle(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test _listen_for_events reconnect sets entities available and logs reconnected."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)
        attempts = 0

        async def fake_connect():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                return
            if attempts == 2:
                raise ConnectionError("Offline")
            if attempts == 3:
                return
            raise asyncio.CancelledError

        async def fake_listen():
            if attempts == 1:
                raise ConnectionError("Dropped")
            if attempts == 3:
                raise asyncio.CancelledError

        mock_client.connect = AsyncMock(side_effect=fake_connect)
        mock_client.listen = AsyncMock(side_effect=fake_listen)

        with (
            patch(
                "custom_components.hcu_integration.coordinator.asyncio.sleep",
                AsyncMock(),
            ),
            caplog.at_level(logging.INFO),
        ):
            await coordinator._listen_for_events()

        conn_logs = [
            r.message
            for r in caplog.records
            if "WebSocket connected to HCU" in r.message
            or "WebSocket reconnected to HCU" in r.message
        ]
        assert conn_logs == [
            "WebSocket connected to HCU",
            "WebSocket reconnected to HCU",
        ]

    async def test_listen_for_events_unexpected_exception_and_disconnect(
        self,
        hass: HomeAssistant,
        base_config_entry: MockConfigEntry,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test unexpected exception in _listen_for_events and cleanup."""
        coordinator = HcuCoordinator(hass, mock_client, base_config_entry)

        attempts = 0

        async def fake_connect():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                mock_client.is_connected = True
                return
            if attempts == 2:
                mock_client.is_connected = False
                raise RuntimeError("Unexpected crash on reconnect")
            raise asyncio.CancelledError

        async def fake_listen():
            raise RuntimeError("Unexpected crash")

        mock_client.connect = AsyncMock(side_effect=fake_connect)
        mock_client.listen = AsyncMock(side_effect=fake_listen)

        with (
            patch(
                "custom_components.hcu_integration.coordinator.asyncio.sleep",
                AsyncMock(),
            ),
            caplog.at_level(logging.ERROR),
        ):
            await coordinator._listen_for_events()

        assert any("WebSocket error. Reconnecting" in r.message for r in caplog.records)
        mock_client.disconnect.assert_awaited()
        assert not coordinator._connected_event.is_set()

    async def test_listen_for_plugin_events_lifecycle(
        self,
        hass: HomeAssistant,
        mock_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ):
        """Test _listen_for_plugin_events connect, announce, reconnect, and exceptions."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_DUAL},
            entry_id="dual_listen_entry",
        )
        entry.add_to_hass(hass)
        coordinator = HcuCoordinator(hass, mock_client, entry)

        step = 0

        async def fake_connect_plugin():
            nonlocal step
            step += 1
            if step == 1:
                mock_client.is_plugin_connected = True
                return
            if step == 2:
                mock_client.is_plugin_connected = False
                raise ConnectionError("Plugin connect dropped")
            if step == 3:
                mock_client.is_plugin_connected = False
                raise ConnectionError("Plugin retry failed")
            if step == 4:
                mock_client.is_plugin_connected = True
                return
            if step == 5:
                mock_client.is_plugin_connected = False
                raise RuntimeError("Unexpected plugin crash")
            if step == 6:
                mock_client.is_plugin_connected = False
                raise RuntimeError("Unexpected plugin crash retry")
            raise asyncio.CancelledError

        async def fake_listen_plugin():
            if step == 1:
                raise ConnectionError("Plugin listen drop")
            if step == 4:
                mock_client.is_plugin_connected = True
                return

        mock_client.connect_plugin = AsyncMock(side_effect=fake_connect_plugin)
        mock_client.listen_plugin = AsyncMock(side_effect=fake_listen_plugin)

        with (
            patch(
                "custom_components.hcu_integration.coordinator.asyncio.sleep",
                AsyncMock(),
            ),
            patch(
                "custom_components.hcu_integration.coordinator.random.uniform",
                return_value=0.5,
            ) as mock_uniform,
            caplog.at_level(logging.DEBUG),
        ):
            await coordinator._listen_for_plugin_events()

        # Connect, announce, reconnect info/warning logs in exact order
        plugin_conn_logs = [
            r.message
            for r in caplog.records
            if "Plugin WebSocket connected" in r.message
            or "Plugin WebSocket reconnected" in r.message
        ]
        assert plugin_conn_logs == [
            "DualBridge: Plugin WebSocket connected",
            "DualBridge: Plugin WebSocket reconnected",
        ]
        assert any(
            "DualBridge Plugin WebSocket disconnected" in r.message
            for r in caplog.records
        )
        assert any(
            r.levelno == logging.ERROR
            and "DualBridge Plugin WebSocket error. Reconnecting" in r.message
            for r in caplog.records
        )
        mock_client.announce_plugin_ready.assert_awaited()
        assert mock_client.disconnect_plugin.await_count == 2
        for call in mock_uniform.call_args_list:
            assert call.args == (0, WEBSOCKET_RECONNECT_JITTER_MAX)
