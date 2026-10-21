"""Tests for state consistency: event order, added events, reconnect refresh and alarm state."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_TYPE,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    DOMAIN,
)
from custom_components.hcu_integration.coordinator import HcuCoordinator

from .test_alarm_control_panel_coverage import _create_panel


def _device(device_id: str, label: str) -> dict:
    return {"id": device_id, "label": label, "functionalChannels": {}}


# --- Event order (Connect API 6.9: the map key sets the order) ---


def test_process_events_follows_map_key_order(api_client: HcuApiClient) -> None:
    """Events are handled by ascending map key, not by insertion order."""
    api_client._state = {"devices": {"dev1": _device("dev1", "Old")}}
    events = {
        "1": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "Last")},
        "0": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "First")},
    }

    api_client.process_events(events)

    assert api_client._state["devices"]["dev1"]["label"] == "Last"


def test_process_events_orders_keys_numerically(api_client: HcuApiClient) -> None:
    """Key "10" comes after key "2"."""
    api_client._state = {"devices": {"dev1": _device("dev1", "Old")}}
    events = {
        "10": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "Last")},
        "2": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "First")},
    }

    api_client.process_events(events)

    assert api_client._state["devices"]["dev1"]["label"] == "Last"


def test_process_events_keeps_order_of_non_numeric_keys(
    api_client: HcuApiClient,
) -> None:
    """Non-numeric keys keep their order and come after numeric keys."""
    api_client._state = {"devices": {"dev1": _device("dev1", "Old")}}
    events = {
        "b": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "Second")},
        "a": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "Last")},
        "0": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev1", "First")},
    }

    api_client.process_events(events)

    assert api_client._state["devices"]["dev1"]["label"] == "Last"


# --- DEVICE_ADDED / GROUP_ADDED (Connect API 6.9.2 and 6.9.5) ---


def test_process_events_device_added(api_client: HcuApiClient) -> None:
    """A DEVICE_ADDED event stores the device and reports it as included."""
    api_client._state = {"devices": {}, "groups": {}}
    device = _device("dev-new", "New Device")

    result = api_client.process_events(
        {"0": {"pushEventType": "DEVICE_ADDED", "device": device}}
    )

    assert api_client._state["devices"]["dev-new"] == device
    assert result.included == {"dev-new"}
    assert "dev-new" in result.updated


def test_process_events_group_added(api_client: HcuApiClient) -> None:
    """A GROUP_ADDED event stores the group and reports it as included."""
    api_client._state = {"devices": {}, "groups": {}}
    group = {"id": "grp-new", "type": "SWITCHING", "label": "New Group"}

    result = api_client.process_events(
        {"0": {"pushEventType": "GROUP_ADDED", "group": group}}
    )

    assert api_client._state["groups"]["grp-new"] == group
    assert result.included == {"grp-new"}


def test_process_events_device_added_then_changed_in_one_transaction(
    api_client: HcuApiClient,
) -> None:
    """DEVICE_ADDED followed by DEVICE_CHANGED keeps the newer data."""
    api_client._state = {"devices": {}, "groups": {}}

    result = api_client.process_events(
        {
            "0": {"pushEventType": "DEVICE_ADDED", "device": _device("dev-new", "A")},
            "1": {"pushEventType": "DEVICE_CHANGED", "device": _device("dev-new", "B")},
        }
    )

    assert api_client._state["devices"]["dev-new"]["label"] == "B"
    assert result.included == {"dev-new"}


# --- State refresh after a WebSocket reconnect ---


@pytest.fixture
def plugin_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={},
        entry_id="robust_entry",
    )
    entry.add_to_hass(hass)
    return entry


def _state(device_ids: list[str], group_ids: list[str]) -> dict:
    return {
        "devices": {d: _device(d, d) for d in device_ids},
        "groups": {g: {"id": g, "type": "META"} for g in group_ids},
        "home": {"id": "home1"},
    }


def _reconnecting_client(old_state: dict, new_state: dict | Exception) -> MagicMock:
    """Client that connects, drops, reconnects and then stops the listener."""
    client = MagicMock()
    client.hcu_device_id = "hcu"
    client.state = old_state
    client.is_connected = False
    attempts = 0

    async def fake_connect() -> None:
        nonlocal attempts
        attempts += 1
        if attempts > 2:
            raise asyncio.CancelledError

    async def fake_listen() -> None:
        # Let tasks started after the connect run before the next step.
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        if attempts == 1:
            raise ConnectionError("dropped")

    async def fake_get_system_state() -> dict:
        if isinstance(new_state, Exception):
            raise new_state
        client.state = new_state
        return new_state

    client.connect = AsyncMock(side_effect=fake_connect)
    client.listen = AsyncMock(side_effect=fake_listen)
    client.get_system_state = AsyncMock(side_effect=fake_get_system_state)
    client.announce_plugin_ready = AsyncMock()
    return client


async def _run_listener(coordinator: HcuCoordinator, hass: HomeAssistant) -> None:
    with patch(
        "custom_components.hcu_integration.coordinator.asyncio.sleep",
        AsyncMock(),
    ):
        await coordinator._listen_for_events()
    await hass.async_block_till_done()


async def test_reconnect_refreshes_state_and_updates_entities(
    hass: HomeAssistant, plugin_entry: MockConfigEntry
) -> None:
    """After a reconnect the full state is loaded again and every entity updates."""
    old = _state(["dev1"], ["grp1"])
    new = _state(["dev1"], ["grp1"])
    new["devices"]["dev1"]["label"] = "changed while offline"
    client = _reconnecting_client(old, new)
    coordinator = HcuCoordinator(hass, client, plugin_entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    await _run_listener(coordinator, hass)

    client.get_system_state.assert_awaited_once()
    coordinator.async_set_updated_data.assert_called_once_with(
        {"dev1", "grp1", "home1"}
    )


async def test_first_connect_does_not_refresh_state(
    hass: HomeAssistant, plugin_entry: MockConfigEntry
) -> None:
    """The first connection is followed by the setup's own state request only."""
    client = _reconnecting_client(_state(["dev1"], []), _state(["dev1"], []))
    client.listen = AsyncMock(side_effect=asyncio.CancelledError)
    coordinator = HcuCoordinator(hass, client, plugin_entry)
    coordinator._initial_state_loaded = True

    await _run_listener(coordinator, hass)

    client.get_system_state.assert_not_awaited()


async def test_reconnect_before_setup_finished_does_not_refresh(
    hass: HomeAssistant, plugin_entry: MockConfigEntry
) -> None:
    """A reconnect during setup leaves the state request to the setup."""
    client = _reconnecting_client(_state(["dev1"], []), _state(["dev1"], []))
    coordinator = HcuCoordinator(hass, client, plugin_entry)

    await _run_listener(coordinator, hass)

    client.get_system_state.assert_not_awaited()


async def test_reconnect_adds_devices_paired_while_offline(
    hass: HomeAssistant, plugin_entry: MockConfigEntry
) -> None:
    """Devices and groups that appeared during the outage get their entities."""
    client = _reconnecting_client(
        _state(["dev1"], ["grp1"]), _state(["dev1", "dev2"], ["grp1", "grp2"])
    )
    coordinator = HcuCoordinator(hass, client, plugin_entry)
    coordinator._initial_state_loaded = True
    coordinator._handle_dynamic_inclusions = MagicMock()
    coordinator.async_set_updated_data = MagicMock()

    await _run_listener(coordinator, hass)

    coordinator._handle_dynamic_inclusions.assert_called_once_with({"dev2", "grp2"})
    coordinator.async_set_updated_data.assert_called_once()


async def test_reconnect_reloads_when_devices_were_removed(
    hass: HomeAssistant, plugin_entry: MockConfigEntry
) -> None:
    """Devices removed during the outage trigger the same reload as DEVICE_REMOVED."""
    client = _reconnecting_client(_state(["dev1", "dev2"], []), _state(["dev1"], []))
    coordinator = HcuCoordinator(hass, client, plugin_entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _run_listener(coordinator, hass)

    schedule_reload.assert_called_once_with(plugin_entry.entry_id)
    coordinator.async_set_updated_data.assert_not_called()


async def test_reconnect_removed_devices_without_auto_reload(
    hass: HomeAssistant,
) -> None:
    """With auto-reload off, removed devices do not reload; entities still update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: False},
        entry_id="robust_entry_no_reload",
    )
    entry.add_to_hass(hass)
    client = _reconnecting_client(_state(["dev1", "dev2"], []), _state(["dev1"], []))
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    with patch.object(hass.config_entries, "async_schedule_reload") as schedule_reload:
        await _run_listener(coordinator, hass)

    schedule_reload.assert_not_called()
    coordinator.async_set_updated_data.assert_called_once_with({"dev1", "home1"})


@pytest.mark.parametrize(
    "error", [HcuApiError("busy"), TimeoutError(), ConnectionError("gone")]
)
async def test_reconnect_refresh_failure_is_logged(
    hass: HomeAssistant,
    plugin_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """A failed refresh logs a warning and keeps the current state."""
    old = _state(["dev1"], [])
    client = _reconnecting_client(old, error)
    coordinator = HcuCoordinator(hass, client, plugin_entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    with caplog.at_level(logging.WARNING):
        await _run_listener(coordinator, hass)

    assert client.state is old
    coordinator.async_set_updated_data.assert_not_called()
    assert any(
        "Could not refresh the HCU state after reconnecting" in r.message
        for r in caplog.records
    )


# --- Alarm panel must not report "unknown" after arming ---


async def test_alarm_panel_never_writes_unknown_after_arming(
    hass: HomeAssistant,
) -> None:
    """The HCU confirmation replaces the optimistic state without an unknown step."""
    panel, _, client = _create_panel(hass)
    written: list[AlarmControlPanelState | None] = []
    panel.async_write_ha_state = MagicMock(
        side_effect=lambda: written.append(panel.alarm_state)
    )

    await panel.async_alarm_arm_away()
    assert written == [AlarmControlPanelState.ARMING]

    # HCU confirms: the absence zone is now active.
    client.state["groups"]["grp-abs"]["active"] = True
    written.clear()
    panel._handle_coordinator_update()

    assert None not in written
    assert written[-1] == AlarmControlPanelState.ARMED_AWAY
    assert panel.assumed_state is False
