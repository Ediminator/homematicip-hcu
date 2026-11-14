"""Tests for the optional config_entry_id target on home-wide HCU actions."""

from __future__ import annotations

import json
import logging
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol
import yaml

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    API_PATHS,
    ATTR_BODY,
    ATTR_COOLING,
    ATTR_DURATION,
    ATTR_ENABLED,
    ATTR_END_TIME,
    ATTR_ON_TIME,
    ATTR_PATH,
    ATTR_RULE_ID,
    ATTR_SOUND_FILE,
    ATTR_USER_MESSAGE_BEHAVIOR_TYPE,
    ATTR_USER_MESSAGE_CATEGORY,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_MESSAGE,
    ATTR_USER_MESSAGE_TITLE,
    DOMAIN,
    SERVICE_ACTIVATE_ECO_MODE,
    SERVICE_ACTIVATE_PARTY_MODE,
    SERVICE_ACTIVATE_VACATION_MODE,
    SERVICE_DEACTIVATE_ABSENCE_MODE,
    SERVICE_PLAY_SOUND,
    SERVICE_SEND_API_COMMAND,
    SERVICE_SET_COOLING_MODE,
    SERVICE_SET_RULE_STATE,
    SERVICE_SWITCH_ON_WITH_TIME,
    SERVICE_USER_MESSAGE,
    SERVICE_USER_MESSAGE_DELETE,
)
from custom_components.hcu_integration.light import HcuNotificationLight
from custom_components.hcu_integration.services import async_register_services

INTEGRATION_DIR = (
    Path(__file__).resolve().parents[1] / "custom_components" / "hcu_integration"
)
SERVICES_YAML_PATH = INTEGRATION_DIR / "services.yaml"
SERVICES_YAML: dict[str, Any] = yaml.safe_load(
    SERVICES_YAML_PATH.read_text(encoding="utf-8")
)

SERVICES_LOGGER = "custom_components.hcu_integration.services"

HOME_WIDE_ACTIONS = (
    SERVICE_SET_RULE_STATE,
    SERVICE_ACTIVATE_VACATION_MODE,
    SERVICE_ACTIVATE_ECO_MODE,
    SERVICE_DEACTIVATE_ABSENCE_MODE,
    SERVICE_SEND_API_COMMAND,
    SERVICE_SET_COOLING_MODE,
    SERVICE_USER_MESSAGE,
    SERVICE_USER_MESSAGE_DELETE,
)

ENTITY_ACTIONS = (
    SERVICE_PLAY_SOUND,
    SERVICE_ACTIVATE_PARTY_MODE,
    SERVICE_SWITCH_ON_WITH_TIME,
)

CLIENT_METHODS = (
    "async_enable_simple_rule",
    "async_activate_vacation",
    "async_activate_absence_permanent",
    "async_deactivate_absence",
    "async_send_api_command",
    "async_create_user_message_request",
    "async_delete_user_message_request",
)


def _action_payload(action: str) -> tuple[dict[str, Any], str]:
    """Return valid service data and expected client method name for a home-wide action."""
    if action == SERVICE_SET_RULE_STATE:
        return (
            {ATTR_RULE_ID: "rule-1", ATTR_ENABLED: True},
            "async_enable_simple_rule",
        )
    if action == SERVICE_ACTIVATE_VACATION_MODE:
        return (
            {ATTR_TEMPERATURE: 16.0, ATTR_END_TIME: "2026_12_24 18:00"},
            "async_activate_vacation",
        )
    if action == SERVICE_ACTIVATE_ECO_MODE:
        return ({}, "async_activate_absence_permanent")
    if action == SERVICE_DEACTIVATE_ABSENCE_MODE:
        return ({}, "async_deactivate_absence")
    if action == SERVICE_SEND_API_COMMAND:
        return (
            {ATTR_PATH: "/hmip/home/getSystemState", ATTR_BODY: {"k": "v"}},
            "async_send_api_command",
        )
    if action == SERVICE_SET_COOLING_MODE:
        return ({ATTR_COOLING: True}, "async_send_api_command")
    if action == SERVICE_USER_MESSAGE:
        return (
            {
                ATTR_USER_MESSAGE_CATEGORY: "INFO",
                ATTR_USER_MESSAGE_ID: "MSG_1",
                ATTR_USER_MESSAGE_TITLE: "Title",
                ATTR_USER_MESSAGE_MESSAGE: "Body",
                ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
            },
            "async_create_user_message_request",
        )
    if action == SERVICE_USER_MESSAGE_DELETE:
        return ({ATTR_USER_MESSAGE_ID: "MSG_1"}, "async_delete_user_message_request")
    raise AssertionError(f"Unhandled action: {action}")


def _make_mock_client() -> SimpleNamespace:
    """Create a mock HCU client covering all home-wide action methods."""
    return SimpleNamespace(
        disconnect=AsyncMock(),
        async_enable_simple_rule=AsyncMock(),
        async_activate_vacation=AsyncMock(),
        async_activate_absence_permanent=AsyncMock(),
        async_deactivate_absence=AsyncMock(),
        async_send_api_command=AsyncMock(),
        async_create_user_message_request=AsyncMock(),
        async_delete_user_message_request=AsyncMock(),
    )


def _assert_client_untouched(client: SimpleNamespace) -> None:
    """Assert no home-wide client method was awaited."""
    for method_name in CLIENT_METHODS:
        getattr(client, method_name).assert_not_awaited()


def _assert_action_sent(client: SimpleNamespace, action: str) -> None:
    """Assert the expected client method was awaited with expected arguments."""
    _, expected_method = _action_payload(action)
    for method_name in CLIENT_METHODS:
        mock_method = getattr(client, method_name)
        if method_name != expected_method:
            mock_method.assert_not_awaited()

    if action == SERVICE_SET_RULE_STATE:
        client.async_enable_simple_rule.assert_awaited_once_with(
            rule_id="rule-1", enabled=True
        )
    elif action == SERVICE_ACTIVATE_VACATION_MODE:
        client.async_activate_vacation.assert_awaited_once_with(
            temperature=16.0, end_time="2026_12_24 18:00"
        )
    elif action == SERVICE_ACTIVATE_ECO_MODE:
        client.async_activate_absence_permanent.assert_awaited_once_with()
    elif action == SERVICE_DEACTIVATE_ABSENCE_MODE:
        client.async_deactivate_absence.assert_awaited_once_with()
    elif action == SERVICE_SEND_API_COMMAND:
        client.async_send_api_command.assert_awaited_once_with(
            path="/hmip/home/getSystemState", body={"k": "v"}
        )
    elif action == SERVICE_SET_COOLING_MODE:
        client.async_send_api_command.assert_awaited_once_with(
            path=API_PATHS["SET_COOLING"], body={ATTR_COOLING: True}
        )
    elif action == SERVICE_USER_MESSAGE:
        client.async_create_user_message_request.assert_awaited_once()
        sent_body = client.async_create_user_message_request.await_args.kwargs["body"]
        assert sent_body["messageCategory"] == "INFO"
        assert sent_body["userMessageId"] == "MSG_1"
        assert sent_body["title"] == {"de": "Title", "en": "Title"}
        assert sent_body["message"] == {"de": "Body", "en": "Body"}
        assert sent_body["behaviorType"] == "DISMISSIBLE"
        assert isinstance(sent_body["timestamp"], int)
    elif action == SERVICE_USER_MESSAGE_DELETE:
        client.async_delete_user_message_request.assert_awaited_once_with(
            user_message_id="MSG_1"
        )
    else:
        raise AssertionError(f"Unhandled action: {action}")


@pytest.fixture
def two_hcus(hass: HomeAssistant) -> SimpleNamespace:
    """Set up two loaded HCU entries (HCU A added first, HCU B added second)."""
    entry_a = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    entry_b = MockConfigEntry(domain=DOMAIN, data={}, title="HCU B")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    client_a = _make_mock_client()
    client_b = _make_mock_client()

    entry_a.runtime_data = SimpleNamespace(
        entities={}, client=client_a, _ha_bridge=None
    )
    entry_b.runtime_data = SimpleNamespace(
        entities={}, client=client_b, _ha_bridge=None
    )
    entry_a.mock_state(hass, ConfigEntryState.LOADED)
    entry_b.mock_state(hass, ConfigEntryState.LOADED)

    async_register_services(hass)

    return SimpleNamespace(
        entry_a=entry_a,
        entry_b=entry_b,
        client_a=client_a,
        client_b=client_b,
    )


def test_home_wide_actions_list_matches_services_yaml() -> None:
    """Literal HOME_WIDE_ACTIONS matches all actions in services.yaml without a target."""
    assert len(HOME_WIDE_ACTIONS) == 8
    yaml_home_wide = {
        name for name, spec in SERVICES_YAML.items() if "target" not in spec
    }
    assert set(HOME_WIDE_ACTIONS) == yaml_home_wide


@pytest.mark.parametrize("target_key", ["a", "b"])
@pytest.mark.parametrize("action", HOME_WIDE_ACTIONS)
async def test_config_entry_id_selects_the_hcu(
    hass: HomeAssistant,
    two_hcus: SimpleNamespace,
    caplog: pytest.LogCaptureFixture,
    action: str,
    target_key: str,
) -> None:
    """T1: config_entry_id routes each home-wide action to the chosen HCU silently."""
    target_entry = two_hcus.entry_a if target_key == "a" else two_hcus.entry_b
    target_client = two_hcus.client_a if target_key == "a" else two_hcus.client_b
    other_client = two_hcus.client_b if target_key == "a" else two_hcus.client_a

    data, _ = _action_payload(action)
    data["config_entry_id"] = target_entry.entry_id

    with caplog.at_level(logging.WARNING, logger=SERVICES_LOGGER):
        await hass.services.async_call(DOMAIN, action, data, blocking=True)

    _assert_action_sent(target_client, action)
    _assert_client_untouched(other_client)
    warnings = [
        r
        for r in caplog.records
        if r.name == SERVICES_LOGGER and r.levelno == logging.WARNING
    ]
    assert warnings == []


@pytest.mark.parametrize("action", HOME_WIDE_ACTIONS)
async def test_without_field_first_hcu_is_used_with_a_warning(
    hass: HomeAssistant,
    two_hcus: SimpleNamespace,
    caplog: pytest.LogCaptureFixture,
    action: str,
) -> None:
    """T2: Omitting config_entry_id with 2+ loaded HCUs uses the first HCU and warns."""
    data, _ = _action_payload(action)

    with caplog.at_level(logging.WARNING, logger=SERVICES_LOGGER):
        await hass.services.async_call(DOMAIN, action, data, blocking=True)

    _assert_action_sent(two_hcus.client_a, action)
    _assert_client_untouched(two_hcus.client_b)

    warnings = [
        r
        for r in caplog.records
        if r.name == SERVICES_LOGGER and r.levelno == logging.WARNING
    ]
    assert len(warnings) == 1
    msg = warnings[0].getMessage()
    assert action in msg
    assert "config_entry_id" in msg
    assert two_hcus.entry_a.title in msg
    assert two_hcus.entry_a.entry_id in msg


async def test_single_hcu_without_field_is_silent(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T3: With a single loaded HCU, omitting config_entry_id logs no warning."""
    entry_a = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    entry_a.add_to_hass(hass)
    client_a = _make_mock_client()
    entry_a.runtime_data = SimpleNamespace(
        entities={}, client=client_a, _ha_bridge=None
    )
    entry_a.mock_state(hass, ConfigEntryState.LOADED)
    async_register_services(hass)

    with caplog.at_level(logging.WARNING, logger=SERVICES_LOGGER):
        await hass.services.async_call(
            DOMAIN, SERVICE_ACTIVATE_ECO_MODE, {}, blocking=True
        )

    _assert_action_sent(client_a, SERVICE_ACTIVATE_ECO_MODE)
    warnings = [
        r
        for r in caplog.records
        if r.name == SERVICES_LOGGER and r.levelno == logging.WARNING
    ]
    assert warnings == []


async def test_second_hcu_not_loaded_without_field_is_silent(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T4: With one loaded HCU and a second not-loaded HCU, no warning is logged."""
    entry_a = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    entry_b = MockConfigEntry(domain=DOMAIN, data={}, title="HCU B")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    client_a = _make_mock_client()
    client_b = _make_mock_client()
    entry_a.runtime_data = SimpleNamespace(
        entities={}, client=client_a, _ha_bridge=None
    )
    entry_b.runtime_data = SimpleNamespace(
        entities={}, client=client_b, _ha_bridge=None
    )
    entry_a.mock_state(hass, ConfigEntryState.LOADED)
    entry_b.mock_state(hass, ConfigEntryState.NOT_LOADED)
    async_register_services(hass)

    with caplog.at_level(logging.WARNING, logger=SERVICES_LOGGER):
        await hass.services.async_call(
            DOMAIN, SERVICE_ACTIVATE_ECO_MODE, {}, blocking=True
        )

    _assert_action_sent(client_a, SERVICE_ACTIVATE_ECO_MODE)
    _assert_client_untouched(client_b)
    warnings = [
        r
        for r in caplog.records
        if r.name == SERVICES_LOGGER and r.levelno == logging.WARNING
    ]
    assert warnings == []


@pytest.mark.parametrize("action", HOME_WIDE_ACTIONS)
async def test_unknown_config_entry_id_is_rejected(
    hass: HomeAssistant,
    two_hcus: SimpleNamespace,
    action: str,
) -> None:
    """T5: An unknown config_entry_id raises service_config_entry_not_found."""
    data, _ = _action_payload(action)
    data["config_entry_id"] = "does-not-exist"

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(DOMAIN, action, data, blocking=True)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "service_config_entry_not_found"
    assert exc_info.value.translation_placeholders == {
        "config_entry_id": "does-not-exist"
    }
    _assert_client_untouched(two_hcus.client_a)
    _assert_client_untouched(two_hcus.client_b)


async def test_config_entry_of_another_integration_is_rejected(
    hass: HomeAssistant,
) -> None:
    """T6: A config entry belonging to another domain is rejected."""
    entry_a = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    other = MockConfigEntry(domain="other", data={}, title="Other")
    entry_a.add_to_hass(hass)
    other.add_to_hass(hass)

    client_a = _make_mock_client()
    entry_a.runtime_data = SimpleNamespace(
        entities={}, client=client_a, _ha_bridge=None
    )
    entry_a.mock_state(hass, ConfigEntryState.LOADED)
    other.mock_state(hass, ConfigEntryState.LOADED)
    async_register_services(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_ECO_MODE,
            {"config_entry_id": other.entry_id},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "service_config_entry_wrong_domain"
    assert exc_info.value.translation_placeholders == {"title": "Other"}
    _assert_client_untouched(client_a)


@pytest.mark.parametrize(
    "state",
    [
        ConfigEntryState.NOT_LOADED,
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.SETUP_ERROR,
    ],
)
async def test_config_entry_that_is_not_loaded_is_rejected(
    hass: HomeAssistant,
    state: ConfigEntryState,
) -> None:
    """T7: An HCU entry that is not loaded raises service_config_entry_not_loaded."""
    entry_a = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    entry_b = MockConfigEntry(domain=DOMAIN, data={}, title="HCU B")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    client_a = _make_mock_client()
    client_b = _make_mock_client()
    entry_a.runtime_data = SimpleNamespace(
        entities={}, client=client_a, _ha_bridge=None
    )
    entry_b.runtime_data = SimpleNamespace(
        entities={}, client=client_b, _ha_bridge=None
    )
    entry_a.mock_state(hass, ConfigEntryState.LOADED)
    entry_b.mock_state(hass, state)
    async_register_services(hass)

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_ECO_MODE,
            {"config_entry_id": entry_b.entry_id},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "service_config_entry_not_loaded"
    assert exc_info.value.translation_placeholders == {"title": "HCU B"}
    _assert_client_untouched(client_a)
    _assert_client_untouched(client_b)


async def test_entry_in_setup_can_be_selected(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """T8: An HCU entry in SETUP_IN_PROGRESS with runtime_data can be targeted."""
    entry_a = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    entry_b = MockConfigEntry(domain=DOMAIN, data={}, title="HCU B")
    entry_a.add_to_hass(hass)
    entry_b.add_to_hass(hass)

    client_a = _make_mock_client()
    client_b = _make_mock_client()
    entry_a.runtime_data = SimpleNamespace(
        entities={}, client=client_a, _ha_bridge=None
    )
    entry_b.runtime_data = SimpleNamespace(
        entities={}, client=client_b, _ha_bridge=None
    )
    entry_a.mock_state(hass, ConfigEntryState.LOADED)
    entry_b.mock_state(hass, ConfigEntryState.SETUP_IN_PROGRESS)
    async_register_services(hass)

    with caplog.at_level(logging.WARNING, logger=SERVICES_LOGGER):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_ECO_MODE,
            {"config_entry_id": entry_b.entry_id},
            blocking=True,
        )

    _assert_action_sent(client_b, SERVICE_ACTIVATE_ECO_MODE)
    _assert_client_untouched(client_a)
    warnings = [
        r
        for r in caplog.records
        if r.name == SERVICES_LOGGER and r.levelno == logging.WARNING
    ]
    assert warnings == []


async def test_empty_and_null_config_entry_id(
    hass: HomeAssistant,
    two_hcus: SimpleNamespace,
) -> None:
    """T9: Empty string gives not-found error; None fails schema validation."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_ECO_MODE,
            {"config_entry_id": ""},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "service_config_entry_not_found"
    assert exc_info.value.translation_placeholders == {"config_entry_id": ""}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_ECO_MODE,
            {"config_entry_id": None},
            blocking=True,
        )

    _assert_client_untouched(two_hcus.client_a)
    _assert_client_untouched(two_hcus.client_b)


async def test_error_of_the_selected_hcu_is_reported_without_fallback(
    hass: HomeAssistant,
    two_hcus: SimpleNamespace,
) -> None:
    """T10: Errors from the selected HCU raise HomeAssistantError without falling back."""
    two_hcus.client_b.async_activate_absence_permanent.side_effect = HcuApiError("x")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_ECO_MODE,
            {"config_entry_id": two_hcus.entry_b.entry_id},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "activate_eco_failed"
    _assert_client_untouched(two_hcus.client_a)


@pytest.mark.parametrize("action", ENTITY_ACTIONS)
async def test_entity_actions_do_not_take_the_field(
    hass: HomeAssistant,
    action: str,
) -> None:
    """T11: Entity-targeted actions still reject config_entry_id at schema validation."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, title="HCU A")
    entry.add_to_hass(hass)

    ent_reg = er.async_get(hass)
    sound = MagicMock(spec=HcuNotificationLight)
    sound.entity_id = ent_reg.async_get_or_create(
        "light", DOMAIN, "sound", config_entry=entry
    ).entity_id
    sound.async_play_sound = AsyncMock()

    switch = SimpleNamespace(
        entity_id=ent_reg.async_get_or_create(
            "switch", DOMAIN, "switch", config_entry=entry
        ).entity_id,
        async_turn_on_with_time=AsyncMock(),
    )
    climate = SimpleNamespace(
        entity_id=ent_reg.async_get_or_create(
            "climate", DOMAIN, "climate", config_entry=entry
        ).entity_id,
        async_activate_party_mode=AsyncMock(),
    )

    entry.runtime_data = SimpleNamespace(
        entities={
            Platform.LIGHT: [sound],
            Platform.SWITCH: [switch],
            Platform.CLIMATE: [climate],
        },
        client=_make_mock_client(),
        _ha_bridge=None,
    )
    entry.mock_state(hass, ConfigEntryState.LOADED)
    async_register_services(hass)

    if action == SERVICE_PLAY_SOUND:
        data: dict[str, Any] = {ATTR_SOUND_FILE: "SOUNDFILE_001"}
        target = {"entity_id": sound.entity_id}
    elif action == SERVICE_ACTIVATE_PARTY_MODE:
        data = {ATTR_TEMPERATURE: 21.5, ATTR_DURATION: 3600}
        target = {"entity_id": climate.entity_id}
    else:
        data = {ATTR_ON_TIME: 30}
        target = {"entity_id": switch.entity_id}

    data["config_entry_id"] = entry.entry_id

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, action, data, target=target, blocking=True
        )

    sound.async_play_sound.assert_not_awaited()
    climate.async_activate_party_mode.assert_not_awaited()
    switch.async_turn_on_with_time.assert_not_awaited()


def test_services_yaml_offers_the_field_on_home_wide_actions_only() -> None:
    """T12: services.yaml defines optional config_entry selector on the 8 home-wide actions only."""
    for action in HOME_WIDE_ACTIONS:
        fields = SERVICES_YAML[action].get("fields") or {}
        assert "config_entry_id" in fields, action
        field_spec = fields["config_entry_id"]
        assert field_spec.get("required") is not True, action
        assert field_spec.get("selector") == {
            "config_entry": {"integration": DOMAIN}
        }, action

    for action in ENTITY_ACTIONS:
        fields = SERVICES_YAML[action].get("fields") or {}
        assert "config_entry_id" not in fields, action


def test_field_and_errors_are_translated() -> None:
    """T13: strings.json, en.json, and de.json translate the field and 3 exceptions."""
    expected_exceptions = {
        "service_config_entry_not_found": {"config_entry_id"},
        "service_config_entry_wrong_domain": {"title"},
        "service_config_entry_not_loaded": {"title"},
    }
    placeholder_re = re.compile(r"\{([a-zA-Z0-9_]+)\}")

    for rel_path in ("strings.json", "translations/en.json", "translations/de.json"):
        data = json.loads((INTEGRATION_DIR / rel_path).read_text(encoding="utf-8"))

        for action in HOME_WIDE_ACTIONS:
            field_strings = data["services"][action]["fields"]["config_entry_id"]
            assert isinstance(field_strings.get("name"), str)
            assert field_strings["name"].strip(), f"{rel_path}:{action}.name"
            assert isinstance(field_strings.get("description"), str)
            assert field_strings["description"].strip(), (
                f"{rel_path}:{action}.description"
            )

        for key, expected_placeholders in expected_exceptions.items():
            msg = data["exceptions"][key]["message"]
            assert isinstance(msg, str) and msg.strip(), f"{rel_path}:{key}"
            assert set(placeholder_re.findall(msg)) == expected_placeholders, (
                f"{rel_path}:{key}"
            )
