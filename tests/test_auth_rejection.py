"""Tests for token rejection detection, setup auth failures, and runtime reauth triggers."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration import (
    async_setup_entry,
    coordinator as coordinator_module,
)
from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_APP_TOKEN,
    CONF_AUTH_TYPE,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_TOKEN,
    DOMAIN,
    HCU_APP_WS_PORT,
    HCU_PLUGIN_WS_PORT,
)
from custom_components.hcu_integration.coordinator import HcuCoordinator

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

SLEEP = "custom_components.hcu_integration.coordinator.asyncio.sleep"
TEST_SGTIN = "3014F711A000000000000001"


def _ws_handshake_error(
    status: int, message: str = "Invalid response status"
) -> aiohttp.WSServerHandshakeError:
    """Create an aiohttp WSServerHandshakeError with the given HTTP status."""
    return aiohttp.WSServerHandshakeError(
        MagicMock(), (), status=status, message=message
    )


def _sample_state() -> dict:
    """Return a minimal valid HCU state payload with one device."""
    return {
        "home": {"id": "home-1", "accessPointId": TEST_SGTIN},
        "devices": {
            TEST_SGTIN: {
                "id": TEST_SGTIN,
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-HCU1",
                "label": "HCU",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                },
            }
        },
        "groups": {},
    }


def _fake_rest_response(
    status: int,
    body_text: str = "",
    json_data: dict | None = None,
) -> MagicMock:
    """Create an async context manager mimicking aiohttp ClientResponse."""
    resp = MagicMock()
    resp.status = status
    resp.ok = 200 <= status < 300
    resp.text = AsyncMock(return_value=body_text)
    resp.json = AsyncMock(return_value=json_data if json_data is not None else {})
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return cm


def _make_entry(
    hass: HomeAssistant,
    auth_type: str = AUTH_TYPE_PLUGIN,
    *,
    entry_id: str = "auth_test_entry",
) -> MockConfigEntry:
    """Create and register a MockConfigEntry for the given auth mode."""
    data: dict = {
        CONF_HOST: "192.0.2.10",
        CONF_AUTH_TYPE: auth_type,
    }
    if auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL):
        data[CONF_PLUGIN_TOKEN] = "saved-plugin-token"
    if auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
        data[CONF_APP_TOKEN] = "saved-app-token"
        data[CONF_HCU_SGTIN] = TEST_SGTIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data=data,
        unique_id=TEST_SGTIN,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


# ---------------------------------------------------------------------------
# Rejection rule and App WebSocket connect() signaling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        # WSServerHandshakeError 401 / 403 -> True
        (_ws_handshake_error(401), True),
        (_ws_handshake_error(403), True),
        # HcuApiError with INVALID_AUTHORIZATION (any status) -> True
        (HcuApiError("rejected", error_code="INVALID_AUTHORIZATION"), True),
        (
            HcuApiError(
                "rejected", error_code="INVALID_AUTHORIZATION", status_code=400
            ),
            True,
        ),
        (
            HcuApiError(
                "rejected", error_code="INVALID_AUTHORIZATION", status_code=401
            ),
            True,
        ),
        (
            HcuApiError(
                "rejected", error_code="INVALID_AUTHORIZATION", status_code=500
            ),
            True,
        ),
        # HcuApiError 401 / 403 without error_code -> True
        (HcuApiError("unauth", status_code=401), True),
        (HcuApiError("forbidden", status_code=403), True),
        (HcuApiError("unauth", status_code=401, error_code=""), True),
        # HcuApiError 401 / 403 with another error_code -> False
        (
            HcuApiError("denied", status_code=401, error_code="CLIENT_ACCESS_DENIED"),
            False,
        ),
        (
            HcuApiError("denied", status_code=403, error_code="CLIENT_ACCESS_DENIED"),
            False,
        ),
        (
            HcuApiError(
                "denied", status_code=401, error_code="CLIENT_INVALID_AUTHORIZATION"
            ),
            False,
        ),
        (
            HcuApiError(
                "denied",
                status_code=403,
                error_code="ACCESS_POINT_REMOTE_ACCESS_DENIED",
            ),
            False,
        ),
        (
            HcuApiError(
                "init",
                status_code=401,
                error_code="NOT_ALLOWED_DURING_INITIALIZATION",
            ),
            False,
        ),
        # HcuApiError other status or no status/code -> False
        (HcuApiError("bad request", status_code=400), False),
        (HcuApiError("not found", status_code=404), False),
        (HcuApiError("server error", status_code=500), False),
        (HcuApiError("bad gateway", status_code=502), False),
        (HcuApiError("unavailable", status_code=503), False),
        (HcuApiError("generic"), False),
        # WSServerHandshakeError other statuses -> False
        (_ws_handshake_error(404), False),
        (_ws_handshake_error(500), False),
        (_ws_handshake_error(502), False),
        (_ws_handshake_error(503), False),
        # Network / transient / other exceptions -> False
        (TimeoutError("timeout"), False),
        (ConnectionError("connection lost"), False),
        (OSError("network unreachable"), False),
        (aiohttp.ClientConnectorError(MagicMock(), OSError("refused")), False),
        (aiohttp.ClientError("other client error"), False),
        (RuntimeError("unexpected"), False),
    ],
)
def test_is_auth_rejection(err: BaseException, expected: bool) -> None:
    """Test is_auth_rejection across all error types, statuses, and codes."""
    assert coordinator_module.is_auth_rejection(err) is expected


@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_DUAL])
@pytest.mark.parametrize("status", [401, 403])
async def test_connect_app_reports_rejected_handshake(
    api_client: HcuApiClient, auth_type: str, status: int
) -> None:
    """App User / DualBridge connect() re-raises port 8888 401/403 if nothing connects."""
    api_client._auth_type = auth_type
    api_client._app_token = "app-token"
    api_client._access_point_id = TEST_SGTIN

    async def fake_ws_connect(url: str, **kwargs):
        if f":{HCU_APP_WS_PORT}" in url:
            raise _ws_handshake_error(status)
        raise aiohttp.ClientConnectionError("9001 refused")

    api_client._session.ws_connect = AsyncMock(side_effect=fake_ws_connect)

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(aiohttp.WSServerHandshakeError) as exc_info,
    ):
        await api_client.connect()

    assert exc_info.value.status == status
    assert api_client.is_connected is False


async def test_connect_app_other_failures_unchanged(api_client: HcuApiClient) -> None:
    """Port 9001 401, port 8888 503, and 8888-401-with-9001-fallback behave as before."""
    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "app-token"
    api_client._access_point_id = TEST_SGTIN

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        # 1. 8888 refused and 9001 handshake 401 -> ConnectionError
        async def refused_8888_401_9001(url: str, **kwargs):
            if f":{HCU_APP_WS_PORT}" in url:
                raise aiohttp.ClientConnectionError("refused")
            raise _ws_handshake_error(401)

        api_client._session.ws_connect = AsyncMock(side_effect=refused_8888_401_9001)
        with pytest.raises(ConnectionError):
            await api_client.connect()
        assert api_client.is_connected is False

        # 2. 8888 handshake 503 -> ConnectionError
        async def err_503_8888(url: str, **kwargs):
            if f":{HCU_APP_WS_PORT}" in url:
                raise _ws_handshake_error(503)
            raise aiohttp.ClientConnectionError("refused")

        api_client._session.ws_connect = AsyncMock(side_effect=err_503_8888)
        with pytest.raises(ConnectionError):
            await api_client.connect()
        assert api_client.is_connected is False

        # 3. 8888 handshake 401 and 9001 connects (App User) -> connected
        mock_ws = AsyncMock()
        mock_ws.closed = False

        async def reject_8888_ok_9001(url: str, **kwargs):
            if f":{HCU_APP_WS_PORT}" in url:
                raise _ws_handshake_error(401)
            return mock_ws

        api_client._session.ws_connect = AsyncMock(side_effect=reject_8888_ok_9001)
        await api_client.connect()
        assert api_client.is_connected is True


# ---------------------------------------------------------------------------
# Setup auth rejection and retry preservation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [401, 403])
async def test_setup_plugin_rejected_handshake_starts_reauth(
    hass: HomeAssistant, status: int
) -> None:
    """Plugin User setup stops immediately in SETUP_ERROR and starts reauth on 401/403."""
    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id=f"plugin_rej_{status}")
    session = MagicMock(spec=aiohttp.ClientSession)
    session.ws_connect = AsyncMock(side_effect=_ws_handshake_error(status))

    with (
        patch(
            "custom_components.hcu_integration.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_CONNECT_TIMEOUT",
            30,
        ),
    ):
        async with asyncio.timeout(2.0):
            result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == entry.entry_id
    assert flows[0]["step_id"] == "reauth_confirm"
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"setup_failed_{entry.entry_id}")
        is None
    )


@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_DUAL])
@pytest.mark.parametrize(
    ("status", "body"),
    [
        (401, ""),
        (403, '{"message": "forbidden"}'),
        (401, '{"errorCode": "INVALID_AUTHORIZATION"}'),
        (400, '{"errorCode": "INVALID_AUTHORIZATION"}'),
    ],
)
async def test_setup_app_rejected_state_load_starts_reauth(
    hass: HomeAssistant, auth_type: str, status: int, body: str
) -> None:
    """App User / DualBridge setup stops in SETUP_ERROR and starts reauth on REST rejection."""
    entry = _make_entry(hass, auth_type, entry_id=f"app_rej_{auth_type}_{status}")
    session = MagicMock(spec=aiohttp.ClientSession)
    session.ws_connect = AsyncMock(side_effect=aiohttp.ClientConnectionError("ws down"))
    session.post = MagicMock(return_value=_fake_rest_response(status, body_text=body))

    with (
        patch(
            "custom_components.hcu_integration.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_CONNECT_TIMEOUT",
            30,
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["step_id"] == "reauth_confirm"
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"setup_failed_{entry.entry_id}")
        is None
    )


@pytest.mark.parametrize(
    ("auth_type", "ws_err", "rest_status", "rest_body", "rest_json"),
    [
        (AUTH_TYPE_PLUGIN, _ws_handshake_error(500), None, "", None),
        (AUTH_TYPE_PLUGIN, _ws_handshake_error(502), None, "", None),
        (AUTH_TYPE_PLUGIN, _ws_handshake_error(503), None, "", None),
        (AUTH_TYPE_PLUGIN, _ws_handshake_error(404), None, "", None),
        (
            AUTH_TYPE_PLUGIN,
            aiohttp.ClientConnectionError("refused"),
            None,
            "",
            None,
        ),
        (AUTH_TYPE_PLUGIN, OSError("net down"), None, "", None),
        (AUTH_TYPE_PLUGIN, TimeoutError("timed out"), None, "", None),
        (AUTH_TYPE_APP, None, 500, "Server error", None),
        (AUTH_TYPE_APP, None, 503, "Unavailable", None),
        (AUTH_TYPE_APP, None, 403, '{"errorCode": "CLIENT_ACCESS_DENIED"}', None),
        (
            AUTH_TYPE_APP,
            None,
            401,
            '{"errorCode": "NOT_ALLOWED_DURING_INITIALIZATION"}',
            None,
        ),
        (AUTH_TYPE_APP, None, 200, "", {"devices": {}, "groups": {}}),
    ],
)
async def test_setup_transient_errors_still_retry(
    hass: HomeAssistant,
    auth_type: str,
    ws_err: Exception | None,
    rest_status: int | None,
    rest_body: str,
    rest_json: dict | None,
) -> None:
    """Transient errors and non-token-rejection codes keep SETUP_RETRY with setup_failed issue."""
    entry = _make_entry(hass, auth_type)
    session = MagicMock(spec=aiohttp.ClientSession)
    session.ws_connect = AsyncMock(
        side_effect=ws_err or aiohttp.ClientConnectionError("ws down")
    )
    if rest_status is not None:
        session.post = MagicMock(
            return_value=_fake_rest_response(
                rest_status, body_text=rest_body, json_data=rest_json
            )
        )

    with (
        patch(
            "custom_components.hcu_integration.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_CONNECT_TIMEOUT",
            0.05,
        ),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"setup_failed_{entry.entry_id}")
        is not None
    )


async def test_setup_rejection_removes_stale_setup_issue(
    hass: HomeAssistant,
) -> None:
    """A stale setup_failed issue is deleted when setup fails due to token rejection."""
    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id="stale_issue_entry")
    ir.async_create_issue(
        hass,
        DOMAIN,
        f"setup_failed_{entry.entry_id}",
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="setup_failed",
        translation_placeholders={
            "host": "192.0.2.10",
            "auth_mode": "Plugin User",
            "reason": "previous timeout",
        },
        data={"entry_id": entry.entry_id},
    )
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"setup_failed_{entry.entry_id}")
        is not None
    )

    session = MagicMock(spec=aiohttp.ClientSession)
    session.ws_connect = AsyncMock(side_effect=_ws_handshake_error(401))

    with (
        patch(
            "custom_components.hcu_integration.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_CONNECT_TIMEOUT",
            30,
        ),
    ):
        async with asyncio.timeout(2.0):
            await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"setup_failed_{entry.entry_id}")
        is None
    )


@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_DUAL])
async def test_setup_state_load_rejection_removes_stale_setup_issue(
    hass: HomeAssistant, auth_type: str
) -> None:
    """A stale setup_failed issue is deleted when REST state load is rejected."""
    entry = _make_entry(hass, auth_type, entry_id=f"stale_{auth_type}")
    issue_id = f"setup_failed_{entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=True,
        severity=ir.IssueSeverity.ERROR,
        translation_key="setup_failed",
        translation_placeholders={
            "host": "192.0.2.10",
            "auth_mode": "App User",
            "reason": "previous error",
        },
        data={"entry_id": entry.entry_id},
    )
    session = MagicMock(spec=aiohttp.ClientSession)
    session.ws_connect = AsyncMock(side_effect=aiohttp.ClientConnectionError("down"))
    session.post = MagicMock(return_value=_fake_rest_response(401))

    with patch(
        "custom_components.hcu_integration.async_get_clientsession",
        return_value=session,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_setup_entry_closes_sockets_on_auth_failure(
    hass: HomeAssistant,
) -> None:
    """async_setup_entry closes both sockets and leaves no runtime_data on ConfigEntryAuthFailed."""
    entry = _make_entry(hass, AUTH_TYPE_DUAL, entry_id="close_sockets_entry")
    mock_client = MagicMock(spec=HcuApiClient)
    mock_client.plugin_id = "de.homeassistant.hcu.integration"
    mock_client._send_message = AsyncMock()
    mock_client.set_ha_entity_bridge = MagicMock()
    mock_client.disconnect = AsyncMock()
    mock_client.disconnect_plugin = AsyncMock()

    with (
        patch(
            "custom_components.hcu_integration.HcuApiClient",
            return_value=mock_client,
        ),
        patch.object(
            HcuCoordinator,
            "async_setup",
            AsyncMock(side_effect=ConfigEntryAuthFailed("rejected")),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await async_setup_entry(hass, entry)

    mock_client.disconnect.assert_awaited_once()
    mock_client.disconnect_plugin.assert_awaited_once()
    assert getattr(entry, "runtime_data", None) is None


async def test_dual_setup_with_rejected_plugin_socket_loads_and_starts_reauth(
    hass: HomeAssistant,
) -> None:
    """DualBridge loads when REST + App WS work even if Plugin WS 9001 rejects with 401."""
    entry = _make_entry(hass, AUTH_TYPE_DUAL, entry_id="dual_plugin_rej")
    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(
        return_value=_fake_rest_response(200, json_data=_sample_state())
    )

    plugin_attempts = 0
    stop_app_ws = asyncio.Event()

    class _FakeAppWs:
        closed = False

        async def close(self) -> None:
            self.closed = True
            stop_app_ws.set()

        def __aiter__(self):
            return self

        async def __anext__(self):
            await stop_app_ws.wait()
            raise StopAsyncIteration

    app_ws = _FakeAppWs()

    async def fake_ws_connect(url: str, **kwargs):
        nonlocal plugin_attempts
        if f":{HCU_PLUGIN_WS_PORT}" in url:
            plugin_attempts += 1
            raise _ws_handshake_error(401)
        return app_ws

    session.ws_connect = AsyncMock(side_effect=fake_ws_connect)

    real_sleep = asyncio.sleep

    async def cancel_backoff_sleep(delay: float) -> None:
        if delay == 0:
            await real_sleep(0)
            return
        raise asyncio.CancelledError

    with (
        patch(
            "custom_components.hcu_integration.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.getmac.get_mac_address",
            return_value="aa:bb:cc:dd:ee:ff",
        ),
        patch(SLEEP, cancel_backoff_sleep),
    ):
        result = await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert result is True
    assert entry.state is ConfigEntryState.LOADED
    assert plugin_attempts >= 1
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["step_id"] == "reauth_confirm"

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


# ---------------------------------------------------------------------------
# Running entry auth rejection handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("auth_type", [AUTH_TYPE_PLUGIN, AUTH_TYPE_APP, AUTH_TYPE_DUAL])
async def test_rejected_reconnect_starts_reauth_and_keeps_retrying(
    hass: HomeAssistant, auth_type: str
) -> None:
    """Rejected connect attempts trigger reauth and keep retrying until connected."""
    entry = _make_entry(hass, auth_type, entry_id=f"r1_{auth_type}")
    client = MagicMock(spec=HcuApiClient)
    client.state = _sample_state()
    client.is_connected = False
    client.disconnect = AsyncMock()
    client.announce_plugin_ready = AsyncMock()
    client.register_event_callback = MagicMock()
    client.get_system_state = AsyncMock(return_value=client.state)

    attempts = 0

    async def fake_connect() -> None:
        nonlocal attempts
        attempts += 1
        if attempts <= 2:
            raise _ws_handshake_error(401)
        client.is_connected = True

    client.connect = AsyncMock(side_effect=fake_connect)
    client.listen = AsyncMock(side_effect=asyncio.CancelledError)

    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True

    with (
        patch.object(entry, "async_start_reauth") as mock_reauth,
        patch(SLEEP, AsyncMock()),
    ):
        await coordinator._listen_for_events()
        await hass.async_block_till_done()

    assert mock_reauth.call_count == 2
    assert client.connect.await_count == 3
    client.register_event_callback.assert_called_once()
    assert coordinator._connected_event.is_set()
    client.get_system_state.assert_awaited_once()


async def test_rejected_plugin_socket_starts_reauth(hass: HomeAssistant) -> None:
    """DualBridge Plugin WS handshake 403 triggers reauth without disconnecting App WS."""
    entry = _make_entry(hass, AUTH_TYPE_DUAL, entry_id="r2_dual")
    client = MagicMock(spec=HcuApiClient)
    client.is_connected = True
    client.is_plugin_connected = False
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    client.connect_plugin = AsyncMock(
        side_effect=[
            _ws_handshake_error(403),
            _ws_handshake_error(403),
            asyncio.CancelledError(),
        ]
    )
    coordinator = HcuCoordinator(hass, client, entry)

    with (
        patch.object(entry, "async_start_reauth") as mock_reauth,
        patch(SLEEP, AsyncMock()),
    ):
        await coordinator._listen_for_plugin_events()

    assert mock_reauth.call_count == 2
    assert client.connect_plugin.await_count == 3
    client.disconnect.assert_not_awaited()


async def test_rejected_state_refresh_starts_reauth(hass: HomeAssistant) -> None:
    """A 401 during _async_refresh_state_after_reconnect starts reauth and retries."""
    entry = _make_entry(hass, AUTH_TYPE_APP, entry_id="r3_refresh")
    client = MagicMock(spec=HcuApiClient)
    client.state = _sample_state()
    client.is_connected = True
    client.get_system_state = AsyncMock(
        side_effect=[
            HcuApiError("HTTP 401", status_code=401),
            client.state,
        ]
    )
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._connection_ready = False
    coordinator.async_set_updated_data = MagicMock()

    with (
        patch.object(entry, "async_start_reauth") as mock_reauth,
        patch(SLEEP, AsyncMock()),
    ):
        await coordinator._async_refresh_state_after_reconnect()

    mock_reauth.assert_called_once_with(hass)
    assert client.get_system_state.await_count == 2
    assert coordinator.connection_ready is True


async def test_update_data_raises_auth_failed_on_rejection(
    hass: HomeAssistant,
) -> None:
    """_async_update_data raises ConfigEntryAuthFailed on rejection, UpdateFailed otherwise."""
    entry = _make_entry(hass, AUTH_TYPE_APP, entry_id="r4_update_data")
    client = MagicMock(spec=HcuApiClient)
    coordinator = HcuCoordinator(hass, client, entry)

    client.get_system_state = AsyncMock(
        side_effect=HcuApiError("HTTP 401", status_code=401)
    )
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()

    client.get_system_state = AsyncMock(side_effect=HcuApiError("Timeout"))
    with pytest.raises(UpdateFailed, match="Error communicating with API: Timeout"):
        await coordinator._async_update_data()


@pytest.mark.parametrize(
    "err",
    [
        _ws_handshake_error(503),
        OSError("network error"),
        TimeoutError("timed out"),
        ConnectionError("closed"),
        HcuApiError("HTTP 500", status_code=500),
        HcuApiError("denied", status_code=403, error_code="CLIENT_ACCESS_DENIED"),
    ],
)
async def test_transient_runtime_errors_do_not_start_reauth(
    hass: HomeAssistant, err: Exception
) -> None:
    """Transient errors and non-token codes never start reauth on connect, plugin, or refresh."""
    entry = _make_entry(hass, AUTH_TYPE_DUAL, entry_id="r5_transient")
    client = MagicMock(spec=HcuApiClient)
    client.state = _sample_state()
    client.is_connected = False
    client.is_plugin_connected = False
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True

    with (
        patch.object(entry, "async_start_reauth") as mock_reauth,
        patch(SLEEP, AsyncMock()),
    ):
        # 1. Primary WS listener
        client.connect = AsyncMock(side_effect=[err, asyncio.CancelledError()])
        await coordinator._listen_for_events()

        # 2. Plugin WS listener
        client.connect_plugin = AsyncMock(side_effect=[err, asyncio.CancelledError()])
        await coordinator._listen_for_plugin_events()

        # 3. State refresh (get_system_state catches TimeoutError, HcuApiError, ConnectionError, ClientError)
        if isinstance(
            err, (TimeoutError, HcuApiError, ConnectionError, aiohttp.ClientError)
        ):
            client.is_connected = True
            client.get_system_state = AsyncMock(side_effect=[err, client.state])
            await coordinator._async_refresh_state_after_reconnect()

    mock_reauth.assert_not_called()


async def test_rejection_is_logged_once_per_outage(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Repeated rejections in one outage log one WARNING with host/status and no token."""
    secret = "secret-token-should-never-appear"
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.55",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: secret,
        },
        entry_id="r6_log_once",
    )
    entry.add_to_hass(hass)

    client = MagicMock(spec=HcuApiClient)
    client.state = _sample_state()
    client.is_connected = False
    client.disconnect = AsyncMock()
    client.connect = AsyncMock(
        side_effect=[
            _ws_handshake_error(401, message=f"Invalid token {secret}"),
            _ws_handshake_error(401, message=f"Invalid token {secret}"),
            _ws_handshake_error(401, message=f"Invalid token {secret}"),
            asyncio.CancelledError(),
        ]
    )
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True

    with (
        patch.object(entry, "async_start_reauth"),
        patch(SLEEP, AsyncMock()),
        caplog.at_level(
            logging.DEBUG, logger="custom_components.hcu_integration.coordinator"
        ),
    ):
        await coordinator._listen_for_events()

    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    debugs = [
        r for r in caplog.records if r.levelname == "DEBUG" and "401" in r.getMessage()
    ]
    assert len(warnings) == 1
    assert "192.0.2.55" in warnings[0].getMessage()
    assert "401" in warnings[0].getMessage()
    assert len(debugs) == 2
    assert all(secret not in r.getMessage() for r in caplog.records)

    # Also verify state refresh logs once with status + error code and never leaks token
    caplog.clear()
    client.is_connected = True
    client.get_system_state = AsyncMock(
        side_effect=[
            HcuApiError(
                f"Rejected {secret}",
                status_code=401,
                error_code="INVALID_AUTHORIZATION",
            ),
            HcuApiError(
                f"Rejected {secret}",
                status_code=401,
                error_code="INVALID_AUTHORIZATION",
            ),
            client.state,
        ]
    )
    coordinator._connection_ready = False
    with (
        patch.object(entry, "async_start_reauth"),
        patch(SLEEP, AsyncMock()),
        caplog.at_level(
            logging.DEBUG, logger="custom_components.hcu_integration.coordinator"
        ),
    ):
        await coordinator._async_refresh_state_after_reconnect()

    refresh_warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    refresh_debugs = [
        r
        for r in caplog.records
        if r.levelname == "DEBUG" and "INVALID_AUTHORIZATION" in r.getMessage()
    ]
    assert len(refresh_warnings) == 1
    assert "192.0.2.55" in refresh_warnings[0].getMessage()
    assert "401" in refresh_warnings[0].getMessage()
    assert "INVALID_AUTHORIZATION" in refresh_warnings[0].getMessage()
    assert len(refresh_debugs) == 1
    assert all(secret not in r.getMessage() for r in caplog.records)


async def test_rejection_warning_once_per_outage_on_both_sockets(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Log one warning per outage and debug on subsequent failures for both sockets."""
    entry = _make_entry(hass, AUTH_TYPE_DUAL, entry_id="log_outages")
    client = MagicMock(spec=HcuApiClient)
    client.state = {"devices": {}, "groups": {}}
    client.is_connected = False
    client.is_plugin_connected = False
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    client.announce_plugin_ready = AsyncMock()
    client.get_system_state = AsyncMock(return_value=client.state)
    client.listen = AsyncMock()
    client.listen_plugin = AsyncMock()
    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._initial_state_loaded = True
    coord_logger = "custom_components.hcu_integration.coordinator"

    def lines(marker: str) -> list[tuple[str, str]]:
        return [
            (r.levelname, r.getMessage().split(" at ")[0].split(":")[0])
            for r in caplog.records
            if r.name == coord_logger
            and r.levelname in ("WARNING", "DEBUG")
            and marker in r.getMessage()
        ]

    with (
        patch.object(entry, "async_start_reauth"),
        patch(SLEEP, AsyncMock()),
        caplog.at_level(logging.DEBUG, logger=coord_logger),
    ):
        # Plugin socket: rejected, refused, rejected, connected, refused, rejected.
        client.connect_plugin = AsyncMock(
            side_effect=[
                _ws_handshake_error(403),
                ConnectionError("refused"),
                _ws_handshake_error(403),
                None,
                ConnectionError("refused"),
                _ws_handshake_error(403),
                asyncio.CancelledError(),
            ]
        )
        await coordinator._listen_for_plugin_events()
        plugin_lines = lines("DualBridge Plugin WebSocket")
        caplog.clear()

        # Primary socket: the same sequence across two outages.
        client.connect = AsyncMock(
            side_effect=[
                _ws_handshake_error(401),
                ConnectionError("refused"),
                _ws_handshake_error(401),
                None,
                ConnectionError("refused"),
                _ws_handshake_error(401),
                asyncio.CancelledError(),
            ]
        )
        await coordinator._listen_for_events()
        await hass.async_block_till_done()
        first_lines = lines("WebSocket")

    assert plugin_lines == [
        ("WARNING", "DualBridge Plugin WebSocket connection to HCU"),
        ("DEBUG", "DualBridge Plugin WebSocket reconnect failed"),
        ("DEBUG", "DualBridge Plugin WebSocket connection to HCU"),
        ("WARNING", "DualBridge Plugin WebSocket disconnected"),
        ("WARNING", "DualBridge Plugin WebSocket connection to HCU"),
    ]
    assert first_lines == [
        ("WARNING", "WebSocket connection to HCU"),
        ("DEBUG", "WebSocket reconnect failed"),
        ("DEBUG", "WebSocket connection to HCU"),
        ("WARNING", "WebSocket disconnected"),
        ("WARNING", "WebSocket connection to HCU"),
    ]


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (_ws_handshake_error(403), "HTTP 403"),
        (HcuApiError("x", status_code=401), "HTTP 401"),
        (
            HcuApiError("x", error_code="INVALID_AUTHORIZATION"),
            "INVALID_AUTHORIZATION",
        ),
        (
            HcuApiError("x", status_code=400, error_code="INVALID_AUTHORIZATION"),
            "HTTP 400 (INVALID_AUTHORIZATION)",
        ),
    ],
)
def test_rejection_log_text(err: BaseException, expected: str) -> None:
    """Log formatter includes the HTTP status and/or error code."""
    assert coordinator_module._format_auth_rejection(err) == expected
