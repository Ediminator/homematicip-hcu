"""Tests for preserving WebSocket events received during a REST state snapshot."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import copy
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    CONF_AUTH_TYPE,
    DOMAIN,
)
from custom_components.hcu_integration.coordinator import HcuCoordinator

DEV_ID = "3014F711A000000000000001"
DEV2_ID = "3014F711A000000000000002"
HCU_ID = "3014F711A0000000000000AA"
GRP_ID = "grp-1"
GRP2_ID = "grp-2"


def _base_snapshot(
    *,
    on: bool = False,
    include_home: bool = True,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "devices": {
            DEV_ID: {
                "id": DEV_ID,
                "type": "PLUGABLE_SWITCH",
                "label": "Hall Plug",
                "permanentlyReachable": True,
                "functionalChannels": {
                    "0": {
                        "functionalChannelType": "DEVICE_BASE",
                        "unreach": False,
                        "lowBat": False,
                    },
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "label": "Channel 1",
                        "on": on,
                    },
                },
            }
        },
        "groups": {
            GRP_ID: {
                "id": GRP_ID,
                "type": "SWITCHING",
                "label": "Living Lights",
                "on": on,
            }
        },
    }
    if include_home:
        state["home"] = {
            "id": "home-1",
            "accessPointId": HCU_ID,
            "weather": {"temperature": 18.0},
        }
    return state


def _build_rest_client(
    hass: HomeAssistant, auth_type: str = AUTH_TYPE_APP
) -> HcuApiClient:
    session = MagicMock(spec=aiohttp.ClientSession)
    return HcuApiClient(
        hass,
        "192.0.2.1",
        "",
        session,
        auth_type=auth_type,
        access_point_id=HCU_ID,
        app_token="app-token",
    )


def _make_gated_cm(
    snapshot: dict[str, Any] | None = None,
    *,
    gate_position: str = "json",
    ok: bool = True,
    status: int = 200,
    text_value: str = "",
    enter_error: Exception | None = None,
    json_error: Exception | None = None,
    json_value: Any = None,
) -> tuple[Any, asyncio.Event, asyncio.Event]:
    entered = asyncio.Event()
    proceed = asyncio.Event()

    class _Resp:
        def __init__(self) -> None:
            self.ok = ok
            self.status = status

        async def text(self) -> str:
            if gate_position == "text":
                entered.set()
                await proceed.wait()
            return text_value

        async def json(self) -> Any:
            if gate_position == "json":
                entered.set()
                await proceed.wait()
            if json_error is not None:
                raise json_error
            if json_value is not None:
                return json_value
            return copy.deepcopy(snapshot)

    class _CM:
        async def __aenter__(self) -> _Resp:
            if gate_position == "enter":
                entered.set()
                await proceed.wait()
            if enter_error is not None:
                raise enter_error
            return _Resp()

        async def __aexit__(self, *args: object) -> bool:
            return False

    return _CM(), entered, proceed


def _switch_event(device_id: str = DEV_ID, *, on: bool = True) -> dict[str, Any]:
    return {
        "0": {
            "pushEventType": "DEVICE_CHANGED",
            "device": {
                "id": device_id,
                "functionalChannels": {"1": {"on": on}},
            },
        }
    }


@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_DUAL])
@pytest.mark.parametrize("gate_position", ["enter", "json"])
async def test_event_during_rest_snapshot_is_kept(
    hass: HomeAssistant, auth_type: str, gate_position: str
) -> None:
    """Event arriving during REST snapshot in App/DualBridge is preserved."""
    client = _build_rest_client(hass, auth_type=auth_type)
    client._state = _base_snapshot(on=False)

    cm, entered, proceed = _make_gated_cm(
        _base_snapshot(on=False), gate_position=gate_position
    )
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events(_switch_event(on=True))
        proceed.set()
        returned = await task

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
    assert returned is client.state


@pytest.mark.parametrize(
    ("event_type", "event_payload", "assert_fn"),
    [
        (
            "DEVICE_CHANGED",
            {
                "pushEventType": "DEVICE_CHANGED",
                "device": {
                    "id": DEV_ID,
                    "functionalChannels": {"1": {"on": True}},
                },
            },
            lambda state: (
                state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
            ),
        ),
        (
            "GROUP_CHANGED",
            {
                "pushEventType": "GROUP_CHANGED",
                "group": {"id": GRP_ID, "on": True},
            },
            lambda state: state["groups"][GRP_ID]["on"] is True,
        ),
        (
            "HOME_CHANGED",
            {
                "pushEventType": "HOME_CHANGED",
                "home": {
                    "id": "home-1",
                    "accessPointId": HCU_ID,
                    "weather": {"temperature": 25.5},
                },
            },
            lambda state: state["home"]["weather"]["temperature"] == 25.5,
        ),
        (
            "DEVICE_ADDED",
            {
                "pushEventType": "DEVICE_ADDED",
                "device": {
                    "id": DEV2_ID,
                    "type": "PLUGABLE_SWITCH",
                    "label": "Added Device",
                    "functionalChannels": {},
                },
            },
            lambda state: (
                DEV2_ID in state["devices"]
                and state["devices"][DEV2_ID]["label"] == "Added Device"
            ),
        ),
        (
            "GROUP_ADDED",
            {
                "pushEventType": "GROUP_ADDED",
                "group": {
                    "id": GRP2_ID,
                    "type": "SWITCHING",
                    "label": "Added Group",
                },
            },
            lambda state: (
                GRP2_ID in state["groups"]
                and state["groups"][GRP2_ID]["label"] == "Added Group"
            ),
        ),
        (
            "DEVICE_REMOVED",
            {
                "pushEventType": "DEVICE_REMOVED",
                "deviceId": DEV_ID,
            },
            lambda state: DEV_ID not in state["devices"],
        ),
        (
            "GROUP_REMOVED",
            {
                "pushEventType": "GROUP_REMOVED",
                "groupId": GRP_ID,
            },
            lambda state: GRP_ID not in state["groups"],
        ),
    ],
)
async def test_every_state_event_type_survives_the_snapshot(
    hass: HomeAssistant,
    event_type: str,
    event_payload: dict[str, Any],
    assert_fn: Callable[[dict[str, Any]], bool],
) -> None:
    """All seven state-changing push event types survive the REST snapshot."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events({"0": event_payload})
        proceed.set()
        await task

    assert assert_fn(client.state), f"{event_type} was lost after snapshot"


async def test_replay_keeps_arrival_order(hass: HomeAssistant) -> None:
    """Replay preserves batch arrival order and numeric map-key order within a batch."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events(
            {
                "0": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {"id": DEV_ID, "label": "First Batch"},
                }
            }
        )
        client.process_events(
            {
                "0": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {"id": DEV_ID, "label": "Second Batch"},
                },
                "10": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {
                        "id": DEV_ID,
                        "functionalChannels": {"1": {"on": True}},
                    },
                },
                "2": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {
                        "id": DEV_ID,
                        "functionalChannels": {"1": {"on": False}},
                    },
                },
            }
        )
        proceed.set()
        await task

    assert client.state["devices"][DEV_ID]["label"] == "Second Batch"
    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True


async def test_partial_event_is_merged_into_the_snapshot(
    hass: HomeAssistant,
) -> None:
    """Partial DEVICE_CHANGED updates only its field and preserves snapshot fields."""
    snapshot = {
        "devices": {
            DEV_ID: {
                "id": DEV_ID,
                "type": "DIMMER",
                "label": "Living Room",
                "permanentlyReachable": True,
                "functionalChannels": {
                    "0": {
                        "functionalChannelType": "DEVICE_BASE",
                        "unreach": False,
                        "lowBat": False,
                    },
                    "1": {
                        "functionalChannelType": "DIMMER_CHANNEL",
                        "label": "Ceiling Lamp",
                        "on": False,
                        "dimLevel": 0.2,
                    },
                },
            }
        },
        "groups": {},
        "home": {"id": "home-1", "accessPointId": HCU_ID},
    }
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = copy.deepcopy(snapshot)

    cm, entered, proceed = _make_gated_cm(snapshot)
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events(
            {
                "0": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {
                        "id": DEV_ID,
                        "functionalChannels": {"1": {"dimLevel": 0.75}},
                    },
                }
            }
        )
        proceed.set()
        await task

    dev = client.state["devices"][DEV_ID]
    assert dev["label"] == "Living Room"
    assert dev["permanentlyReachable"] is True
    assert dev["functionalChannels"]["0"]["unreach"] is False
    assert dev["functionalChannels"]["0"]["lowBat"] is False
    assert dev["functionalChannels"]["1"]["label"] == "Ceiling Lamp"
    assert dev["functionalChannels"]["1"]["on"] is False
    assert dev["functionalChannels"]["1"]["dimLevel"] == 0.75


async def test_added_then_changed_device_survives(hass: HomeAssistant) -> None:
    """DEVICE_ADDED followed by DEVICE_CHANGED during snapshot keeps the new device."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events(
            {
                "0": {
                    "pushEventType": "DEVICE_ADDED",
                    "device": {
                        "id": DEV2_ID,
                        "type": "PLUGABLE_SWITCH",
                        "label": "Initial Label",
                        "functionalChannels": {
                            "1": {
                                "functionalChannelType": "SWITCH_CHANNEL",
                                "on": False,
                            }
                        },
                    },
                }
            }
        )
        client.process_events(
            {
                "0": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {
                        "id": DEV2_ID,
                        "functionalChannels": {"1": {"on": True}},
                    },
                }
            }
        )
        proceed.set()
        await task

    assert DEV2_ID in client.state["devices"]
    assert client.state["devices"][DEV2_ID]["label"] == "Initial Label"
    assert client.state["devices"][DEV2_ID]["functionalChannels"]["1"]["on"] is True


async def test_events_before_the_call_are_not_replayed(hass: HomeAssistant) -> None:
    """Events processed before get_system_state starts are not replayed."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    client.process_events(_switch_event(on=True))
    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True

    cm, _entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    proceed.set()
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        await client.get_system_state()

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is False


async def test_events_after_the_call_are_handled_as_before(
    hass: HomeAssistant,
) -> None:
    """Events processed after get_system_state returns work normally."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm, _entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    proceed.set()
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        await client.get_system_state()

    result = client.process_events(_switch_event(on=True))
    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
    assert DEV_ID in result.updated


@pytest.mark.parametrize(
    "failure_mode",
    ["http_500", "client_error", "invalid_json", "non_dict_body", "cancelled"],
)
async def test_failed_snapshot_keeps_cache_and_leaves_nothing_behind(
    hass: HomeAssistant, failure_mode: str
) -> None:
    """Failed/cancelled snapshots preserve the cache and drop their event buffer."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    old_cache = _base_snapshot(on=False)
    client._state = old_cache

    if failure_mode == "http_500":
        cm1, entered1, proceed1 = _make_gated_cm(
            gate_position="text",
            ok=False,
            status=500,
            text_value="Internal Server Error",
        )
    elif failure_mode == "client_error":
        cm1, entered1, proceed1 = _make_gated_cm(
            gate_position="enter",
            enter_error=aiohttp.ClientConnectionError("conn reset"),
        )
    elif failure_mode == "invalid_json":
        cm1, entered1, proceed1 = _make_gated_cm(
            gate_position="json",
            json_error=ValueError("invalid json"),
        )
    elif failure_mode == "non_dict_body":
        cm1, entered1, proceed1 = _make_gated_cm(
            gate_position="json",
            json_value=["not", "a", "dict"],
        )
    else:
        cm1, entered1, proceed1 = _make_gated_cm(_base_snapshot(on=False))

    cm2, _entered2, proceed2 = _make_gated_cm(_base_snapshot(on=False))
    proceed2.set()
    client._session.post = MagicMock(side_effect=[cm1, cm2])

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task1 = asyncio.create_task(client.get_system_state())
        await entered1.wait()
        client.process_events(_switch_event(on=True))

        if failure_mode == "cancelled":
            task1.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task1
        else:
            proceed1.set()
            with pytest.raises(HcuApiError):
                await task1

        assert client._state is old_cache
        assert client._state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
        assert getattr(client, "_snapshot_event_buffers", []) == []

        # Second call succeeds with on=False and no events during it;
        # the event from the failed window must not be replayed.
        await client.get_system_state()

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is False
    assert getattr(client, "_snapshot_event_buffers", []) == []


@pytest.mark.parametrize("finish_order", ["first_first", "second_first"])
async def test_overlapping_snapshots_keep_later_events(
    hass: HomeAssistant, finish_order: str
) -> None:
    """Overlapping REST snapshots both keep events that arrived after both started."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm1, entered1, proceed1 = _make_gated_cm(_base_snapshot(on=False))
    cm2, entered2, proceed2 = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(side_effect=[cm1, cm2])

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task1 = asyncio.create_task(client.get_system_state())
        await entered1.wait()
        task2 = asyncio.create_task(client.get_system_state())
        await entered2.wait()

        client.process_events(_switch_event(on=True))

        if finish_order == "first_first":
            proceed1.set()
            await task1
            proceed2.set()
            await task2
        else:
            proceed2.set()
            await task2
            proceed1.set()
            await task1

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
    assert client._snapshot_event_buffers == []


async def test_overlapping_snapshot_does_not_record_earlier_replay(
    hass: HomeAssistant,
) -> None:
    """An event before call 2 starts is not re-recorded into call 2 when call 1 replays."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm1, entered1, proceed1 = _make_gated_cm(_base_snapshot(on=False))
    cm2, entered2, proceed2 = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(side_effect=[cm1, cm2])

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task1 = asyncio.create_task(client.get_system_state())
        await entered1.wait()

        # Arrives before call 2 starts.
        client.process_events(_switch_event(on=True))

        task2 = asyncio.create_task(client.get_system_state())
        await entered2.wait()

        proceed1.set()
        await task1
        assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True

        proceed2.set()
        await task2

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is False
    assert client._snapshot_event_buffers == []


async def test_overlapping_snapshots_later_ends_before_event(
    hass: HomeAssistant,
) -> None:
    """When a later overlapping snapshot finishes first, the earlier call still keeps events."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm1, entered1, proceed1 = _make_gated_cm(_base_snapshot(on=False))
    cm2, entered2, proceed2 = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(side_effect=[cm1, cm2])

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task1 = asyncio.create_task(client.get_system_state())
        await entered1.wait()
        task2 = asyncio.create_task(client.get_system_state())
        await entered2.wait()

        # Later call finishes while both buffers are equal (empty).
        proceed2.set()
        await task2

        client.process_events(_switch_event(on=True))

        proceed1.set()
        await task1

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
    assert client._snapshot_event_buffers == []


async def test_overlapping_snapshots_later_fails_before_event(
    hass: HomeAssistant,
) -> None:
    """When a later overlapping snapshot fails first, the earlier call still keeps events."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm1, entered1, proceed1 = _make_gated_cm(_base_snapshot(on=False))
    cm2, entered2, proceed2 = _make_gated_cm(
        gate_position="text",
        ok=False,
        status=500,
        text_value="Internal Server Error",
    )
    client._session.post = MagicMock(side_effect=[cm1, cm2])

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task1 = asyncio.create_task(client.get_system_state())
        await entered1.wait()
        task2 = asyncio.create_task(client.get_system_state())
        await entered2.wait()

        proceed2.set()
        with pytest.raises(HcuApiError):
            await task2

        client.process_events(_switch_event(on=True))

        proceed1.set()
        await task1

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
    assert client._snapshot_event_buffers == []


async def test_sequential_snapshots_both_keep_events(
    hass: HomeAssistant,
) -> None:
    """Two sequential snapshot calls each preserve events received during their own window."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm1, entered1, proceed1 = _make_gated_cm(_base_snapshot(on=False))
    cm2, entered2, proceed2 = _make_gated_cm(_base_snapshot(on=True))
    client._session.post = MagicMock(side_effect=[cm1, cm2])

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task1 = asyncio.create_task(client.get_system_state())
        await entered1.wait()
        client.process_events(_switch_event(on=True))
        proceed1.set()
        await task1
        assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True

        task2 = asyncio.create_task(client.get_system_state())
        await entered2.wait()
        client.process_events(_switch_event(on=False))
        proceed2.set()
        await task2

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is False
    assert client._snapshot_event_buffers == []
    assert client._replaying_snapshot_events is False


async def test_live_handling_is_unchanged_during_the_call(
    hass: HomeAssistant,
) -> None:
    """Events during the REST call still update the current cache immediately."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()

        result = client.process_events(_switch_event(on=True))
        assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
        assert result.updated == {DEV_ID}
        assert result.included == set()
        assert result.excluded == set()

        proceed.set()
        await task


async def test_replay_does_not_run_the_event_callback(hass: HomeAssistant) -> None:
    """Replay updates cache only and never triggers _event_callback."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)
    callback = MagicMock()
    client.register_event_callback(callback)

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events(
            {
                "0": {
                    "pushEventType": "DEVICE_CHANNEL_EVENT",
                    "deviceId": DEV_ID,
                    "channelIndex": 1,
                    "channelEventType": "PRESS_SHORT",
                },
                "1": {
                    "pushEventType": "DEVICE_CHANGED",
                    "device": {
                        "id": DEV_ID,
                        "functionalChannels": {"1": {"on": True}},
                    },
                },
            }
        )
        callback.assert_not_called()
        proceed.set()
        await task

    callback.assert_not_called()
    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True


async def test_hcu_ids_follow_the_final_cache(hass: HomeAssistant) -> None:
    """HCU device IDs are recomputed from the final cache after replay."""
    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False, include_home=False)

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False, include_home=False))
    client._session.post = MagicMock(return_value=cm)

    new_hcu_id = "3014F711A000000000000099"
    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        task = asyncio.create_task(client.get_system_state())
        await entered.wait()
        client.process_events(
            {
                "0": {
                    "pushEventType": "HOME_CHANGED",
                    "home": {
                        "id": "home-1",
                        "accessPointId": new_hcu_id,
                    },
                }
            }
        )
        proceed.set()
        await task

    assert client.hcu_device_id == new_hcu_id
    assert new_hcu_id in client.hcu_part_device_ids


async def test_reconnect_refresh_keeps_event_from_the_window(
    hass: HomeAssistant,
) -> None:
    """Coordinator reconnect refresh keeps WS events received while REST runs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.1", CONF_AUTH_TYPE: AUTH_TYPE_APP},
        options={},
        entry_id="tr2-reconnect-refresh",
    )
    entry.add_to_hass(hass)

    client = _build_rest_client(hass, auth_type=AUTH_TYPE_APP)
    client._state = _base_snapshot(on=False)
    ws = MagicMock()
    ws.closed = False
    client._websocket = ws

    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    coordinator._connection_ready = False
    coordinator._connection_generation = 1
    coordinator.async_set_updated_data = MagicMock()

    cm, entered, proceed = _make_gated_cm(_base_snapshot(on=False))
    client._session.post = MagicMock(return_value=cm)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        refresh_task = asyncio.create_task(
            coordinator._async_refresh_state_after_reconnect()
        )
        await entered.wait()

        coordinator._handle_event_message({"events": _switch_event(on=True)})

        proceed.set()
        await refresh_task

    assert client.state["devices"][DEV_ID]["functionalChannels"]["1"]["on"] is True
    assert coordinator.connection_ready is True
    assert len(coordinator.async_set_updated_data.call_args_list) == 2
    refresh_updated_ids = coordinator.async_set_updated_data.call_args_list[-1][0][0]
    assert DEV_ID in refresh_updated_ids
