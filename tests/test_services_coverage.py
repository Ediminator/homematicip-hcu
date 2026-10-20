"""Coverage tests for HCU services."""

from __future__ import annotations

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    API_PATHS,
    ATTR_BODY,
    ATTR_COOLING,
    ATTR_DURATION,
    ATTR_ENABLED,
    ATTR_END_TIME,
    ATTR_PATH,
    ATTR_RULE_ID,
    ATTR_USER_MESSAGE_BEHAVIOR_TYPE,
    ATTR_USER_MESSAGE_CATEGORY,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_MESSAGE,
    ATTR_USER_MESSAGE_TITLE,
    DOMAIN,
)
from custom_components.hcu_integration.services import (
    INTEGRATION_SERVICES,
    _as_multilang,
    _get_entity_from_entity_id,
    async_create_user_message_request,
    async_delete_user_message_request,
    async_handle_activate_eco_mode,
    async_handle_activate_party_mode,
    async_handle_activate_vacation_mode,
    async_handle_deactivate_absence_mode,
    async_handle_play_sound,
    async_handle_send_api_command,
    async_handle_set_cooling_mode,
    async_handle_set_rule_state,
    async_handle_switch_on_with_time,
    async_register_services,
)


def _make_hass_with_client() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create a mock hass instance with a coordinator and client."""
    hass = MagicMock()
    client = MagicMock()
    client.async_enable_simple_rule = AsyncMock()
    client.async_activate_vacation = AsyncMock()
    client.async_activate_absence_permanent = AsyncMock()
    client.async_deactivate_absence = AsyncMock()
    client.async_send_api_command = AsyncMock()
    client.async_create_user_message_request = AsyncMock()
    client.async_delete_user_message_request = AsyncMock()

    coordinator = MagicMock()
    coordinator.client = client
    coordinator.entities = {}
    entry = MagicMock()
    entry.state = ConfigEntryState.LOADED
    entry.runtime_data = coordinator
    hass.config_entries.async_entries.return_value = [entry]
    return hass, coordinator, client


def test_get_entity_from_entity_id_unsupported_domain() -> None:
    """Test _get_entity_from_entity_id with unsupported entity domain."""
    hass, _, _ = _make_hass_with_client()
    assert _get_entity_from_entity_id(hass, "sensor.temperature") is None


def test_as_multilang() -> None:
    """Test _as_multilang parsing helper."""
    # String
    assert _as_multilang("hello", "title") == {"de": "hello", "en": "hello"}

    # Dict of strings
    valid_dict = {"de": "Hallo", "en": "Hello"}
    assert _as_multilang(valid_dict, "title") == valid_dict

    # Dict with non-string keys
    assert _as_multilang({1: "val"}, "title") is None

    # Dict with non-string values
    assert _as_multilang({"de": 123}, "title") is None

    # Unsupported type
    assert _as_multilang(12345, "title") is None


async def test_set_rule_state_success() -> None:
    """Test async_handle_set_rule_state success."""
    hass, _, client = _make_hass_with_client()
    call = SimpleNamespace(data={ATTR_RULE_ID: "rule-1", ATTR_ENABLED: True})

    await async_handle_set_rule_state(hass, call)
    client.async_enable_simple_rule.assert_awaited_once_with(
        rule_id="rule-1", enabled=True
    )


async def test_activate_party_mode_entity_incompatible_or_value_error() -> None:
    """Test async_handle_activate_party_mode with entity missing method and ValueError."""
    hass, coordinator, _ = _make_hass_with_client()

    # Entity without async_activate_party_mode
    climate_no_method = MagicMock()
    climate_no_method.entity_id = "climate.dummy"
    del climate_no_method.async_activate_party_mode

    coordinator.entities = {Platform.CLIMATE: [climate_no_method]}

    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["climate.dummy"],
                    ATTR_TEMPERATURE: 21.0,
                    ATTR_DURATION: 3600,
                }
            ),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "entities_not_hcu_climate"
    assert "climate.dummy" in exc.value.translation_placeholders["entities"]

    # Entity raises ValueError
    climate_raises_val = MagicMock()
    climate_raises_val.entity_id = "climate.val_err"
    climate_raises_val.async_activate_party_mode = AsyncMock(
        side_effect=ValueError("Invalid end time")
    )
    coordinator.entities = {Platform.CLIMATE: [climate_raises_val]}

    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["climate.val_err"],
                    ATTR_TEMPERATURE: 21.0,
                    ATTR_DURATION: 3600,
                }
            ),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "entities_invalid_param"
    assert "climate.val_err" in exc.value.translation_placeholders["entities"]

    # Entity raises ServiceValidationError
    climate_raises_sve = MagicMock()
    climate_raises_sve.entity_id = "climate.sve_err"
    climate_raises_sve.async_activate_party_mode = AsyncMock(
        side_effect=ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="party_mode_needs_end_time_or_duration",
        )
    )
    coordinator.entities = {Platform.CLIMATE: [climate_raises_sve]}

    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["climate.sve_err"],
                    ATTR_TEMPERATURE: 21.0,
                    ATTR_DURATION: 3600,
                }
            ),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "party_mode_needs_end_time_or_duration"


async def test_activate_vacation_mode_success_and_connection_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_handle_activate_vacation_mode success and ConnectionError."""
    hass, _, client = _make_hass_with_client()
    call = SimpleNamespace(
        data={ATTR_TEMPERATURE: 17.5, ATTR_END_TIME: "2026-12-31 23:59:00"}
    )

    await async_handle_activate_vacation_mode(hass, call)
    client.async_activate_vacation.assert_awaited_once_with(
        temperature=17.5, end_time="2026_12_31 23:59"
    )
    assert "Activated vacation mode until 2026-12-31 23:59:00" in caplog.text

    client.async_activate_vacation.side_effect = ConnectionError("Disconnected")
    with pytest.raises(HomeAssistantError):
        await async_handle_activate_vacation_mode(hass, call)
    assert "Error activating vacation mode: Disconnected" in caplog.text

    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_activate_vacation_mode(
            hass,
            SimpleNamespace(data={ATTR_TEMPERATURE: 17.5, ATTR_END_TIME: "not-a-date"}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "invalid_end_time"
    assert exc.value.translation_placeholders == {"value": "not-a-date"}

    client.async_activate_vacation.side_effect = ValueError("Bad parameter")
    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_activate_vacation_mode(hass, call)
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "invalid_vacation_param"
    assert "Invalid parameter for vacation mode: Bad parameter" in caplog.text


async def test_activate_eco_and_deactivate_absence_success(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test eco and deactivate absence success handlers."""
    hass, _, client = _make_hass_with_client()

    await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))
    client.async_activate_absence_permanent.assert_awaited_once_with()
    assert "Activated eco mode" in caplog.text

    client.async_activate_absence_permanent.side_effect = ConnectionError(
        "Disconnected"
    )
    with pytest.raises(HomeAssistantError):
        await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))
    assert "Error activating eco mode: Disconnected" in caplog.text

    await async_handle_deactivate_absence_mode(hass, SimpleNamespace(data={}))
    client.async_deactivate_absence.assert_awaited_once_with()


async def test_switch_on_with_time_validation_and_unsupported_entity() -> None:
    """Test async_handle_switch_on_with_time entity not found and missing method."""
    hass, coordinator, _ = _make_hass_with_client()

    # 1. Entity not found
    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_switch_on_with_time(
            hass,
            SimpleNamespace(data={ATTR_ENTITY_ID: ["switch.not_found"], "on_time": 60}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "entities_not_found"
    assert "switch.not_found" in exc.value.translation_placeholders["entities"]

    # 2. Entity found but does not have async_turn_on_with_time
    entity_no_method = MagicMock()
    entity_no_method.entity_id = "switch.no_method"
    del entity_no_method.async_turn_on_with_time
    coordinator.entities = {Platform.SWITCH: [entity_no_method]}

    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_switch_on_with_time(
            hass,
            SimpleNamespace(data={ATTR_ENTITY_ID: ["switch.no_method"], "on_time": 60}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "entities_timed_on_unsupported"
    assert "switch.no_method" in exc.value.translation_placeholders["entities"]


async def test_send_api_command() -> None:
    """Test async_handle_send_api_command validation, success and errors."""
    hass, _, client = _make_hass_with_client()

    # Missing body
    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_send_api_command(
            hass,
            SimpleNamespace(data={ATTR_PATH: "/test", ATTR_BODY: None}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "attribute_invalid_dict"

    # Missing path / path not str
    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_send_api_command(
            hass,
            SimpleNamespace(data={ATTR_PATH: None, ATTR_BODY: {}}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "attribute_invalid_string"

    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_send_api_command(
            hass,
            SimpleNamespace(data={ATTR_PATH: 123, ATTR_BODY: {}}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "attribute_invalid_string"

    # Success
    await async_handle_send_api_command(
        hass,
        SimpleNamespace(data={ATTR_PATH: "/test/path", ATTR_BODY: {"foo": "bar"}}),
    )
    client.async_send_api_command.assert_awaited_once_with(
        path="/test/path", body={"foo": "bar"}
    )

    # HcuApiError
    client.async_send_api_command.side_effect = HcuApiError("API Error")
    with pytest.raises(HomeAssistantError) as exc:
        await async_handle_send_api_command(
            hass,
            SimpleNamespace(data={ATTR_PATH: "/test/path", ATTR_BODY: {}}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "send_api_command_failed"
    assert exc.value.translation_placeholders == {
        "path": "/test/path",
        "error": "API Error",
    }

    # No client (ValueError -> ServiceValidationError)
    hass_no_client = MagicMock()
    hass_no_client.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_send_api_command(
            hass_no_client,
            SimpleNamespace(data={ATTR_PATH: "/test/path", ATTR_BODY: {}}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "no_hcu_available"


async def test_set_cooling_mode() -> None:
    """Test async_handle_set_cooling_mode success and errors."""
    hass, _, client = _make_hass_with_client()

    # Success
    await async_handle_set_cooling_mode(
        hass,
        SimpleNamespace(data={ATTR_COOLING: True}),
    )
    client.async_send_api_command.assert_awaited_once_with(
        path=API_PATHS["SET_COOLING"], body={ATTR_COOLING: True}
    )

    # HcuApiError
    client.async_send_api_command.side_effect = HcuApiError("Cooling failed")
    with pytest.raises(HomeAssistantError) as exc:
        await async_handle_set_cooling_mode(
            hass,
            SimpleNamespace(data={ATTR_COOLING: False}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "set_cooling_mode_failed"

    # No client
    hass_no_client = MagicMock()
    hass_no_client.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError) as exc:
        await async_handle_set_cooling_mode(
            hass_no_client,
            SimpleNamespace(data={ATTR_COOLING: True}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "no_hcu_available"


async def test_create_user_message_request() -> None:
    """Test async_create_user_message_request validation, success and error handling."""
    hass, _, client = _make_hass_with_client()

    # Invalid title
    with pytest.raises(ServiceValidationError) as exc:
        await async_create_user_message_request(
            hass,
            SimpleNamespace(
                data={
                    ATTR_USER_MESSAGE_ID: "msg-1",
                    ATTR_USER_MESSAGE_TITLE: [1, 2, 3],
                    ATTR_USER_MESSAGE_MESSAGE: "Test",
                    ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
                    ATTR_USER_MESSAGE_CATEGORY: "INFO",
                }
            ),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "attribute_invalid_multilang"

    # Invalid message
    with pytest.raises(ServiceValidationError) as exc:
        await async_create_user_message_request(
            hass,
            SimpleNamespace(
                data={
                    ATTR_USER_MESSAGE_ID: "msg-1",
                    ATTR_USER_MESSAGE_TITLE: "Title",
                    ATTR_USER_MESSAGE_MESSAGE: {"invalid": 123},
                    ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
                    ATTR_USER_MESSAGE_CATEGORY: "INFO",
                }
            ),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "attribute_invalid_multilang"

    # Success with dict and str
    call = SimpleNamespace(
        data={
            ATTR_USER_MESSAGE_ID: "msg-1",
            ATTR_USER_MESSAGE_TITLE: {"de": "Titel", "en": "Title"},
            ATTR_USER_MESSAGE_MESSAGE: "Hello world",
            ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
            ATTR_USER_MESSAGE_CATEGORY: "INFO",
        }
    )
    start_time = int(time.time() * 1000)
    await async_create_user_message_request(hass, call)
    end_time = int(time.time() * 1000)
    client.async_create_user_message_request.assert_awaited_once()
    sent_body = client.async_create_user_message_request.call_args.kwargs["body"]
    assert sent_body["userMessageId"] == "msg-1"
    assert (
        sent_body["category"]
        if "category" in sent_body
        else sent_body["messageCategory"] == "INFO"
    )
    assert sent_body["behaviorType"] == "DISMISSIBLE"
    assert sent_body["title"] == {"de": "Titel", "en": "Title"}
    assert sent_body["message"] == {"de": "Hello world", "en": "Hello world"}
    assert start_time - 1000 <= sent_body["timestamp"] <= end_time + 1000

    # ConnectionError -> HomeAssistantError
    client.async_create_user_message_request.side_effect = ConnectionError(
        "Disconnected"
    )
    with pytest.raises(HomeAssistantError) as exc:
        await async_create_user_message_request(hass, call)
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "create_user_message_failed"

    # No client -> ServiceValidationError
    hass_no_client = MagicMock()
    hass_no_client.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError) as exc:
        await async_create_user_message_request(hass_no_client, call)
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "no_hcu_available"


async def test_delete_user_message_request() -> None:
    """Test async_delete_user_message_request validation, success and error handling."""
    hass, _, client = _make_hass_with_client()

    # user_message_id is not str
    with pytest.raises(ServiceValidationError) as exc:
        await async_delete_user_message_request(
            hass,
            SimpleNamespace(data={ATTR_USER_MESSAGE_ID: 12345}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "attribute_invalid_string"

    # Success
    await async_delete_user_message_request(
        hass,
        SimpleNamespace(data={ATTR_USER_MESSAGE_ID: "msg-123"}),
    )
    client.async_delete_user_message_request.assert_awaited_once_with(
        user_message_id="msg-123"
    )

    # HcuApiError -> HomeAssistantError
    client.async_delete_user_message_request.side_effect = HcuApiError("Delete failed")
    with pytest.raises(HomeAssistantError) as exc:
        await async_delete_user_message_request(
            hass,
            SimpleNamespace(data={ATTR_USER_MESSAGE_ID: "msg-123"}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "delete_user_message_failed"

    # No client -> ServiceValidationError
    hass_no_client = MagicMock()
    hass_no_client.config_entries.async_entries.return_value = []
    with pytest.raises(ServiceValidationError) as exc:
        await async_delete_user_message_request(
            hass_no_client,
            SimpleNamespace(data={ATTR_USER_MESSAGE_ID: "msg-123"}),
        )
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "no_hcu_available"


def test_async_register_services(hass: HomeAssistant) -> None:
    """Test registering all integration services."""
    async_register_services(hass)

    for service_name in INTEGRATION_SERVICES:
        assert hass.services.has_service(DOMAIN, service_name)


async def test_play_sound_error_logging(caplog: pytest.LogCaptureFixture) -> None:
    """Test async_handle_play_sound logs error when entity fails."""
    from custom_components.hcu_integration.const import ATTR_SOUND_FILE, ATTR_VOLUME

    hass, coordinator, _ = _make_hass_with_client()
    failing_entity = MagicMock()
    failing_entity.entity_id = "light.test_bell"
    failing_entity.async_play_sound = AsyncMock(side_effect=HcuApiError("offline"))
    coordinator.entities = {Platform.LIGHT: [failing_entity]}

    with pytest.raises(HomeAssistantError):
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["light.test_bell"],
                    ATTR_SOUND_FILE: "DOORBELL",
                    ATTR_VOLUME: 0.8,
                    ATTR_DURATION: 5,
                }
            ),
        )
    assert "Error playing sound on light.test_bell" in caplog.text


@pytest.mark.asyncio
async def test_services_translation_helpers_coverage() -> None:
    """Test helper functions for exception translations and reason formatting."""
    from pathlib import Path
    from unittest.mock import patch

    from custom_components.hcu_integration.services import (
        _async_get_exception_translations,
        _format_target_reason,
        _InvalidTarget,
        _load_exception_messages_from_json,
        _raise_collected_errors,
    )

    hass = MagicMock()

    # 1. async_get_translations returns component messages
    with patch(
        "custom_components.hcu_integration.services.async_get_translations",
        AsyncMock(
            return_value={
                f"component.{DOMAIN}.exceptions.reason_not_found.message": "nicht gefunden",
                "custom_key": "custom_val",
            }
        ),
    ):
        res = await _async_get_exception_translations(hass, "de")
        assert res["reason_not_found"] == "nicht gefunden"
        assert res["custom_key"] == "custom_val"

    # 2. _load_exception_messages_from_json handles reading error and fallback
    fallback = _load_exception_messages_from_json("unknown_lang")
    assert "party_mode_needs_end_time_or_duration" in fallback

    with patch.object(Path, "read_text", side_effect=OSError("disk error")):
        empty = _load_exception_messages_from_json("en")
        assert empty == {}

    # 3. _format_target_reason with formatting placeholders, errors, and exception fallbacks
    translations = {"test_key": "Error: {value}"}
    target_ok = _InvalidTarget("ent1", "test_key", placeholders={"value": "123"})
    assert _format_target_reason(target_ok, translations) == "Error: 123"

    target_err = _InvalidTarget("ent2", "test_key", placeholders={"missing": "123"})
    assert _format_target_reason(target_err, translations) == "Error: {value}"

    target_exc = _InvalidTarget(
        "ent3",
        "unknown_reason",
        exception=ServiceValidationError("Direct error message"),
    )
    assert _format_target_reason(target_exc, {}) == "Direct error message"

    target_unknown = _InvalidTarget("ent4", "some_custom_reason")
    assert _format_target_reason(target_unknown, {}) == "some custom reason"

    # 4. _raise_collected_errors early return when nothing to raise
    await _raise_collected_errors(hass, "test_svc", [], [])

    # 5. Multiple entities sharing the same exception
    exc = ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="party_mode_needs_end_time_or_duration",
    )
    targets_same_exc = [
        _InvalidTarget("c1", "party_mode_needs_end_time_or_duration", exception=exc),
        _InvalidTarget("c2", "party_mode_needs_end_time_or_duration", exception=exc),
    ]
    with pytest.raises(ServiceValidationError) as raised:
        await _raise_collected_errors(hass, "test_svc", targets_same_exc, [])
    assert raised.value.translation_key == "party_mode_needs_end_time_or_duration"
