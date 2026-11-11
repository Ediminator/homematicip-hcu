"""Secrets (PINs, activation keys, tokens) never appear in the logs."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.hcu_integration import api as api_module
from custom_components.hcu_integration.api import HcuApiClient
from custom_components.hcu_integration.const import AUTH_TYPE_DUAL
from custom_components.hcu_integration.util import LogRedacted, redact_secrets

DEVICE_ID = "3014F711A0000000000000AA"
PIN = "4711"
LOGGER = "custom_components.hcu_integration"


def test_redact_secrets_masks_secret_fields_at_any_depth() -> None:
    data = {
        "type": "HMIP_SYSTEM_REQUEST",
        "body": {
            "path": "/hmip/device/control/setLockState",
            "body": {
                "deviceId": DEVICE_ID,
                "authorizationPin": PIN,
                "targetLockState": "OPEN",
            },
        },
        "list": [{"activationKey": "ABCD-1234"}, {"authToken": "tok"}],
        "AUTHTOKEN": "app-token",
        "CLIENTAUTH": "client-auth",
        "pin": "0000",
        "plugin_token": "plugin-token",
        "app_token": "app-token",
        "authorizationPinAssigned": True,
    }

    redacted = redact_secrets(data)

    assert redacted["body"]["body"] == {
        "deviceId": DEVICE_ID,
        "authorizationPin": "**REDACTED**",
        "targetLockState": "OPEN",
    }
    assert redacted["list"] == [
        {"activationKey": "**REDACTED**"},
        {"authToken": "**REDACTED**"},
    ]
    for key in ("AUTHTOKEN", "CLIENTAUTH", "pin", "plugin_token", "app_token"):
        assert redacted[key] == "**REDACTED**"
    # Similar names that are not secrets stay as they are.
    assert redacted["authorizationPinAssigned"] is True
    assert redacted["body"]["path"] == "/hmip/device/control/setLockState"
    # The data that is sent is not changed.
    assert data["body"]["body"]["authorizationPin"] == PIN
    assert data["list"][0]["activationKey"] == "ABCD-1234"


def test_redact_secrets_passes_other_values_through() -> None:
    assert redact_secrets("text") == "text"
    assert redact_secrets(None) is None
    assert redact_secrets([1, "a"]) == [1, "a"]


def test_log_redacted_formats_without_secrets() -> None:
    wrapped = LogRedacted({"authorizationPin": PIN, "on": True})

    assert PIN not in str(wrapped)
    assert PIN not in repr(wrapped)
    assert str(wrapped) == str({"authorizationPin": "**REDACTED**", "on": True})


def test_log_redacted_only_formats_when_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Disabled debug logging does not pay for the redaction."""
    logger = logging.getLogger(f"{LOGGER}.test_lazy")
    logger.setLevel(logging.INFO)
    with patch("custom_components.hcu_integration.util.redact_secrets") as redact:
        logger.debug("%s", LogRedacted({"authorizationPin": PIN}))
    redact.assert_not_called()


def _connected_ws_client(hass: HomeAssistant) -> tuple[HcuApiClient, MagicMock]:
    client = HcuApiClient(hass, "192.0.2.1", "plugin-token", MagicMock())
    ws = MagicMock()
    ws.closed = False
    ws.send_json = AsyncMock()
    client._websocket = ws
    return client, ws


async def _answered(fut, timeout):  # noqa: ASYNC109 - stands in for wait_for
    return {}


@pytest.mark.parametrize(
    "send",
    [
        lambda client: client.async_set_lock_state(DEVICE_ID, 1, "OPEN", PIN),
        lambda client: client.async_pull_latch(DEVICE_ID, 1, PIN),
    ],
    ids=["set_lock_state", "pull_latch"],
)
async def test_websocket_request_log_hides_pin(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, send
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    client, ws = _connected_ws_client(hass)

    with patch.object(api_module.asyncio, "wait_for", _answered):
        await send(client)

    sent = ws.send_json.await_args.args[0]
    assert sent["body"]["body"]["authorizationPin"] == PIN
    assert PIN not in caplog.text
    assert "'authorizationPin': '**REDACTED**'" in caplog.text


async def test_rest_request_log_hides_pin(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    response = MagicMock()
    response.ok = True
    response.status = 200
    response.content_length = 0
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    session = MagicMock()
    session.post = MagicMock(return_value=context)
    client = HcuApiClient(
        hass,
        "192.0.2.1",
        "plugin-token",
        session,
        auth_type=AUTH_TYPE_DUAL,
        access_point_id=DEVICE_ID,
        app_token="app-token",
    )

    await client.async_set_lock_state(DEVICE_ID, 1, "OPEN", PIN)

    assert session.post.call_args.kwargs["json"]["authorizationPin"] == PIN
    assert PIN not in caplog.text
    assert "'authorizationPin': '**REDACTED**'" in caplog.text


async def test_incoming_message_log_hides_secrets(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """With advanced debugging every incoming message is logged, without secrets."""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    client = HcuApiClient(
        hass, "192.0.2.1", "plugin-token", MagicMock(), advanced_debugging=True
    )
    client.register_event_callback(MagicMock())

    client._handle_incoming_message(
        {"type": "SOME_EVENT", "body": {"authToken": "secret-token"}}
    )

    assert "secret-token" not in caplog.text
    assert "'authToken': '**REDACTED**'" in caplog.text


async def test_plugin_request_log_hides_secrets(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    client = HcuApiClient(hass, "192.0.2.1", "plugin-token", MagicMock())

    with patch.object(client, "_send_config_update_response", AsyncMock()):
        client._handle_incoming_message(
            {
                "type": "CONFIG_UPDATE_REQUEST",
                "id": "req-1",
                "body": {"properties": {"pin": "1234"}},
            }
        )
        await hass.async_block_till_done()

    assert "1234" not in caplog.text
    assert "'pin': '**REDACTED**'" in caplog.text


async def test_error_response_log_hides_secrets(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """An error response that repeats the request does not leak the PIN."""
    caplog.set_level(logging.DEBUG, logger=LOGGER)
    client = HcuApiClient(hass, "192.0.2.1", "plugin-token", MagicMock())
    future = hass.loop.create_future()
    client._pending_requests["req-1"] = future

    client._handle_incoming_message(
        {
            "type": "HMIP_SYSTEM_RESPONSE",
            "id": "req-1",
            "body": {
                "code": 403,
                "body": {"errorCode": "INVALID_PIN", "authorizationPin": PIN},
            },
        }
    )

    assert PIN not in str(future.exception())
    assert PIN not in caplog.text
    assert "INVALID_PIN" in caplog.text
