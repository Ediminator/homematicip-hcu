"""Tests for action input schemas of all HCU integration services."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol
import yaml

from custom_components.hcu_integration.climate import HcuClimate
from custom_components.hcu_integration.const import (
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
    ATTR_VOLUME,
    CONF_COMFORT_TEMPERATURE,
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
from custom_components.hcu_integration.services import (
    INTEGRATION_SERVICES,
    async_register_services,
)

SERVICES_YAML_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "hcu_integration"
    / "services.yaml"
)
SERVICES_YAML: dict[str, Any] = yaml.safe_load(
    SERVICES_YAML_PATH.read_text(encoding="utf-8")
)

REQUIRED_FIELDS: list[tuple[str, str]] = [
    (action, field)
    for action, spec in SERVICES_YAML.items()
    for field, field_spec in (spec.get("fields") or {}).items()
    if field_spec.get("required")
]

NUMBER_RANGE_OUT_OF_BOUNDS: list[tuple[str, str, str, float]] = []
NUMBER_RANGE_LIMITS: list[tuple[str, str, float]] = []
for _action, _spec in SERVICES_YAML.items():
    for _field, _field_spec in (_spec.get("fields") or {}).items():
        _number = (_field_spec.get("selector") or {}).get("number")
        if not isinstance(_number, dict) or "min" not in _number:
            continue
        _min = float(_number["min"])
        _step = float(_number.get("step", 1))
        NUMBER_RANGE_OUT_OF_BOUNDS.append(
            ("below_min", _action, _field, round(_min - _step, 6))
        )
        NUMBER_RANGE_LIMITS.append((_action, _field, _min))
        if "max" in _number:
            _max = float(_number["max"])
            NUMBER_RANGE_OUT_OF_BOUNDS.append(
                ("above_max", _action, _field, round(_max + _step, 6))
            )
            NUMBER_RANGE_LIMITS.append((_action, _field, _max))


def _register(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    domain: str,
    unique_id: str,
    device_id: str | None = None,
) -> str:
    """Create an entity registry entry and return its entity_id."""
    return (
        er.async_get(hass)
        .async_get_or_create(
            domain,
            DOMAIN,
            unique_id,
            config_entry=entry,
            device_id=device_id,
        )
        .entity_id
    )


@pytest.fixture
def setup(hass: HomeAssistant) -> SimpleNamespace:
    """Set up a loaded entry with mock entities, mock client, and registered services."""
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    dev_reg = dr.async_get(hass)
    area = ar.async_get(hass).async_create("Hall")
    chime = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "chime")}
    )
    dev_reg.async_update_device(chime.id, area_id=area.id)
    radiator = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "radiator")}
    )

    sound = MagicMock(spec=HcuNotificationLight)
    sound.entity_id = _register(hass, entry, "light", "sound", chime.id)
    sound.async_play_sound = AsyncMock()
    switch = SimpleNamespace(
        entity_id=_register(hass, entry, "switch", "switch", chime.id),
        async_play_sound=AsyncMock(),
        async_turn_on_with_time=AsyncMock(),
    )
    climate = SimpleNamespace(
        entity_id=_register(hass, entry, "climate", "climate", radiator.id),
        async_activate_party_mode=AsyncMock(),
    )
    client = SimpleNamespace(
        disconnect=AsyncMock(),
        async_enable_simple_rule=AsyncMock(),
        async_activate_vacation=AsyncMock(),
        async_activate_absence_permanent=AsyncMock(),
        async_deactivate_absence=AsyncMock(),
        async_send_api_command=AsyncMock(),
        async_create_user_message_request=AsyncMock(),
        async_delete_user_message_request=AsyncMock(),
        async_activate_group_party_mode=AsyncMock(),
    )

    entry.runtime_data = SimpleNamespace(
        entities={
            Platform.LIGHT: [sound],
            Platform.SWITCH: [switch],
            Platform.CLIMATE: [climate],
        },
        client=client,
        _ha_bridge=None,
    )
    entry.mock_state(hass, ConfigEntryState.LOADED)
    async_register_services(hass)

    return SimpleNamespace(
        entry=entry,
        client=client,
        sound=sound,
        switch=switch,
        climate=climate,
    )


def _base_call(
    action: str, setup: SimpleNamespace
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return valid (data, target) for a given action."""
    if action == SERVICE_PLAY_SOUND:
        return (
            {ATTR_SOUND_FILE: "SOUNDFILE_001", ATTR_VOLUME: 0.8, ATTR_DURATION: 4.5},
            {"entity_id": setup.sound.entity_id},
        )
    if action == SERVICE_SET_RULE_STATE:
        return (
            {ATTR_RULE_ID: "00000000-0000-0000-0000-000000000000", ATTR_ENABLED: True},
            None,
        )
    if action == SERVICE_ACTIVATE_VACATION_MODE:
        return (
            {"temperature": 16.0, ATTR_END_TIME: "2026-12-24 18:00"},
            None,
        )
    if action == SERVICE_ACTIVATE_ECO_MODE:
        return ({}, None)
    if action == SERVICE_DEACTIVATE_ABSENCE_MODE:
        return ({}, None)
    if action == SERVICE_ACTIVATE_PARTY_MODE:
        return (
            {"temperature": 21.5, ATTR_DURATION: 3600},
            {"entity_id": setup.climate.entity_id},
        )
    if action == SERVICE_SWITCH_ON_WITH_TIME:
        return (
            {ATTR_ON_TIME: 120.0},
            {"entity_id": setup.switch.entity_id},
        )
    if action == SERVICE_SET_COOLING_MODE:
        return ({ATTR_COOLING: True}, None)
    if action == SERVICE_SEND_API_COMMAND:
        return (
            {
                ATTR_PATH: "/hmip/device/control/setOpticalSignal",
                ATTR_BODY: {
                    "deviceId": "3014F711A00023E0C9A5E9356",
                    "channelIndex": 8,
                    "opticalSignalBehaviour": "FLASH_MIDDLE",
                    "simpleRGBColorState": "PURPLE",
                    "dimLevel": 0.42,
                },
            },
            None,
        )
    if action == SERVICE_USER_MESSAGE:
        return (
            {
                ATTR_USER_MESSAGE_CATEGORY: "INFO",
                ATTR_USER_MESSAGE_ID: "WASHER_FINISHED",
                ATTR_USER_MESSAGE_TITLE: "Washing Machine",
                ATTR_USER_MESSAGE_MESSAGE: "The laundry cycle has finished.",
                ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "ACKNOWLEDGEABLE_BY_OK",
            },
            None,
        )
    if action == SERVICE_USER_MESSAGE_DELETE:
        return ({ATTR_USER_MESSAGE_ID: "WASHER_FINISHED"}, None)
    raise AssertionError(f"Unhandled action {action}")


def _assert_nothing_sent(setup: SimpleNamespace) -> None:
    """Assert that no entity method or client API method was awaited."""
    setup.sound.async_play_sound.assert_not_awaited()
    setup.switch.async_play_sound.assert_not_awaited()
    setup.switch.async_turn_on_with_time.assert_not_awaited()
    setup.climate.async_activate_party_mode.assert_not_awaited()
    for name in (
        "async_enable_simple_rule",
        "async_activate_vacation",
        "async_activate_absence_permanent",
        "async_deactivate_absence",
        "async_send_api_command",
        "async_create_user_message_request",
        "async_delete_user_message_request",
        "async_activate_group_party_mode",
    ):
        getattr(setup.client, name).assert_not_awaited()


def _extract_schema_field_names(schema: Any) -> set[str]:
    """Return the non-target field names defined by a service schema."""
    raw = getattr(schema, "schema", None)
    if isinstance(raw, dict):
        return {getattr(k, "schema", k) for k in raw}
    validators = getattr(raw, "validators", ())
    for validator in validators:
        candidate = getattr(validator, "schema", validator)
        if isinstance(candidate, dict):
            names = {getattr(k, "schema", k) for k in candidate}
            return names - set(cv.TARGET_SERVICE_FIELDS) - {"metadata"}
    raise AssertionError(f"Cannot inspect schema fields from {schema!r}")


@pytest.mark.parametrize(("action", "missing_field"), REQUIRED_FIELDS)
async def test_missing_required_field_is_rejected(
    hass: HomeAssistant, setup: SimpleNamespace, action: str, missing_field: str
) -> None:
    """T1: Every required field from services.yaml fails validation when omitted."""
    data, target = _base_call(action, setup)
    del data[missing_field]

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, action, data, target=target, blocking=True
        )

    _assert_nothing_sent(setup)


@pytest.mark.parametrize(
    ("_bound", "action", "field", "bad_value"), NUMBER_RANGE_OUT_OF_BOUNDS
)
async def test_number_outside_documented_range_is_rejected(
    hass: HomeAssistant,
    setup: SimpleNamespace,
    _bound: str,
    action: str,
    field: str,
    bad_value: float,
) -> None:
    """T2: Values just below min or just above max fail schema validation."""
    data, target = _base_call(action, setup)
    data[field] = bad_value

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, action, data, target=target, blocking=True
        )

    _assert_nothing_sent(setup)


@pytest.mark.parametrize(("action", "field", "limit_value"), NUMBER_RANGE_LIMITS)
async def test_documented_range_limits_are_accepted(
    hass: HomeAssistant,
    setup: SimpleNamespace,
    action: str,
    field: str,
    limit_value: float,
) -> None:
    """T3: Exact min and max boundaries from services.yaml are accepted."""
    data, target = _base_call(action, setup)
    data[field] = limit_value

    await hass.services.async_call(DOMAIN, action, data, target=target, blocking=True)

    if action == SERVICE_PLAY_SOUND:
        assert setup.sound.async_play_sound.await_args.kwargs[field] == limit_value
    elif action == SERVICE_ACTIVATE_VACATION_MODE:
        assert (
            setup.client.async_activate_vacation.await_args.kwargs[field] == limit_value
        )
    elif action == SERVICE_ACTIVATE_PARTY_MODE:
        assert (
            setup.climate.async_activate_party_mode.await_args.kwargs[field]
            == limit_value
        )
    elif action == SERVICE_SWITCH_ON_WITH_TIME:
        assert (
            setup.switch.async_turn_on_with_time.await_args.kwargs[field] == limit_value
        )
    else:
        raise AssertionError(f"Unhandled range check action {action}")


@pytest.mark.parametrize("action", list(SERVICES_YAML))
async def test_unknown_field_is_rejected(
    hass: HomeAssistant, setup: SimpleNamespace, action: str
) -> None:
    """T4: Unknown fields are rejected for every action."""
    data, target = _base_call(action, setup)
    data["bogus"] = 1

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, action, data, target=target, blocking=True
        )

    _assert_nothing_sent(setup)


@pytest.mark.parametrize(
    "overrides",
    [
        {ATTR_USER_MESSAGE_CATEGORY: "info"},
        {ATTR_USER_MESSAGE_CATEGORY: "DEBUG"},
        {ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "LATER"},
        {ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "dismissible"},
    ],
)
async def test_user_message_values_outside_the_list_are_rejected(
    hass: HomeAssistant, setup: SimpleNamespace, overrides: dict[str, str]
) -> None:
    """T5: Disallowed user message categories or behavior types are rejected."""
    data, _ = _base_call(SERVICE_USER_MESSAGE, setup)
    data.update(overrides)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, SERVICE_USER_MESSAGE, data, blocking=True
        )

    _assert_nothing_sent(setup)


@pytest.mark.parametrize(
    ("action", "data_override", "use_switch_target"),
    [
        (
            SERVICE_PLAY_SOUND,
            {ATTR_SOUND_FILE: "SOUNDFILE_001", ATTR_VOLUME: 0.8, ATTR_DURATION: 4.5},
            True,
        ),
        (
            SERVICE_SET_RULE_STATE,
            {ATTR_RULE_ID: "00000000-0000-0000-0000-000000000000", ATTR_ENABLED: True},
            False,
        ),
        (
            SERVICE_ACTIVATE_PARTY_MODE,
            {"temperature": 21.5, ATTR_END_TIME: "2026-12-31 23:00"},
            False,
        ),
        (
            SERVICE_ACTIVATE_VACATION_MODE,
            {"temperature": 16.0, ATTR_END_TIME: "2026-12-24 18:00"},
            False,
        ),
        (SERVICE_ACTIVATE_ECO_MODE, {}, False),
        (SERVICE_DEACTIVATE_ABSENCE_MODE, {}, False),
        (SERVICE_SWITCH_ON_WITH_TIME, {ATTR_ON_TIME: 120.0}, False),
        (SERVICE_SET_COOLING_MODE, {ATTR_COOLING: True}, False),
        (
            SERVICE_SEND_API_COMMAND,
            {
                ATTR_PATH: "/hmip/device/control/setOpticalSignal",
                ATTR_BODY: {
                    "deviceId": "3014F711A00023E0C9A5E9356",
                    "channelIndex": 8,
                    "opticalSignalBehaviour": "FLASH_MIDDLE",
                    "simpleRGBColorState": "PURPLE",
                    "dimLevel": 0.42,
                },
            },
            False,
        ),
        (
            SERVICE_USER_MESSAGE,
            {
                ATTR_USER_MESSAGE_CATEGORY: "INFO",
                ATTR_USER_MESSAGE_ID: "WASHER_FINISHED",
                ATTR_USER_MESSAGE_TITLE: "Washing Machine",
                ATTR_USER_MESSAGE_MESSAGE: "The laundry cycle has finished.",
                ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "ACKNOWLEDGEABLE_BY_OK",
            },
            False,
        ),
        (SERVICE_USER_MESSAGE_DELETE, {ATTR_USER_MESSAGE_ID: "WASHER_FINISHED"}, False),
    ],
)
async def test_documented_examples_still_work(
    hass: HomeAssistant,
    setup: SimpleNamespace,
    action: str,
    data_override: dict[str, Any],
    use_switch_target: bool,
) -> None:
    """T6: All documented action examples pass validation and forward expected values."""
    _, target = _base_call(action, setup)
    if use_switch_target:
        target = {"entity_id": setup.switch.entity_id}

    await hass.services.async_call(
        DOMAIN, action, dict(data_override), target=target, blocking=True
    )

    if action == SERVICE_PLAY_SOUND:
        setup.switch.async_play_sound.assert_awaited_once_with(
            sound_file="SOUNDFILE_001", volume=0.8, duration=4.5
        )
    elif action == SERVICE_SET_RULE_STATE:
        setup.client.async_enable_simple_rule.assert_awaited_once_with(
            rule_id="00000000-0000-0000-0000-000000000000", enabled=True
        )
    elif action == SERVICE_ACTIVATE_PARTY_MODE:
        setup.climate.async_activate_party_mode.assert_awaited_once_with(
            temperature=21.5, end_time_str="2026-12-31 23:00", duration=None
        )
    elif action == SERVICE_ACTIVATE_VACATION_MODE:
        setup.client.async_activate_vacation.assert_awaited_once_with(
            temperature=16.0, end_time="2026_12_24 18:00"
        )
    elif action == SERVICE_ACTIVATE_ECO_MODE:
        setup.client.async_activate_absence_permanent.assert_awaited_once_with()
    elif action == SERVICE_DEACTIVATE_ABSENCE_MODE:
        setup.client.async_deactivate_absence.assert_awaited_once_with()
    elif action == SERVICE_SWITCH_ON_WITH_TIME:
        setup.switch.async_turn_on_with_time.assert_awaited_once_with(on_time=120.0)
    elif action == SERVICE_SET_COOLING_MODE:
        setup.client.async_send_api_command.assert_awaited_once_with(
            path="/hmip/home/heating/setCooling", body={ATTR_COOLING: True}
        )
    elif action == SERVICE_SEND_API_COMMAND:
        setup.client.async_send_api_command.assert_awaited_once_with(
            path=data_override[ATTR_PATH], body=data_override[ATTR_BODY]
        )
    elif action == SERVICE_USER_MESSAGE:
        sent_body = setup.client.async_create_user_message_request.await_args.kwargs[
            "body"
        ]
        assert sent_body["messageCategory"] == "INFO"
        assert sent_body["userMessageId"] == "WASHER_FINISHED"
        assert sent_body["title"] == {"de": "Washing Machine", "en": "Washing Machine"}
        assert sent_body["message"] == {
            "de": "The laundry cycle has finished.",
            "en": "The laundry cycle has finished.",
        }
        assert sent_body["behaviorType"] == "ACKNOWLEDGEABLE_BY_OK"
    elif action == SERVICE_USER_MESSAGE_DELETE:
        setup.client.async_delete_user_message_request.assert_awaited_once_with(
            user_message_id="WASHER_FINISHED"
        )


async def test_values_are_converted(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """T7: String numbers/booleans, comma-separated entity_ids, and unquoted datetimes convert."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_SOUND,
        {
            "entity_id": f"{setup.sound.entity_id}, {setup.switch.entity_id}",
            ATTR_SOUND_FILE: "soundfile_001",
            ATTR_VOLUME: "0.8",
        },
        blocking=True,
    )
    sound_kwargs = setup.sound.async_play_sound.await_args.kwargs
    assert isinstance(sound_kwargs["volume"], float)
    assert sound_kwargs["volume"] == 0.8
    assert sound_kwargs["sound_file"] == "SOUNDFILE_001"
    setup.switch.async_play_sound.assert_awaited_once()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_RULE_STATE,
        {ATTR_RULE_ID: "rule-1", ATTR_ENABLED: "true"},
        blocking=True,
    )
    assert setup.client.async_enable_simple_rule.await_args.kwargs["enabled"] is True

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_COOLING_MODE,
        {ATTR_COOLING: "false"},
        blocking=True,
    )
    assert setup.client.async_send_api_command.await_args.kwargs["body"] == {
        ATTR_COOLING: False
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVATE_VACATION_MODE,
        {"temperature": 21.3, ATTR_END_TIME: datetime(2026, 12, 24, 18, 0)},
        blocking=True,
    )
    assert setup.client.async_activate_vacation.await_args.kwargs == {
        "temperature": 21.3,
        "end_time": "2026_12_24 18:00",
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SWITCH_ON_WITH_TIME,
        {ATTR_ON_TIME: 10},
        target={"entity_id": setup.switch.entity_id},
        blocking=True,
    )
    on_time_arg = setup.switch.async_turn_on_with_time.await_args.kwargs["on_time"]
    assert isinstance(on_time_arg, float)
    assert on_time_arg == 10.0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVATE_PARTY_MODE,
        {"temperature": 21.3, ATTR_DURATION: 3600},
        target={"entity_id": setup.climate.entity_id},
        blocking=True,
    )
    assert (
        setup.climate.async_activate_party_mode.await_args.kwargs["temperature"] == 21.3
    )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_USER_MESSAGE,
        {
            ATTR_USER_MESSAGE_CATEGORY: "WARN",
            ATTR_USER_MESSAGE_ID: "msg-dict",
            ATTR_USER_MESSAGE_TITLE: {"en": "Title", "de": "Titel"},
            ATTR_USER_MESSAGE_MESSAGE: {"en": "Body", "de": "Text"},
            ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
        },
        blocking=True,
    )
    msg_body = setup.client.async_create_user_message_request.await_args.kwargs["body"]
    assert msg_body["title"] == {"en": "Title", "de": "Titel"}
    assert msg_body["message"] == {"en": "Body", "de": "Text"}


async def test_translated_checks_still_reach_the_user(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """T8: Handler-level translated ServiceValidationError checks are preserved."""
    with pytest.raises(ServiceValidationError) as exc_sound:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_SOUND,
            {ATTR_SOUND_FILE: "NOPE"},
            target={"entity_id": setup.sound.entity_id},
            blocking=True,
        )
    assert exc_sound.value.translation_key == "invalid_sound_file"

    group_data = {
        "id": "group-heating-1",
        "type": "HEATING",
        "label": "Living Room",
        "controlMode": "AUTOMATIC",
        "setPointTemperature": 20.0,
        "actualTemperature": 19.5,
        "minTemperature": 5.0,
        "maxTemperature": 30.0,
        "controllable": True,
        "ecoAllowed": True,
        "cooling": False,
        "coolingAllowed": False,
        "coolingIgnored": False,
        "activeProfile": "PROFILE_1",
        "profiles": {
            "PROFILE_1": {
                "index": "PROFILE_1",
                "name": "Standard",
                "enabled": True,
                "visible": True,
            }
        },
        "channels": [],
    }
    climate_coord = SimpleNamespace(
        config_entry=SimpleNamespace(
            entry_id=setup.entry.entry_id,
            domain=DOMAIN,
            data={},
            options={CONF_COMFORT_TEMPERATURE: 21.5},
        ),
        data={group_data["id"]: group_data},
    )
    setup.client.hcu_device_id = "hcu-main"
    setup.client.is_connected = True
    setup.client.state = {
        "home": {"functionalHomes": {"INDOOR_CLIMATE": {"absenceType": "NOT_ABSENT"}}}
    }
    setup.client.get_group_by_id = MagicMock(return_value=group_data)
    real_climate = HcuClimate(
        climate_coord, setup.client, group_data, climate_coord.config_entry
    )
    real_climate.entity_id = setup.climate.entity_id
    real_climate.async_write_ha_state = MagicMock()
    setup.entry.runtime_data.entities[Platform.CLIMATE] = [real_climate]

    with pytest.raises(ServiceValidationError) as exc_party:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_PARTY_MODE,
            {
                "temperature": 21.0,
                ATTR_END_TIME: "2026-12-31 23:00",
                ATTR_DURATION: 3600,
            },
            target={"entity_id": real_climate.entity_id},
            blocking=True,
        )
    assert exc_party.value.translation_key == "party_mode_end_time_and_duration"

    with pytest.raises(ServiceValidationError) as exc_party_missing:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_PARTY_MODE,
            {"temperature": 21.0},
            target={"entity_id": real_climate.entity_id},
            blocking=True,
        )
    assert (
        exc_party_missing.value.translation_key
        == "party_mode_needs_end_time_or_duration"
    )

    with pytest.raises(ServiceValidationError) as exc_all:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_SOUND,
            {ATTR_SOUND_FILE: "SOUNDFILE_001"},
            target={"entity_id": "all"},
            blocking=True,
        )
    assert exc_all.value.translation_key == "entities_not_found"

    with pytest.raises(ServiceValidationError) as exc_vacation:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_ACTIVATE_VACATION_MODE,
            {"temperature": 16.0, ATTR_END_TIME: "not-a-valid-date"},
            blocking=True,
        )
    assert exc_vacation.value.translation_key == "invalid_end_time"

    with pytest.raises(ServiceValidationError) as exc_multilang:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_USER_MESSAGE,
            {
                ATTR_USER_MESSAGE_CATEGORY: "INFO",
                ATTR_USER_MESSAGE_ID: "msg-1",
                ATTR_USER_MESSAGE_TITLE: {"de": "x", "en": 5},
                ATTR_USER_MESSAGE_MESSAGE: {"de": "Hallo", "en": "Hello"},
                ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
            },
            blocking=True,
        )
    assert exc_multilang.value.translation_key == "attribute_invalid_multilang"

    _assert_nothing_sent(setup)


def test_every_action_has_a_schema(hass: HomeAssistant) -> None:
    """T9: Every integration action is registered with an input schema."""
    async_register_services(hass)
    registered = hass.services.async_services_for_domain(DOMAIN)

    assert set(INTEGRATION_SERVICES) == set(SERVICES_YAML)
    for name in INTEGRATION_SERVICES:
        assert registered[name].schema is not None, f"Missing schema for {name}"


@pytest.mark.parametrize("action", list(SERVICES_YAML))
async def test_schema_matches_services_yaml_fields(
    hass: HomeAssistant, setup: SimpleNamespace, action: str
) -> None:
    """T10: Schema field names and services.yaml fields match exactly for every action."""
    service = hass.services.async_services_for_domain(DOMAIN)[action]
    yaml_fields = set((SERVICES_YAML[action].get("fields") or {}).keys())
    if service.schema is not None:
        assert _extract_schema_field_names(service.schema) == yaml_fields

    data, target = _base_call(action, setup)
    if action == SERVICE_ACTIVATE_PARTY_MODE:
        # Both end_time and duration are in services.yaml; schema accepts both.
        data[ATTR_END_TIME] = "2026-12-31 23:00"
    await hass.services.async_call(DOMAIN, action, data, target=target, blocking=True)


async def test_edge_cases_target_null_and_empty_dict(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """Reject missing targets, malformed entity_ids, and null values; allow empty body dict."""
    for action in (
        SERVICE_PLAY_SOUND,
        SERVICE_ACTIVATE_PARTY_MODE,
        SERVICE_SWITCH_ON_WITH_TIME,
    ):
        data, _ = _base_call(action, setup)
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(DOMAIN, action, data, blocking=True)

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_SOUND,
            {ATTR_SOUND_FILE: "SOUNDFILE_001"},
            target={"entity_id": "not-an-entity-id"},
            blocking=True,
        )

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_SOUND,
            {ATTR_SOUND_FILE: "SOUNDFILE_001", ATTR_VOLUME: None},
            target={"entity_id": setup.sound.entity_id},
            blocking=True,
        )

    _assert_nothing_sent(setup)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SEND_API_COMMAND,
        {ATTR_PATH: "/hmip/home/getSystemState", ATTR_BODY: {}},
        blocking=True,
    )
    setup.client.async_send_api_command.assert_awaited_once_with(
        path="/hmip/home/getSystemState", body={}
    )
