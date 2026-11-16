"""Tests for retried command payloads and for requests that are already settled."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
)

DIM_PATH = "/hmip/device/control/setDimLevel"
COLOR_PATH = "/hmip/device/control/setHueSaturationDimLevel"
SIGNAL_PATH = "/hmip/device/control/setOpticalSignal"
SLATS_PATH = "/hmip/device/control/setSlatsLevel"
PARTY_PATH = "/hmip/group/heating/activatePartyMode"
SCOPE = ("device", "dev-1", "1")


@pytest.mark.parametrize(
    ("override_seq", "expected_dim_level"),
    [
        (4, 0.8),  # recorded by an older command: the retry keeps its own value
        (5, 0.8),  # recorded by this command itself: nothing to refresh
        (6, 0.3),  # recorded by a newer command: the retry adopts the newer value
    ],
)
def test_retry_body_adopts_only_values_of_newer_commands(
    api_client: HcuApiClient, override_seq: int, expected_dim_level: float
):
    """A retried command takes a shared field only from a command sent after it."""
    api_client._scope_field_overrides[SCOPE] = {"dimLevel": (override_seq, 0.3)}
    body = {"deviceId": "dev-1", "channelIndex": 1, "hue": 120, "dimLevel": 0.8}
    sent = dict(body)

    refreshed = api_client._refresh_retry_body(COLOR_PATH, SCOPE, 5, body)

    assert refreshed == {**sent, "dimLevel": expected_dim_level}
    # The caller's body is never changed in place.
    assert body == sent
    assert (refreshed is body) is (expected_dim_level == 0.8)


def test_retry_body_refreshes_each_field_on_its_own(api_client: HcuApiClient):
    """Only the fields with a newer value change; the others keep the sent value."""
    api_client._scope_field_overrides[SCOPE] = {
        "dimLevel": (9, 0.1),
        "simpleRGBColorState": (2, "RED"),
    }
    body = {"deviceId": "dev-1", "dimLevel": 1.0, "simpleRGBColorState": "BLUE"}

    assert api_client._refresh_retry_body(SIGNAL_PATH, SCOPE, 5, body) == {
        "deviceId": "dev-1",
        "dimLevel": 0.1,
        "simpleRGBColorState": "BLUE",
    }


@pytest.mark.parametrize(
    ("path", "body", "overrides", "expected"),
    [
        # The shading level is stored under one name for both payload keys.
        (
            SLATS_PATH,
            {"deviceId": "dev-1", "shutterLevel": 0.5, "slatsLevel": 0.2},
            {"primary_level": (9, 0.9)},
            {"deviceId": "dev-1", "shutterLevel": 0.9, "slatsLevel": 0.2},
        ),
        (
            PARTY_PATH,
            {"groupId": "g-1", "temperature": 18.0, "endTime": "2030_01_01 10:00"},
            {"setPointTemperature": (9, 22.5)},
            {"groupId": "g-1", "temperature": 22.5, "endTime": "2030_01_01 10:00"},
        ),
        # A field the retried payload does not carry is never added.
        (
            COLOR_PATH,
            {"deviceId": "dev-1", "hue": 120},
            {"dimLevel": (9, 0.1)},
            {"deviceId": "dev-1", "hue": 120},
        ),
        (
            SIGNAL_PATH,
            {"deviceId": "dev-1", "dimLevel": 1.0, "simpleRGBColorState": "BLUE"},
            {"dimLevel": (9, 0.1), "simpleRGBColorState": (8, "GREEN")},
            {"deviceId": "dev-1", "dimLevel": 0.1, "simpleRGBColorState": "GREEN"},
        ),
        # A path without shared fields is sent again unchanged.
        (
            "/hmip/device/control/setSwitchState",
            {"deviceId": "dev-1", "on": True, "dimLevel": 0.8},
            {"dimLevel": (9, 0.1)},
            {"deviceId": "dev-1", "on": True, "dimLevel": 0.8},
        ),
    ],
)
def test_retry_body_field_mapping(
    api_client: HcuApiClient,
    path: str,
    body: dict[str, Any],
    overrides: dict[str, tuple[int, Any]],
    expected: dict[str, Any],
):
    """Each retried action refreshes exactly the payload keys mapped for it."""
    api_client._scope_field_overrides[SCOPE] = overrides

    assert api_client._refresh_retry_body(path, SCOPE, 5, body) == expected


@pytest.mark.parametrize(
    ("scope", "body"),
    [
        (None, {"deviceId": "dev-1", "dimLevel": 0.8}),
        (SCOPE, {}),
        (("device", "other", "1"), {"deviceId": "other", "dimLevel": 0.8}),
    ],
)
def test_retry_body_is_returned_unchanged_without_overrides(
    api_client: HcuApiClient, scope: tuple[str, ...] | None, body: dict[str, Any]
):
    """Without a scope, a payload or recorded values the same body is sent again."""
    api_client._scope_field_overrides[SCOPE] = {"dimLevel": (9, 0.1)}

    assert api_client._refresh_retry_body(COLOR_PATH, scope, 5, body) is body


@pytest.mark.parametrize(
    ("action", "values", "expected"),
    [
        # Without a brightness the colour command leaves a pending brightness
        # command alone.
        (
            "setHueSaturationDimLevel",
            {"hue": 120, "saturationLevel": 1.0},
            ("light_color", ("light_off", "switch_state")),
        ),
        (
            "setColorTemperatureDimLevel",
            {"colorTemperature": 3000},
            ("light_color", ("light_off", "switch_state")),
        ),
        (
            "setOpticalSignal",
            {"opticalSignalBehaviour": "ON"},
            ("optical_signal", ("light_off", "switch_state")),
        ),
        # With a brightness it replaces it.
        (
            "setHueSaturationDimLevel",
            {"hue": 120, "saturationLevel": 1.0, "dimLevel": 0.5},
            ("light_color", ("light_off", "switch_state", "dim_level")),
        ),
        (
            "setOpticalSignal",
            {
                "opticalSignalBehaviour": "ON",
                "dimLevel": 0.5,
                "simpleRGBColorState": "RED",
            },
            (
                "optical_signal",
                ("light_off", "switch_state", "dim_level", "light_color"),
            ),
        ),
    ],
)
def test_light_command_replaces_brightness_only_when_it_carries_one(
    action: str, values: dict[str, Any], expected: tuple[str, tuple[str, ...]]
):
    """The settings a light command replaces depend on the fields it carries."""
    body = {"deviceId": "dev-1", "channelIndex": 1, **values}

    assert (
        HcuApiClient._command_aspect_spec("/hmip/device/control/" + action, body)
        == expected
    )


class _GatedResponse:
    """Async context manager for a fake REST response that can be held back."""

    def __init__(self, response: MagicMock, gate: asyncio.Event | None = None) -> None:
        self._response = response
        self._gate = gate

    async def __aenter__(self) -> MagicMock:
        if self._gate is not None:
            await self._gate.wait()
        return self._response

    async def __aexit__(self, *args: object) -> bool:
        return False


def _rest_response(*, busy: bool) -> MagicMock:
    response = MagicMock()
    response.ok = not busy
    response.status = 400 if busy else 200
    response.text = AsyncMock(return_value='{"errorCode": "DEVICE_BUSY"}')
    response.content_length = 0
    response.content_type = "application/json"
    return response


async def test_busy_retry_keeps_its_value_over_an_older_command(
    api_client: HcuApiClient,
):
    """A retried colour command does not fall back to an older brightness command.

    The brightness command (0.3) is sent first and succeeds while the colour
    command (brightness 0.8) is already waiting. The colour command is then
    rejected once as busy. Its retry has to send 0.8 again, not 0.3.
    """
    api_client._app_token = "app-token"
    posted: list[tuple[str, dict[str, Any]]] = []
    dim_in_flight = asyncio.Event()
    release_dim = asyncio.Event()
    color_attempts = 0

    def fake_post(url: str, *, json: dict[str, Any], **_kwargs: Any) -> _GatedResponse:
        nonlocal color_attempts
        action = url.rsplit("/", 1)[-1]
        posted.append((action, dict(json)))
        if action == "setDimLevel":
            dim_in_flight.set()
            return _GatedResponse(_rest_response(busy=False), release_dim)
        color_attempts += 1
        return _GatedResponse(_rest_response(busy=color_attempts == 1))

    api_client._session.post = MagicMock(side_effect=fake_post)
    dim_body = {"deviceId": "dev-1", "channelIndex": 1, "dimLevel": 0.3}
    color_body = {
        "deviceId": "dev-1",
        "channelIndex": 1,
        "hue": 120,
        "saturationLevel": 1.0,
        "dimLevel": 0.8,
    }

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch("custom_components.hcu_integration.api.API_RETRY_BASE_DELAY", 0),
    ):
        dim_task = asyncio.create_task(
            api_client._async_app_rest_call(DIM_PATH, dim_body)
        )
        async with asyncio.timeout(1.0):
            await dim_in_flight.wait()
        color_task = asyncio.create_task(
            api_client._async_app_rest_call(COLOR_PATH, color_body)
        )
        # One loop turn runs the colour command up to the command lock, which
        # the brightness command still holds.
        await asyncio.sleep(0)
        assert api_client._command_seq == 2
        assert api_client._scope_active_counts == {SCOPE: 2}
        release_dim.set()

        async with asyncio.timeout(1.0):
            assert await dim_task == {}
            assert await color_task == {}

    assert posted == [
        ("setDimLevel", dim_body),
        ("setHueSaturationDimLevel", color_body),
        ("setHueSaturationDimLevel", color_body),
    ]
    assert api_client._scope_field_overrides == {}
    assert api_client._scope_active_counts == {}


def _system_response(request_id: str) -> dict[str, Any]:
    return {
        "type": "HMIP_SYSTEM_RESPONSE",
        "id": request_id,
        "body": {"code": 200, "body": {"late": True}},
    }


async def test_late_response_for_a_cancelled_request_is_dropped(
    api_client: HcuApiClient,
):
    """A response that arrives after the request was cancelled changes nothing."""
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.cancel()
    api_client._pending_requests["req-1"] = future
    hook = MagicMock()
    api_client._response_hooks["req-1"] = hook

    api_client._handle_incoming_message(_system_response("req-1"))

    assert future.cancelled()
    assert api_client._pending_requests == {}
    hook.assert_not_called()


async def test_late_response_keeps_the_result_of_a_settled_request(
    api_client: HcuApiClient,
):
    """A second response for the same request does not replace the first result."""
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    future.set_result({"first": True})
    api_client._pending_requests["req-1"] = future

    api_client._handle_incoming_message(_system_response("req-1"))

    assert future.result() == {"first": True}
    assert api_client._pending_requests == {}


async def test_late_response_keeps_the_error_of_a_failed_request(
    api_client: HcuApiClient,
):
    """A response after a failure does not replace the error of the request."""
    future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    error = HcuApiError("request failed")
    future.set_exception(error)
    api_client._pending_requests["req-1"] = future

    api_client._handle_incoming_message(_system_response("req-1"))

    assert future.exception() is error
    assert api_client._pending_requests == {}


def _ending_websocket(api_client: HcuApiClient, *, with_error: bool) -> None:
    """Connect the client to a fake WebSocket that ends with or without an error."""
    websocket = AsyncMock()
    websocket.closed = False
    api_client._websocket = websocket
    error_frame = MagicMock()
    error_frame.type = aiohttp.WSMsgType.ERROR
    error_frame.data = "boom"

    async def frames():
        if with_error:
            yield error_frame

    websocket.__aiter__.side_effect = frames


async def test_listener_stop_fails_only_the_unsettled_requests(
    api_client: HcuApiClient,
):
    """When the listener stops, settled requests keep their outcome."""
    loop = asyncio.get_running_loop()
    answered: asyncio.Future[Any] = loop.create_future()
    answered.set_result({"ok": True})
    cancelled: asyncio.Future[Any] = loop.create_future()
    cancelled.cancel()
    waiting: asyncio.Future[Any] = loop.create_future()
    api_client._pending_requests.update(
        {"answered": answered, "cancelled": cancelled, "waiting": waiting}
    )
    _ending_websocket(api_client, with_error=True)

    with pytest.raises(ConnectionAbortedError) as err:
        await api_client.listen()

    assert str(err.value) == "WebSocket connection issue: boom"
    assert answered.result() == {"ok": True}
    assert cancelled.cancelled()
    assert isinstance(waiting.exception(), ConnectionAbortedError)
    assert str(waiting.exception()) == "WebSocket listener stopped unexpectedly."
    assert api_client._pending_requests == {}


@pytest.mark.parametrize("with_error", [True, False])
@pytest.mark.parametrize(
    ("auth_type", "user_message_failed"),
    [(AUTH_TYPE_PLUGIN, True), (AUTH_TYPE_APP, True), (AUTH_TYPE_DUAL, False)],
)
async def test_listener_stop_fails_user_messages_only_on_their_own_socket(
    api_client: HcuApiClient,
    auth_type: str,
    user_message_failed: bool,
    with_error: bool,
):
    """In DualBridge mode user messages wait on the Plugin WebSocket, not this one."""
    api_client._auth_type = auth_type
    request: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    user_message: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
    api_client._pending_requests["req-1"] = request
    api_client._pending_user_messages["msg-1"] = user_message
    _ending_websocket(api_client, with_error=with_error)

    if with_error:
        with pytest.raises(
            ConnectionAbortedError, match=r"^WebSocket connection issue"
        ):
            await api_client.listen()
    else:
        assert await api_client.listen() is None

    # Requests always travel over this socket, so they fail in every mode.
    assert str(request.exception()) == "WebSocket listener stopped unexpectedly."
    assert api_client._pending_requests == {}
    assert user_message.done() is user_message_failed
    if user_message_failed:
        assert (
            str(user_message.exception()) == "WebSocket listener stopped unexpectedly."
        )
        assert api_client._pending_user_messages == {}
    else:
        assert api_client._pending_user_messages == {"msg-1": user_message}
        user_message.cancel()


def _frame(frame_type: aiohttp.WSMsgType, payload: dict[str, Any] | None = None):
    frame = MagicMock()
    frame.type = frame_type
    frame.data = b""
    frame.json = MagicMock(return_value=payload)
    return frame


@pytest.mark.parametrize("listener", ["listen", "listen_plugin"])
async def test_listener_skips_frame_types_it_does_not_handle(
    api_client: HcuApiClient, listener: str
):
    """Frames of other types neither stop the listener nor reach a handler."""
    event = {"type": "HMIP_SYSTEM_EVENT", "id": "evt-1"}
    skipped = [aiohttp.WSMsgType.PING, aiohttp.WSMsgType.PONG]
    if listener == "listen_plugin":
        # The Plugin WebSocket carries text frames only.
        skipped.append(aiohttp.WSMsgType.BINARY)
    websocket = AsyncMock()
    websocket.closed = False

    async def frames():
        for frame_type in skipped:
            yield _frame(frame_type)
        yield _frame(aiohttp.WSMsgType.TEXT, event)

    websocket.__aiter__.side_effect = frames
    api_client._websocket = websocket
    api_client._plugin_websocket = websocket

    with patch.object(api_client, "_handle_incoming_message") as handle:
        assert await getattr(api_client, listener)() is None

    handle.assert_called_once_with(event)
