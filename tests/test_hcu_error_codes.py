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
# 5. Per-Target Superseding Across DEVICE_BUSY & Transport Retries
# ==============================================================================


async def test_app_rest_busy_retry_skips_stale_retry_when_superseded(
    api_client: HcuApiClient,
) -> None:
    """Newer command on the same target runs immediately and cancels an older DEVICE_BUSY retry."""
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

        # Newer OFF on same target AND ON on another target both finish immediately during backoff!
        await asyncio.gather(
            api_client._async_app_rest_call(
                "/hmip/group/watering/setWateringSwitchState",
                {"groupId": "g-water", "wateringActive": False},
            ),
            api_client._async_app_rest_call(
                "/hmip/group/switching/setState",
                {"groupId": "g-other", "on": True},
            ),
        )

        release_sleep.set()
        with pytest.raises(HcuApiError) as exc_info:
            await task_on
        assert exc_info.value.error_code == "DEVICE_BUSY"

    g_water_actions = [
        payload["wateringActive"]
        for _, payload in sent_payloads
        if payload.get("groupId") == "g-water"
    ]
    # Stale retry of wateringActive=True was skipped; watering stays OFF!
    assert g_water_actions == [True, False]
    assert api_client._target_generations == {}
    assert api_client._target_active_counts == {}


async def test_ws_busy_and_timeout_retries_do_not_block_cover_stop_or_undo_newer_commands(
    api_client: HcuApiClient,
) -> None:
    """Cover stop runs immediately without waiting on an in-flight move, and stale retries abort."""
    # Part 1: DEVICE_BUSY sleep on d-1 is superseded by an immediate OFF command
    sent_bodies: list[tuple[str, dict]] = []
    first_busy = True
    sleep_entered = asyncio.Event()
    release_sleep = asyncio.Event()

    async def fake_send_busy(msg: dict, log_body: bool = True) -> None:
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
        patch.object(api_client, "_send_message", side_effect=fake_send_busy),
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

        # Newer OFF on d-1, ON on d-2, and getSystemState all finish immediately
        await asyncio.gather(
            api_client._send_hmip_request(
                "/hmip/device/control/setSwitchState",
                {"deviceId": "d-1", "channelIndex": 1, "on": False},
            ),
            api_client._send_hmip_request(
                "/hmip/device/control/setSwitchState",
                {"deviceId": "d-2", "channelIndex": 1, "on": True},
            ),
            api_client.get_system_state(),
        )

        release_sleep.set()
        with pytest.raises(HcuApiError) as busy_exc:
            await t_on
        assert busy_exc.value.error_code == "DEVICE_BUSY"

    assert [b["on"] for _, b in sent_bodies if b.get("deviceId") == "d-1"] == [
        True,
        False,
    ]

    # Part 2: Cover move reply is lost; async_stop_cover runs immediately without waiting 33s,
    # and the timed-out move aborts without sleeping or retrying!
    cover_events: list[str] = []
    move_sent = asyncio.Event()

    async def fake_send_cover(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        path = msg["body"]["path"]
        cover_events.append(path)
        if path.endswith("/setShutterLevel"):
            move_sent.set()
            # Simulate lost HCU reply: do not resolve pending future!
        else:
            api_client._handle_incoming_message(
                {"type": "HMIP_SYSTEM_RESPONSE", "id": msg_id, "body": {"code": 200}}
            )

    mock_sleep = AsyncMock()
    with (
        patch.object(api_client, "_send_message", side_effect=fake_send_cover),
        patch("custom_components.hcu_integration.api.asyncio.sleep", mock_sleep),
    ):
        move_task = asyncio.create_task(
            api_client._send_hmip_request(
                "/hmip/device/control/setShutterLevel",
                {"deviceId": "d-cover", "channelIndex": 1, "shutterLevel": 0.0},
                timeout=0.05,
            )
        )
        await move_sent.wait()

        # Stop command completes BEFORE move_task even finishes its first 50ms timeout!
        await api_client.async_stop_cover("d-cover", 1)
        assert not move_task.done()

        with pytest.raises(HcuApiError):
            await move_task

    assert cover_events == [
        "/hmip/device/control/setShutterLevel",
        "/hmip/device/control/stop",
    ]
    mock_sleep.assert_not_awaited()

    # Part 3: Transport retry already in backoff sleep is also cancelled if superseded mid-sleep
    timeout_sleep_entered = asyncio.Event()
    timeout_sleep_release = asyncio.Event()
    retry_paths: list[str] = []

    async def fake_send_timeout_then_ok(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        path = msg["body"]["path"]
        retry_paths.append(path)
        if path.endswith("/setShutterLevel"):
            raise ConnectionError("transient drop")
        api_client._handle_incoming_message(
            {"type": "HMIP_SYSTEM_RESPONSE", "id": msg_id, "body": {"code": 200}}
        )

    async def controlled_timeout_sleep(_delay: float) -> None:
        timeout_sleep_entered.set()
        await timeout_sleep_release.wait()

    with (
        patch.object(
            api_client, "_send_message", side_effect=fake_send_timeout_then_ok
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_timeout_sleep,
        ),
    ):
        t_move2 = asyncio.create_task(
            api_client._send_hmip_request(
                "/hmip/device/control/setShutterLevel",
                {"deviceId": "d-cover2", "channelIndex": 1, "shutterLevel": 1.0},
            )
        )
        await timeout_sleep_entered.wait()
        await api_client.async_stop_cover("d-cover2", 1)
        timeout_sleep_release.set()
        with pytest.raises(HcuApiError):
            await t_move2

    assert retry_paths == [
        "/hmip/device/control/setShutterLevel",
        "/hmip/device/control/stop",
    ]
    assert api_client._target_generations == {}
    assert api_client._target_active_counts == {}

    # Verify target key classification across remaining Connect API target shapes
    assert api_client._command_target_key("/hmip/home/getSystemState", {}) is None
    assert api_client._command_target_key(
        "/hmip/device/deleteDevice", {"deviceId": "d-only"}
    ) == ("device", "d-only", "deleteDevice")
    assert api_client._command_target_key(
        "/hmip/rule/enableSimpleRule", {"ruleId": "r-1"}
    ) == api_client._command_target_key(
        "/hmip/rule/disableSimpleRule", {"ruleId": "r-1"}
    )
    assert api_client._command_target_key(
        "/hmip/home/heating/activateAbsencePermanent", {}
    ) == api_client._command_target_key("/hmip/home/heating/deactivateAbsence", {})
    assert api_client._command_target_key(
        "/hmip/home/heating/activateAbsencePermanent", {}
    ) != api_client._command_target_key(
        "/hmip/home/heating/setCooling", {"cooling": True}
    )
    assert api_client._command_target_key(
        "/hmip/home/security/setExtendedZonesActivation", {}
    ) != api_client._command_target_key(
        "/hmip/home/security/acknowledgeSafetyAlarm", {}
    )
    assert api_client._command_target_key("/hmip/home/setPin", {"pin": "1234"}) == (
        "home",
        "setPin",
    )
    assert api_client._command_target_key(
        "/hmip/plugin/createUserMessage", {"userMessageId": "m-1"}
    ) == api_client._command_target_key(
        "/hmip/plugin/deleteUserMessage", {"userMessageId": "m-1"}
    )
    assert api_client._command_target_key(
        "/hmip/plugin/createUserMessage", {"userMessageId": "m-1"}
    ) != api_client._command_target_key(
        "/hmip/plugin/deleteUserMessage", {"userMessageId": "m-2"}
    )
    assert api_client._command_target_key("/hmip/custom/ping", {}) == (
        "path",
        "/hmip/custom/ping",
        "ping",
    )
    # Garage door opener with light & alarm siren group keep independent features distinct
    assert api_client._command_target_key(
        "/hmip/device/control/sendDoorCommand",
        {"deviceId": "d-gar", "channelIndex": 1, "doorCommand": "OPEN"},
    ) != api_client._command_target_key(
        "/hmip/device/control/setSwitchState",
        {"deviceId": "d-gar", "channelIndex": 1, "on": True},
    )
    assert api_client._command_target_key(
        "/hmip/group/switching/setState", {"groupId": "g-sir", "on": False}
    ) == api_client._command_target_key(
        "/hmip/group/switching/setSwitchStateWithTime",
        {"groupId": "g-sir", "on": True, "onTime": 30},
    )
    assert api_client._command_target_key(
        "/hmip/group/switching/setState", {"groupId": "g-sir", "on": True}
    ) != api_client._command_target_key(
        "/hmip/group/switching/alarm/testSignalAcoustic",
        {"groupId": "g-sir", "signalAcoustic": "FREQUENCY_RISING"},
    )


async def test_independent_settings_on_same_target_do_not_cancel_retries_rest_and_ws(
    api_client: HcuApiClient,
) -> None:
    """Independent settings on the same group/device/home keep retrying across REST and WS."""
    api_client._app_token = "app-tok"

    # 1. App User REST: setSetPointTemperature gets DEVICE_BUSY; concurrent setBoost,
    # setControlMode("MANUAL"), and setActiveProfile on the SAME heating group do NOT cancel it!
    rest_calls: list[tuple[str, dict]] = []
    temp_busy_once = True
    rest_sleep_entered = asyncio.Event()
    rest_sleep_release = asyncio.Event()

    def make_rest_post(url: str, *, json: dict | None = None, **_kwargs):
        nonlocal temp_busy_once
        path = url.split(":6969", 1)[-1]
        body = dict(json or {})
        rest_calls.append((path, body))
        resp = MagicMock()
        if path.endswith("/setSetPointTemperature") and temp_busy_once:
            temp_busy_once = False
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

    async def controlled_rest_sleep(_delay: float) -> None:
        rest_sleep_entered.set()
        await rest_sleep_release.wait()

    api_client._session.post = MagicMock(side_effect=make_rest_post)

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_rest_sleep,
        ),
    ):
        temp_task = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/heating/setSetPointTemperature",
                {"groupId": "g-heat", "setPointTemperature": 21.5},
            )
        )
        await rest_sleep_entered.wait()

        # Boost, MANUAL control mode, and profile selection on the same group run during delay
        await asyncio.gather(
            api_client._async_app_rest_call(
                "/hmip/group/heating/setBoost",
                {"groupId": "g-heat", "boost": True},
            ),
            api_client._async_app_rest_call(
                "/hmip/group/heating/setControlMode",
                {"groupId": "g-heat", "controlMode": "MANUAL"},
            ),
            api_client._async_app_rest_call(
                "/hmip/group/heating/setActiveProfile",
                {"groupId": "g-heat", "profileIndex": "PROFILE_2"},
            ),
        )
        rest_sleep_release.set()
        assert await temp_task == {"ok": True}

    assert [p.rsplit("/", 1)[-1] for p, _ in rest_calls].count(
        "setSetPointTemperature"
    ) == 2
    assert api_client._target_generations == {}
    assert api_client._target_active_counts == {}

    # 2. App User REST: color retry refreshes dimLevel after brightness-only update (rolls back
    # rejected updates), setSetPointTemperature never drops setControlMode / activatePartyMode
    # (refreshing party temperature instead), and activatePartyMode supersedes an older setpoint!
    rest_merge_calls: list[tuple[str, dict]] = []
    rest_busy_seen: set[str] = set()
    merge_sleeping = 0
    merge_ready = asyncio.Event()
    merge_release = asyncio.Event()

    def make_merge_post(url: str, *, json: dict | None = None, **_kwargs):
        path = url.split(":6969", 1)[-1]
        act = path.rsplit("/", 1)[-1]
        body = dict(json or {})
        rest_merge_calls.append((act, body))
        resp = MagicMock()
        tag = f"{act}:{body.get('deviceId') or body.get('groupId')}"
        if body.get("dimLevel") == 0.99:
            resp.ok = False
            resp.status = 400
            resp.text = AsyncMock(
                return_value='{"errorCode": "INVALID_PARAMETER_VALUE"}'
            )
            return _ResponseCtx(resp)
        if (
            act
            in (
                "setHueSaturationDimLevel",
                "setControlMode",
                "activatePartyMode",
                "setSetPointTemperature",
            )
            and body.get("groupId") != "g-party-supersede-2"
            and not (
                act == "setSetPointTemperature"
                and body.get("groupId") in ("g-mode", "g-party")
            )
            and not (
                act == "activatePartyMode"
                and body.get("groupId") == "g-temp-superseded"
            )
            and tag not in rest_busy_seen
        ):
            rest_busy_seen.add(tag)
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

    async def controlled_merge_sleep(_delay: float) -> None:
        nonlocal merge_sleeping
        merge_sleeping += 1
        if merge_sleeping == 4:
            merge_ready.set()
        await merge_release.wait()

    api_client._session.post = MagicMock(side_effect=make_merge_post)

    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_merge_sleep,
        ),
    ):
        caller_color_body = {
            "deviceId": "d-rest-rgb",
            "channelIndex": 1,
            "hue": 120,
            "saturationLevel": 0.8,
            "dimLevel": 1.0,
        }
        t_rest_color = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/device/control/setHueSaturationDimLevel",
                caller_color_body,
            )
        )
        t_rest_mode = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/heating/setControlMode",
                {"groupId": "g-mode", "controlMode": "AUTOMATIC"},
            )
        )
        t_rest_party = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/heating/activatePartyMode",
                {
                    "groupId": "g-party",
                    "temperature": 19.0,
                    "endTime": "2026_12_31 23:00",
                },
            )
        )
        t_rest_superseded_temp = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/group/heating/setSetPointTemperature",
                {"groupId": "g-temp-superseded", "setPointTemperature": 23.0},
            )
        )
        await merge_ready.wait()

        # Brightness 40% succeeds, then invalid 99% fails (must roll back to 40%!)
        await api_client._async_app_rest_call(
            "/hmip/device/control/setDimLevel",
            {"deviceId": "d-rest-rgb", "channelIndex": 1, "dimLevel": 0.4},
        )
        with pytest.raises(HcuApiError):
            await api_client._async_app_rest_call(
                "/hmip/device/control/setDimLevel",
                {"deviceId": "d-rest-rgb", "channelIndex": 1, "dimLevel": 0.99},
            )

        # Temperature updates on g-mode and g-party must NOT drop mode changes,
        # while activatePartyMode on g-temp-superseded DOES supersede older setpoint!
        await asyncio.gather(
            api_client._async_app_rest_call(
                "/hmip/group/heating/setSetPointTemperature",
                {"groupId": "g-mode", "setPointTemperature": 21.0},
            ),
            api_client._async_app_rest_call(
                "/hmip/group/heating/setSetPointTemperature",
                {"groupId": "g-party", "setPointTemperature": 22.0},
            ),
            api_client._async_app_rest_call(
                "/hmip/group/heating/activatePartyMode",
                {
                    "groupId": "g-temp-superseded",
                    "temperature": 18.5,
                    "endTime": "2026_12_31 23:00",
                },
            ),
        )

        merge_release.set()
        assert await asyncio.gather(t_rest_color, t_rest_mode, t_rest_party) == [
            {"ok": True},
            {"ok": True},
            {"ok": True},
        ]
        with pytest.raises(HcuApiError) as exc_party:
            await t_rest_superseded_temp
        assert exc_party.value.error_code == "DEVICE_BUSY"

    rest_color_retries = [
        b
        for act, b in rest_merge_calls
        if act == "setHueSaturationDimLevel" and b.get("deviceId") == "d-rest-rgb"
    ]
    assert [b["dimLevel"] for b in rest_color_retries] == [1.0, 0.4]
    assert caller_color_body["dimLevel"] == 1.0
    assert (
        sum(
            1
            for act, b in rest_merge_calls
            if act == "setControlMode" and b.get("groupId") == "g-mode"
        )
        == 2
    )
    rest_party_retries = [
        b
        for act, b in rest_merge_calls
        if act == "activatePartyMode" and b.get("groupId") == "g-party"
    ]
    assert [b["temperature"] for b in rest_party_retries] == [19.0, 22.0]
    assert (
        sum(
            1
            for act, b in rest_merge_calls
            if act == "setSetPointTemperature"
            and b.get("groupId") == "g-temp-superseded"
        )
        == 1
    )

    # 3. Plugin WebSocket: independent heating boost, home setCooling vs absence,
    # light brightness (>0) + color (with refreshed dimLevel on both DEVICE_BUSY and transport
    # retry!), optical signal + RGB color, slats + shutter level, group secondary + primary
    # shading, and setControlMode(with setPointTemperature) + setSetPointTemperature!
    ws_calls: list[tuple[str, dict]] = []
    busy_first_keys: set[str] = set()
    ws_sleep_count = 0
    ws_all_sleeping = asyncio.Event()
    ws_release = asyncio.Event()

    async def fake_ws_send(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        path = msg["body"]["path"]
        body = dict(msg["body"]["body"])
        ws_calls.append((path, body))
        action = path.rsplit("/", 1)[-1]
        busy_tag = f"{action}:{body.get('deviceId') or body.get('groupId') or 'home'}"
        if (
            action == "setColorTemperatureDimLevel"
            and body.get("deviceId") == "d-ct-drop"
            and busy_tag not in busy_first_keys
        ):
            busy_first_keys.add(busy_tag)
            raise ConnectionError("transient ws drop")
        if (
            action
            in (
                "setSetPointTemperature",
                "activateAbsencePermanent",
                "setHueSaturationDimLevel",
                "setOpticalSignal",
                "setSlatsLevel",
                "setSecondaryShadingLevel",
                "setControlMode",
            )
            and not (
                action == "setSetPointTemperature" and body.get("groupId") == "g-cm"
            )
            and not (action == "setControlMode" and body.get("groupId") == "g-ws")
            and busy_tag not in busy_first_keys
        ):
            busy_first_keys.add(busy_tag)
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": "DEVICE_BUSY"}},
                }
            )
            return
        api_client._handle_incoming_message(
            {"type": "HMIP_SYSTEM_RESPONSE", "id": msg_id, "body": {"code": 200}}
        )

    async def controlled_ws_sleep(_delay: float) -> None:
        nonlocal ws_sleep_count
        ws_sleep_count += 1
        if ws_sleep_count == 8:
            ws_all_sleeping.set()
        await ws_release.wait()

    with (
        patch.object(api_client, "_send_message", side_effect=fake_ws_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_ws_sleep,
        ),
    ):
        tasks = [
            asyncio.create_task(
                api_client.async_set_group_setpoint_temperature("g-ws", 21.0)
            ),
            asyncio.create_task(api_client.async_activate_absence_permanent()),
            asyncio.create_task(
                api_client.async_set_hue_saturation("d-rgb", 1, 120, 0.8, 1.0)
            ),
            asyncio.create_task(
                api_client.async_set_color_temperature("d-ct-drop", 1, 3200, 1.0)
            ),
            asyncio.create_task(
                api_client.async_device_control(
                    "/hmip/device/control/setOpticalSignal",
                    "d-opt",
                    2,
                    {
                        "simpleRGBColorState": "BLUE",
                        "dimLevel": 1.0,
                        "opticalSignalBehaviour": "BLINKING_MIDDLE",
                    },
                )
            ),
            asyncio.create_task(
                api_client.async_set_slats_level("d-blind", 1, 0.8, shutter_level=0.0)
            ),
            asyncio.create_task(
                api_client.async_group_control(
                    "/hmip/group/switching/setSecondaryShadingLevel",
                    "g-cov",
                    {
                        "primaryShadingLevel": 0.0,
                        "secondaryShadingLevel": 0.6,
                        "shutterLevel": 0.0,
                        "slatsLevel": 0.6,
                    },
                )
            ),
            asyncio.create_task(
                api_client.async_set_group_control_mode(
                    "g-cm", "MANUAL", setPointTemperature=18.0
                )
            ),
        ]
        await ws_all_sleeping.wait()

        # Concurrent updates on the exact same targets
        await asyncio.gather(
            api_client.async_set_group_boost("g-ws", True),
            api_client.async_set_group_control_mode("g-ws", "AUTOMATIC"),
            api_client.async_home_control(
                "/hmip/home/heating/setCooling", {"cooling": False}
            ),
            api_client.async_set_dim_level("d-rgb", 1, 0.4),
            api_client.async_set_dim_level("d-ct-drop", 1, 0.25),
            api_client.async_device_control(
                "/hmip/device/control/setSimpleRGBColorDimLevel",
                "d-opt",
                2,
                {"simpleRGBColorState": "RED", "dimLevel": 0.35},
            ),
            api_client.async_set_shutter_level("d-blind", 1, 0.5),
            api_client.async_group_control(
                "/hmip/group/switching/setPrimaryShadingLevel",
                "g-cov",
                {"primaryShadingLevel": 0.75},
            ),
            api_client.async_set_group_setpoint_temperature("g-cm", 21.5),
        )
        ws_release.set()
        await asyncio.gather(*tasks)

    rgb_bodies = [
        b
        for p, b in ws_calls
        if p.endswith("/setHueSaturationDimLevel") and b.get("deviceId") == "d-rgb"
    ]
    assert [b["dimLevel"] for b in rgb_bodies] == [1.0, 0.4]
    ct_drop_bodies = [
        b
        for p, b in ws_calls
        if p.endswith("/setColorTemperatureDimLevel")
        and b.get("deviceId") == "d-ct-drop"
    ]
    assert [b["dimLevel"] for b in ct_drop_bodies] == [1.0, 0.25]
    opt_bodies = [
        b
        for p, b in ws_calls
        if p.endswith("/setOpticalSignal") and b.get("deviceId") == "d-opt"
    ]
    assert opt_bodies[-1]["dimLevel"] == 0.35
    assert opt_bodies[-1]["simpleRGBColorState"] == "RED"
    assert opt_bodies[-1]["opticalSignalBehaviour"] == "BLINKING_MIDDLE"
    slats_bodies = [
        b
        for p, b in ws_calls
        if p.endswith("/setSlatsLevel") and b.get("deviceId") == "d-blind"
    ]
    assert [(b["slatsLevel"], b["shutterLevel"]) for b in slats_bodies] == [
        (0.8, 0.0),
        (0.8, 0.5),
    ]
    sec_bodies = [
        b
        for p, b in ws_calls
        if p.endswith("/setSecondaryShadingLevel") and b.get("groupId") == "g-cov"
    ]
    assert sec_bodies[-1]["primaryShadingLevel"] == 0.75
    assert sec_bodies[-1]["shutterLevel"] == 0.75
    assert sec_bodies[-1]["secondaryShadingLevel"] == 0.6
    cm_bodies = [
        b
        for p, b in ws_calls
        if p.endswith("/setControlMode") and b.get("groupId") == "g-cm"
    ]
    assert [b["setPointTemperature"] for b in cm_bodies] == [18.0, 21.5]
    assert (
        sum(
            1
            for p, b in ws_calls
            if p.endswith("/setSetPointTemperature") and b.get("groupId") == "g-ws"
        )
        == 2
    )
    assert sum(1 for p, _ in ws_calls if p.endswith("/activateAbsencePermanent")) == 2

    # 4. Cross-aspect superseding on WS: light turn-off (dimLevel=0 & optical OFF) cancels
    # color/signal, setFavoriteShadingPosition cancels stale setSlatsLevel, and color with
    # dimLevel cancels an older dim-only retry!
    override_calls: list[str] = []
    override_busy_seen: set[tuple[str, str]] = set()
    override_sleeping = 0
    override_ready = asyncio.Event()
    override_release = asyncio.Event()

    async def fake_override_send(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        path = msg["body"]["path"]
        body = msg["body"]["body"]
        act = path.rsplit("/", 1)[-1]
        target = str(body.get("deviceId") or body.get("groupId") or "")
        override_calls.append(act)
        if (
            act
            in (
                "setColorTemperatureDimLevel",
                "setOpticalSignal",
                "setSlatsLevel",
                "setDimLevel",
            )
            and body.get("dimLevel") != 0.0
            and body.get("opticalSignalBehaviour") != "OFF"
            and (act, target) not in override_busy_seen
        ):
            override_busy_seen.add((act, target))
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": "DEVICE_BUSY"}},
                }
            )
            return
        api_client._handle_incoming_message(
            {"type": "HMIP_SYSTEM_RESPONSE", "id": msg_id, "body": {"code": 200}}
        )

    async def controlled_override_sleep(_delay: float) -> None:
        nonlocal override_sleeping
        override_sleeping += 1
        if override_sleeping == 5:
            override_ready.set()
        await override_release.wait()

    with (
        patch.object(api_client, "_send_message", side_effect=fake_override_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_override_sleep,
        ),
    ):
        t_ct = asyncio.create_task(
            api_client.async_set_color_temperature("d-ct", 1, 3000, 1.0)
        )
        t_opt = asyncio.create_task(
            api_client.async_device_control(
                "/hmip/device/control/setOpticalSignal",
                "d-bsl",
                2,
                {
                    "simpleRGBColorState": "BLUE",
                    "dimLevel": 1.0,
                    "opticalSignalBehaviour": "BLINKING_MIDDLE",
                },
            )
        )
        t_slats = asyncio.create_task(
            api_client.async_set_slats_level("d-bbl", 1, 0.5, shutter_level=0.0)
        )
        t_dim = asyncio.create_task(
            api_client.async_set_dim_level("d-dim-first", 1, 0.3)
        )
        t_grp_dim = asyncio.create_task(
            api_client.async_group_control(
                "/hmip/group/switching/setDimLevel", "g-lg", {"dimLevel": 0.7}
            )
        )
        await override_ready.wait()

        await asyncio.gather(
            api_client.async_set_dim_level("d-ct", 1, 0.0),
            api_client.async_device_control(
                "/hmip/device/control/setOpticalSignal",
                "d-bsl",
                2,
                {
                    "simpleRGBColorState": "BLACK",
                    "dimLevel": 0.0,
                    "opticalSignalBehaviour": "OFF",
                },
            ),
            api_client.async_device_control(
                "/hmip/device/control/setFavoriteShadingPosition", "d-bbl", 1
            ),
            api_client.async_set_hue_saturation("d-dim-first", 1, 200, 0.9, 0.8),
            api_client.async_set_switching_group_state("g-lg", False),
        )
        override_release.set()
        for superseded in (t_ct, t_opt, t_slats, t_dim, t_grp_dim):
            with pytest.raises(HcuApiError) as sup_exc:
                await superseded
            assert sup_exc.value.error_code == "DEVICE_BUSY"

    assert override_calls.count("setColorTemperatureDimLevel") == 1
    assert override_calls.count("setSlatsLevel") == 1
    assert api_client._target_generations == {}
    assert api_client._target_active_counts == {}
    assert api_client._scope_active_counts == {}
    assert api_client._scope_field_overrides == {}


async def test_queued_rest_and_inflight_ws_retries_refresh_fields_and_supersede(
    api_client: HcuApiClient,
) -> None:
    """Test queued REST retries under _command_lock and WS retries overlapping in-flight updates."""
    real_sleep = asyncio.sleep

    # 1. App User REST:
    # - Q1: Color retry wakes up while setDimLevel(0.4) holds _command_lock mid-POST ->
    #   queued Color retry must refresh dimLevel=0.4 AFTER _command_lock is acquired!
    # - Q2: Color retry wakes up and queues on _command_lock behind an unrelated POST,
    #   and setDimLevel(0.0) arrives while Color is queued -> Color must abort under lock!
    api_client._auth_type = "app"
    api_client._app_token = "app-token"
    api_client._client_auth = "client-auth"
    api_client._access_point_id = "3014F711A000000000000001"

    rest_sent: list[tuple[str, dict]] = []
    busy_seen: set[str] = set()
    q1_color_sleeping = asyncio.Event()
    q1_color_wake = asyncio.Event()
    q1_dim_in_post = asyncio.Event()
    q1_dim_finish = asyncio.Event()

    q2_color_sleeping = asyncio.Event()
    q2_color_wake = asyncio.Event()
    q2_other_in_post = asyncio.Event()
    q2_other_finish = asyncio.Event()

    def make_queued_post(url: str, **kwargs):
        action = url.rsplit("/", 1)[-1]
        body = dict(kwargs.get("json") or {})
        dev_id = str(body.get("deviceId") or "")
        rest_sent.append((action, body))

        resp = MagicMock()
        if action == "setHueSaturationDimLevel" and dev_id not in busy_seen:
            busy_seen.add(dev_id)
            resp.ok = False
            resp.status = 400
            resp.text = AsyncMock(return_value='{"errorCode": "DEVICE_BUSY"}')
            cm = MagicMock()
            cm.__aenter__ = AsyncMock(return_value=resp)
            cm.__aexit__ = AsyncMock(return_value=False)
            return cm

        resp.ok = True
        resp.status = 200
        if dev_id == "d-q-rgb" and action == "setDimLevel":
            # Also exercise empty-body 204 response recording on_success!
            resp.content_length = 0
            resp.content_type = "text/plain"
        else:
            resp.content_length = 12
            resp.content_type = "application/json"
            resp.json = AsyncMock(return_value={"ok": True})

        async def enter_post():
            if dev_id == "d-q-rgb" and action == "setDimLevel":
                q1_dim_in_post.set()
                await q1_dim_finish.wait()
            elif dev_id == "d-other":
                q2_other_in_post.set()
                await q2_other_finish.wait()
            return resp

        cm = MagicMock()
        cm.__aenter__ = AsyncMock(side_effect=enter_post)
        cm.__aexit__ = AsyncMock(return_value=False)
        return cm

    sleep_idx = 0

    async def controlled_rest_sleep(_delay: float) -> None:
        nonlocal sleep_idx
        sleep_idx += 1
        if sleep_idx == 1:
            q1_color_sleeping.set()
            await q1_color_wake.wait()
        else:
            q2_color_sleeping.set()
            await q2_color_wake.wait()

    api_client._session.post = MagicMock(side_effect=make_queued_post)
    with (
        patch(
            "custom_components.hcu_integration.api.create_unverified_ssl_context",
            AsyncMock(return_value=None),
        ),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_rest_sleep,
        ),
    ):
        # Q1: Queued REST color retry refreshes dimLevel after setDimLevel releases _command_lock
        t_q1_color = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/device/control/setHueSaturationDimLevel",
                {
                    "deviceId": "d-q-rgb",
                    "channelIndex": 1,
                    "hue": 180,
                    "saturationLevel": 0.7,
                    "dimLevel": 1.0,
                },
            )
        )
        await q1_color_sleeping.wait()

        t_q1_dim = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/device/control/setDimLevel",
                {"deviceId": "d-q-rgb", "channelIndex": 1, "dimLevel": 0.4},
            )
        )
        await q1_dim_in_post.wait()

        # Wake Color while setDimLevel holds _command_lock mid-POST
        q1_color_wake.set()
        for _ in range(5):
            await real_sleep(0)

        q1_dim_finish.set()
        assert await asyncio.gather(t_q1_dim, t_q1_color) == [{}, {"ok": True}]

        # Q2: Color wakes and queues behind unrelated d-other POST; setDimLevel(0.0)
        # arrives while Color is ALREADY queued on _command_lock!
        t_q2_color = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/device/control/setHueSaturationDimLevel",
                {
                    "deviceId": "d-q-off",
                    "channelIndex": 1,
                    "hue": 60,
                    "saturationLevel": 1.0,
                    "dimLevel": 0.9,
                },
            )
        )
        await q2_color_sleeping.wait()

        t_q2_other = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/device/control/setSwitchState",
                {"deviceId": "d-other", "channelIndex": 1, "on": True},
            )
        )
        await q2_other_in_post.wait()

        # Wake Color so it queues directly on _command_lock behind d-other
        q2_color_wake.set()
        for _ in range(5):
            await real_sleep(0)

        # Issue light turn-off while Color is already parked on _command_lock
        t_q2_off = asyncio.create_task(
            api_client._async_app_rest_call(
                "/hmip/device/control/setDimLevel",
                {"deviceId": "d-q-off", "channelIndex": 1, "dimLevel": 0.0},
            )
        )
        for _ in range(5):
            await real_sleep(0)

        q2_other_finish.set()
        with pytest.raises(HcuApiError) as q2_exc:
            await t_q2_color
        assert q2_exc.value.error_code == "DEVICE_BUSY"
        assert await asyncio.gather(t_q2_other, t_q2_off) == [
            {"ok": True},
            {"ok": True},
        ]

    q1_color_bodies = [
        b
        for act, b in rest_sent
        if act == "setHueSaturationDimLevel" and b.get("deviceId") == "d-q-rgb"
    ]
    assert [b["dimLevel"] for b in q1_color_bodies] == [1.0, 0.4]
    q2_color_bodies = [
        b
        for act, b in rest_sent
        if act == "setHueSaturationDimLevel" and b.get("deviceId") == "d-q-off"
    ]
    assert len(q2_color_bodies) == 1

    # 2. Plugin WebSocket:
    # - Q3a: Two multi-field retries (color + optical signal) wake while setDimLevel(0.35)
    #   is mid-flight awaiting HMIP_SYSTEM_RESPONSE -> both wait for setDimLevel(0.35) and
    #   send dimLevel=0.35!
    # - Q3b: Color retry waiting on mid-flight setDimLevel(0.5) wakes immediately and aborts
    #   when urgent setDimLevel(0.0) arrives!
    # - Q3c: Color retry waiting on hung setDimLevel(0.6) respects request timeout fallback.
    api_client._auth_type = "plugin"
    api_client._app_token = ""

    ws_sent: list[tuple[str, dict]] = []
    ws_busy_once: set[tuple[str, str]] = set()
    deferred_msg_ids: dict[str, str] = {}
    ws_dim_sent_events: dict[str, asyncio.Event] = {
        "d-ws-q": asyncio.Event(),
        "d-ws-sup": asyncio.Event(),
        "d-ws-to": asyncio.Event(),
    }
    ws_sleep_events: list[tuple[asyncio.Event, asyncio.Event]] = [
        (asyncio.Event(), asyncio.Event()) for _ in range(4)
    ]
    ws_sleep_n = 0

    async def fake_ws_inflight_send(msg: dict, log_body: bool = True) -> None:
        msg_id = msg["id"]
        path = msg["body"]["path"]
        body = dict(msg["body"]["body"])
        act = path.rsplit("/", 1)[-1]
        dev_id = str(body.get("deviceId") or "")
        ws_sent.append((act, body))

        if (
            act in ("setHueSaturationDimLevel", "setOpticalSignal")
            and (act, dev_id) not in ws_busy_once
        ):
            ws_busy_once.add((act, dev_id))
            api_client._handle_incoming_message(
                {
                    "type": "HMIP_SYSTEM_RESPONSE",
                    "id": msg_id,
                    "body": {"code": 400, "body": {"errorCode": "DEVICE_BUSY"}},
                }
            )
            return

        if act == "setDimLevel" and body.get("dimLevel", 0.0) > 0.0:
            deferred_msg_ids[dev_id] = msg_id
            ws_dim_sent_events[dev_id].set()
            return

        api_client._handle_incoming_message(
            {"type": "HMIP_SYSTEM_RESPONSE", "id": msg_id, "body": {"code": 200}}
        )

    async def controlled_ws_inflight_sleep(_delay: float) -> None:
        nonlocal ws_sleep_n
        idx = ws_sleep_n
        ws_sleep_n += 1
        ready_ev, wake_ev = ws_sleep_events[idx]
        ready_ev.set()
        await wake_ev.wait()

    with (
        patch.object(api_client, "_send_message", side_effect=fake_ws_inflight_send),
        patch(
            "custom_components.hcu_integration.api.asyncio.sleep",
            side_effect=controlled_ws_inflight_sleep,
        ),
    ):
        # Q3a: Color + Optical both wake while setDimLevel(0.35) is mid-flight
        t_ws_col = asyncio.create_task(
            api_client.async_set_hue_saturation("d-ws-q", 1, 200, 0.9, 1.0)
        )
        t_ws_opt = asyncio.create_task(
            api_client.async_device_control(
                "/hmip/device/control/setOpticalSignal",
                "d-ws-q",
                1,
                {
                    "dimLevel": 1.0,
                    "opticalSignalBehaviour": "ON",
                },
            )
        )
        await ws_sleep_events[0][0].wait()
        await ws_sleep_events[1][0].wait()

        t_ws_dim = asyncio.create_task(
            api_client.async_set_dim_level("d-ws-q", 1, 0.35)
        )
        await ws_dim_sent_events["d-ws-q"].wait()

        ws_sleep_events[0][1].set()
        ws_sleep_events[1][1].set()
        for _ in range(5):
            await real_sleep(0)

        # Neither retry should have fired before setDimLevel(0.35) gets its 200 response!
        assert (
            sum(
                1
                for act, b in ws_sent
                if act == "setHueSaturationDimLevel" and b.get("deviceId") == "d-ws-q"
            )
            == 1
        )
        api_client._handle_incoming_message(
            {
                "type": "HMIP_SYSTEM_RESPONSE",
                "id": deferred_msg_ids["d-ws-q"],
                "body": {"code": 200},
            }
        )
        await asyncio.gather(t_ws_dim, t_ws_col, t_ws_opt)

        # Q3b: Superseded immediately while waiting on mid-flight setDimLevel(0.5)
        t_ws_sup_col = asyncio.create_task(
            api_client.async_set_hue_saturation("d-ws-sup", 1, 100, 0.5, 1.0)
        )
        await ws_sleep_events[2][0].wait()
        t_ws_sup_dim = asyncio.create_task(
            api_client.async_set_dim_level("d-ws-sup", 1, 0.5)
        )
        await ws_dim_sent_events["d-ws-sup"].wait()
        ws_sleep_events[2][1].set()
        for _ in range(5):
            await real_sleep(0)

        await api_client.async_set_dim_level("d-ws-sup", 1, 0.0)
        with pytest.raises(HcuApiError) as ws_sup_exc:
            await t_ws_sup_col
        assert ws_sup_exc.value.error_code == "DEVICE_BUSY"
        api_client._handle_incoming_message(
            {
                "type": "HMIP_SYSTEM_RESPONSE",
                "id": deferred_msg_ids["d-ws-sup"],
                "body": {"code": 200},
            }
        )
        await t_ws_sup_dim

        # Q3c: Timeout bound when in-flight setDimLevel(0.6) hangs longer than timeout
        t_ws_to_col = asyncio.create_task(
            api_client._send_hmip_request(
                "/hmip/device/control/setHueSaturationDimLevel",
                {
                    "deviceId": "d-ws-to",
                    "channelIndex": 1,
                    "hue": 30,
                    "saturationLevel": 0.5,
                    "dimLevel": 0.8,
                },
                timeout=0.01,  # type: ignore[arg-type]
            )
        )
        await ws_sleep_events[3][0].wait()
        t_ws_to_dim = asyncio.create_task(
            api_client.async_set_dim_level("d-ws-to", 1, 0.6)
        )
        await ws_dim_sent_events["d-ws-to"].wait()
        ws_sleep_events[3][1].set()
        await t_ws_to_col
        api_client._handle_incoming_message(
            {
                "type": "HMIP_SYSTEM_RESPONSE",
                "id": deferred_msg_ids["d-ws-to"],
                "body": {"code": 200},
            }
        )
        await t_ws_to_dim

    ws_q_col = [
        b
        for act, b in ws_sent
        if act == "setHueSaturationDimLevel" and b.get("deviceId") == "d-ws-q"
    ]
    ws_q_opt = [
        b
        for act, b in ws_sent
        if act == "setOpticalSignal" and b.get("deviceId") == "d-ws-q"
    ]
    assert [b["dimLevel"] for b in ws_q_col] == [1.0, 0.35]
    assert [b["dimLevel"] for b in ws_q_opt] == [1.0, 0.35]
    assert (
        sum(
            1
            for act, b in ws_sent
            if act == "setHueSaturationDimLevel" and b.get("deviceId") == "d-ws-sup"
        )
        == 1
    )
    assert api_client._target_generations == {}
    assert api_client._target_active_counts == {}
    assert api_client._scope_active_counts == {}
    assert api_client._scope_field_overrides == {}
    assert api_client._scope_inflight_fields == {}
    assert api_client._scope_change_events == {}
