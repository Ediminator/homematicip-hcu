"""Entities are unavailable while the HCU connection is down.

After a reconnect they stay unavailable until the full state has been loaded
again, so they never show values that changed while the connection was down.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import CONF_HOST, STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_TYPE,
    DOMAIN,
    WEBSOCKET_RECONNECT_INITIAL_DELAY,
)
from custom_components.hcu_integration.coordinator import HcuCoordinator
from custom_components.hcu_integration.entity import (
    HcuBaseEntity,
    HcuGroupBaseEntity,
    HcuHomeBaseEntity,
)

from .test_dynamic_devices import _make_client
from .test_state_consistency import _state

SLEEP = "custom_components.hcu_integration.coordinator.asyncio.sleep"
SWITCH_ID = "3014F711A0000000000000AB"
SWITCH_ENTITY = "switch.kitchen_plug"


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={},
        entry_id="connection_entry",
    )
    entry.add_to_hass(hass)
    return entry


def _dropping_client(state: dict) -> MagicMock:
    """Client whose connection drops right after it was made."""
    client = MagicMock()
    client.state = state
    client.is_connected = False
    client.connect = AsyncMock()
    client.listen = AsyncMock(side_effect=ConnectionError("HCU went away"))
    client.disconnect = AsyncMock()
    client.announce_plugin_ready = AsyncMock()
    return client


async def test_connection_drop_updates_every_entity(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Losing the WebSocket makes every device, group and home entity write its state."""
    client = _dropping_client(_state(["dev1"], ["grp1"]))
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    updates: list[set[str]] = []
    coordinator.async_add_listener(lambda: updates.append(set(coordinator.data)))

    with (
        patch(SLEEP, AsyncMock(side_effect=asyncio.CancelledError)),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._listen_for_events()

    assert coordinator.connection_ready is False
    assert updates == [{"dev1", "grp1", "home1"}]


async def test_connection_drop_without_home_in_state(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A state without a home object still updates the device entities."""
    client = _dropping_client({"devices": {"dev1": {"id": "dev1"}}, "groups": {}})
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    with (
        patch(SLEEP, AsyncMock(side_effect=asyncio.CancelledError)),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._listen_for_events()

    coordinator.async_set_updated_data.assert_called_once_with({"dev1"})


async def test_repeated_connection_failures_update_entities_once(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Failed reconnect attempts do not write the entity states again."""
    client = _dropping_client(_state(["dev1"], []))
    client.connect = AsyncMock(
        side_effect=[None, ConnectionError("down"), asyncio.CancelledError()]
    )
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    with patch(SLEEP, AsyncMock()):
        await coordinator._listen_for_events()

    coordinator.async_set_updated_data.assert_called_once_with({"dev1", "home1"})


@pytest.mark.parametrize(
    "make_entity",
    [
        lambda coordinator, client: HcuBaseEntity(
            coordinator,
            client,
            {"id": "dev1", "permanentlyReachable": True, "functionalChannels": {}},
            "1",
        ),
        lambda coordinator, client: HcuGroupBaseEntity(
            coordinator, client, {"id": "grp1"}
        ),
        lambda coordinator, client: HcuHomeBaseEntity(coordinator, client),
    ],
    ids=["device", "group", "home"],
)
def test_entities_unavailable_until_state_is_loaded_again(make_entity) -> None:
    """A connected socket alone is not enough while the state is outdated."""
    client = MagicMock()
    client.is_connected = True
    client.state = {"home": {"id": "home1"}}
    device = {"id": "dev1", "permanentlyReachable": True, "functionalChannels": {}}
    client.get_device_by_address.return_value = device
    client.get_group_by_id.return_value = {"id": "grp1"}
    coordinator = MagicMock()
    coordinator.connection_ready = True
    entity = make_entity(coordinator, client)

    assert entity.available is True
    coordinator.connection_ready = False
    assert entity.available is False


async def test_refresh_marks_connection_ready(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """After the state was loaded again, entities update and become available."""
    client = MagicMock()
    client.state = _state(["dev1"], [])
    client.is_connected = True
    client.get_system_state = AsyncMock(return_value=client.state)
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._connection_ready = False
    ready_on_update: list[bool] = []
    coordinator.async_set_updated_data = MagicMock(
        side_effect=lambda ids: ready_on_update.append(coordinator.connection_ready)
    )

    await coordinator._async_refresh_state_after_reconnect()

    assert coordinator.connection_ready is True
    # Entities are written after the flag is set, so they show as available.
    assert ready_on_update == [True]
    coordinator.async_set_updated_data.assert_called_once_with({"dev1", "home1"})


async def test_refresh_failure_is_retried_while_connected(
    hass: HomeAssistant, entry: MockConfigEntry, caplog: pytest.LogCaptureFixture
) -> None:
    """A failed refresh is retried with a delay instead of leaving entities unavailable."""
    client = MagicMock()
    client.state = _state(["dev1"], [])
    client.is_connected = True
    client.get_system_state = AsyncMock(
        side_effect=[HcuApiError("busy"), HcuApiError("busy"), client.state]
    )
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._connection_ready = False
    coordinator.async_set_updated_data = MagicMock()

    with patch(SLEEP, AsyncMock()) as sleep, caplog.at_level(logging.DEBUG):
        await coordinator._async_refresh_state_after_reconnect()

    assert client.get_system_state.await_count == 3
    assert [c.args for c in sleep.await_args_list] == [
        (WEBSOCKET_RECONNECT_INITIAL_DELAY,),
        (WEBSOCKET_RECONNECT_INITIAL_DELAY * 2,),
    ]
    assert coordinator.connection_ready is True
    coordinator.async_set_updated_data.assert_called_once_with({"dev1", "home1"})
    retry_logs = [
        r.levelname for r in caplog.records if "Retrying in" in r.getMessage()
    ]
    # Logged once as a warning, then only at debug level.
    assert retry_logs == ["WARNING", "DEBUG"]


async def test_refresh_for_an_old_connection_does_not_mark_ready(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """A refresh that finishes after a newer connection was made leaves that to its own refresh."""
    client = MagicMock()
    client.state = _state(["dev1"], [])
    client.is_connected = True
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._connection_ready = False
    coordinator.async_set_updated_data = MagicMock()

    async def reconnect_while_loading() -> dict:
        coordinator._connection_generation += 1
        return client.state

    client.get_system_state = AsyncMock(side_effect=reconnect_while_loading)

    await coordinator._async_refresh_state_after_reconnect()

    assert coordinator.connection_ready is False


async def test_refresh_stops_retrying_when_connection_is_lost(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """Without a connection the refresh gives up; the next connection starts a new one."""
    client = MagicMock()
    client.state = _state(["dev1"], [])
    client.is_connected = False
    client.get_system_state = AsyncMock(side_effect=ConnectionError("gone"))
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._connection_ready = False
    coordinator.async_set_updated_data = MagicMock()

    with patch(SLEEP, AsyncMock()) as sleep:
        await coordinator._async_refresh_state_after_reconnect()

    client.get_system_state.assert_awaited_once()
    sleep.assert_not_awaited()
    assert coordinator.connection_ready is False
    coordinator.async_set_updated_data.assert_not_called()


async def test_app_user_first_connect_after_setup_updates_entities(
    hass: HomeAssistant,
) -> None:
    """App User: entities added before the WebSocket connected update once it is up."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_APP},
        options={},
        entry_id="app_entry",
    )
    entry.add_to_hass(hass)
    client = _dropping_client(_state(["dev1"], []))
    client.listen = AsyncMock(side_effect=asyncio.CancelledError)
    client.get_system_state = AsyncMock()
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    coordinator.async_set_updated_data = MagicMock()

    await coordinator._listen_for_events()

    coordinator.async_set_updated_data.assert_called_once_with({"dev1", "home1"})
    client.get_system_state.assert_not_awaited()


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_switch_state_through_drop_reconnect_and_refresh(
    hass: HomeAssistant,
) -> None:
    """End to end: on, unavailable after the drop and before the refresh, then the new value."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        options={},
        unique_id="hcu-test-1",
    )
    entry.add_to_hass(hass)
    client = _make_client()
    client._state["devices"][SWITCH_ID] = {
        "id": SWITCH_ID,
        "type": "PLUGABLE_SWITCH",
        "modelType": "HmIP-PS",
        "label": "Kitchen Plug",
        "oem": "eQ-3",
        "permanentlyReachable": True,
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "index": 1,
                "groups": ["room-1"],
                "on": True,
            },
        },
    }
    with (
        patch("custom_components.hcu_integration.HcuApiClient", return_value=client),
        patch(
            "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    coordinator: HcuCoordinator = entry.runtime_data
    coordinator._initial_state_loaded = True
    assert hass.states.get(SWITCH_ENTITY).state == STATE_ON

    # The connection drops.
    client.is_connected = False
    client.connect = AsyncMock()
    client.listen = AsyncMock(side_effect=ConnectionError("HCU went away"))
    with (
        patch(SLEEP, AsyncMock(side_effect=asyncio.CancelledError)),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._listen_for_events()
    assert hass.states.get(SWITCH_ENTITY).state == STATE_UNAVAILABLE

    # Reconnected: an event arrives before the refresh. The switch stays
    # unavailable because the rest of its state may be outdated.
    client.is_connected = True
    coordinator._connection_generation += 1
    coordinator._handle_event_message(
        {
            "type": "HMIP_SYSTEM_EVENT",
            "body": {
                "eventTransaction": {
                    "events": {
                        "0": {
                            "pushEventType": "DEVICE_CHANGED",
                            "device": {
                                "id": SWITCH_ID,
                                "functionalChannels": {"1": {"on": True}},
                            },
                        }
                    }
                }
            },
        }
    )
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH_ENTITY).state == STATE_UNAVAILABLE

    # The refresh loads the state that changed while the connection was down.
    async def load_state() -> dict:
        client._state["devices"][SWITCH_ID]["functionalChannels"]["1"]["on"] = False
        return client._state

    client.get_system_state = AsyncMock(side_effect=load_state)
    await coordinator._async_refresh_state_after_reconnect()
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH_ENTITY).state == STATE_OFF

    await hass.config_entries.async_unload(entry.entry_id)
