"""Tests for awaiting HCU responses on user message actions."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import (
    HcuApiClient,
    HcuApiError,
    PluginUserRequiredError,
)
from custom_components.hcu_integration.const import (
    ATTR_USER_MESSAGE_BEHAVIOR_TYPE,
    ATTR_USER_MESSAGE_CATEGORY,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_MESSAGE,
    ATTR_USER_MESSAGE_TITLE,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    DOMAIN,
    PLUGIN_ID,
)
from custom_components.hcu_integration.services import (
    async_create_user_message_request,
    async_delete_user_message_request,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

SAMPLE_BODY: dict[str, Any] = {
    "messageCategory": "INFO",
    "userMessageId": "msg-1",
    "title": {"en": "Title", "de": "Titel"},
    "message": {"en": "Body", "de": "Text"},
    "behaviorType": "DISMISSIBLE",
    "timestamp": 123456789,
}

INTEGRATION_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "hcu_integration"
)


def _mock_ws() -> AsyncMock:
    """Create a mock open WebSocket."""
    ws = AsyncMock()
    ws.closed = False
    return ws


def _assert_nothing_pending(client: HcuApiClient) -> None:
    """Assert no request or user message future remains pending on the client."""
    assert client._pending_requests == {}
    for attr_name, value in vars(client).items():
        if "pending" in attr_name and isinstance(value, dict):
            assert value == {}, f"Unexpected pending entries in {attr_name}: {value}"


def _setup_entry_with_client(
    hass: HomeAssistant, client: HcuApiClient
) -> MockConfigEntry:
    """Register a loaded config entry backed by a real HcuApiClient."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="HCU")
    entry.add_to_hass(hass)
    entry.runtime_data = SimpleNamespace(entities={}, client=client, _ha_bridge=None)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    return entry


def _create_call(user_message_id: str = "msg-1") -> SimpleNamespace:
    """Build a create_user_message_request ServiceCall-like payload."""
    return SimpleNamespace(
        data={
            ATTR_USER_MESSAGE_CATEGORY: "INFO",
            ATTR_USER_MESSAGE_ID: user_message_id,
            ATTR_USER_MESSAGE_TITLE: "Title",
            ATTR_USER_MESSAGE_MESSAGE: "Body",
            ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
        }
    )


def _delete_call(user_message_id: str = "msg-1") -> SimpleNamespace:
    """Build a delete_user_message_request ServiceCall-like payload."""
    return SimpleNamespace(data={ATTR_USER_MESSAGE_ID: user_message_id})


def _setup_client_for_mode(
    client: HcuApiClient, mode: str
) -> tuple[AsyncMock, AsyncMock | None]:
    """Attach open mock sockets for Plugin User or DualBridge mode."""
    client._auth_type = mode
    primary_ws = _mock_ws()
    client._websocket = primary_ws
    if mode == AUTH_TYPE_DUAL:
        client._app_token = "app-token"
        plugin_ws = _mock_ws()
        client._plugin_websocket = plugin_ws
        return plugin_ws, primary_ws
    client._plugin_websocket = None
    return primary_ws, None


# ==============================================================================
# Client tests
# ==============================================================================


@pytest.mark.parametrize("mode", [AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL])
async def test_create_waits_for_the_answer(api_client: HcuApiClient, mode: str) -> None:
    """Create request waits until CREATE_USER_MESSAGE_RESPONSE arrives."""
    target_ws, app_ws = _setup_client_for_mode(api_client, mode)
    sent_frames: list[dict[str, Any]] = []
    sent_event = asyncio.Event()

    async def capture_send(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        sent_event.set()

    target_ws.send_json.side_effect = capture_send

    task = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await sent_event.wait()

    assert not task.done()
    assert len(sent_frames) == 1
    if app_ws is not None:
        app_ws.send_json.assert_not_called()

    sent = sent_frames[0]
    assert sent["pluginId"] == PLUGIN_ID
    assert sent["type"] == "CREATE_USER_MESSAGE_REQUEST"
    assert sent["body"] == SAMPLE_BODY
    assert isinstance(sent["id"], str) and sent["id"]

    api_client._handle_incoming_message(
        {
            "type": "CREATE_USER_MESSAGE_RESPONSE",
            "id": sent["id"],
            "pluginId": PLUGIN_ID,
            "body": {"success": True, "userMessageId": "msg-1"},
        }
    )

    async with asyncio.timeout(1.0):
        result = await task
    assert result is None
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize(
    ("body", "expected_code"),
    [
        (
            {
                "success": False,
                "userMessageId": "msg-1",
                "error": {"code": "INVALID_REQUEST", "message": "bad payload"},
            },
            "INVALID_REQUEST",
        ),
        ({"success": False, "userMessageId": "msg-1"}, None),
        ({"userMessageId": "msg-1"}, None),
        ({"success": "true", "userMessageId": "msg-1"}, None),
        (None, None),
        (["unexpected"], None),
    ],
)
async def test_create_fails_when_the_answer_reports_failure(
    api_client: HcuApiClient, body: Any, expected_code: str | None
) -> None:
    """Create request raises HcuApiError when the response does not report success."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)

    async def answer(frame: dict[str, Any]) -> None:
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message,
            {
                "type": "CREATE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": body,
            },
        )

    target_ws.send_json.side_effect = answer

    with pytest.raises(HcuApiError) as exc_info:
        async with asyncio.timeout(1.0):
            await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    assert exc_info.value.error_code == expected_code
    if expected_code is not None:
        assert expected_code in str(exc_info.value)
    _assert_nothing_pending(api_client)


async def test_create_fails_on_error_response(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
) -> None:
    """ERROR_RESPONSE matching the sent id fails the create request cleanly."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    callback = MagicMock()
    api_client.register_event_callback(callback)

    async def reject(frame: dict[str, Any]) -> None:
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message,
            {
                "type": "ERROR_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {
                    "error": {"code": "NOT_ALLOWED", "message": "rejected"},
                    "originalMessage": "",
                },
            },
        )

    target_ws.send_json.side_effect = reject

    with caplog.at_level(logging.WARNING), pytest.raises(HcuApiError) as exc_info:
        async with asyncio.timeout(1.0):
            await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    assert exc_info.value.error_code == "NOT_ALLOWED"
    callback.assert_not_called()
    assert "matches no pending request" not in caplog.text
    _assert_nothing_pending(api_client)


async def test_create_times_out_without_sending_again(
    api_client: HcuApiClient,
) -> None:
    """Create request raises HcuApiError on timeout and never retries."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)

    with (
        patch("custom_components.hcu_integration.api.API_REQUEST_TIMEOUT", 0.05),
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    assert not isinstance(exc_info.value, TimeoutError)
    assert "0.05" in str(exc_info.value)
    target_ws.send_json.assert_awaited_once()
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize(
    "response_type",
    ["CREATE_USER_MESSAGE_RESPONSE", "DELETE_USER_MESSAGE_RESPONSE"],
)
async def test_unmatched_answers_are_dropped(
    api_client: HcuApiClient,
    caplog: pytest.LogCaptureFixture,
    response_type: str,
) -> None:
    """Late, duplicate, or unknown user message responses are dropped at debug level."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    callback = MagicMock()
    api_client.register_event_callback(callback)

    sent_ids: list[str] = []

    async def capture_only(frame: dict[str, Any]) -> None:
        sent_ids.append(frame["id"])

    target_ws.send_json.side_effect = capture_only

    # 1. Late answer after timeout
    with (
        patch("custom_components.hcu_integration.api.API_REQUEST_TIMEOUT", 0.02),
        pytest.raises(HcuApiError),
    ):
        await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    late_frame = {
        "type": response_type,
        "id": sent_ids[0],
        "pluginId": PLUGIN_ID,
        "body": {"success": True, "userMessageId": "msg-1"},
    }
    with caplog.at_level(logging.DEBUG):
        api_client._handle_incoming_message(late_frame)

    # 2. Duplicate answer after a successful request
    async def answer_once(frame: dict[str, Any]) -> None:
        sent_ids.append(frame["id"])
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message,
            {
                "type": response_type,
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {"success": True, "userMessageId": "msg-1"},
            },
        )

    target_ws.send_json.side_effect = answer_once
    if response_type == "CREATE_USER_MESSAGE_RESPONSE":
        await api_client.async_create_user_message_request(body=SAMPLE_BODY)
    else:
        await api_client.async_delete_user_message_request(user_message_id="msg-1")

    duplicate_frame = {
        "type": response_type,
        "id": sent_ids[-1],
        "pluginId": PLUGIN_ID,
        "body": {"success": True, "userMessageId": "msg-1"},
    }
    unknown_frame = {
        "type": response_type,
        "id": "unknown-id",
        "pluginId": PLUGIN_ID,
        "body": {"success": True, "userMessageId": "msg-1"},
    }
    with caplog.at_level(logging.DEBUG):
        api_client._handle_incoming_message(duplicate_frame)
        api_client._handle_incoming_message(unknown_frame)

    callback.assert_not_called()
    assert caplog.text
    _assert_nothing_pending(api_client)


async def test_concurrent_requests_get_their_own_answer(
    api_client: HcuApiClient,
) -> None:
    """Two concurrent user message calls resolve by their own message id."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    sent_frames: list[dict[str, Any]] = []
    both_sent = asyncio.Event()

    async def capture(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        if len(sent_frames) == 2:
            both_sent.set()

    target_ws.send_json.side_effect = capture

    task1 = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    task2 = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await both_sent.wait()

    # Feed responses in reverse order: task2 succeeds, task1 fails.
    api_client._handle_incoming_message(
        {
            "type": "CREATE_USER_MESSAGE_RESPONSE",
            "id": sent_frames[1]["id"],
            "pluginId": PLUGIN_ID,
            "body": {"success": True, "userMessageId": "msg-1"},
        }
    )
    api_client._handle_incoming_message(
        {
            "type": "CREATE_USER_MESSAGE_RESPONSE",
            "id": sent_frames[0]["id"],
            "pluginId": PLUGIN_ID,
            "body": {
                "success": False,
                "userMessageId": "msg-1",
                "error": {"code": "INVALID_REQUEST", "message": "rejected"},
            },
        }
    )

    async with asyncio.timeout(1.0):
        assert await task2 is None
        with pytest.raises(HcuApiError) as exc_info:
            await task1
    assert exc_info.value.error_code == "INVALID_REQUEST"
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize(
    "outcome",
    ["success", "failure", "error_response", "timeout"],
)
async def test_delete_waits_for_the_answer(
    api_client: HcuApiClient, outcome: str
) -> None:
    """Delete request waits for DELETE_USER_MESSAGE_RESPONSE or ERROR_RESPONSE."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    sent_frames: list[dict[str, Any]] = []
    sent_event = asyncio.Event()

    async def capture(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        sent_event.set()

    target_ws.send_json.side_effect = capture

    timeout_val = 0.05 if outcome == "timeout" else 10
    with patch(
        "custom_components.hcu_integration.api.API_REQUEST_TIMEOUT", timeout_val
    ):
        task = asyncio.create_task(
            api_client.async_delete_user_message_request(user_message_id="msg-1")
        )
        async with asyncio.timeout(1.0):
            await sent_event.wait()

        assert not task.done()
        assert len(sent_frames) == 1
        sent = sent_frames[0]
        assert sent["type"] == "DELETE_USER_MESSAGE_REQUEST"
        assert sent["body"] == {"userMessageId": "msg-1"}
        assert isinstance(sent["id"], str) and sent["id"]

        if outcome == "success":
            api_client._handle_incoming_message(
                {
                    "type": "DELETE_USER_MESSAGE_RESPONSE",
                    "id": sent["id"],
                    "pluginId": PLUGIN_ID,
                    "body": {"success": True, "userMessageId": "msg-1"},
                }
            )
            async with asyncio.timeout(1.0):
                assert await task is None
        elif outcome == "failure":
            api_client._handle_incoming_message(
                {
                    "type": "DELETE_USER_MESSAGE_RESPONSE",
                    "id": sent["id"],
                    "pluginId": PLUGIN_ID,
                    "body": {
                        "success": False,
                        "userMessageId": "msg-1",
                        "error": {"code": "UNKNOWN_REQUEST", "message": "not found"},
                    },
                }
            )
            with pytest.raises(HcuApiError) as exc_info:
                async with asyncio.timeout(1.0):
                    await task
            assert exc_info.value.error_code == "UNKNOWN_REQUEST"
        elif outcome == "error_response":
            api_client._handle_incoming_message(
                {
                    "type": "ERROR_RESPONSE",
                    "id": sent["id"],
                    "pluginId": PLUGIN_ID,
                    "body": {
                        "error": {"code": "NOT_ALLOWED", "message": "denied"},
                        "originalMessage": "",
                    },
                }
            )
            with pytest.raises(HcuApiError) as exc_info:
                async with asyncio.timeout(1.0):
                    await task
            assert exc_info.value.error_code == "NOT_ALLOWED"
        else:
            with pytest.raises(HcuApiError) as exc_info:
                async with asyncio.timeout(1.0):
                    await task
            assert "0.05" in str(exc_info.value)

    assert len(sent_frames) == 1
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize(
    "scenario",
    [
        "fail_then_success",
        "success_then_fail",
        "timeout_then_success",
        "fail_then_fail",
    ],
)
async def test_delete_with_two_plugin_ids(hass: HomeAssistant, scenario: str) -> None:
    """Delete sends entry ID then plain PLUGIN_ID sequentially and succeeds if either succeeds."""
    unique_id = f"{PLUGIN_ID}-ab12cd"
    client = HcuApiClient(
        hass=hass,
        host="192.168.1.100",
        auth_token="test-token",
        session=MagicMock(spec=aiohttp.ClientSession),
        plugin_id=unique_id,
    )
    target_ws, _ = _setup_client_for_mode(client, AUTH_TYPE_PLUGIN)

    sent_frames: list[dict[str, Any]] = []
    first_sent = asyncio.Event()
    second_sent = asyncio.Event()

    async def capture(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        if len(sent_frames) == 1:
            first_sent.set()
        elif len(sent_frames) == 2:
            second_sent.set()

    target_ws.send_json.side_effect = capture

    timeout_val = 0.03 if scenario == "timeout_then_success" else 10
    with patch(
        "custom_components.hcu_integration.api.API_REQUEST_TIMEOUT", timeout_val
    ):
        task = asyncio.create_task(
            client.async_delete_user_message_request(user_message_id="msg-1")
        )
        async with asyncio.timeout(1.0):
            await first_sent.wait()

        # Second request must not be sent before the first one finishes.
        await asyncio.sleep(0)
        assert len(sent_frames) == 1
        assert sent_frames[0]["pluginId"] == unique_id

        if scenario != "timeout_then_success":
            first_ok = scenario == "success_then_fail"
            first_body: dict[str, Any] = {"success": first_ok, "userMessageId": "msg-1"}
            if not first_ok:
                first_body["error"] = {"code": "FIRST_ERR", "message": "first"}
            client._handle_incoming_message(
                {
                    "type": "DELETE_USER_MESSAGE_RESPONSE",
                    "id": sent_frames[0]["id"],
                    "pluginId": unique_id,
                    "body": first_body,
                }
            )

        async with asyncio.timeout(1.0):
            await second_sent.wait()

        assert len(sent_frames) == 2
        assert sent_frames[1]["pluginId"] == PLUGIN_ID

        second_ok = scenario in (
            "fail_then_success",
            "timeout_then_success",
        )
        second_body: dict[str, Any] = {"success": second_ok, "userMessageId": "msg-1"}
        if not second_ok:
            second_body["error"] = {"code": "SECOND_ERR", "message": "second"}
        client._handle_incoming_message(
            {
                "type": "DELETE_USER_MESSAGE_RESPONSE",
                "id": sent_frames[1]["id"],
                "pluginId": PLUGIN_ID,
                "body": second_body,
            }
        )

        if scenario == "fail_then_fail":
            with pytest.raises(HcuApiError) as exc_info:
                async with asyncio.timeout(1.0):
                    await task
            assert exc_info.value.error_code == "SECOND_ERR"
        else:
            async with asyncio.timeout(1.0):
                assert await task is None

    _assert_nothing_pending(client)


@pytest.mark.parametrize("action", ["create", "delete"])
async def test_app_user_mode_refuses_user_messages(
    api_client: HcuApiClient, action: str
) -> None:
    """App User mode raises PluginUserRequiredError without sending anything."""
    from custom_components.hcu_integration.api import PluginUserRequiredError

    assert issubclass(PluginUserRequiredError, ConnectionError)

    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "app-token"
    app_ws = _mock_ws()
    api_client._websocket = app_ws

    with pytest.raises(PluginUserRequiredError):
        if action == "create":
            await api_client.async_create_user_message_request(body=SAMPLE_BODY)
        else:
            await api_client.async_delete_user_message_request(user_message_id="msg-1")

    app_ws.send_json.assert_not_called()
    _assert_nothing_pending(api_client)


async def test_call_cancelled_while_waiting_leaves_nothing_pending(
    api_client: HcuApiClient,
) -> None:
    """Cancelling an awaiting user message call cleans up its pending entry."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    callback = MagicMock()
    api_client.register_event_callback(callback)
    sent_frames: list[dict[str, Any]] = []
    sent_event = asyncio.Event()

    async def capture(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        sent_event.set()

    target_ws.send_json.side_effect = capture

    task = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await sent_event.wait()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    _assert_nothing_pending(api_client)

    api_client._handle_incoming_message(
        {
            "type": "CREATE_USER_MESSAGE_RESPONSE",
            "id": sent_frames[0]["id"],
            "pluginId": PLUGIN_ID,
            "body": {"success": True, "userMessageId": "msg-1"},
        }
    )
    callback.assert_not_called()


@pytest.mark.parametrize("mode", [AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL])
@pytest.mark.parametrize("action", ["create", "delete"])
async def test_connection_down_is_reported(
    api_client: HcuApiClient, mode: str, action: str
) -> None:
    """Disconnected Plugin User socket raises ConnectionError with nothing pending."""
    api_client._auth_type = mode
    app_ws: AsyncMock | None = None
    if mode == AUTH_TYPE_DUAL:
        api_client._app_token = "app-token"
        app_ws = _mock_ws()
        api_client._websocket = app_ws
        api_client._plugin_websocket = None
    else:
        api_client._websocket = None

    with pytest.raises(ConnectionError):
        if action == "create":
            await api_client.async_create_user_message_request(body=SAMPLE_BODY)
        else:
            await api_client.async_delete_user_message_request(user_message_id="msg-1")

    if app_ws is not None:
        app_ws.send_json.assert_not_called()
    _assert_nothing_pending(api_client)


async def test_failed_send_leaves_nothing_pending(
    api_client: HcuApiClient,
) -> None:
    """Send failure cancels the unfinished future, propagates the error, and leaves no pending entry."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    captured_futures: list[asyncio.Future[None]] = []

    async def fail_send(_frame: dict[str, Any]) -> None:
        captured_futures.extend(api_client._pending_user_messages.values())
        raise ConnectionResetError("socket reset")

    target_ws.send_json.side_effect = fail_send

    with pytest.raises(ConnectionResetError):
        await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    _assert_nothing_pending(api_client)
    assert len(captured_futures) == 1
    assert captured_futures[0].cancelled()


# ==============================================================================
# Listener tests
# ==============================================================================


async def test_dualbridge_listener_passes_user_message_answers(
    api_client: HcuApiClient,
) -> None:
    """DualBridge listen_plugin passes both user message response types to the handler."""
    api_client._auth_type = AUTH_TYPE_DUAL
    ws = _mock_ws()
    api_client._plugin_websocket = ws

    create_frame = {
        "type": "CREATE_USER_MESSAGE_RESPONSE",
        "id": "r1",
        "pluginId": PLUGIN_ID,
        "body": {"success": True, "userMessageId": "msg-1"},
    }
    delete_frame = {
        "type": "DELETE_USER_MESSAGE_RESPONSE",
        "id": "r2",
        "pluginId": PLUGIN_ID,
        "body": {"success": True, "userMessageId": "msg-1"},
    }

    frames = []
    for payload in (create_frame, delete_frame):
        frame_msg = MagicMock()
        frame_msg.type = aiohttp.WSMsgType.TEXT
        frame_msg.json = MagicMock(return_value=payload)
        frames.append(frame_msg)

    closed_msg = MagicMock()
    closed_msg.type = aiohttp.WSMsgType.CLOSED
    closed_msg.data = "Normal closure"

    async def _msg_iter():
        for frame in frames:
            yield frame
        yield closed_msg

    ws.__aiter__.side_effect = _msg_iter

    with (
        patch.object(api_client, "_handle_incoming_message") as mock_handle,
        pytest.raises(ConnectionAbortedError),
    ):
        await api_client.listen_plugin()

    assert mock_handle.call_count == 2
    assert mock_handle.call_args_list[0].args[0] == create_frame
    assert mock_handle.call_args_list[1].args[0] == delete_frame


@pytest.mark.parametrize("success", [True, False])
async def test_dualbridge_round_trip(api_client: HcuApiClient, success: bool) -> None:
    """Full DualBridge round trip over listen_plugin completes or raises HcuApiError."""
    plugin_ws, app_ws = _setup_client_for_mode(api_client, AUTH_TYPE_DUAL)
    incoming_queue: asyncio.Queue[MagicMock] = asyncio.Queue()

    async def send_and_enqueue(frame: dict[str, Any]) -> None:
        response_msg = MagicMock()
        response_msg.type = aiohttp.WSMsgType.TEXT
        body: dict[str, Any] = {"success": success, "userMessageId": "msg-1"}
        if not success:
            body["error"] = {"code": "INVALID_REQUEST", "message": "bad"}
        response_msg.json = MagicMock(
            return_value={
                "type": "CREATE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": body,
            }
        )
        await incoming_queue.put(response_msg)

    plugin_ws.send_json.side_effect = send_and_enqueue

    async def _msg_iter():
        while True:
            yield await incoming_queue.get()

    plugin_ws.__aiter__.side_effect = _msg_iter

    listener = asyncio.create_task(api_client.listen_plugin())
    try:
        async with asyncio.timeout(1.0):
            if success:
                await api_client.async_create_user_message_request(body=SAMPLE_BODY)
            else:
                with pytest.raises(HcuApiError) as exc_info:
                    await api_client.async_create_user_message_request(body=SAMPLE_BODY)
                assert exc_info.value.error_code == "INVALID_REQUEST"
    finally:
        listener.cancel()
        with pytest.raises(asyncio.CancelledError):
            await listener

    assert app_ws is not None
    app_ws.send_json.assert_not_called()


@pytest.mark.parametrize("reason", ["closed", "error", "cancelled"])
async def test_plugin_listener_end_fails_waiting_calls(
    api_client: HcuApiClient, reason: str
) -> None:
    """Ending listen_plugin in DualBridge fails waiting user message calls immediately."""
    plugin_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_DUAL)
    sent_event = asyncio.Event()
    proceed_end = asyncio.Event()

    async def capture(_frame: dict[str, Any]) -> None:
        sent_event.set()

    plugin_ws.send_json.side_effect = capture

    async def _msg_iter():
        await proceed_end.wait()
        end_msg = MagicMock()
        end_msg.type = (
            aiohttp.WSMsgType.ERROR if reason == "error" else aiohttp.WSMsgType.CLOSED
        )
        end_msg.data = "ended"
        yield end_msg

    plugin_ws.__aiter__.side_effect = _msg_iter

    listener = asyncio.create_task(api_client.listen_plugin())
    call_task = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await sent_event.wait()

    if reason == "cancelled":
        listener.cancel()
        with pytest.raises(asyncio.CancelledError):
            await listener
    else:
        proceed_end.set()
        with pytest.raises(ConnectionAbortedError):
            await listener

    with pytest.raises(ConnectionError):
        async with asyncio.timeout(1.0):
            await call_task
    _assert_nothing_pending(api_client)


async def test_app_listener_end_keeps_waiting_calls(
    api_client: HcuApiClient,
) -> None:
    """Ending the primary App listener in DualBridge leaves user message calls waiting."""
    plugin_ws, app_ws = _setup_client_for_mode(api_client, AUTH_TYPE_DUAL)
    assert app_ws is not None
    sent_frames: list[dict[str, Any]] = []
    sent_event = asyncio.Event()

    async def capture(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        sent_event.set()

    plugin_ws.send_json.side_effect = capture

    closed_msg = MagicMock()
    closed_msg.type = aiohttp.WSMsgType.CLOSED
    closed_msg.data = "app closed"

    async def _app_iter():
        yield closed_msg

    app_ws.__aiter__.side_effect = _app_iter

    call_task = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await sent_event.wait()

    with pytest.raises(ConnectionAbortedError):
        await api_client.listen()

    assert not call_task.done()

    api_client._handle_incoming_message(
        {
            "type": "CREATE_USER_MESSAGE_RESPONSE",
            "id": sent_frames[0]["id"],
            "pluginId": PLUGIN_ID,
            "body": {"success": True, "userMessageId": "msg-1"},
        }
    )
    async with asyncio.timeout(1.0):
        assert await call_task is None
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize("reason", ["closed", "cancelled"])
async def test_primary_listener_end_fails_waiting_calls(
    api_client: HcuApiClient, reason: str
) -> None:
    """Ending listen() in Plugin User mode fails waiting user message calls immediately."""
    primary_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    sent_event = asyncio.Event()
    proceed_end = asyncio.Event()

    async def capture(_frame: dict[str, Any]) -> None:
        sent_event.set()

    primary_ws.send_json.side_effect = capture

    async def _msg_iter():
        await proceed_end.wait()
        closed_msg = MagicMock()
        closed_msg.type = aiohttp.WSMsgType.CLOSED
        closed_msg.data = "closed"
        yield closed_msg

    primary_ws.__aiter__.side_effect = _msg_iter

    listener = asyncio.create_task(api_client.listen())
    call_task = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await sent_event.wait()

    if reason == "cancelled":
        listener.cancel()
        with pytest.raises(asyncio.CancelledError):
            await listener
    else:
        proceed_end.set()
        with pytest.raises(ConnectionAbortedError):
            await listener

    with pytest.raises(ConnectionError):
        async with asyncio.timeout(1.0):
            await call_task
    _assert_nothing_pending(api_client)


# ==============================================================================
# Action handler tests
# ==============================================================================


@pytest.mark.parametrize("rejection_kind", ["response_error", "error_response"])
async def test_create_action_fails_when_hcu_rejects(
    hass: HomeAssistant, api_client: HcuApiClient, rejection_kind: str
) -> None:
    """Create action raises translated HomeAssistantError when the HCU rejects."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    _setup_entry_with_client(hass, api_client)
    hass.config.language = "en"

    async def reject(frame: dict[str, Any]) -> None:
        if rejection_kind == "response_error":
            payload = {
                "type": "CREATE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {
                    "success": False,
                    "userMessageId": "msg-1",
                    "error": {"code": "INVALID_REQUEST", "message": "bad"},
                },
            }
        else:
            payload = {
                "type": "ERROR_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {
                    "error": {"code": "INVALID_REQUEST", "message": "bad"},
                    "originalMessage": "",
                },
            }
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message, payload
        )

    target_ws.send_json.side_effect = reject

    with pytest.raises(HomeAssistantError) as exc_info:
        async with asyncio.timeout(1.0):
            await async_create_user_message_request(hass, _create_call())

    assert exc_info.value.translation_key == "create_user_message_failed"
    assert "INVALID_REQUEST" in exc_info.value.translation_placeholders["error"]


async def test_delete_action_fails_when_hcu_rejects(
    hass: HomeAssistant, api_client: HcuApiClient
) -> None:
    """Delete action raises translated HomeAssistantError when the HCU rejects."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    _setup_entry_with_client(hass, api_client)
    hass.config.language = "en"

    async def reject(frame: dict[str, Any]) -> None:
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message,
            {
                "type": "DELETE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {
                    "success": False,
                    "userMessageId": "msg-1",
                    "error": {"code": "UNKNOWN_REQUEST", "message": "missing"},
                },
            },
        )

    target_ws.send_json.side_effect = reject

    with pytest.raises(HomeAssistantError) as exc_info:
        async with asyncio.timeout(1.0):
            await async_delete_user_message_request(hass, _delete_call("msg-1"))

    assert exc_info.value.translation_key == "delete_user_message_failed"
    assert exc_info.value.translation_placeholders["user_message_id"] == "msg-1"
    assert "UNKNOWN_REQUEST" in exc_info.value.translation_placeholders["error"]


@pytest.mark.parametrize("action", ["create", "delete"])
async def test_actions_fail_in_app_user_mode(
    hass: HomeAssistant, api_client: HcuApiClient, action: str
) -> None:
    """User message actions raise translated error in App User mode without sending."""
    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "app-token"
    app_ws = _mock_ws()
    api_client._websocket = app_ws
    _setup_entry_with_client(hass, api_client)

    with pytest.raises(HomeAssistantError) as exc_info:
        if action == "create":
            await async_create_user_message_request(hass, _create_call())
        else:
            await async_delete_user_message_request(hass, _delete_call())

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "user_message_requires_plugin_user"
    assert not exc_info.value.translation_placeholders
    app_ws.send_json.assert_not_called()


async def test_action_fails_when_hcu_does_not_answer(
    hass: HomeAssistant, api_client: HcuApiClient
) -> None:
    """Create action raises create_user_message_failed naming the timeout seconds."""
    _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    _setup_entry_with_client(hass, api_client)

    with (
        patch("custom_components.hcu_integration.api.API_REQUEST_TIMEOUT", 0.05),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await async_create_user_message_request(hass, _create_call())

    assert exc_info.value.translation_key == "create_user_message_failed"
    assert "0.05" in exc_info.value.translation_placeholders["error"]


def test_plugin_user_required_text_exists() -> None:
    """All three translation files define user_message_requires_plugin_user cleanly."""
    paths = [
        INTEGRATION_DIR / "strings.json",
        INTEGRATION_DIR / "translations" / "en.json",
        INTEGRATION_DIR / "translations" / "de.json",
    ]
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        entry = data["exceptions"]["user_message_requires_plugin_user"]
        text = entry["message"]
        assert isinstance(text, str) and text
        assert "{" not in text
        assert "—" not in text
        assert " - " not in text
        assert " – " not in text


async def test_actions_succeed_when_hcu_confirms(
    hass: HomeAssistant, api_client: HcuApiClient
) -> None:
    """Both user message actions return None when the HCU confirms success."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    _setup_entry_with_client(hass, api_client)

    async def confirm(frame: dict[str, Any]) -> None:
        resp_type = (
            "CREATE_USER_MESSAGE_RESPONSE"
            if frame["type"] == "CREATE_USER_MESSAGE_REQUEST"
            else "DELETE_USER_MESSAGE_RESPONSE"
        )
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message,
            {
                "type": resp_type,
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {"success": True, "userMessageId": "msg-1"},
            },
        )

    target_ws.send_json.side_effect = confirm

    async with asyncio.timeout(1.0):
        assert await async_create_user_message_request(hass, _create_call()) is None
        assert await async_delete_user_message_request(hass, _delete_call()) is None


async def test_failed_send_is_not_repeated(api_client: HcuApiClient) -> None:
    """A failed send is passed on without a second attempt."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    target_ws.send_json.side_effect = ConnectionResetError("socket reset")

    with pytest.raises(ConnectionResetError):
        await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    assert target_ws.send_json.await_count == 1
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize("mode", [AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL, ""])
async def test_listener_ending_without_error_fails_waiting_calls(
    api_client: HcuApiClient, mode: str
) -> None:
    """A listener whose socket is closed ends without an error and fails waiting calls.

    The message iterator of the WebSocket stops when the connection is
    closed, so the listener returns instead of raising. The request must not
    be sent a second time.
    """
    target_ws, _ = _setup_client_for_mode(api_client, mode)
    sent_frames: list[dict[str, Any]] = []
    sent_event = asyncio.Event()

    async def capture(frame: dict[str, Any]) -> None:
        sent_frames.append(frame)
        sent_event.set()

    target_ws.send_json.side_effect = capture

    async def _closed_socket():
        return
        yield  # pragma: no cover

    target_ws.__aiter__.side_effect = _closed_socket

    call_task = asyncio.create_task(
        api_client.async_create_user_message_request(body=SAMPLE_BODY)
    )
    async with asyncio.timeout(1.0):
        await sent_event.wait()

    if mode == AUTH_TYPE_DUAL:
        await api_client.listen_plugin()
    else:
        await api_client.listen()

    with pytest.raises(ConnectionError):
        async with asyncio.timeout(1.0):
            await call_task
    assert len(sent_frames) == 1
    _assert_nothing_pending(api_client)


@pytest.mark.parametrize(
    ("body", "expected_code", "expected_text"),
    [
        ({"success": 1}, None, "The HCU reported a failure without details"),
        (
            {"success": False, "error": {"code": "", "message": "m"}},
            None,
            "The HCU reported a failure without details",
        ),
        (
            {"success": False, "error": {"code": 42, "message": "m"}},
            None,
            "The HCU reported a failure without details",
        ),
        (
            {"success": False, "error": ["CODE"]},
            None,
            "The HCU reported a failure without details",
        ),
        (
            {"success": False, "error": {"code": "CODE", "message": "some text"}},
            "CODE",
            "HCU Error: CODE some text",
        ),
        ({"success": False, "error": {"code": "CODE"}}, "CODE", "HCU Error: CODE"),
        (
            {"success": False, "error": {"code": "CODE", "message": None}},
            "CODE",
            "HCU Error: CODE",
        ),
        (
            {"success": False, "error": {"code": "CODE", "message": 5}},
            "CODE",
            "HCU Error: CODE",
        ),
    ],
)
async def test_failure_answer_details(
    api_client: HcuApiClient,
    body: Any,
    expected_code: str | None,
    expected_text: str,
) -> None:
    """Only a non-empty string code and a string message are taken from the answer."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)

    async def answer(frame: dict[str, Any]) -> None:
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message,
            {
                "type": "CREATE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": body,
            },
        )

    target_ws.send_json.side_effect = answer

    with pytest.raises(HcuApiError) as exc_info:
        async with asyncio.timeout(1.0):
            await api_client.async_create_user_message_request(body=SAMPLE_BODY)

    assert exc_info.value.error_code == expected_code
    assert str(exc_info.value) == expected_text


async def test_unmatched_answer_is_logged_once_at_debug_level(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
) -> None:
    """An answer for an unknown or unusable id gives one debug line and no error."""
    _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    callback = MagicMock()
    api_client.register_event_callback(callback)
    # Another request is waiting, so the id of each answer is really looked up.
    waiting: asyncio.Future[None] = asyncio.get_running_loop().create_future()
    api_client._pending_user_messages["waiting-id"] = waiting

    with caplog.at_level(logging.DEBUG):
        for message_id in ("unknown-id", None, 7, ["a"], {"a": 1}):
            caplog.clear()
            api_client._handle_incoming_message(
                {
                    "type": "CREATE_USER_MESSAGE_RESPONSE",
                    "id": message_id,
                    "body": {"success": True, "userMessageId": "msg-1"},
                }
            )
            records = [r for r in caplog.records if r.name.endswith(".api")]
            assert [r.levelno for r in records] == [logging.DEBUG]
            assert "CREATE_USER_MESSAGE_RESPONSE" in records[0].getMessage()

    callback.assert_not_called()
    assert not waiting.done()
    assert api_client._pending_user_messages == {"waiting-id": waiting}
    api_client._pending_user_messages.clear()


async def test_answer_for_a_finished_request_is_ignored(
    api_client: HcuApiClient,
) -> None:
    """An answer or a listener end that meets an already cancelled request raises nothing."""
    _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    loop = asyncio.get_running_loop()

    cancelled = loop.create_future()
    cancelled.cancel()
    api_client._pending_user_messages["req-1"] = cancelled
    api_client._handle_incoming_message(
        {
            "type": "CREATE_USER_MESSAGE_RESPONSE",
            "id": "req-1",
            "body": {"success": True, "userMessageId": "msg-1"},
        }
    )

    cancelled = loop.create_future()
    cancelled.cancel()
    api_client._pending_user_messages["req-2"] = cancelled
    api_client._fail_pending_user_messages("listener stopped")

    _assert_nothing_pending(api_client)


async def test_answer_that_arrives_during_the_send_is_used(
    api_client: HcuApiClient,
) -> None:
    """The request is registered before it is sent."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)

    async def answer_at_once(frame: dict[str, Any]) -> None:
        api_client._handle_incoming_message(
            {
                "type": "CREATE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": PLUGIN_ID,
                "body": {"success": True, "userMessageId": "msg-1"},
            }
        )

    target_ws.send_json.side_effect = answer_at_once

    async with asyncio.timeout(1.0):
        await api_client.async_create_user_message_request(body=SAMPLE_BODY)
    _assert_nothing_pending(api_client)


async def test_delete_tries_the_second_id_after_a_failed_send(
    hass: HomeAssistant,
) -> None:
    """A send error of the first delete request does not stop the second one."""
    client = HcuApiClient(
        hass=hass,
        host="192.168.1.100",
        auth_token="test-token",
        session=MagicMock(spec=aiohttp.ClientSession),
        plugin_id=f"{PLUGIN_ID}-ab12cd",
    )
    target_ws, _ = _setup_client_for_mode(client, AUTH_TYPE_PLUGIN)
    sent_plugin_ids: list[str] = []

    async def fail_then_confirm(frame: dict[str, Any]) -> None:
        sent_plugin_ids.append(frame["pluginId"])
        if len(sent_plugin_ids) == 1:
            raise ConnectionResetError("socket reset")
        asyncio.get_running_loop().call_soon(
            client._handle_incoming_message,
            {
                "type": "DELETE_USER_MESSAGE_RESPONSE",
                "id": frame["id"],
                "pluginId": frame["pluginId"],
                "body": {"success": True, "userMessageId": "msg-1"},
            },
        )

    target_ws.send_json.side_effect = fail_then_confirm

    async with asyncio.timeout(1.0):
        await client.async_delete_user_message_request(user_message_id="msg-1")
    assert sent_plugin_ids == [f"{PLUGIN_ID}-ab12cd", PLUGIN_ID]
    _assert_nothing_pending(client)


@pytest.mark.parametrize("action", ["create", "delete"])
async def test_app_user_mode_action_error_keeps_its_cause(
    hass: HomeAssistant, api_client: HcuApiClient, action: str
) -> None:
    """The App User mode error is a plain HomeAssistantError chained to the client error."""
    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "app-token"
    _setup_entry_with_client(hass, api_client)

    with pytest.raises(HomeAssistantError) as exc_info:
        if action == "create":
            await async_create_user_message_request(hass, _create_call())
        else:
            await async_delete_user_message_request(hass, _delete_call())

    assert type(exc_info.value) is HomeAssistantError
    assert isinstance(exc_info.value.__cause__, PluginUserRequiredError)


async def test_delete_action_reports_a_lost_connection_as_failed(
    hass: HomeAssistant, api_client: HcuApiClient
) -> None:
    """A connection error in Plugin User mode is not reported as a wrong connection mode."""
    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    _setup_entry_with_client(hass, api_client)
    target_ws.send_json.side_effect = ConnectionResetError("socket reset")

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_delete_user_message_request(hass, _delete_call("msg-1"))

    assert exc_info.value.translation_key == "delete_user_message_failed"
    assert exc_info.value.translation_placeholders == {
        "user_message_id": "msg-1",
        "error": "socket reset",
    }
    assert isinstance(exc_info.value.__cause__, ConnectionResetError)


async def test_disconnect_during_failed_send_leaves_no_unretrieved_future_exception(
    api_client: HcuApiClient,
) -> None:
    """If the listener stops while _send_message is suspended and send raises, no future exception leaks."""
    import gc

    target_ws, _ = _setup_client_for_mode(api_client, AUTH_TYPE_PLUGIN)
    unretrieved: list[dict[str, Any]] = []
    loop = asyncio.get_running_loop()
    previous_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda _loop, context: unretrieved.append(context))

    async def fail_after_listener_exit(_message: dict[str, Any]) -> None:
        api_client._fail_pending_user_messages(
            ConnectionAbortedError("Plugin WebSocket listener exited")
        )
        raise ConnectionResetError("send aborted")

    target_ws.send_json.side_effect = fail_after_listener_exit

    try:
        with pytest.raises(ConnectionResetError, match="send aborted"):
            await api_client.async_create_user_message_request({"id": "msg-1"})
        gc.collect()
        await asyncio.sleep(0)
    finally:
        loop.set_exception_handler(previous_handler)

    _assert_nothing_pending(api_client)
    assert unretrieved == []
