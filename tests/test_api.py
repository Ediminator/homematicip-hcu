"""Tests for the HCU API client."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant.core import HomeAssistant

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError


@pytest.fixture
def mock_websocket():
    """Create a mock WebSocket connection."""
    mock_ws = AsyncMock()
    mock_ws.closed = False
    mock_ws.send_json = AsyncMock()
    mock_ws.receive_json = AsyncMock()
    mock_ws.close = AsyncMock()
    return mock_ws


@pytest.fixture
def api_client(hass: HomeAssistant):
    """Create an API client instance."""
    session = MagicMock(spec=aiohttp.ClientSession)
    client = HcuApiClient(
        hass=hass,
        host="192.168.1.100",
        auth_token="test-token",
        session=session,
        auth_port=6969,
        websocket_port=9001,
    )
    return client


def test_api_client_initialization(api_client: HcuApiClient):
    """Test API client initialization."""
    assert api_client._host == "192.168.1.100"
    assert api_client._auth_token == "test-token"
    assert api_client._auth_port == 6969
    assert api_client._websocket_port == 9001
    assert api_client.state == {}
    assert not api_client.is_connected


def test_api_client_state_property(api_client: HcuApiClient):
    """Test the state property."""
    test_state = {"devices": {}, "groups": {}}
    api_client._state = test_state
    assert api_client.state == test_state


def test_get_device_by_address(api_client: HcuApiClient):
    """Test getting device by address."""
    test_device = {"id": "device1", "label": "Test Device"}
    api_client._state = {"devices": {"device1": test_device}}

    result = api_client.get_device_by_address("device1")
    assert result == test_device

    result = api_client.get_device_by_address("nonexistent")
    assert result is None


def test_get_group_by_id(api_client: HcuApiClient):
    """Test getting group by ID."""
    test_group = {"id": "group1", "label": "Test Group"}
    api_client._state = {"groups": {"group1": test_group}}

    result = api_client.get_group_by_id("group1")
    assert result == test_group

    result = api_client.get_group_by_id("nonexistent")
    assert result is None


def test_process_events_device_changed(api_client: HcuApiClient):
    """Test processing DEVICE_CHANGED events."""
    device_data = {
        "id": "device1",
        "label": "Updated Device",
        "functionalChannels": {},
    }
    events = {
        "event1": {
            "pushEventType": "DEVICE_CHANGED",
            "device": device_data,
        }
    }

    api_client._state = {"devices": {}}
    result = api_client.process_events(events)

    assert "device1" in result.updated
    assert api_client._state["devices"]["device1"] == device_data


def test_process_events_group_changed(api_client: HcuApiClient):
    """Test processing GROUP_CHANGED events."""
    group_data = {
        "id": "group1",
        "label": "Updated Group",
    }
    events = {
        "event1": {
            "pushEventType": "GROUP_CHANGED",
            "group": group_data,
        }
    }

    api_client._state = {"groups": {}}
    result = api_client.process_events(events)

    assert "group1" in result.updated
    assert api_client._state["groups"]["group1"] == group_data


def test_process_events_home_changed(api_client: HcuApiClient):
    """Test processing HOME_CHANGED events."""
    home_data = {
        "id": "home123",
        "weather": {"temperature": 20.5},
        "functionalHomes": {},
    }
    events = {
        "event1": {
            "pushEventType": "HOME_CHANGED",
            "home": home_data,
        }
    }

    api_client._state = {}
    result = api_client.process_events(events)

    assert "home123" in result.updated
    assert api_client._state["home"] == home_data


def test_process_events_partial_device_update(api_client: HcuApiClient):
    """Test processing partial device updates with channel merging."""
    # Set up initial device state with existing channels
    initial_device = {
        "id": "device1",
        "label": "Test Device",
        "functionalChannels": {
            "0": {"unreach": False, "lowBat": False},
            "1": {"on": False, "currentLevel": 0.0},
        }
    }
    api_client._state = {"devices": {"device1": initial_device}}

    # Simulate partial update that only modifies channel 1
    partial_update = {
        "id": "device1",
        "functionalChannels": {
            "1": {"on": True, "currentLevel": 0.5},
        }
    }
    events = {
        "event1": {
            "pushEventType": "DEVICE_CHANGED",
            "device": partial_update,
        }
    }

    result = api_client.process_events(events)

    assert "device1" in result.updated
    # Channel 0 should remain unchanged
    assert api_client._state["devices"]["device1"]["functionalChannels"]["0"]["unreach"] is False
    assert api_client._state["devices"]["device1"]["functionalChannels"]["0"]["lowBat"] is False
    # Channel 1 should be updated with merged values
    assert api_client._state["devices"]["device1"]["functionalChannels"]["1"]["on"] is True
    assert api_client._state["devices"]["device1"]["functionalChannels"]["1"]["currentLevel"] == 0.5


async def test_retry_logic_connection_error_then_success(api_client: HcuApiClient):
    """Test retry logic succeeds after ConnectionError on first attempt."""
    api_client._pending_requests = {}

    # First attempt raises ConnectionError, second attempt succeeds
    call_count = 0

    async def mock_send(msg):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Connection failed")

    api_client._send_message = AsyncMock(side_effect=mock_send)

    # Second attempt succeeds
    with patch.object(asyncio, "wait_for") as mock_wait:
        mock_wait.return_value = {"result": "success"}

        result = await api_client._send_hmip_request("/test/path", timeout=1)

        assert result == {"result": "success"}
        assert call_count == 2  # Failed once, succeeded on retry


async def test_retry_logic_timeout_then_success(api_client: HcuApiClient):
    """Test retry logic succeeds after TimeoutError on first attempt."""
    api_client._pending_requests = {}
    api_client._send_message = AsyncMock()

    # First attempt times out, second attempt succeeds
    with patch.object(asyncio, "wait_for") as mock_wait:
        mock_wait.side_effect = [
            asyncio.TimeoutError(),
            {"result": "success"},
        ]

        result = await api_client._send_hmip_request("/test/path", timeout=1)

        assert result == {"result": "success"}
        assert mock_wait.call_count == 2  # Failed once, succeeded on retry
        assert api_client._send_message.call_count == 2


async def test_retry_logic_exhaustion_raises_error(api_client: HcuApiClient):
    """Test that HcuApiError is raised after exhausting max retries."""
    api_client._pending_requests = {}

    # All attempts fail with ConnectionError
    async def mock_send(msg):
        raise ConnectionError("Connection failed")

    api_client._send_message = AsyncMock(side_effect=mock_send)

    # Should raise HcuApiError after 3 failed attempts
    with pytest.raises(HcuApiError) as exc_info:
        await api_client._send_hmip_request("/test/path", timeout=1)

    assert "Connection failed" in str(exc_info.value)
    assert api_client._send_message.call_count == 3


def _make_client(hass: HomeAssistant) -> HcuApiClient:
    """Build an HcuApiClient with the real constructor, bypassing the api_client fixture."""
    session = MagicMock(spec=aiohttp.ClientSession)
    return HcuApiClient(hass=hass, host="192.168.1.100", auth_token="test-token", session=session)


async def test_async_app_rest_call_uses_shared_session(hass: HomeAssistant):
    """_async_app_rest_call must use the shared HA session, not a session of its own
    (Home Assistant integrations must not create their own ClientSession)."""
    client = _make_client(hass)

    fake_response = MagicMock()
    fake_response.ok = True
    fake_response.content_length = 0
    fake_response.content_type = "application/json"

    class _FakeRequestContext:
        async def __aenter__(self):
            return fake_response

        async def __aexit__(self, *args):
            return False

    client._session.post = MagicMock(return_value=_FakeRequestContext())

    await client._async_app_rest_call("/test/path", {"a": 1})

    client._session.post.assert_called_once()


async def test_async_app_rest_call_parses_chunked_json_body(hass: HomeAssistant):
    """A chunked response (no Content-Length header, content_length is None) with a
    real JSON body must be parsed, not treated as empty. Only an actually empty body
    (content_length == 0) should short-circuit to {}."""
    client = _make_client(hass)

    fake_response = MagicMock()
    fake_response.ok = True
    fake_response.content_length = None  # Transfer-Encoding: chunked
    fake_response.content_type = "application/json"
    fake_response.json = AsyncMock(return_value={"result": "ok"})

    class _FakeRequestContext:
        async def __aenter__(self):
            return fake_response

        async def __aexit__(self, *args):
            return False

    client._session.post = MagicMock(return_value=_FakeRequestContext())

    result = await client._async_app_rest_call("/test/path", {"a": 1})

    assert result == {"result": "ok"}
    fake_response.json.assert_called_once()


async def test_async_app_rest_call_serializes_concurrent_commands(hass: HomeAssistant):
    """Concurrent App User commands must be serialized via _command_lock instead of
    being sent in parallel, to avoid RF collisions when multiple devices/groups are
    commanded at the same time (e.g. by an HA group helper). See #411/#414."""
    client = _make_client(hass)

    in_flight = 0
    max_concurrent = 0

    fake_response = MagicMock()
    fake_response.ok = True
    fake_response.content_length = 0
    fake_response.content_type = "application/json"

    class _FakeRequestContext:
        async def __aenter__(self):
            nonlocal in_flight, max_concurrent
            in_flight += 1
            max_concurrent = max(max_concurrent, in_flight)
            await asyncio.sleep(0.01)
            return fake_response

        async def __aexit__(self, *args):
            nonlocal in_flight
            in_flight -= 1
            return False

    client._session.post = MagicMock(return_value=_FakeRequestContext())

    await asyncio.gather(
        client._async_app_rest_call("/first", {"a": 1}),
        client._async_app_rest_call("/second", {"b": 2}),
        client._async_app_rest_call("/third", {"c": 3}),
    )

    assert max_concurrent == 1


async def test_async_app_rest_call_times_out_instead_of_hanging(hass: HomeAssistant, monkeypatch):
    """A stalled REST response must not hold _command_lock indefinitely; it should
    raise HcuApiError once API_REQUEST_TIMEOUT elapses, freeing the lock for the
    next queued command."""
    from custom_components.hcu_integration import api as api_module

    monkeypatch.setattr(api_module, "API_REQUEST_TIMEOUT", 0.05)
    client = _make_client(hass)

    class _HangingRequestContext:
        async def __aenter__(self):
            await asyncio.sleep(10)
            raise AssertionError("should have timed out before completing")

        async def __aexit__(self, *args):
            return False

    client._session.post = MagicMock(return_value=_HangingRequestContext())

    with pytest.raises(HcuApiError):
        await client._async_app_rest_call("/slow/path", {"a": 1})

    assert not client._command_lock.locked()


def test_hcu_device_id_property(api_client: HcuApiClient):
    """Test HCU device ID property."""
    api_client._state = {
        "home": {
            "accessPointId": "device1",
        },
        "devices": {
            "device1": {"type": "HOME_CONTROL_ACCESS_POINT", "id": "device1"},
            "device2": {"type": "HMIP-PSM", "id": "device2"},
        }
    }
    api_client._update_hcu_device_ids()

    assert api_client.hcu_device_id == "device1"


def test_hcu_part_device_ids_property(api_client: HcuApiClient):
    """Test HCU part device IDs property."""
    api_client._state = {
        "home": {
            "accessPointId": "device1",
        },
        "devices": {
            "device1": {"type": "HOME_CONTROL_ACCESS_POINT", "id": "device1"},
            "device2": {"type": "WIRED_ACCESS_POINT", "id": "device2"},
            "device3": {"type": "HMIP-PSM", "id": "device3"},
        }
    }
    api_client._update_hcu_device_ids()

    assert api_client.hcu_part_device_ids == {"device1", "device2"}


def test_event_callback_registration(api_client: HcuApiClient):
    """Test event callback registration."""
    callback_called = False

    def test_callback(event):
        nonlocal callback_called
        callback_called = True

    api_client.register_event_callback(test_callback)

    # Simulate receiving an event
    api_client._handle_incoming_message({"type": "HMIP_SYSTEM_EVENT", "body": {}})

    assert callback_called


async def test_handle_incoming_message_system_response_success(api_client: HcuApiClient):
    """Test _handle_incoming_message resolves future on successful HMIP_SYSTEM_RESPONSE."""
    message_id = "test-message-id-123"
    expected_body = {"devices": {}, "groups": {}}

    # Create a pending request
    future = asyncio.get_running_loop().create_future()
    api_client._pending_requests[message_id] = future

    # Simulate successful response from HCU
    success_message = {
        "type": "HMIP_SYSTEM_RESPONSE",
        "id": message_id,
        "body": {
            "code": 200,
            "body": expected_body,
        },
    }

    api_client._handle_incoming_message(success_message)

    # Verify the future was resolved with the body
    assert future.done()
    assert not future.cancelled()
    result = await future
    assert result == expected_body
    assert message_id not in api_client._pending_requests


async def test_handle_incoming_message_system_response_error(api_client: HcuApiClient):
    """Test _handle_incoming_message rejects future on error HMIP_SYSTEM_RESPONSE."""
    message_id = "test-message-id-456"

    # Create a pending request
    future = asyncio.get_running_loop().create_future()
    api_client._pending_requests[message_id] = future

    # Simulate error response from HCU
    error_message = {
        "type": "HMIP_SYSTEM_RESPONSE",
        "id": message_id,
        "body": {
            "code": 500,
            "errorCode": "INTERNAL_ERROR",
            "message": "Something went wrong",
        },
    }

    api_client._handle_incoming_message(error_message)

    # Verify the future was rejected with HcuApiError
    assert future.done()
    assert not future.cancelled()
    with pytest.raises(HcuApiError) as exc_info:
        await future
    assert "HCU Error:" in str(exc_info.value)
    assert message_id not in api_client._pending_requests


async def test_handle_incoming_message_plugin_state_request(api_client: HcuApiClient):
    """Test _handle_incoming_message triggers _send_plugin_ready for PLUGIN_STATE_REQUEST."""
    message_id = "plugin-state-123"

    with patch.object(api_client, "_send_plugin_ready", new_callable=AsyncMock) as mock_handler:
        api_client._handle_incoming_message({
            "type": "PLUGIN_STATE_REQUEST",
            "id": message_id,
        })

        # Give the async task time to be created and executed
        await asyncio.sleep(0.01)

        mock_handler.assert_called_once_with(message_id)


async def test_handle_incoming_message_discover_request(api_client: HcuApiClient):
    """Test _handle_incoming_message triggers _send_discover_response for DISCOVER_REQUEST."""
    message_id = "discover-456"

    with patch.object(api_client, "_send_discover_response", new_callable=AsyncMock) as mock_handler:
        api_client._handle_incoming_message({
            "type": "DISCOVER_REQUEST",
            "id": message_id,
        })

        # Give the async task time to be created and executed
        await asyncio.sleep(0.01)

        mock_handler.assert_called_once_with(message_id)


async def test_handle_incoming_message_config_template_request(api_client: HcuApiClient):
    """Test _handle_incoming_message triggers _send_config_template_response for CONFIG_TEMPLATE_REQUEST."""
    message_id = "config-template-789"

    with patch.object(api_client, "_send_config_template_response", new_callable=AsyncMock) as mock_handler:
        api_client._handle_incoming_message({
            "type": "CONFIG_TEMPLATE_REQUEST",
            "id": message_id,
        })

        # Give the async task time to be created and executed
        await asyncio.sleep(0.01)

        mock_handler.assert_called_once_with(message_id)


async def test_handle_incoming_message_config_update_request(api_client: HcuApiClient):
    """Test _handle_incoming_message triggers _send_config_update_response for CONFIG_UPDATE_REQUEST."""
    message_id = "config-update-012"

    with patch.object(api_client, "_send_config_update_response", new_callable=AsyncMock) as mock_handler:
        api_client._handle_incoming_message({
            "type": "CONFIG_UPDATE_REQUEST",
            "id": message_id,
        })

        # Give the async task time to be created and executed
        await asyncio.sleep(0.01)

        mock_handler.assert_called_once_with(message_id)


@pytest.mark.parametrize(
    "is_on,on_time,expected_path_key,expected_extra_body",
    [
        (True, None, "SET_SWITCH_STATE", {}),
        (True, 10.0, "SET_SWITCH_STATE_WITH_TIME", {"onTime": 10.0}),
        (False, None, "SET_SWITCH_STATE", {}),
        (False, 10.0, "SET_SWITCH_STATE", {}),
    ],
)
async def test_async_set_switch_state(
    api_client: HcuApiClient,
    is_on: bool,
    on_time: float | None,
    expected_path_key: str,
    expected_extra_body: dict,
):
    """Test async_set_switch_state selects correct API path."""
    from custom_components.hcu_integration.const import API_PATHS

    device_id = "device1"
    channel_index = 1

    # Mock async_device_control
    with patch.object(api_client, "async_device_control", new_callable=AsyncMock) as mock_control:
        await api_client.async_set_switch_state(
            device_id, channel_index, is_on, on_time=on_time
        )

        expected_body = {"on": is_on, **expected_extra_body}

        mock_control.assert_called_with(
            API_PATHS[expected_path_key],
            device_id,
            channel_index,
            expected_body
        )


async def test_async_create_user_message_request_uses_plain_plugin_id(hass: HomeAssistant):
    """User messages must use the plain PLUGIN_ID, not a per-entry unique variant."""
    from custom_components.hcu_integration.const import PLUGIN_ID

    session = MagicMock(spec=aiohttp.ClientSession)
    client = HcuApiClient(
        hass=hass,
        host="192.168.1.100",
        auth_token="test-token",
        session=session,
        plugin_id=f"{PLUGIN_ID}-ab12cd",
    )

    body = {"title": {"en": "Hi"}, "message": {"en": "Hello"}}
    with patch.object(client, "_send_message", new_callable=AsyncMock) as mock_send:
        await client.async_create_user_message_request(body=body)

    mock_send.assert_called_once()
    sent_message = mock_send.call_args[0][0]
    assert sent_message["pluginId"] == PLUGIN_ID
    assert sent_message["type"] == "CREATE_USER_MESSAGE_REQUEST"
    assert sent_message["body"] == body


async def test_async_delete_user_message_request_uses_plain_plugin_id(hass: HomeAssistant):
    """Deleting a user message must also use the plain PLUGIN_ID."""
    from custom_components.hcu_integration.const import PLUGIN_ID

    session = MagicMock(spec=aiohttp.ClientSession)
    client = HcuApiClient(
        hass=hass,
        host="192.168.1.100",
        auth_token="test-token",
        session=session,
        plugin_id=f"{PLUGIN_ID}-ab12cd",
    )

    with patch.object(client, "_send_message", new_callable=AsyncMock) as mock_send:
        await client.async_delete_user_message_request(user_message_id="msg-1")

    mock_send.assert_called_once()
    sent_message = mock_send.call_args[0][0]
    assert sent_message["pluginId"] == PLUGIN_ID
    assert sent_message["type"] == "DELETE_USER_MESSAGE_REQUEST"
    assert sent_message["body"] == {"userMessageId": "msg-1"}
