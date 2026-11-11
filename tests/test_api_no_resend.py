"""Tests ensuring non-idempotent Plugin WS requests are not resent after transport failure."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.const import (
    API_PATHS,
    ERROR_DEVICE_BUSY,
    LOCK_STATE_LOCKED,
    LOCK_STATE_OPEN,
    LOCK_STATE_UNLOCKED,
)


@pytest.mark.parametrize(
    ("expected_path", "invoke"),
    [
        pytest.param(
            API_PATHS["TOGGLE_GARAGE_DOOR_STATE"],
            lambda client: client.async_toggle_garage_door_state("dev-1", 1),
            id="toggle_garage_door",
        ),
        pytest.param(
            API_PATHS["SEND_DOOR_IMPULSE"],
            lambda client: client.async_send_door_impulse("dev-1", 1),
            id="door_impulse",
        ),
        pytest.param(
            API_PATHS["SEND_PULL_LATCH"],
            lambda client: client.async_pull_latch("dev-1", 1, None),
            id="pull_latch",
        ),
        pytest.param(
            API_PATHS["SET_SOUND_FILE"],
            lambda client: client.async_set_sound_file(
                "dev-1", 1, "SOUNDFILE_001", 1.0, 5.0
            ),
            id="play_sound",
        ),
        pytest.param(
            API_PATHS["DEVICE_IDENTIFY"],
            lambda client: client.async_send_identify("dev-1", 1),
            id="identify",
        ),
        pytest.param(
            API_PATHS["SET_LOCK_STATE"],
            lambda client: client.async_set_lock_state(
                "dev-1", 1, LOCK_STATE_OPEN, None
            ),
            id="lock_open",
        ),
    ],
)
async def test_action_request_is_sent_once_after_timeout(
    api_client: HcuApiClient,
    expected_path: str,
    invoke: Callable[[HcuApiClient], Awaitable[None]],
) -> None:
    """Action requests must be sent at most once when waiting for a reply times out."""
    sent: list[dict[str, Any]] = []
    timeout_err = TimeoutError()

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(msg)

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=timeout_err,
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await invoke(api_client)

    assert len(sent) == 1
    assert sent[0]["body"]["path"] == expected_path
    mock_sleep.assert_not_awaited()
    assert expected_path in str(exc_info.value)
    assert "TimeoutError" in str(exc_info.value)
    assert "not sent again" in str(exc_info.value)
    assert "may or may not have been carried out" in str(exc_info.value)
    assert "after 3 retries" not in str(exc_info.value)
    assert exc_info.value.error_code is None
    assert exc_info.value.__cause__ is timeout_err
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}


@pytest.mark.parametrize(
    ("expected_path", "invoke"),
    [
        pytest.param(
            API_PATHS["SET_SWITCH_STATE_WITH_TIME"],
            lambda client: client.async_set_switch_state("dev-1", 1, True, on_time=0.5),
            id="switch_on_with_time",
        ),
        pytest.param(
            API_PATHS["SET_SWITCHING_GROUP_STATE_WITH_TIME"],
            lambda client: client.async_set_switching_group_state_with_time(
                "grp-1", True, 0.5
            ),
            id="switching_group_with_time",
        ),
        pytest.param(
            API_PATHS["SET_WATERING_SWITCH_STATE_WITH_TIME"],
            lambda client: client.async_set_watering_switch_state(
                "dev-1", 1, True, on_time=0.5
            ),
            id="watering_switch_with_time",
        ),
        pytest.param(
            API_PATHS["SET_GROUP_WATERING_SWITCH_STATE_WITH_TIME"],
            lambda client: client.async_group_control(
                API_PATHS["SET_GROUP_WATERING_SWITCH_STATE_WITH_TIME"],
                "grp-1",
                {"wateringActive": True, "wateringTime": 0.5},
            ),
            id="watering_group_with_time",
        ),
        pytest.param(
            API_PATHS["SET_DIM_LEVEL_WITH_TIME"],
            lambda client: client.async_set_dim_level("dev-1", 1, 0.5, on_time=0.5),
            id="dim_level_with_on_time",
        ),
    ],
)
async def test_timed_on_request_is_sent_once_after_timeout(
    api_client: HcuApiClient,
    expected_path: str,
    invoke: Callable[[HcuApiClient], Awaitable[None]],
) -> None:
    """Timed-on requests must be sent at most once when waiting for a reply times out."""
    sent: list[dict[str, Any]] = []
    timeout_err = TimeoutError()

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(msg)

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=timeout_err,
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await invoke(api_client)

    assert len(sent) == 1
    assert sent[0]["body"]["path"] == expected_path
    mock_sleep.assert_not_awaited()
    assert expected_path in str(exc_info.value)
    assert "TimeoutError" in str(exc_info.value)
    assert "not sent again" in str(exc_info.value)
    assert "may or may not have been carried out" in str(exc_info.value)
    assert "after 3 retries" not in str(exc_info.value)
    assert exc_info.value.error_code is None
    assert exc_info.value.__cause__ is timeout_err
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}


async def test_late_answer_does_not_cause_a_second_send(
    api_client: HcuApiClient,
) -> None:
    """A late HCU response after timeout must not cause a second send."""
    sent: list[str] = []

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(msg["body"]["path"])

    async def late_wait_for(fut: asyncio.Future[Any], **_kwargs: Any) -> Any:
        if len(sent) == 1:
            raise TimeoutError
        return {}

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=late_wait_for,
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError),
    ):
        await api_client.async_toggle_garage_door_state("dev-1", 1)

    assert sent == [API_PATHS["TOGGLE_GARAGE_DOOR_STATE"]]
    mock_sleep.assert_not_awaited()


async def test_action_request_is_not_sent_again_after_connection_loss(
    api_client: HcuApiClient,
) -> None:
    """ConnectionAbortedError from listener cleanup must not resend an action request."""
    sent: list[dict[str, Any]] = []
    conn_err = ConnectionAbortedError("WebSocket listener stopped unexpectedly.")

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(msg)

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=conn_err,
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client.async_toggle_garage_door_state("dev-1", 1)

    assert len(sent) == 1
    assert "WebSocket listener stopped unexpectedly." in str(exc_info.value)
    assert "not sent again" in str(exc_info.value)
    assert "may or may not have been carried out" in str(exc_info.value)
    assert exc_info.value.__cause__ is conn_err
    mock_sleep.assert_not_awaited()


async def test_action_request_fails_at_once_when_not_connected(
    api_client: HcuApiClient,
) -> None:
    """A ConnectionError from _send_message must not retry an action request."""
    conn_err = ConnectionError("Not connected to HCU WebSocket.")

    with (
        patch.object(api_client, "_send_message", side_effect=conn_err) as mock_send,
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client.async_send_door_impulse("dev-1", 1)

    assert mock_send.await_count == 1
    mock_sleep.assert_not_awaited()
    assert "Not connected to HCU WebSocket." in str(exc_info.value)
    assert "not sent again" in str(exc_info.value)
    assert "may or may not have been carried out" in str(exc_info.value)
    assert exc_info.value.__cause__ is conn_err
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}


async def test_send_api_command_follows_the_rule(api_client: HcuApiClient) -> None:
    """send_api_command must also avoid resending paths in the no-resend set."""
    sent: list[dict[str, Any]] = []

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(msg)

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=TimeoutError(),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError),
    ):
        await api_client.async_send_api_command(
            API_PATHS["TOGGLE_GARAGE_DOOR_STATE"],
            {"deviceId": "dev-1", "channelIndex": 1},
        )

    assert len(sent) == 1
    mock_sleep.assert_not_awaited()


@pytest.mark.parametrize(
    ("expected_path", "invoke"),
    [
        pytest.param(
            API_PATHS["SET_SWITCH_STATE"],
            lambda client: client.async_set_switch_state("dev-1", 1, True),
            id="set_switch_state",
        ),
        pytest.param(
            API_PATHS["SEND_DOOR_COMMAND"],
            lambda client: client.async_send_door_command("dev-1", 1, "OPEN"),
            id="send_door_command",
        ),
        pytest.param(
            API_PATHS["SET_LOCK_STATE"],
            lambda client: client.async_set_lock_state(
                "dev-1", 1, LOCK_STATE_LOCKED, None
            ),
            id="lock_locked",
        ),
        pytest.param(
            API_PATHS["SET_LOCK_STATE"],
            lambda client: client.async_set_lock_state(
                "dev-1", 1, LOCK_STATE_UNLOCKED, None
            ),
            id="lock_unlocked",
        ),
        pytest.param(
            API_PATHS["SET_DIM_LEVEL_WITH_TIME"],
            lambda client: client.async_set_dim_level("dev-1", 1, 0.5, ramp_time=2.0),
            id="dim_level_with_ramp_time",
        ),
        pytest.param(
            "/test/path",
            lambda client: client.async_send_api_command("/test/path", {}),
            id="unknown_path",
        ),
    ],
)
async def test_target_state_requests_are_still_retried(
    api_client: HcuApiClient,
    expected_path: str,
    invoke: Callable[[HcuApiClient], Awaitable[None]],
) -> None:
    """Target-state and unknown requests must keep retrying with the same message ID."""
    sent: list[dict[str, Any]] = []

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(dict(msg))

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=[TimeoutError(), {}],
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await invoke(api_client)

    assert len(sent) == 2
    assert sent[0]["body"]["path"] == expected_path
    assert sent[1]["body"]["path"] == expected_path
    assert sent[0]["id"] == sent[1]["id"]
    mock_sleep.assert_awaited_once()


async def test_device_busy_answer_is_still_retried_once_for_action_requests(
    api_client: HcuApiClient,
) -> None:
    """DEVICE_BUSY responses on action requests still retry once with a new ID."""
    sent_ids: list[str] = []

    async def fake_send(msg: dict[str, Any], log_body: bool = True) -> None:
        msg_id = msg["id"]
        sent_ids.append(msg_id)
        if len(sent_ids) == 1:
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": ERROR_DEVICE_BUSY}},
                }
            )
        else:
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 200, "body": {}},
                }
            )

    with (
        patch.object(api_client, "_send_message", side_effect=fake_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
    ):
        await api_client.async_toggle_garage_door_state("dev-1", 1)

    assert len(sent_ids) == 2
    assert sent_ids[0] != sent_ids[1]
    mock_sleep.assert_awaited_once()


def test_no_resend_paths_are_known_api_paths() -> None:
    """API_NO_RESEND_PATHS must match the documented action and timed-on paths."""
    from custom_components.hcu_integration.const import API_NO_RESEND_PATHS

    expected = frozenset(
        {
            API_PATHS["TOGGLE_GARAGE_DOOR_STATE"],
            API_PATHS["SEND_DOOR_IMPULSE"],
            API_PATHS["SEND_PULL_LATCH"],
            API_PATHS["SET_SOUND_FILE"],
            API_PATHS["DEVICE_IDENTIFY"],
            API_PATHS["SET_SWITCH_STATE_WITH_TIME"],
            API_PATHS["SET_SWITCHING_GROUP_STATE_WITH_TIME"],
            API_PATHS["SET_WATERING_SWITCH_STATE_WITH_TIME"],
            API_PATHS["SET_GROUP_WATERING_SWITCH_STATE_WITH_TIME"],
        }
    )
    assert API_NO_RESEND_PATHS.issubset(API_PATHS.values())
    assert expected == API_NO_RESEND_PATHS


async def test_action_request_failure_is_logged_once(
    api_client: HcuApiClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Failed action requests log one WARNING with the path and without attempt 1/3."""
    api_client._send_message = AsyncMock()
    expected_path = API_PATHS["TOGGLE_GARAGE_DOOR_STATE"]

    with (
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=TimeoutError(),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        caplog.at_level(logging.WARNING, logger="custom_components.hcu_integration"),
        pytest.raises(HcuApiError),
    ):
        await api_client.async_toggle_garage_door_state("dev-1", 1)

    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert expected_path in warnings[0].message
    assert "attempt 1/3" not in warnings[0].message
    assert "TimeoutError" in warnings[0].message
    assert "not sent again" in warnings[0].message
    assert "may or may not have been carried out" in warnings[0].message


async def test_late_system_response_after_timeout_is_ignored(
    api_client: HcuApiClient,
) -> None:
    """A late HMIP_SYSTEM_RESPONSE after an action timeout is ignored safely."""
    sent_ids: list[str] = []
    on_success = MagicMock()

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent_ids.append(msg["id"])

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=TimeoutError(),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(HcuApiError),
    ):
        await api_client._send_hmip_request(
            API_PATHS["TOGGLE_GARAGE_DOOR_STATE"],
            {"deviceId": "dev-1", "channelIndex": 1},
            on_success=on_success,
        )

    assert len(sent_ids) == 1
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}

    api_client._handle_incoming_message(
        {
            "type": "HMIP_SYSTEM_RESPONSE",
            "id": sent_ids[0],
            "body": {"code": 200, "body": {"ok": True}},
        }
    )
    on_success.assert_not_called()
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}


async def test_action_request_device_busy_then_timeout_does_not_resend(
    api_client: HcuApiClient,
) -> None:
    """A timeout on the DEVICE_BUSY retry of an action request must not resend again."""
    sent_ids: list[str] = []

    async def fake_send(msg: dict[str, Any], log_body: bool = True) -> None:
        msg_id = msg["id"]
        sent_ids.append(msg_id)
        if len(sent_ids) == 1:
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": ERROR_DEVICE_BUSY}},
                }
            )

    async def fake_wait_for(fut: asyncio.Future[Any], **_kwargs: Any) -> Any:
        if fut.done():
            return fut.result()
        raise TimeoutError

    with (
        patch.object(api_client, "_send_message", side_effect=fake_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=fake_wait_for,
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client.async_toggle_garage_door_state("dev-1", 1)

    assert len(sent_ids) == 2
    assert sent_ids[0] != sent_ids[1]
    mock_sleep.assert_awaited_once()
    assert isinstance(exc_info.value.__cause__, TimeoutError)
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}


async def test_retried_request_exhaustion_cleans_up_pending_requests(
    api_client: HcuApiClient,
) -> None:
    """A retried request that exhausts all attempts cleans up pending request tracking."""
    sent: list[dict[str, Any]] = []

    async def record_send(msg: dict[str, Any], log_body: bool = True) -> None:
        sent.append(msg)

    with (
        patch.object(api_client, "_send_message", side_effect=record_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=TimeoutError(),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            new_callable=AsyncMock,
        ),
        pytest.raises(HcuApiError, match="Request failed after 3 retries"),
    ):
        await api_client.async_set_switch_state("dev-1", 1, True)

    assert len(sent) == 3
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}
