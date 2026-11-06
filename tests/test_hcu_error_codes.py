"""Tests for Connect API 6.10 error code parsing, DEVICE_BUSY retry, translations, and #506 SGTIN validation."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.button import HcuAcknowledgeSafetyAlarmButton
from custom_components.hcu_integration.config_flow import HcuConfigFlow
from custom_components.hcu_integration.const import (
    ATTR_BODY,
    ATTR_COOLING,
    ATTR_ENABLED,
    ATTR_END_TIME,
    ATTR_PATH,
    ATTR_RULE_ID,
    ATTR_USER_MESSAGE_BEHAVIOR_TYPE,
    ATTR_USER_MESSAGE_CATEGORY,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_MESSAGE,
    ATTR_USER_MESSAGE_TITLE,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_TYPE,
    CONF_PLUGIN_TOKEN,
    DOMAIN,
)
from custom_components.hcu_integration.services import (
    async_create_user_message_request,
    async_delete_user_message_request,
    async_handle_activate_eco_mode,
    async_handle_activate_vacation_mode,
    async_handle_deactivate_absence_mode,
    async_handle_send_api_command,
    async_handle_set_cooling_mode,
    async_handle_set_rule_state,
)
from custom_components.hcu_integration.util import (
    async_format_hcu_error,
    command_failed,
    handle_lock_api_error,
    lock_error_to_exception,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")


class _ResponseCtx:
    """Async context manager wrapping a mock aiohttp response."""

    def __init__(self, resp: MagicMock) -> None:
        self._resp = resp

    async def __aenter__(self) -> MagicMock:
        return self._resp

    async def __aexit__(self, *args: object) -> bool:
        return False


# ==============================================================================
# 1. API Error Code Parsing (Plugin WebSocket & App User REST)
# ==============================================================================


async def test_hmip_system_response_parses_error_code_and_status(
    api_client: HcuApiClient,
) -> None:
    """HMIP_SYSTEM_RESPONSE non-200 attaches error_code and status_code to HcuApiError."""
    fut1 = asyncio.get_running_loop().create_future()
    api_client._pending_requests["req-1"] = fut1

    api_client._handle_incoming_message(
        {
            "type": "HMIP_SYSTEM_RESPONSE",
            "id": "req-1",
            "body": {
                "code": 400,
                "body": {"errorCode": "DEVICE_UNREACHABLE"},
            },
        }
    )

    with pytest.raises(HcuApiError) as exc_info:
        await fut1
    assert exc_info.value.error_code == "DEVICE_UNREACHABLE"
    assert exc_info.value.status_code == 400
    assert "HCU Error:" in str(exc_info.value)

    # Missing or non-dict inner body leaves error_code as None
    fut2 = asyncio.get_running_loop().create_future()
    api_client._pending_requests["req-2"] = fut2
    api_client._handle_incoming_message(
        {
            "type": "HMIP_SYSTEM_RESPONSE",
            "id": "req-2",
            "body": {"code": 500, "body": "Internal failure"},
        }
    )
    with pytest.raises(HcuApiError) as exc_info2:
        await fut2
    assert exc_info2.value.error_code is None
    assert exc_info2.value.status_code == 500


@pytest.mark.parametrize(
    ("raw_text", "expected_code"),
    [
        ('{"errorCode": "INVALID_REQUEST"}', "INVALID_REQUEST"),
        ('{"body": {"errorCode": "FEATURE_NOT_SUPPORTED"}}', "FEATURE_NOT_SUPPORTED"),
        ('{"other": "value"}', None),
        ('["not", "a", "dict"]', None),
        ("Plain text gateway error", None),
    ],
)
async def test_app_rest_call_parses_json_error_code(
    api_client: HcuApiClient,
    raw_text: str,
    expected_code: str | None,
) -> None:
    """_async_app_rest_call extracts errorCode from JSON 4xx/5xx responses."""
    api_client._app_token = "app-tok"
    resp = MagicMock()
    resp.ok = False
    resp.status = 400
    resp.text = AsyncMock(return_value=raw_text)
    api_client._session.post = MagicMock(return_value=_ResponseCtx(resp))

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client._async_app_rest_call("/hmip/device/control/setSwitchState", {})

    assert exc_info.value.error_code == expected_code
    assert exc_info.value.status_code == 400


async def test_get_current_state_rest_parses_json_error_code(
    api_client: HcuApiClient,
) -> None:
    """_async_get_current_state_rest attaches error_code and status_code on HTTP error."""
    api_client._app_token = "app-tok"
    resp = MagicMock()
    resp.ok = False
    resp.status = 401
    resp.text = AsyncMock(return_value='{"errorCode": "INVALID_AUTHORIZATION"}')
    api_client._session.post = MagicMock(return_value=_ResponseCtx(resp))

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client._async_get_current_state_rest()

    assert exc_info.value.error_code == "INVALID_AUTHORIZATION"
    assert exc_info.value.status_code == 401


# ==============================================================================
# 2. Transient DEVICE_BUSY Single Retry (Plugin WS & App REST)
# ==============================================================================


async def test_send_hmip_request_retries_device_busy_once_with_new_id_and_hook(
    api_client: HcuApiClient,
) -> None:
    """Plugin WS retries DEVICE_BUSY once using a fresh message_id and preserves on_success."""
    sent_ids: list[str] = []
    hook_results: list[object] = []

    async def fake_send(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        sent_ids.append(msg_id)
        if len(sent_ids) == 1:
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": "DEVICE_BUSY"}},
                }
            )
        else:
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 200, "body": {"ok": True}},
                }
            )

    with (
        patch.object(api_client, "_send_message", side_effect=fake_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep", AsyncMock()
        ) as mock_sleep,
    ):
        result = await api_client._send_hmip_request(
            "/hmip/device/control/setSwitchState",
            {"on": True},
            on_success=hook_results.append,
        )

    assert result == {"ok": True}
    assert len(sent_ids) == 2
    assert sent_ids[0] != sent_ids[1]
    assert hook_results == [{"ok": True}]
    assert mock_sleep.await_count == 1
    assert api_client._pending_requests == {}
    assert api_client._response_hooks == {}


async def test_send_hmip_request_device_busy_stops_after_single_retry(
    api_client: HcuApiClient,
) -> None:
    """Plugin WS retries DEVICE_BUSY at most once (2 total attempts, not API_MAX_RETRIES)."""
    sent_ids: list[str] = []

    async def fake_send(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        sent_ids.append(msg_id)
        api_client._handle_incoming_message(
            {
                "type": "HMIP_SYSTEM_RESPONSE",
                "id": msg_id,
                "body": {"code": 400, "body": {"errorCode": "DEVICE_BUSY"}},
            }
        )

    with (
        patch.object(api_client, "_send_message", side_effect=fake_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep", AsyncMock()
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client._send_hmip_request("/hmip/device/control/setSwitchState", {})

    assert exc_info.value.error_code == "DEVICE_BUSY"
    assert len(sent_ids) == 2
    assert mock_sleep.await_count == 1


async def test_send_hmip_request_non_transient_error_does_not_retry(
    api_client: HcuApiClient,
) -> None:
    """DEVICE_UNREACHABLE raises immediately without sleeping or retrying."""
    sent_ids: list[str] = []

    async def fake_send(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        sent_ids.append(msg_id)
        api_client._handle_incoming_message(
            {
                "type": "HMIP_SYSTEM_RESPONSE",
                "id": msg_id,
                "body": {"code": 400, "body": {"errorCode": "DEVICE_UNREACHABLE"}},
            }
        )

    with (
        patch.object(api_client, "_send_message", side_effect=fake_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep", AsyncMock()
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client._send_hmip_request("/hmip/device/control/setSwitchState", {})

    assert exc_info.value.error_code == "DEVICE_UNREACHABLE"
    assert len(sent_ids) == 1
    mock_sleep.assert_not_awaited()


async def test_app_rest_call_retries_device_busy_once_and_releases_lock(
    api_client: HcuApiClient,
) -> None:
    """App REST retries DEVICE_BUSY once while releasing _command_lock during backoff."""
    api_client._app_token = "app-tok"

    busy_resp = MagicMock()
    busy_resp.ok = False
    busy_resp.status = 400
    busy_resp.text = AsyncMock(return_value='{"errorCode": "DEVICE_BUSY"}')

    ok_resp = MagicMock()
    ok_resp.ok = True
    ok_resp.status = 200
    ok_resp.content_length = 12
    ok_resp.content_type = "application/json"
    ok_resp.json = AsyncMock(return_value={"status": "done"})

    api_client._session.post = MagicMock(
        side_effect=[_ResponseCtx(busy_resp), _ResponseCtx(ok_resp)]
    )

    lock_held_during_sleep: list[bool] = []

    async def check_sleep(_delay: float) -> None:
        lock_held_during_sleep.append(api_client._command_lock.locked())

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=check_sleep,
        ),
    ):
        res = await api_client._async_app_rest_call(
            "/hmip/device/control/setSwitchState", {}
        )

    assert res == {"status": "done"}
    assert api_client._session.post.call_count == 2
    assert lock_held_during_sleep == [False]

    # Persistent DEVICE_BUSY fails after single retry
    api_client._session.post = MagicMock(
        side_effect=[_ResponseCtx(busy_resp), _ResponseCtx(busy_resp)]
    )
    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep", AsyncMock()
        ) as mock_sleep,
        pytest.raises(HcuApiError) as exc_info,
    ):
        await api_client._async_app_rest_call("/hmip/device/control/setSwitchState", {})

    assert exc_info.value.error_code == "DEVICE_BUSY"
    assert api_client._session.post.call_count == 2
    assert mock_sleep.await_count == 1


# ==============================================================================
# 3. Error Code Mapping (Entity Actions, Lock Errors, Home Services, EN & DE)
# ==============================================================================


@pytest.mark.parametrize(
    ("error_code", "expected_key", "expects_code_placeholder"),
    [
        ("DEVICE_UNREACHABLE", "hcu_error_device_unreachable", False),
        ("DEVICE_BUSY", "hcu_error_device_busy", False),
        ("INVALID_PIN", "hcu_error_invalid_pin", False),
        ("INVALID_AUTHORIZATION_PIN", "hcu_error_invalid_pin", False),
        ("CLIENT_ACCESS_DENIED", "hcu_error_access_denied", False),
        ("CLIENT_INVALID_AUTHORIZATION", "hcu_error_access_denied", False),
        ("ACCESS_POINT_REMOTE_ACCESS_DENIED", "hcu_error_access_denied", False),
        ("INVALID_AUTHORIZATION", "hcu_error_invalid_authorization", False),
        ("FEATURE_NOT_SUPPORTED", "hcu_error_feature_not_supported", False),
        ("FEATURE_NOT_ENABLED", "hcu_error_feature_not_supported", False),
        ("LIVE_OTAU_IN_PROGRESS", "hcu_error_otau_in_progress", False),
        ("DATA_TRANSFER_IN_PROGRESS", "hcu_error_system_busy", False),
        ("NOT_ALLOWED_DURING_AP_EXCHANGE", "hcu_error_system_busy", False),
        ("NOT_ALLOWED_DURING_INITIALIZATION", "hcu_error_system_busy", False),
        ("NOT_ALLOWED_DURING_ACTIVE_ALARM", "hcu_error_active_alarm", False),
        ("NOT_ALLOWED_DURING_ABSENCE_MODE", "hcu_error_absence_active", False),
        ("NOT_ALLOWED_DURING_COOLING", "hcu_error_cooling_conflict", False),
        ("COOLING_NOT_ENABLED", "hcu_error_cooling_conflict", False),
        ("COOLING_EXTERNALLY_CONTROLLED", "hcu_error_cooling_conflict", False),
        ("INVALID_REQUEST", "hcu_error_invalid_request", True),
        ("UNKNOWN_REQUEST", "hcu_error_invalid_request", True),
        ("INVALID_PARAMETER_VALUE", "hcu_error_invalid_request", True),
        ("INVALID_PARAMETER_VALUE_LENGTH", "hcu_error_invalid_request", True),
        ("INVALID_PARAMETER_SIZE", "hcu_error_invalid_request", True),
        ("INVALID_NUMBER_PARAMETER_VALUE", "hcu_error_invalid_request", True),
        ("INVALID_MULTIPLE_NUMBER_PARAMETER_VALUE", "hcu_error_invalid_request", True),
        ("UNKNOWN_DEVICE", "hcu_error_unknown_object", True),
        ("UNKNOWN_CHANNEL", "hcu_error_unknown_object", True),
        ("UNKNOWN_GROUP", "hcu_error_unknown_object", True),
        ("UNKNOWN_RULE", "hcu_error_unknown_object", True),
        ("INVALID_RULE_TYPE", "hcu_error_unknown_object", True),
    ],
)
def test_command_failed_maps_connect_api_error_codes(
    error_code: str,
    expected_key: str,
    expects_code_placeholder: bool,
) -> None:
    """command_failed translates known Connect API 6.10 error codes."""
    api_err = HcuApiError(
        f"HCU Error: {{'code': 400, 'body': {{'errorCode': '{error_code}'}}}}",
        error_code=error_code,
        status_code=400,
    )
    ha_err = command_failed("light.living_room", api_err)
    assert ha_err.translation_domain == DOMAIN
    assert ha_err.translation_key == expected_key
    expected_placeholders = {"entity": "light.living_room"}
    if expects_code_placeholder:
        expected_placeholders["code"] = error_code
    assert ha_err.translation_placeholders == expected_placeholders


def test_command_failed_unmapped_error_code_uses_clean_code() -> None:
    """Unmapped Connect API error codes fall back to command_failed with the clean code."""
    api_err = HcuApiError(
        "HCU Error: {'code': 400, 'body': {'errorCode': 'MAX_DEVICES_REACHED'}}",
        error_code="MAX_DEVICES_REACHED",
        status_code=400,
    )
    ha_err = command_failed("switch.garage", api_err)
    assert ha_err.translation_key == "command_failed"
    assert ha_err.translation_placeholders == {
        "entity": "switch.garage",
        "error": "MAX_DEVICES_REACHED",
    }


def test_lock_error_handling_does_not_treat_invalid_request_as_access_denied() -> None:
    """INVALID_REQUEST on a lock must not falsely claim missing user authorization."""
    invalid_req = HcuApiError(
        "HTTP 400: {'errorCode': 'INVALID_REQUEST'}",
        error_code="INVALID_REQUEST",
        status_code=400,
    )
    err_type = handle_lock_api_error(invalid_req, "Front Door", "1234")
    assert err_type is None
    exc = lock_error_to_exception(err_type, "lock.front_door", invalid_req)
    assert exc.translation_key == "hcu_error_invalid_request"
    assert exc.translation_placeholders == {
        "entity": "lock.front_door",
        "code": "INVALID_REQUEST",
    }

    # Structured PIN & access denied error codes still route to lock-specific keys
    pin_err = HcuApiError("HCU Error", error_code="INVALID_AUTHORIZATION_PIN")
    assert handle_lock_api_error(pin_err, "Front Door", "1234") == "invalid_pin"

    denied_err = HcuApiError(
        "HCU Error", error_code="ACCESS_POINT_REMOTE_ACCESS_DENIED"
    )
    assert handle_lock_api_error(denied_err, "Front Door", "1234") == "access_denied"

    unreachable_err = HcuApiError("HCU Error", error_code="DEVICE_UNREACHABLE")
    assert handle_lock_api_error(unreachable_err, "Front Door", "1234") is None
    assert (
        lock_error_to_exception(
            None, "lock.front_door", unreachable_err
        ).translation_key
        == "hcu_error_device_unreachable"
    )


async def test_home_services_and_button_format_hcu_errors_in_en_and_de(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Home-level services and safety-alarm button format HCU error codes in EN and DE."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)

    client = MagicMock()
    client.hcu_device_id = "3014F711A000000000000001"
    client.state = {"devices": {}, "groups": {}, "home": {}}
    coordinator = MagicMock()
    coordinator.client = client
    coordinator.config_entry = mock_config_entry
    coordinator.entities = {}
    mock_config_entry.runtime_data = coordinator

    # 1. English formatting across home-level actions
    hass.config.language = "en"
    client.async_activate_vacation = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error: {'code': 400}",
            error_code="NOT_ALLOWED_DURING_COOLING",
            status_code=400,
        )
    )
    with pytest.raises(HomeAssistantError) as vac_exc:
        await async_handle_activate_vacation_mode(
            hass,
            SimpleNamespace(
                data={"temperature": 17.0, ATTR_END_TIME: "2026-12-31 18:00"}
            ),
        )
    assert vac_exc.value.translation_key == "activate_vacation_failed"
    assert "cooling" in vac_exc.value.translation_placeholders["error"].lower()
    assert "{" not in vac_exc.value.translation_placeholders["error"]

    # 2. German formatting across remaining home-level actions & button
    hass.config.language = "de"
    de_translations = await async_get_translations(hass, "de", "exceptions", {DOMAIN})
    assert de_translations

    client.async_enable_simple_rule = AsyncMock(
        side_effect=HcuApiError("HCU Error", error_code="UNKNOWN_RULE", status_code=400)
    )
    with pytest.raises(HomeAssistantError) as rule_exc:
        await async_handle_set_rule_state(
            hass, SimpleNamespace(data={ATTR_RULE_ID: "r-1", ATTR_ENABLED: True})
        )
    assert "UNKNOWN_RULE" in rule_exc.value.translation_placeholders["error"]
    assert "nicht gefunden" in rule_exc.value.translation_placeholders["error"]

    client.async_activate_absence_permanent = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error", error_code="NOT_ALLOWED_DURING_ACTIVE_ALARM", status_code=400
        )
    )
    with pytest.raises(HomeAssistantError) as eco_exc:
        await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))
    assert "Alarm" in eco_exc.value.translation_placeholders["error"]

    client.async_deactivate_absence = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error", error_code="DATA_TRANSFER_IN_PROGRESS", status_code=400
        )
    )
    with pytest.raises(HomeAssistantError) as deact_exc:
        await async_handle_deactivate_absence_mode(hass, SimpleNamespace(data={}))
    assert "HCU" in deact_exc.value.translation_placeholders["error"]

    client.async_send_api_command = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error", error_code="UNKNOWN_REQUEST", status_code=400
        )
    )
    with pytest.raises(HomeAssistantError) as cmd_exc:
        await async_handle_send_api_command(
            hass, SimpleNamespace(data={ATTR_PATH: "/hmip/bad", ATTR_BODY: {}})
        )
    assert "UNKNOWN_REQUEST" in cmd_exc.value.translation_placeholders["error"]

    client.async_send_api_command = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error", error_code="COOLING_NOT_ENABLED", status_code=400
        )
    )
    with pytest.raises(HomeAssistantError) as cool_exc:
        await async_handle_set_cooling_mode(
            hass, SimpleNamespace(data={ATTR_COOLING: True})
        )
    assert "Kühlmodus" in cool_exc.value.translation_placeholders["error"]

    client.async_create_user_message_request = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error", error_code="FEATURE_NOT_SUPPORTED", status_code=400
        )
    )
    with pytest.raises(HomeAssistantError) as umsg_exc:
        await async_create_user_message_request(
            hass,
            SimpleNamespace(
                data={
                    ATTR_USER_MESSAGE_ID: "m1",
                    ATTR_USER_MESSAGE_TITLE: "T",
                    ATTR_USER_MESSAGE_MESSAGE: "M",
                    ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
                    ATTR_USER_MESSAGE_CATEGORY: "INFO",
                }
            ),
        )
    assert "unterstützt" in umsg_exc.value.translation_placeholders["error"]

    client.async_delete_user_message_request = AsyncMock(
        side_effect=HcuApiError("HCU Error", error_code="DEVICE_BUSY", status_code=400)
    )
    with pytest.raises(HomeAssistantError) as del_exc:
        await async_delete_user_message_request(
            hass, SimpleNamespace(data={ATTR_USER_MESSAGE_ID: "m1"})
        )
    assert "beschäftigt" in del_exc.value.translation_placeholders["error"]

    # Safety alarm acknowledge button
    button = HcuAcknowledgeSafetyAlarmButton(coordinator, client)
    button.hass = hass
    client.async_acknowledge_safety_alarm = AsyncMock(
        side_effect=HcuApiError(
            "HCU Error", error_code="DEVICE_UNREACHABLE", status_code=400
        )
    )
    with pytest.raises(HomeAssistantError) as btn_exc:
        await button.async_press()
    assert btn_exc.value.translation_key == "acknowledge_safety_alarm_failed"
    assert "erreicht" in btn_exc.value.translation_placeholders["error"]

    # Unmapped code, empty translation catalog, & plain ConnectionError fallbacks
    assert (
        await async_format_hcu_error(
            hass, HcuApiError("raw", error_code="MAX_DEVICES_REACHED")
        )
        == "MAX_DEVICES_REACHED"
    )
    with patch(
        "custom_components.hcu_integration.util.async_get_translations",
        AsyncMock(return_value={}),
    ):
        assert (
            await async_format_hcu_error(
                hass, HcuApiError("raw", error_code="DEVICE_UNREACHABLE")
            )
            == "DEVICE_UNREACHABLE"
        )
    assert await async_format_hcu_error(hass, ConnectionError("offline")) == "offline"


# ==============================================================================
# 4. Issue #506: App User SGTIN Validation & HTTP 400 INVALID_REQUEST Mapping
# ==============================================================================


async def test_app_auth_init_requires_sgtin_and_maps_invalid_request(
    hass: HomeAssistant,
) -> None:
    """Fresh App User setup rejects empty SGTIN and maps HTTP 400 INVALID_REQUEST to invalid_sgtin."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.50"}
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"use_app_user": True, "use_plugin_user": True}
    )
    assert result_auth["step_id"] == "app_auth_init"

    # 1. Submitting empty or whitespace SGTIN fails locally without network request
    with patch.object(
        HcuConfigFlow, "_async_connection_request", AsyncMock()
    ) as mock_req:
        res_empty = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"sgtin": "   "}
        )
    assert res_empty["errors"] == {"sgtin": "sgtin_required"}
    mock_req.assert_not_awaited()

    # 2. HTTP 400 INVALID_REQUEST from /hmip/auth/connectionRequest -> invalid_sgtin
    invalid_req_err = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=400,
        message="INVALID_REQUEST",
    )
    with patch.object(
        HcuConfigFlow, "_async_connection_request", side_effect=invalid_req_err
    ):
        res_bad_sgtin = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"sgtin": "3014F711A000000000000000"}
        )
    assert res_bad_sgtin["errors"] == {"sgtin": "invalid_sgtin"}


async def test_reconfigure_app_auth_init_requires_sgtin_and_maps_invalid_request(
    hass: HomeAssistant,
) -> None:
    """Reconfigure from Plugin-only to DualBridge validates empty and rejected SGTIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.50",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-plug-only",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.50"}
    )
    res_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": False},
    )
    assert res_init["step_id"] == "reconfigure_app_auth_init"

    # 1. Empty SGTIN -> sgtin_required
    with patch.object(
        HcuConfigFlow, "_async_connection_request", AsyncMock()
    ) as mock_req:
        res_empty = await hass.config_entries.flow.async_configure(
            res_init["flow_id"], user_input={"sgtin": ""}
        )
    assert res_empty["errors"] == {"sgtin": "sgtin_required"}
    mock_req.assert_not_awaited()

    # 2. HTTP 400 INVALID_REQUEST -> invalid_sgtin
    invalid_req_err = aiohttp.ClientResponseError(
        request_info=MagicMock(),
        history=(),
        status=400,
        message="INVALID_REQUEST",
    )
    with patch.object(
        HcuConfigFlow, "_async_connection_request", side_effect=invalid_req_err
    ):
        res_bad = await hass.config_entries.flow.async_configure(
            res_init["flow_id"], user_input={"sgtin": "wrong-sgtin"}
        )
    assert res_bad["errors"] == {"sgtin": "invalid_sgtin"}


async def test_connection_request_extracts_error_code_into_client_response_error(
    hass: HomeAssistant,
) -> None:
    """_async_connection_request sets ClientResponseError.message to the HCU JSON errorCode."""
    flow = HcuConfigFlow()
    flow.hass = hass

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.status = 400
    mock_resp.headers = {}
    mock_resp.history = ()
    mock_resp.request_info = MagicMock()
    mock_resp.text = AsyncMock(return_value='{"errorCode":"INVALID_REQUEST"}')

    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=_ResponseCtx(mock_resp))

    with pytest.raises(aiohttp.ClientResponseError) as exc_info:
        await flow._async_connection_request(
            session, "192.0.2.50", 6969, "cid", "auth", "bad-sgtin", None
        )
    assert exc_info.value.status == 400
    assert exc_info.value.message == "INVALID_REQUEST"


# ==============================================================================
# 5. Per-Target Ordering Across DEVICE_BUSY & Transport Retries
# ==============================================================================


async def test_app_rest_busy_retry_preserves_per_target_order_without_blocking_other_targets(
    api_client: HcuApiClient,
) -> None:
    """Same-target commands wait for an in-flight DEVICE_BUSY retry; other targets proceed."""
    api_client._app_token = "app-tok"

    sent_payloads: list[tuple[str, dict]] = []
    first_busy_sent = False
    sleep_entered = asyncio.Event()
    release_sleep = asyncio.Event()

    def make_post(_url: str, *, json: dict | None = None, **_kwargs):
        nonlocal first_busy_sent
        body = dict(json or {})
        sent_payloads.append((_url.split(":6969", 1)[-1], body))
        resp = MagicMock()
        if body.get("groupId") == "g-water" and not first_busy_sent:
            first_busy_sent = True
            resp.ok = False
            resp.status = 400
            resp.text = AsyncMock(return_value='{"errorCode": "DEVICE_BUSY"}')
        else:
            resp.ok = True
            resp.status = 200
            resp.content_length = 12
            resp.content_type = "application/json"
            resp.json = AsyncMock(return_value={"ok": True})
        return _ResponseCtx(resp)

    api_client._session.post = MagicMock(side_effect=make_post)

    async def controlled_sleep(_delay: float) -> None:
        sleep_entered.set()
        await release_sleep.wait()

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_sleep,
        ),
    ):
        task_on = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/watering/setWateringSwitchState",
                {"groupId": "g-water", "wateringActive": True},
            )
        )
        await sleep_entered.wait()

        # Queue same-target OFF and independent other-target ON while task_on is in backoff
        task_off = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/watering/setWateringSwitchState",
                {"groupId": "g-water", "wateringActive": False},
            )
        )
        task_other = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/switching/setState",
                {"groupId": "g-other", "on": True},
            )
        )
        # Other target completes immediately without waiting for g-water's sleep!
        await task_other
        assert not task_off.done()

        release_sleep.set()
        await asyncio.gather(task_on, task_off)

    g_water_actions = [
        payload["wateringActive"]
        for _, payload in sent_payloads
        if payload.get("groupId") == "g-water"
    ]
    # True (BUSY) -> True (retry OK) -> False (final OK): newer OFF is never overwritten!
    assert g_water_actions == [True, True, False]
    assert api_client._target_locks == {}
    assert api_client._target_lock_counts == {}


async def test_ws_busy_retry_preserves_per_target_order_and_covers_target_keys(
    api_client: HcuApiClient,
) -> None:
    """Plugin WS retries serialize per target while allowing other targets and getSystemState."""
    sent_bodies: list[tuple[str, dict]] = []
    first_busy = True
    sleep_entered = asyncio.Event()
    release_sleep = asyncio.Event()

    async def fake_send(msg: dict, log_body: bool = True) -> None:
        nonlocal first_busy
        msg_id = msg["id"]
        path = msg["body"]["path"]
        body = dict(msg["body"]["body"])
        sent_bodies.append((path, body))
        if body.get("deviceId") == "d-1" and first_busy:
            first_busy = False
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": "DEVICE_BUSY"}},
                }
            )
        elif path.endswith("/getSystemState"):
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 200, "body": {"devices": {}, "groups": {}}},
                }
            )
        else:
            api_client._handle_incoming_message(
                {"type": "HMIP_SYSTEM_RESPONSE", "id": msg_id, "body": {"code": 200}}
            )

    async def controlled_sleep(_delay: float) -> None:
        sleep_entered.set()
        await release_sleep.wait()

    with (
        patch.object(api_client, "_send_message", side_effect=fake_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_sleep,
        ),
    ):
        t_on = asyncio.create_task(
            api_client._send_hmip_request(
                "/hmip/device/control/setSwitchState",
                {"deviceId": "d-1", "channelIndex": 1, "on": True},
            )
        )
        await sleep_entered.wait()

        t_off = asyncio.create_task(
            api_client._send_hmip_request(
                "/hmip/device/control/setSwitchState",
                {"deviceId": "d-1", "channelIndex": 1, "on": False},
            )
        )
        t_other = asyncio.create_task(
            api_client._send_hmip_request(
                "/hmip/device/control/setSwitchState",
                {"deviceId": "d-2", "channelIndex": 1, "on": True},
            )
        )
        t_state = asyncio.create_task(api_client.get_system_state())

        # Both d-2 and getSystemState finish while d-1 is sleeping
        await asyncio.gather(t_other, t_state)
        assert not t_off.done()

        release_sleep.set()
        await asyncio.gather(t_on, t_off)

    d1_actions = [
        body["on"] for _, body in sent_bodies if body.get("deviceId") == "d-1"
    ]
    assert d1_actions == [True, True, False]
    assert api_client._target_locks == {}
    assert api_client._target_lock_counts == {}

    # Verify target key classification across remaining Connect API target shapes
    assert api_client._command_target_key(
        "/hmip/device/deleteDevice", {"deviceId": "d-only"}
    ) == ("device", "d-only")
    assert api_client._command_target_key(
        "/hmip/rule/enableSimpleRule", {"ruleId": "r-1"}
    ) == api_client._command_target_key(
        "/hmip/rule/disableSimpleRule", {"ruleId": "r-1"}
    )
    assert api_client._command_target_key(
        "/hmip/home/heating/activateAbsencePermanent", {}
    ) == api_client._command_target_key("/hmip/home/heating/deactivateAbsence", {})
    assert api_client._command_target_key(
        "/hmip/plugin/createUserMessage", {"userMessageId": "m-1"}
    ) == ("path", "/hmip/plugin/createUserMessage")
