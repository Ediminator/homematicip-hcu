"""Comprehensive coverage tests for custom_components.hcu_integration.api.

Covers connection lifecycle, REST methods, listeners, message dispatching,
event handling, and device/group/home control methods to achieve >=95% line coverage.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from custom_components.hcu_integration.api import (
    HcuApiClient,
    HcuApiError,
    ProcessEventsResult,
)
from custom_components.hcu_integration.const import (
    API_PATHS,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    HCU_APP_WS_PORT,
    HCU_PLUGIN_WS_PORT,
    HCU_REST_PORT,
    PLUGIN_ID,
    WEBSOCKET_HEARTBEAT_INTERVAL,
    WEBSOCKET_RECEIVE_TIMEOUT,
)


@pytest.fixture
def mock_ws():
    """Create a mock WebSocket connection."""
    ws = AsyncMock()
    ws.closed = False
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock()
    ws.close = AsyncMock()
    return ws


# ==============================================================================
# 1. Entity bridge and state initialization
# ==============================================================================


def test_set_ha_entity_bridge(api_client: HcuApiClient):
    """Test attaching and detaching the HA entity bridge."""
    mock_bridge = MagicMock()
    api_client.set_ha_entity_bridge(mock_bridge)
    assert api_client._ha_entity_bridge is mock_bridge

    api_client.set_ha_entity_bridge(None)
    assert api_client._ha_entity_bridge is None


def test_state_warning_when_empty(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test that accessing empty state logs a warning."""
    api_client._state = {}
    with caplog.at_level(logging.WARNING):
        s = api_client.state
    assert s == {}
    assert "State cache accessed before initialization." in caplog.text


# ==============================================================================
# 2. _update_hcu_device_ids candidate selection branches
# ==============================================================================


def test_update_hcu_device_ids_model_fallback(api_client: HcuApiClient):
    """Test fallback to HmIP-HCU modelType when device type is not in HCU_DEVICE_TYPES."""
    api_client._state = {
        "home": {},
        "devices": {
            "dev_custom": {
                "type": "UNKNOWN_CUSTOM_TYPE",
                "modelType": "HmIP-HCU-Pro",
                "id": "dev_custom",
            }
        },
    }
    api_client._update_hcu_device_ids()
    assert api_client.hcu_device_id == "dev_custom"
    assert "dev_custom" in api_client.hcu_part_device_ids


def test_update_hcu_device_ids_primary_hcu_model_precedence(api_client: HcuApiClient):
    """Test HmIP-HCU modelType takes precedence over non-HAP accessPointId."""
    api_client._state = {
        "home": {"accessPointId": "dev_switch"},
        "devices": {
            "dev_switch": {
                "type": "SWITCH",
                "modelType": "HmIP-PS",
                "id": "dev_switch",
            },
            "dev_hcu": {
                "type": "OTHER",
                "modelType": "HmIP-HCU-XL",
                "id": "dev_hcu",
            },
        },
    }
    api_client._update_hcu_device_ids()
    assert api_client.hcu_device_id == "dev_hcu"


def test_update_hcu_device_ids_access_point_is_hap_with_non_hap_candidate(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test accessPointId pointing to HAP/DRAP selects non-HAP candidate as primary."""
    api_client._state = {
        "home": {"accessPointId": "hap_id"},
        "devices": {
            "hap_id": {
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-HAP",
                "id": "hap_id",
            },
            "custom_ap": {
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-RF-GATEWAY",
                "id": "custom_ap",
            },
        },
    }
    with caplog.at_level(logging.WARNING):
        api_client._update_hcu_device_ids()

    assert api_client.hcu_device_id == "custom_ap"
    assert "home.accessPointId points to HAP/DRAP" in caplog.text


def test_update_hcu_device_ids_access_point_is_hap_with_only_hap_devices(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test accessPointId pointing to HAP/DRAP falls back to accessPointId if only HAP/DRAP exist."""
    api_client._state = {
        "home": {"accessPointId": "hap_id"},
        "devices": {
            "hap_id": {
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-HAP",
                "id": "hap_id",
            }
        },
    }
    with caplog.at_level(logging.WARNING):
        api_client._update_hcu_device_ids()

    assert api_client.hcu_device_id == "hap_id"
    assert "Only HAP/DRAP devices found, using accessPointId as primary" in caplog.text


def test_update_hcu_device_ids_no_access_point_with_non_hap_candidate(
    api_client: HcuApiClient,
):
    """Test no accessPointId selects non-HAP candidate as primary."""
    api_client._state = {
        "home": {},
        "devices": {
            "drap_id": {
                "type": "WIRED_ACCESS_POINT",
                "modelType": "HmIPW-DRAP",
                "id": "drap_id",
            },
            "custom_ap": {
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-RF-GATEWAY",
                "id": "custom_ap",
            },
        },
    }
    api_client._update_hcu_device_ids()
    assert api_client.hcu_device_id == "custom_ap"


def test_update_hcu_device_ids_no_access_point_only_hap_devices(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test no accessPointId with only HAP/DRAP devices falls back to first sorted device."""
    api_client._state = {
        "home": {},
        "devices": {
            "drap_2": {
                "type": "WIRED_ACCESS_POINT",
                "modelType": "HmIP-DRAP",
                "id": "drap_2",
            },
            "hap_1": {
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-HAP",
                "id": "hap_1",
            },
        },
    }
    with caplog.at_level(logging.WARNING):
        api_client._update_hcu_device_ids()

    assert api_client.hcu_device_id == "drap_2"
    assert (
        "Only HAP/DRAP devices found, using first available device as primary"
        in caplog.text
    )


def test_update_hcu_device_ids_no_aps_at_all(api_client: HcuApiClient):
    """Test no access points at all results in hcu_device_id=None."""
    api_client._state = {
        "home": {},
        "devices": {
            "plug": {
                "type": "HMIP-PSM",
                "modelType": "HMIP-PSM",
                "id": "plug",
            }
        },
    }
    api_client._update_hcu_device_ids()
    assert api_client.hcu_device_id is None
    assert api_client.hcu_part_device_ids == set()


# ==============================================================================
# 3. Connection & WebSocket lifecycle
# ==============================================================================


def test_is_plugin_connected_and_has_plugin_connection(
    api_client: HcuApiClient, mock_ws: AsyncMock
):
    """Test is_plugin_connected and has_plugin_connection across all auth types."""
    # When plugin_websocket is None
    assert not api_client.is_plugin_connected

    # When plugin_websocket is active
    api_client._plugin_websocket = mock_ws
    assert api_client.is_plugin_connected

    # Closed plugin_websocket
    mock_ws.closed = True
    assert not api_client.is_plugin_connected

    # has_plugin_connection in DUAL mode
    api_client._auth_type = AUTH_TYPE_DUAL
    mock_ws.closed = False
    assert api_client.has_plugin_connection
    mock_ws.closed = True
    assert not api_client.has_plugin_connection

    # has_plugin_connection in PLUGIN mode
    api_client._auth_type = AUTH_TYPE_PLUGIN
    api_client._websocket = mock_ws
    mock_ws.closed = False
    assert api_client.has_plugin_connection

    # has_plugin_connection in default "" mode
    api_client._auth_type = ""
    assert api_client.has_plugin_connection

    # has_plugin_connection in APP mode
    api_client._auth_type = AUTH_TYPE_APP
    assert api_client.has_plugin_connection is False


async def test_connect_reconnects_if_already_connected(
    api_client: HcuApiClient, mock_ws: AsyncMock
):
    """Test connect() disconnects existing connection first."""
    api_client._websocket = mock_ws
    mock_ws.closed = False

    with (
        patch.object(api_client, "disconnect", new_callable=AsyncMock) as mock_disc,
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
    ):
        api_client._session.ws_connect = AsyncMock(return_value=mock_ws)
        await api_client.connect()
        mock_disc.assert_called_once()


async def test_connect_dual_app_token_failure_raises(api_client: HcuApiClient):
    """Test connect() in DUAL mode with app_token only attempts port 8888."""
    api_client._auth_type = AUTH_TYPE_DUAL
    api_client._app_token = "app-token"
    api_client._access_point_id = "AP123"
    api_client._session.ws_connect = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("refused")
    )

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(
            ConnectionError,
            match=f"App User WebSocket unavailable on port {HCU_APP_WS_PORT}",
        ),
    ):
        await api_client.connect()

    assert api_client._session.ws_connect.await_count == 1
    assert (
        api_client._session.ws_connect.await_args[0][0]
        == f"wss://192.168.1.100:{HCU_APP_WS_PORT}"
    )


async def test_connect_app_both_ports_fail_raises(api_client: HcuApiClient):
    """Test connect() in APP mode attempts both ports 8888 and 9001 and raises ConnectionError."""
    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "app-token"
    api_client._access_point_id = "AP123"
    api_client._session.ws_connect = AsyncMock(
        side_effect=aiohttp.ClientConnectionError("refused")
    )

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(
            ConnectionError,
            match="App User WebSocket unavailable on ports 8888 and 9001",
        ),
    ):
        await api_client.connect()

    assert api_client._session.ws_connect.await_count == 2


async def test_connect_plugin_mode(api_client: HcuApiClient, mock_ws: AsyncMock):
    """Test connect() in plugin mode sends correct headers to port 9001."""
    api_client._auth_type = AUTH_TYPE_PLUGIN
    api_client._session.ws_connect = AsyncMock(return_value=mock_ws)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        await api_client.connect()

    assert api_client._websocket is mock_ws
    api_client._session.ws_connect.assert_called_once_with(
        f"wss://192.168.1.100:{HCU_PLUGIN_WS_PORT}",
        headers={
            "authtoken": "test-token",
            "plugin-id": PLUGIN_ID,
            "hmip-system-events": "true",
        },
        ssl=None,
        heartbeat=WEBSOCKET_HEARTBEAT_INTERVAL,
        receive_timeout=WEBSOCKET_RECEIVE_TIMEOUT,
    )


async def test_connect_plugin_and_disconnect_plugin(
    api_client: HcuApiClient, mock_ws: AsyncMock
):
    """Test connect_plugin and disconnect_plugin lifecycle."""
    api_client._session.ws_connect = AsyncMock(return_value=mock_ws)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        await api_client.connect_plugin()

    assert api_client._plugin_websocket is mock_ws
    assert api_client.is_plugin_connected

    # Reconnect closes existing plugin websocket first
    new_mock_ws = AsyncMock()
    new_mock_ws.closed = False
    api_client._session.ws_connect = AsyncMock(return_value=new_mock_ws)

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        await api_client.connect_plugin()

    mock_ws.close.assert_called_once()
    assert api_client._plugin_websocket is new_mock_ws

    # Explicit disconnect_plugin
    await api_client.disconnect_plugin()
    new_mock_ws.close.assert_called_once()
    assert api_client._plugin_websocket is None


async def test_disconnect_closes_both_websockets(
    api_client: HcuApiClient, mock_ws: AsyncMock
):
    """Test disconnect() closes primary and plugin WebSockets."""
    plugin_ws = AsyncMock()
    plugin_ws.closed = False
    api_client._websocket = mock_ws
    api_client._plugin_websocket = plugin_ws

    await api_client.disconnect()

    mock_ws.close.assert_called_once()
    plugin_ws.close.assert_called_once()
    assert api_client._websocket is None
    assert api_client._plugin_websocket is None


# ==============================================================================
# 4. REST Calls
# ==============================================================================


async def test_async_get_current_state_rest_success(api_client: HcuApiClient):
    """Test _async_get_current_state_rest parses body and updates state."""
    api_client._app_token = "app-token"
    api_client._access_point_id = "3014F711A0000000000000AA"
    api_client._client_auth = "CLIENTAUTH123"

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json = AsyncMock(
        return_value={
            "body": {
                "devices": {"dev1": {"type": "HMIP-PSM"}},
                "groups": {"grp1": {"id": "grp1"}},
            }
        }
    )

    class _Context:
        async def __aenter__(self):
            return mock_resp

        async def __aexit__(self, *args):
            return False

    api_client._session.post = MagicMock(return_value=_Context())

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        state = await api_client._async_get_current_state_rest()

    assert "dev1" in state["devices"]
    assert "grp1" in state["groups"]
    call_args = api_client._session.post.call_args
    assert (
        call_args[0][0]
        == f"https://192.168.1.100:{HCU_REST_PORT}/hmip/home/getCurrentState"
    )
    headers = call_args[1]["headers"]
    assert headers["AUTHTOKEN"] == "app-token"
    assert headers["CLIENTAUTH"] == "CLIENTAUTH123"
    assert headers["ACCESSPOINT-ID"] == "3014F711A0000000000000AA"


async def test_async_get_current_state_rest_defaults_devices_and_groups(
    api_client: HcuApiClient,
):
    """Test _async_get_current_state_rest populates default empty dicts for missing devices and groups."""
    api_client._auth_type = "app"
    api_client._app_token = "app-token"
    api_client._access_point_id = "3014F711A0000000000000AA"

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json = AsyncMock(return_value={"body": {}})

    class _Context:
        async def __aenter__(self):
            return mock_resp

        async def __aexit__(self, *args):
            return False

    api_client._session.post = MagicMock(return_value=_Context())

    with patch(
        "custom_components.hcu_integration.api.create_unverified_ssl_context",
        AsyncMock(return_value=None),
    ):
        state = await api_client._async_get_current_state_rest()

    assert "devices" in state
    assert state["devices"] == {}
    assert "groups" in state
    assert state["groups"] == {}
    assert api_client.state["groups"] == {}


async def test_async_get_current_state_rest_errors(api_client: HcuApiClient):
    """Test error handling in _async_get_current_state_rest."""
    api_client._app_token = "app-token"

    # HTTP error response
    bad_resp = MagicMock()
    bad_resp.ok = False
    bad_resp.status = 403
    bad_resp.text = AsyncMock(return_value="Forbidden")

    class _BadContext:
        async def __aenter__(self):
            return bad_resp

        async def __aexit__(self, *args):
            return False

    api_client._session.post = MagicMock(return_value=_BadContext())
    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HcuApiError, match="getCurrentState HTTP 403: Forbidden"),
    ):
        await api_client._async_get_current_state_rest()

    # Network error
    class _ErrContext:
        async def __aenter__(self):
            raise aiohttp.ClientConnectionError("conn reset")

        async def __aexit__(self, *args):
            return False

    api_client._session.post = MagicMock(return_value=_ErrContext())
    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HcuApiError, match="getCurrentState request failed"),
    ):
        await api_client._async_get_current_state_rest()

    # Non-dict JSON response
    list_resp = MagicMock()
    list_resp.ok = True
    list_resp.json = AsyncMock(return_value=["unexpected", "list"])

    class _ListContext:
        async def __aenter__(self):
            return list_resp

        async def __aexit__(self, *args):
            return False

    api_client._session.post = MagicMock(return_value=_ListContext())
    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HcuApiError, match="unexpected response type"),
    ):
        await api_client._async_get_current_state_rest()


async def test_async_app_rest_call_headers_and_error(api_client: HcuApiClient):
    """Test headers and HTTP error handling in _async_app_rest_call."""
    api_client._app_token = "app-tok"
    api_client._client_auth = "auth-hash"
    api_client._access_point_id = "ap-id"

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status = 502
    mock_resp.text = AsyncMock(return_value="Bad Gateway")

    class _Context:
        async def __aenter__(self):
            return mock_resp

        async def __aexit__(self, *args):
            return False

    api_client._session.post = MagicMock(return_value=_Context())

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HcuApiError, match="HTTP 502 for /some/path: Bad Gateway"),
    ):
        await api_client._async_app_rest_call("/some/path", {"cmd": 1})

    call_args = api_client._session.post.call_args
    headers = call_args[1]["headers"]
    assert headers["CLIENTAUTH"] == "auth-hash"
    assert headers["ACCESSPOINT-ID"] == "ap-id"


async def test_async_set_power_up_switch_state(api_client: HcuApiClient):
    """Test async_set_power_up_switch_state calls _async_app_rest_call with correct payload."""
    with patch.object(
        api_client, "_async_app_rest_call", new_callable=AsyncMock
    ) as mock_call:
        await api_client.async_set_power_up_switch_state("dev1", 1, "PERMANENT_OFF")
        mock_call.assert_called_once_with(
            "/hmip/device/configuration/setPowerUpSwitchState",
            {
                "deviceId": "dev1",
                "channelIndex": 1,
                "powerUpSwitchState": "PERMANENT_OFF",
            },
        )


async def test_async_set_temperature_offset(api_client: HcuApiClient):
    """Test async_set_temperature_offset sends the offset for the channel."""
    with patch.object(
        api_client, "_send_hmip_request", new_callable=AsyncMock
    ) as mock_call:
        await api_client.async_set_temperature_offset("dev1", 1, -1.5)
        mock_call.assert_called_once_with(
            "/hmip/device/configuration/setTemperatureOffset",
            {"deviceId": "dev1", "channelIndex": 1, "temperatureOffset": -1.5},
        )


# ==============================================================================
# 5. Listeners & Incoming Messages
# ==============================================================================


async def test_handle_incoming_message_non_dict_and_advanced_debugging(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test handling non-dict messages and advanced debugging logging."""
    with caplog.at_level(logging.WARNING):
        api_client._handle_incoming_message("invalid-string-msg")  # type: ignore[arg-type]
    assert "Received non-dict message, ignoring: str" in caplog.text

    api_client._advanced_debugging = True
    with caplog.at_level(logging.DEBUG):
        api_client._handle_incoming_message({"type": "CUSTOM_DEBUG", "id": "123"})
    assert "API ← CUSTOM_DEBUG (id=123)" in caplog.text


async def test_handle_incoming_message_system_response_invalid_body_type(
    api_client: HcuApiClient,
):
    """Test HMIP_SYSTEM_RESPONSE with non-dict body sets exception on future."""
    future = asyncio.get_running_loop().create_future()
    api_client._pending_requests["req1"] = future

    api_client._handle_incoming_message(
        {
            "type": "HMIP_SYSTEM_RESPONSE",
            "id": "req1",
            "body": "not-a-dict",
        }
    )

    assert future.done()
    with pytest.raises(HcuApiError, match="Invalid response structure: str"):
        await future


async def test_handle_incoming_message_special_event_routing(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test incoming INCLUSION_EVENT, EXCLUSION_EVENT, STATUS_REQUEST, CONTROL_REQUEST."""
    with (
        patch.object(
            api_client, "_handle_inclusion_event", new_callable=AsyncMock
        ) as mock_inc,
        patch.object(
            api_client, "_handle_status_request", new_callable=AsyncMock
        ) as mock_stat,
        patch.object(
            api_client, "_handle_control_request", new_callable=AsyncMock
        ) as mock_ctrl,
        caplog.at_level(logging.INFO),
    ):
        # INCLUSION_EVENT
        inclusion_msg = {
            "type": "INCLUSION_EVENT",
            "body": {"deviceIds": ["d1"]},
        }
        api_client._handle_incoming_message(inclusion_msg)
        await asyncio.sleep(0.01)
        mock_inc.assert_awaited_once_with(inclusion_msg)

        # EXCLUSION_EVENT
        api_client._handle_incoming_message(
            {
                "type": "EXCLUSION_EVENT",
                "body": {"deviceIds": ["d2"]},
            }
        )
        assert "EXCLUSION_EVENT for devices: ['d2']" in caplog.text

        # STATUS_REQUEST
        status_msg = {"type": "STATUS_REQUEST", "id": "msg-stat"}
        api_client._handle_incoming_message(status_msg)
        await asyncio.sleep(0.01)
        mock_stat.assert_awaited_once_with(status_msg)

        # CONTROL_REQUEST
        control_msg = {"type": "CONTROL_REQUEST", "id": "msg-ctrl"}
        api_client._handle_incoming_message(control_msg)
        await asyncio.sleep(0.01)
        mock_ctrl.assert_awaited_once_with(control_msg)


async def test_handle_incoming_message_plugin_request_missing_id(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test plugin request missing id logs a warning and does not dispatch."""
    with caplog.at_level(logging.WARNING):
        api_client._handle_incoming_message({"type": "PLUGIN_STATE_REQUEST"})
    assert (
        "Received PLUGIN_STATE_REQUEST without message ID, cannot respond"
        in caplog.text
    )


async def test_listen_plugin_lifecycle_and_filtering(api_client: HcuApiClient):
    """Test listen_plugin connection check, DualBridge filtering, JSON errors, and close."""
    # Not connected raises ConnectionAbortedError
    with pytest.raises(
        ConnectionAbortedError, match="Plugin WebSocket is not connected"
    ):
        await api_client.listen_plugin()

    # Connected
    api_client._auth_type = AUTH_TYPE_DUAL
    ws = AsyncMock()
    ws.closed = False
    api_client._plugin_websocket = ws

    msg_skipped = MagicMock()
    msg_skipped.type = aiohttp.WSMsgType.TEXT
    # DEVICE_CHANGED is not in _PLUGIN_WS_HANDLED_INCOMING_TYPES -> ignored in DUAL mode
    msg_skipped.json = MagicMock(
        return_value={"type": "DEVICE_CHANGED", "device": {"id": "d1"}}
    )

    msg_handled = MagicMock()
    msg_handled.type = aiohttp.WSMsgType.TEXT
    msg_handled.json = MagicMock(
        return_value={"type": "USER_MESSAGE_ACK_EVENT", "id": "ack1"}
    )

    msg_bad_json = MagicMock()
    msg_bad_json.type = aiohttp.WSMsgType.TEXT
    msg_bad_json.json = MagicMock(side_effect=ValueError("bad json"))

    msg_closed = MagicMock()
    msg_closed.type = aiohttp.WSMsgType.CLOSED
    msg_closed.data = "Normal closure"

    async def _msg_iter():
        yield msg_skipped
        yield msg_handled
        yield msg_bad_json
        yield msg_closed

    ws.__aiter__.side_effect = _msg_iter

    with (
        patch.object(api_client, "_handle_incoming_message") as mock_handle,
        pytest.raises(ConnectionAbortedError, match="Plugin WebSocket issue"),
    ):
        await api_client.listen_plugin()

    # Handled message was routed; skipped message was not
    mock_handle.assert_called_once_with(
        {"type": "USER_MESSAGE_ACK_EVENT", "id": "ack1"}
    )


async def test_listen_lifecycle_binary_frames_and_finally(
    api_client: HcuApiClient,
    caplog: pytest.LogCaptureFixture,
):
    """Test listen() binary decoding, json error recovery, closure, and pending request cleanup."""
    # Not connected raises ConnectionAbortedError
    with pytest.raises(ConnectionAbortedError, match="WebSocket is not connected"):
        await api_client.listen()

    ws = AsyncMock()
    ws.closed = False
    api_client._websocket = ws

    # Add a pending request that should be cancelled in finally
    future = asyncio.get_running_loop().create_future()
    api_client._pending_requests["pending1"] = future

    msg_text_good = MagicMock()
    msg_text_good.type = aiohttp.WSMsgType.TEXT
    msg_text_good.json = MagicMock(return_value={"type": "TEXT_EVENT", "id": "txt1"})

    msg_text_bad = MagicMock()
    msg_text_bad.type = aiohttp.WSMsgType.TEXT
    msg_text_bad.json = MagicMock(side_effect=ValueError("bad json"))

    msg_binary_good = MagicMock()
    msg_binary_good.type = aiohttp.WSMsgType.BINARY
    msg_binary_good.data = b'{"type": "PUSH_EVENT", "id": "bin1"}'

    msg_binary_bad = MagicMock()
    msg_binary_bad.type = aiohttp.WSMsgType.BINARY
    msg_binary_bad.data = b"not-valid-json"

    msg_closed = MagicMock()
    msg_closed.type = aiohttp.WSMsgType.ERROR
    msg_closed.data = "Error frame"

    async def _msg_iter():
        yield msg_text_good
        yield msg_text_bad
        yield msg_binary_good
        yield msg_binary_bad
        yield msg_closed

    ws.__aiter__.side_effect = _msg_iter

    with (
        patch.object(api_client, "_handle_incoming_message") as mock_handle,
        pytest.raises(ConnectionAbortedError, match="WebSocket connection issue"),
        caplog.at_level(logging.WARNING),
    ):
        await api_client.listen()

    assert mock_handle.call_count == 2
    mock_handle.assert_any_call({"type": "TEXT_EVENT", "id": "txt1"})
    mock_handle.assert_any_call({"type": "PUSH_EVENT", "id": "bin1"})
    # Verify pending requests cleanup in finally block
    assert future.done()
    assert "Failed to parse JSON from WebSocket" in caplog.text
    assert "Failed to parse binary WS message" in caplog.text
    with pytest.raises(
        ConnectionAbortedError, match="WebSocket listener stopped unexpectedly"
    ):
        await future
    assert len(api_client._pending_requests) == 0


# ==============================================================================
# 6. _send_message routing
# ==============================================================================


async def test_send_message_dual_bridge_routing(
    api_client: HcuApiClient, mock_ws: AsyncMock
):
    """Test _send_message routing to plugin WS in DualBridge mode."""
    api_client._auth_type = AUTH_TYPE_DUAL
    api_client._websocket = mock_ws

    plugin_msg = {"type": "STATUS_RESPONSE", "id": "stat1"}

    # Plugin WS not connected raises ConnectionError
    api_client._plugin_websocket = None
    with pytest.raises(ConnectionError, match="Plugin WebSocket not connected"):
        await api_client._send_message(plugin_msg)

    # Plugin WS connected sends to plugin ws
    plugin_ws = AsyncMock()
    plugin_ws.closed = False
    api_client._plugin_websocket = plugin_ws
    await api_client._send_message(plugin_msg)
    plugin_ws.send_json.assert_called_once_with(plugin_msg)
    mock_ws.send_json.assert_not_called()

    # Non-plugin message in Dual mode goes to primary ws
    general_msg = {"type": "HMIP_SYSTEM_REQUEST", "id": "gen1"}
    await api_client._send_message(general_msg)
    mock_ws.send_json.assert_called_once_with(general_msg)


async def test_send_message_not_connected_raises(api_client: HcuApiClient):
    """Test _send_message raises ConnectionError when primary WebSocket is disconnected."""
    api_client._websocket = None
    with pytest.raises(ConnectionError, match="Not connected to HCU WebSocket"):
        await api_client._send_message({"type": "SOME_MSG"})


# ==============================================================================
# 7. _send_hmip_request routes and error behaviors
# ==============================================================================


async def test_send_hmip_request_routes_to_app_rest(api_client: HcuApiClient):
    """Test _send_hmip_request delegates to _async_app_rest_call for App Users."""
    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "token"

    with patch.object(
        api_client, "_async_app_rest_call", new_callable=AsyncMock
    ) as mock_rest:
        mock_rest.return_value = {"res": 1}
        result = await api_client._send_hmip_request("/test/path", {"key": "val"})

    assert result == {"res": 1}
    mock_rest.assert_called_once_with("/test/path", {"key": "val"})


async def test_send_hmip_request_hcu_api_error_no_retry(
    api_client: HcuApiClient,
):
    """Test that HcuApiError is re-raised immediately without retrying."""
    api_client._pending_requests = {}
    with (
        patch.object(
            api_client,
            "_send_message",
            AsyncMock(side_effect=HcuApiError("HCU specific error")),
        ) as mock_send,
        pytest.raises(HcuApiError, match="HCU specific error"),
    ):
        await api_client._send_hmip_request("/test/path")

    assert mock_send.call_count == 1
    assert len(api_client._pending_requests) == 0


async def test_send_hmip_request_success_after_retry_logs_info(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test successful request after retry logs success info message."""
    api_client._pending_requests = {}
    call_count = 0

    async def mock_send(msg, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("temporary drop")

    with (
        patch.object(api_client, "_send_message", side_effect=mock_send),
        patch.object(asyncio, "wait_for", return_value={"status": "ok"}),
        patch.object(asyncio, "sleep", AsyncMock()),
        caplog.at_level(logging.INFO),
    ):
        res = await api_client._send_hmip_request("/test/retry")

    assert res == {"status": "ok"}
    assert "Request succeeded on attempt 2/3 for path /test/retry" in caplog.text


# ==============================================================================
# 8. Plugin lifecycle handlers
# ==============================================================================


async def test_announce_plugin_ready(api_client: HcuApiClient):
    """Test announce_plugin_ready sends PLUGIN_STATE_RESPONSE and sets event."""
    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client.announce_plugin_ready()

    mock_send.assert_called_once()
    msg = mock_send.call_args[0][0]
    assert msg["type"] == "PLUGIN_STATE_RESPONSE"
    assert msg["body"]["pluginReadinessStatus"] == "READY"
    assert api_client._plugin_ready_event.is_set()


async def test_handle_inclusion_event(api_client: HcuApiClient):
    """Test _handle_inclusion_event with and without bridge and known devices."""
    # Without bridge: early return
    api_client._ha_entity_bridge = None
    await api_client._handle_inclusion_event({"body": {"deviceIds": ["dev1"]}})

    # With bridge
    mock_bridge = MagicMock()
    mock_bridge.is_known_device.side_effect = lambda d: d == "dev1"
    mock_bridge.send_status_event = AsyncMock()
    mock_bridge.handle_stale_inclusion_devices = AsyncMock()
    api_client.set_ha_entity_bridge(mock_bridge)

    await api_client._handle_inclusion_event({"body": {"deviceIds": ["dev1", "dev2"]}})
    mock_bridge.send_status_event.assert_called_once_with(["dev1"])
    mock_bridge.handle_stale_inclusion_devices.assert_called_once_with(["dev1", "dev2"])


async def test_handle_status_request(api_client: HcuApiClient):
    """Test _handle_status_request builds device statuses and responds."""
    # With bridge
    mock_bridge = MagicMock()
    mock_bridge.build_status_devices.return_value = [{"deviceId": "d1", "state": "ON"}]
    api_client.set_ha_entity_bridge(mock_bridge)

    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._handle_status_request(
            {"id": "stat-1", "body": {"deviceIds": ["d1"]}}
        )

    mock_bridge.build_status_devices.assert_called_once_with(["d1"])
    sent = mock_send.call_args[0][0]
    assert sent["id"] == "stat-1"
    assert sent["type"] == "STATUS_RESPONSE"
    assert sent["body"]["devices"] == [{"deviceId": "d1", "state": "ON"}]

    # Without bridge
    api_client.set_ha_entity_bridge(None)
    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._handle_status_request({"id": "stat-2", "body": {}})
    sent = mock_send.call_args[0][0]
    assert sent["id"] == "stat-2"
    assert sent["type"] == "STATUS_RESPONSE"
    assert sent["body"]["devices"] == []


async def test_send_discover_response(api_client: HcuApiClient):
    """Test _send_discover_response with and without bridge."""
    mock_bridge = MagicMock()
    mock_bridge.build_discover_devices.return_value = [{"deviceId": "bridge-dev"}]
    api_client.set_ha_entity_bridge(mock_bridge)

    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._send_discover_response("disc-1")

    sent = mock_send.call_args[0][0]
    assert sent["id"] == "disc-1"
    assert sent["type"] == "DISCOVER_RESPONSE"
    assert sent["body"]["devices"] == [{"deviceId": "bridge-dev"}]

    api_client.set_ha_entity_bridge(None)
    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._send_discover_response("disc-2")
    sent = mock_send.call_args[0][0]
    assert sent["id"] == "disc-2"
    assert sent["type"] == "DISCOVER_RESPONSE"
    assert sent["body"]["devices"] == []


async def test_handle_control_request(api_client: HcuApiClient):
    """Test _handle_control_request delegates to bridge for HA devices and acknowledges."""
    mock_bridge = MagicMock()
    mock_bridge.is_ha_device.side_effect = lambda d: d == "ha-dev"
    mock_bridge.handle_control_request = AsyncMock()
    mock_bridge.send_status_event = AsyncMock()
    api_client.set_ha_entity_bridge(mock_bridge)

    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._handle_control_request(
            {"id": "ctrl-1", "body": {"deviceId": "ha-dev"}}
        )

    mock_bridge.handle_control_request.assert_called_once_with({"deviceId": "ha-dev"})
    mock_bridge.send_status_event.assert_called_once_with(["ha-dev"])
    sent = mock_send.call_args[0][0]
    assert sent["id"] == "ctrl-1"
    assert sent["type"] == "CONTROL_RESPONSE"
    assert sent["body"]["devices"] == [{"deviceId": "ha-dev"}]

    # Non-HA device does not call bridge
    mock_bridge.reset_mock()
    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._handle_control_request(
            {"id": "ctrl-2", "body": {"deviceId": "other-dev"}}
        )
    mock_bridge.handle_control_request.assert_not_called()
    mock_bridge.send_status_event.assert_not_called()
    sent = mock_send.call_args[0][0]
    assert sent["id"] == "ctrl-2"
    assert sent["type"] == "CONTROL_RESPONSE"
    assert sent["body"]["devices"] == [{"deviceId": "other-dev"}]


async def test_send_config_update_response(api_client: HcuApiClient):
    """Test _send_config_update_response returns status APPLIED."""
    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._send_config_update_response("cfg-upd-1")

    sent = mock_send.call_args[0][0]
    assert sent["id"] == "cfg-upd-1"
    assert sent["type"] == "CONFIG_UPDATE_RESPONSE"
    assert sent["body"] == {"status": "APPLIED"}


# ==============================================================================
# 9. get_system_state
# ==============================================================================


async def test_get_system_state_app_user(api_client: HcuApiClient):
    """Test get_system_state calls _async_get_current_state_rest for App Users."""
    api_client._auth_type = AUTH_TYPE_APP
    api_client._app_token = "token"

    with patch.object(
        api_client, "_async_get_current_state_rest", new_callable=AsyncMock
    ) as mock_rest:
        mock_rest.return_value = {"devices": {}, "groups": {}}
        res = await api_client.get_system_state()

    assert res == {"devices": {}, "groups": {}}
    mock_rest.assert_called_once()


def _system_state_response(body):
    """Fake _send_hmip_request that delivers body to the on_success hook."""

    async def fake_send(*_args, on_success=None, **_kwargs):
        on_success(body)
        return body

    return AsyncMock(side_effect=fake_send)


async def test_get_system_state_plugin_user_empty_or_invalid_responses(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test get_system_state handles empty and non-dict responses safely."""
    initial_state = {"devices": {"existing": {}}, "groups": {}}
    api_client._state = initial_state

    # Empty response
    with (
        patch.object(api_client, "_send_hmip_request", _system_state_response(None)),
        caplog.at_level(logging.ERROR),
    ):
        res = await api_client.get_system_state()
    assert res == initial_state
    assert "Received empty response from get_system_state" in caplog.text

    # Non-dict response
    with (
        patch.object(
            api_client,
            "_send_hmip_request",
            _system_state_response(["not", "a", "dict"]),
        ),
        caplog.at_level(logging.ERROR),
    ):
        res = await api_client.get_system_state()
    assert res == initial_state
    assert "Invalid system state response: expected dict" in caplog.text


async def test_send_config_template_response_payload(api_client: HcuApiClient):
    """Test full payload of config template response including group ordering and properties."""
    with patch.object(api_client, "_send_message", new_callable=AsyncMock) as mock_send:
        await api_client._send_config_template_response("msg-template-1")

    mock_send.assert_awaited_once()
    msg = mock_send.call_args[0][0]
    assert msg["id"] == "msg-template-1"
    assert msg["type"] == "CONFIG_TEMPLATE_RESPONSE"
    groups = msg["body"]["groups"]
    assert groups["info"]["order"] == 1
    assert groups["links"]["order"] == 2


async def test_get_system_state_plugin_user_missing_devices_groups_keys(
    api_client: HcuApiClient,
):
    """Test get_system_state supplies empty dicts for missing devices and groups keys."""
    raw_response = {"home": {"accessPointId": "ap1"}}
    mock_send = _system_state_response(raw_response)
    with patch.object(api_client, "_send_hmip_request", mock_send):
        state = await api_client.get_system_state()

    mock_send.assert_awaited_once_with(
        path=API_PATHS["GET_SYSTEM_STATE"],
        timeout=30,
        on_success=api_client._apply_system_state,
    )

    assert state["devices"] == {}
    assert state["groups"] == {}
    assert state["home"]["accessPointId"] == "ap1"


# ==============================================================================
# 10. process_events
# ==============================================================================


class _CustomNonDictEvent:
    """Non-dict object that provides a .get() method to pass sorting."""

    def get(self, key, default=None):
        return 0


def test_process_events_invalid_types_and_unknown_event(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test process_events with non-dict events param, non-dict event, and unknown event type."""
    # Non-dict events
    res = api_client.process_events("not-a-dict")  # type: ignore[arg-type]
    assert isinstance(res, ProcessEventsResult)
    assert len(res.all_ids) == 0

    # Non-dict event item that passes sorting via .get() and unknown event type
    events = {
        "ev1": _CustomNonDictEvent(),
        "ev2": {"pushEventType": "CUSTOM_UNKNOWN_TYPE", "index": 1},
    }
    with caplog.at_level(logging.DEBUG):
        res = api_client.process_events(events)
    assert "Skipping non-dict event" in caplog.text
    assert "Received push event type: CUSTOM_UNKNOWN_TYPE" in caplog.text


def test_process_events_device_removed_and_group_removed(
    api_client: HcuApiClient,
):
    """Test DEVICE_REMOVED and GROUP_REMOVED event processing."""
    api_client._state = {
        "devices": {
            "dev1": {"label": "Device 1"},
            "dev2": {"label": "Device 2"},
        },
        "groups": {"grp1": {"label": "Group 1"}, "grp2": {"label": "Group 2"}},
    }

    events = {
        "ev1": {"pushEventType": "DEVICE_REMOVED", "deviceId": "dev1"},
        "ev2": {"pushEventType": "DEVICE_REMOVED", "device": {"id": "dev2"}},
        "ev3": {"pushEventType": "DEVICE_REMOVED"},  # missing ID
        "ev4": {"pushEventType": "GROUP_REMOVED", "groupId": "grp1"},
        "ev5": {"pushEventType": "GROUP_REMOVED", "group": {"id": "grp2"}},
        "ev6": {"pushEventType": "GROUP_REMOVED"},  # missing ID
    }

    result = api_client.process_events(events)

    assert result.excluded == {"dev1", "dev2", "grp1", "grp2"}
    assert "dev1" not in api_client._state["devices"]
    assert "dev2" not in api_client._state["devices"]
    assert "grp1" not in api_client._state["groups"]
    assert "grp2" not in api_client._state["groups"]


def test_process_events_missing_data_or_missing_id(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test process_events when data is missing or data dict lacks 'id'."""
    events = {
        "ev1": {"pushEventType": "DEVICE_CHANGED"},  # missing "device"
        "ev2": {"pushEventType": "DEVICE_CHANGED", "device": "not-a-dict"},
        "ev3": {"pushEventType": "DEVICE_CHANGED", "device": {"label": "no-id"}},
    }

    with caplog.at_level(logging.DEBUG):
        res = api_client.process_events(events)

    assert len(res.all_ids) == 0
    assert (
        "Skipping event of type 'DEVICE_CHANGED' with missing or invalid data"
        in caplog.text
    )


def test_process_events_device_and_channel_reload_triggers(
    api_client: HcuApiClient,
):
    """Test reload_required triggers for device label, channel fields, and group fields."""
    api_client._state = {
        "devices": {
            "dev_label": {"id": "dev_label", "label": "Old Name"},
            "dev_ch": {
                "id": "dev_ch",
                "label": "Same",
                "functionalChannels": {
                    "0": {
                        "channelRole": "SWITCH",
                        "switchVisualization": "LIGHT",
                    },
                    "1": {
                        "channelRole": "SWITCH",
                        "switchVisualization": "LIGHT",
                    },
                },
            },
        },
        "groups": {
            "grp_label": {"id": "grp_label", "label": "Old Group"},
        },
    }

    events = {
        "ev1": {
            "pushEventType": "DEVICE_CHANGED",
            "device": {"id": "dev_label", "label": "New Name"},
        },
        "ev2": {
            "pushEventType": "DEVICE_CHANGED",
            "device": {
                "id": "dev_ch",
                "functionalChannels": {
                    "0": {"channelRole": "SWITCH"},
                    "1": {"channelRole": "SHADING"},
                },
            },
        },
        "ev3": {
            "pushEventType": "GROUP_CHANGED",
            "group": {"id": "grp_label", "label": "New Group"},
        },
    }

    result = api_client.process_events(events)
    assert result.reload_required == {"dev_label", "dev_ch", "grp_label"}
    assert api_client._state["devices"]["dev_label"]["label"] == "New Name"
    assert (
        api_client._state["devices"]["dev_ch"]["functionalChannels"]["1"]["channelRole"]
        == "SHADING"
    )
    # switchVisualization preserved via merging
    assert (
        api_client._state["devices"]["dev_ch"]["functionalChannels"]["1"][
            "switchVisualization"
        ]
        == "LIGHT"
    )


# ==============================================================================
# 11. Generic and Specific Control Methods
# ==============================================================================


async def test_generic_control_methods(api_client: HcuApiClient):
    """Test async_device_control, async_send_api_command, async_group_control, and async_home_control."""
    with patch.object(
        api_client, "_send_hmip_request", new_callable=AsyncMock
    ) as mock_req:
        await api_client.async_device_control("/dev/path", "dev1", 2, {"extra": "data"})
        mock_req.assert_called_with(
            "/dev/path", {"deviceId": "dev1", "channelIndex": 2, "extra": "data"}
        )

        await api_client.async_send_api_command("/api/cmd", {"param": 1})
        mock_req.assert_called_with("/api/cmd", {"param": 1})

        await api_client.async_group_control("/grp/path", "grp1", {"key": "val"})
        mock_req.assert_called_with("/grp/path", {"groupId": "grp1", "key": "val"})

        await api_client.async_home_control("/home/path", {"setting": True})
        mock_req.assert_called_with("/home/path", {"setting": True})


async def test_specific_device_control_methods(api_client: HcuApiClient):
    """Test all specific device control methods."""
    with patch.object(
        api_client, "async_device_control", new_callable=AsyncMock
    ) as mock_ctrl:
        # Watering switch
        await api_client.async_set_watering_switch_state(
            "dev1", 1, is_on=True, on_time=30.0
        )
        mock_ctrl.assert_called_with(
            API_PATHS["SET_WATERING_SWITCH_STATE_WITH_TIME"],
            "dev1",
            1,
            {"wateringActive": True, "wateringTime": 30.0},
        )

        await api_client.async_set_watering_switch_state(
            "dev1", 1, is_on=False, on_time=30.0
        )
        mock_ctrl.assert_called_with(
            API_PATHS["SET_WATERING_SWITCH_STATE"],
            "dev1",
            1,
            {"wateringActive": False},
        )

        # Dim level
        await api_client.async_set_dim_level("dev1", 1, 0.75, ramp_time=2.0)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_DIM_LEVEL_WITH_TIME"],
            "dev1",
            1,
            {"dimLevel": 0.75, "rampTime": 2.0},
        )

        await api_client.async_set_dim_level("dev1", 1, 0.5, on_time=15.0)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_DIM_LEVEL_WITH_TIME"],
            "dev1",
            1,
            {"dimLevel": 0.5, "onTime": 15.0},
        )

        await api_client.async_set_dim_level("dev1", 1, 0.3)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_DIM_LEVEL"],
            "dev1",
            1,
            {"dimLevel": 0.3},
        )

        # Color temp
        await api_client.async_set_color_temperature(
            "dev1", 1, 2700, 0.8, ramp_time=1.5
        )
        mock_ctrl.assert_called_with(
            API_PATHS["SET_COLOR_TEMP_WITH_TIME"],
            "dev1",
            1,
            {"colorTemperature": 2700, "dimLevel": 0.8, "rampTime": 1.5},
        )

        await api_client.async_set_color_temperature("dev1", 1, 4000, 1.0)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_COLOR_TEMP"],
            "dev1",
            1,
            {"colorTemperature": 4000, "dimLevel": 1.0},
        )

        # Hue saturation
        await api_client.async_set_hue_saturation(
            "dev1", 1, 120, 0.9, 0.8, ramp_time=1.0
        )
        mock_ctrl.assert_called_with(
            API_PATHS["SET_HUE_WITH_TIME"],
            "dev1",
            1,
            {"hue": 120, "saturationLevel": 0.9, "dimLevel": 0.8, "rampTime": 1.0},
        )

        await api_client.async_set_hue_saturation("dev1", 1, 240, 1.0, 0.5)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_HUE"],
            "dev1",
            1,
            {"hue": 240, "saturationLevel": 1.0, "dimLevel": 0.5},
        )

        # Shutter & primary shading
        await api_client.async_set_shutter_level("dev1", 1, 0.4)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_SHUTTER_LEVEL"],
            "dev1",
            1,
            {"shutterLevel": 0.4},
        )

        await api_client.async_set_primary_shading_level("dev1", 1, 0.6)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_PRIMARY_SHADING_LEVEL"],
            "dev1",
            1,
            {"primaryShadingLevel": 0.6},
        )

        # Stop cover, door command, door impulse, identify, toggle garage door
        await api_client.async_stop_cover("dev1", 1)
        mock_ctrl.assert_called_with(API_PATHS["STOP_COVER"], "dev1", 1)

        await api_client.async_send_door_command("dev1", 1, "OPEN")
        mock_ctrl.assert_called_with(
            API_PATHS["SEND_DOOR_COMMAND"], "dev1", 1, {"doorCommand": "OPEN"}
        )

        await api_client.async_send_door_impulse("dev1", 1)
        mock_ctrl.assert_called_with(API_PATHS["SEND_DOOR_IMPULSE"], "dev1", 1)

        await api_client.async_send_identify("dev1", 1)
        mock_ctrl.assert_called_with(API_PATHS["DEVICE_IDENTIFY"], "dev1", 1)

        await api_client.async_toggle_garage_door_state("dev1", 1)
        mock_ctrl.assert_called_with(API_PATHS["TOGGLE_GARAGE_DOOR_STATE"], "dev1", 1)

        # Lock state and latch
        await api_client.async_set_lock_state("dev1", 1, "LOCKED", pin="1234")
        mock_ctrl.assert_called_with(
            API_PATHS["SET_LOCK_STATE"],
            "dev1",
            1,
            {"targetLockState": "LOCKED", "authorizationPin": "1234"},
        )

        await api_client.async_set_lock_state("dev1", 1, "UNLOCKED", pin=None)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_LOCK_STATE"],
            "dev1",
            1,
            {"targetLockState": "UNLOCKED"},
        )

        await api_client.async_pull_latch("dev1", 1, pin="5678")
        mock_ctrl.assert_called_with(
            API_PATHS["SEND_PULL_LATCH"],
            "dev1",
            1,
            {"authorizationPin": "5678"},
        )

        await api_client.async_pull_latch("dev1", 1, pin=None)
        mock_ctrl.assert_called_with(
            API_PATHS["SEND_PULL_LATCH"],
            "dev1",
            1,
            {},
        )

        # Sound file, resets, epaper
        await api_client.async_set_sound_file("dev1", 1, "alarm.mp3", 0.9, 10.0)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_SOUND_FILE"],
            "dev1",
            1,
            {"soundFile": "alarm.mp3", "volumeLevel": 0.9, "onTime": 10.0},
        )

        await api_client.async_reset_energy_counter("dev1", 1)
        mock_ctrl.assert_called_with(API_PATHS["RESET_ENERGY_COUNTER"], "dev1", 1)

        await api_client.async_reset_water_volume("dev1", 1)
        mock_ctrl.assert_called_with(API_PATHS["RESET_WATER_VOLUME"], "dev1", 1)

        await api_client.async_set_epaper_display("dev1", 1, {"text": "hello"})
        mock_ctrl.assert_called_with(
            API_PATHS["SET_EPAPER_DISPLAY"],
            "dev1",
            1,
            {"display": {"text": "hello"}},
        )


async def test_async_set_slats_level_branches(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
):
    """Test async_set_slats_level with explicit shutterLevel, cached level, and missing levels."""
    api_client._state = {
        "devices": {
            "dev_with_level": {
                "functionalChannels": {"1": {"shutterLevel": 0.8}},
            },
            "dev_without_level": {
                "functionalChannels": {"1": {}},
            },
        }
    }

    with patch.object(
        api_client, "async_device_control", new_callable=AsyncMock
    ) as mock_ctrl:
        # Explicit shutter_level
        await api_client.async_set_slats_level("dev1", 1, 0.5, shutter_level=0.3)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_SLATS_LEVEL"],
            "dev1",
            1,
            {"slatsLevel": 0.5, "shutterLevel": 0.3},
        )

        # Implicit shutter_level from state cache
        await api_client.async_set_slats_level("dev_with_level", 1, 0.4)
        mock_ctrl.assert_called_with(
            API_PATHS["SET_SLATS_LEVEL"],
            "dev_with_level",
            1,
            {"slatsLevel": 0.4, "shutterLevel": 0.8},
        )

        # Device found but no shutterLevel in channel
        with caplog.at_level(logging.WARNING):
            await api_client.async_set_slats_level("dev_without_level", 1, 0.2)
        assert (
            "Could not determine shutterLevel for device dev_without_level channel 1"
            in caplog.text
        )

        # Device not found in state cache
        with caplog.at_level(logging.WARNING):
            await api_client.async_set_slats_level("unknown_dev", 1, 0.1)
        assert "Device unknown_dev not found in state cache" in caplog.text


async def test_specific_group_and_home_control_methods(
    api_client: HcuApiClient,
):
    """Test all specific group and home control methods."""
    with (
        patch.object(
            api_client, "async_group_control", new_callable=AsyncMock
        ) as mock_grp,
        patch.object(
            api_client, "async_home_control", new_callable=AsyncMock
        ) as mock_home,
    ):
        # Rule
        await api_client.async_enable_simple_rule("rule-1", enabled=True)
        mock_home.assert_called_with(
            API_PATHS["ENABLE_SIMPLE_RULE"], {"ruleId": "rule-1", "enabled": True}
        )

        # Group boost, mode, profile, setpoint
        await api_client.async_set_group_boost("grp1", boost=True)
        mock_grp.assert_called_with(
            API_PATHS["SET_GROUP_BOOST"], "grp1", {"boost": True}
        )

        await api_client.async_set_group_control_mode(
            "grp1", "MANUAL", extraOption=True
        )
        mock_grp.assert_called_with(
            API_PATHS["SET_GROUP_CONTROL_MODE"],
            "grp1",
            body={"controlMode": "MANUAL", "extraOption": True},
        )

        await api_client.async_set_group_active_profile("grp1", "PROFILE_2")
        mock_grp.assert_called_with(
            API_PATHS["SET_GROUP_ACTIVE_PROFILE"],
            "grp1",
            {"profileIndex": "PROFILE_2"},
        )

        await api_client.async_set_group_setpoint_temperature("grp1", 21.5)
        mock_grp.assert_called_with(
            API_PATHS["SET_GROUP_SET_POINT_TEMP"],
            "grp1",
            {"setPointTemperature": 21.5},
        )

        # Zones, safety alarm, vacation, absence, party mode
        await api_client.async_set_zones_activation({"zones": ["INTERNAL"]})
        mock_home.assert_called_with(
            API_PATHS["SET_ZONES_ACTIVATION"], {"zones": ["INTERNAL"]}
        )

        await api_client.async_acknowledge_safety_alarm()
        mock_home.assert_called_with(API_PATHS["ACKNOWLEDGE_SAFETY_ALARM"], {})

        await api_client.async_activate_vacation(17.0, "2026-12-31 23:59")
        mock_home.assert_called_with(
            API_PATHS["ACTIVATE_VACATION"],
            {
                "absenceType": "VACATION",
                "temperature": 17.0,
                "endTime": "2026-12-31 23:59",
            },
        )

        await api_client.async_deactivate_vacation()
        mock_home.assert_called_with(API_PATHS["DEACTIVATE_VACATION"])

        await api_client.async_activate_absence_permanent()
        mock_home.assert_called_with(API_PATHS["ACTIVATE_ABSENCE_PERMANENT"])

        await api_client.async_deactivate_absence()
        mock_home.assert_called_with(API_PATHS["DEACTIVATE_ABSENCE"])

        await api_client.async_activate_group_party_mode(
            "grp1", 20.0, "2026-10-31 22:00"
        )
        mock_grp.assert_called_with(
            API_PATHS["ACTIVATE_PARTY_MODE"],
            "grp1",
            {"temperature": 20.0, "endTime": "2026-10-31 22:00"},
        )

        # Switching group and alarm siren methods
        await api_client.async_set_switching_group_state("grp1", on=True)
        mock_grp.assert_called_with(
            API_PATHS["SET_SWITCHING_GROUP_STATE"], "grp1", {"on": True}
        )

        await api_client.async_set_alarm_switching_group_state("grp1", on=False)
        mock_grp.assert_called_with(
            API_PATHS["SET_SWITCHING_GROUP_STATE"], "grp1", {"on": False}
        )

        await api_client.async_test_alarm_signal_acoustic("grp1", "FREQUENCY_RISING")
        mock_grp.assert_called_with(
            API_PATHS["TEST_ALARM_SIGNAL_ACOUSTIC"],
            "grp1",
            {"signalAcoustic": "FREQUENCY_RISING"},
        )

        await api_client.async_test_alarm_signal_optical("grp1", "BLINKING_FAST")
        mock_grp.assert_called_with(
            API_PATHS["TEST_ALARM_SIGNAL_OPTICAL"],
            "grp1",
            {"signalOptical": "BLINKING_FAST"},
        )
