"""Tests for ERROR_RESPONSE handling on the Plugin WebSocket (Connect API 6.4.7, #516)."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    HCU_ERROR_CODE_TRANSLATION_KEYS,
)
from custom_components.hcu_integration.util import command_failed

_PATH = "/hmip/group/switching/alarm/testSignalAcoustic"


def _error_response(msg_id: str | None, body: object) -> dict:
    message: dict = {
        "pluginId": "de.homeassistant.hcu.integration",
        "type": "ERROR_RESPONSE",
        "body": body,
    }
    if msg_id is not None:
        message["id"] = msg_id
    return message


def _not_allowed(msg_id: str | None) -> dict:
    # Frame as sent by a HmIP-HCU1-A on firmware 1.8.10.
    return _error_response(
        msg_id,
        {
            "error": {
                "code": "NOT_ALLOWED",
                "message": f"Not allowed for this plugin: {_PATH}",
            },
            "originalMessage": "",
        },
    )


async def test_error_response_fails_the_pending_request(
    api_client: HcuApiClient,
) -> None:
    future = asyncio.get_running_loop().create_future()
    api_client._pending_requests["req-1"] = future
    hook = MagicMock()
    api_client._response_hooks["req-1"] = hook

    api_client._handle_incoming_message(_not_allowed("req-1"))

    with pytest.raises(HcuApiError) as exc_info:
        await future
    assert exc_info.value.error_code == "NOT_ALLOWED"
    assert str(exc_info.value) == (
        f"HCU Error: NOT_ALLOWED Not allowed for this plugin: {_PATH}"
    )
    assert "req-1" not in api_client._pending_requests
    assert "req-1" not in api_client._response_hooks
    hook.assert_not_called()


@pytest.mark.parametrize(
    "body", [None, "oops", {"error": "oops"}, {"error": {"code": ""}}]
)
async def test_error_response_without_a_usable_error_code(
    api_client: HcuApiClient, body: object
) -> None:
    future = asyncio.get_running_loop().create_future()
    api_client._pending_requests["req-2"] = future

    api_client._handle_incoming_message(_error_response("req-2", body))

    with pytest.raises(HcuApiError) as exc_info:
        await future
    assert exc_info.value.error_code is None
    assert str(exc_info.value) == "HCU Error: ERROR_RESPONSE"


async def test_error_response_for_an_already_finished_request(
    api_client: HcuApiClient,
) -> None:
    future = asyncio.get_running_loop().create_future()
    future.set_result(None)
    api_client._pending_requests["req-3"] = future

    api_client._handle_incoming_message(_not_allowed("req-3"))

    assert "req-3" not in api_client._pending_requests
    assert future.result() is None


@pytest.mark.parametrize("msg_id", ["unknown-id", None])
async def test_unmatched_error_response_is_logged_not_forwarded(
    api_client: HcuApiClient,
    caplog: pytest.LogCaptureFixture,
    msg_id: str | None,
) -> None:
    callback = MagicMock()
    api_client.register_event_callback(callback)

    with caplog.at_level(logging.WARNING):
        api_client._handle_incoming_message(_not_allowed(msg_id))

    callback.assert_not_called()
    assert "matches no pending request" in caplog.text
    assert "NOT_ALLOWED" in caplog.text


async def test_rejected_request_fails_without_retries(
    api_client: HcuApiClient,
) -> None:
    """A NOT_ALLOWED request fails at once instead of 3 timeouts (#516)."""
    api_client._auth_type = AUTH_TYPE_PLUGIN
    sent: list[dict] = []

    async def reject(message: dict, **_kwargs: object) -> None:
        sent.append(message)
        asyncio.get_running_loop().call_soon(
            api_client._handle_incoming_message, _not_allowed(message["id"])
        )

    api_client._send_message = AsyncMock(side_effect=reject)

    with pytest.raises(HcuApiError) as exc_info:
        await api_client._send_hmip_request(
            _PATH, {"groupId": "g1", "signalAcoustic": "FREQUENCY_RISING"}
        )

    assert exc_info.value.error_code == "NOT_ALLOWED"
    assert len(sent) == 1
    assert api_client._pending_requests == {}


async def test_dualbridge_plugin_ws_passes_error_responses(
    api_client: HcuApiClient,
) -> None:
    api_client._auth_type = AUTH_TYPE_DUAL
    ws = AsyncMock()
    ws.closed = False
    api_client._plugin_websocket = ws
    frame = _not_allowed("req-4")

    msg = MagicMock()
    msg.type = aiohttp.WSMsgType.TEXT
    msg.json = MagicMock(return_value=frame)
    closed = MagicMock()
    closed.type = aiohttp.WSMsgType.CLOSED
    closed.data = "Normal closure"

    async def _msg_iter():
        yield msg
        yield closed

    ws.__aiter__.side_effect = _msg_iter

    with (
        patch.object(api_client, "_handle_incoming_message") as mock_handle,
        pytest.raises(ConnectionAbortedError),
    ):
        await api_client.listen_plugin()

    mock_handle.assert_called_once_with(frame)


async def test_timeout_warning_names_the_exception(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
) -> None:
    """str(TimeoutError()) is empty; the log shows the exception type instead."""
    api_client._auth_type = AUTH_TYPE_PLUGIN
    api_client._send_message = AsyncMock()

    with (
        patch(
            "custom_components.hcu_integration.api.asyncio.wait_for",
            side_effect=TimeoutError(),
        ),
        patch("custom_components.hcu_integration.api.asyncio.sleep"),
        caplog.at_level(logging.WARNING),
        pytest.raises(HcuApiError),
    ):
        await api_client._send_hmip_request(_PATH, {"groupId": "g1"})

    assert f"Request failed on attempt 1/3 for path {_PATH}: TimeoutError" in (
        caplog.text
    )


def test_not_allowed_maps_to_a_translated_error() -> None:
    assert HCU_ERROR_CODE_TRANSLATION_KEYS["NOT_ALLOWED"] == "hcu_error_not_allowed"
    err = command_failed(
        "select.indoor_sirene_test", HcuApiError("x", error_code="NOT_ALLOWED")
    )
    assert err.translation_key == "hcu_error_not_allowed"
    assert err.translation_placeholders == {"entity": "select.indoor_sirene_test"}
