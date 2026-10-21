"""Unit tests for the Homematic IP HCU service handlers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    ATTR_BODY,
    ATTR_COOLING,
    ATTR_DURATION,
    ATTR_ENABLED,
    ATTR_END_TIME,
    ATTR_PATH,
    ATTR_RULE_ID,
    ATTR_SOUND_FILE,
    ATTR_USER_MESSAGE_BEHAVIOR_TYPE,
    ATTR_USER_MESSAGE_CATEGORY,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_MESSAGE,
    ATTR_USER_MESSAGE_TITLE,
    ATTR_VOLUME,
    DOMAIN,
)
from custom_components.hcu_integration.services import (
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
)
from custom_components.hcu_integration.switch import HcuSwitch


def _make_hass_with_client() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Create a mock hass instance with a single coordinator and client."""
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


@pytest.mark.asyncio
async def test_services_raise_validation_error_when_no_hcu_client() -> None:
    """Verify service handlers raise ServiceValidationError when no HCU is configured."""
    hass = MagicMock()
    hass.config_entries.async_entries.return_value = []
    call = SimpleNamespace(data={ATTR_RULE_ID: "r1", ATTR_ENABLED: True})

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_set_rule_state(hass, call)
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_hcu_available"
    assert exc_info.value.translation_placeholders == {
        "error": "No HCU client available"
    }

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_hcu_available"
    assert exc_info.value.translation_placeholders == {
        "error": "No HCU client available"
    }

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_deactivate_absence_mode(hass, SimpleNamespace(data={}))
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_hcu_available"
    assert exc_info.value.translation_placeholders == {
        "error": "No HCU client available"
    }


@pytest.mark.asyncio
async def test_services_raise_home_assistant_error_on_api_failure() -> None:
    """Verify service handlers propagate HcuApiError as HomeAssistantError."""
    hass, _coordinator, client = _make_hass_with_client()
    client.async_enable_simple_rule.side_effect = HcuApiError("HCU rejected rule")
    client.async_activate_absence_permanent.side_effect = HcuApiError("Eco failed")
    client.async_deactivate_absence.side_effect = ConnectionError("Disconnected")

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_set_rule_state(
            hass, SimpleNamespace(data={ATTR_RULE_ID: "r1", ATTR_ENABLED: True})
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "set_rule_state_failed"
    assert exc_info.value.translation_placeholders == {
        "rule_id": "r1",
        "error": "HCU rejected rule",
    }

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "activate_eco_failed"
    assert exc_info.value.translation_placeholders == {"error": "Eco failed"}

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_deactivate_absence_mode(hass, SimpleNamespace(data={}))
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "deactivate_absence_failed"
    assert exc_info.value.translation_placeholders == {"error": "Disconnected"}


@pytest.mark.asyncio
async def test_service_validation_errors_for_invalid_inputs() -> None:
    """Verify service handlers raise ServiceValidationError on invalid parameters."""
    hass, _coordinator, _ = _make_hass_with_client()

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_activate_vacation_mode(
            hass,
            SimpleNamespace(
                data={ATTR_TEMPERATURE: 16.0, ATTR_END_TIME: "not-a-valid-date"}
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "invalid_end_time"
    assert exc_info.value.translation_placeholders == {"value": "not-a-valid-date"}

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_switch_on_with_time(
            hass, SimpleNamespace(data={ATTR_ENTITY_ID: ["switch.test"]})
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "attribute_required"
    assert exc_info.value.translation_placeholders == {
        "attribute": "on_time",
        "action": "switch_on_with_time",
    }

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_send_api_command(
            hass, SimpleNamespace(data={ATTR_PATH: "/hmip/test", ATTR_BODY: "invalid"})
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "attribute_invalid_dict"
    assert exc_info.value.translation_placeholders == {
        "attribute": "body",
        "action": "send_api_command",
    }

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_set_cooling_mode(
            hass, SimpleNamespace(data={ATTR_COOLING: "not_a_bool"})
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "attribute_invalid_bool"
    assert exc_info.value.translation_placeholders == {
        "attribute": "cooling",
        "action": "set_cooling_mode",
    }

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_create_user_message_request(
            hass,
            SimpleNamespace(
                data={
                    ATTR_USER_MESSAGE_ID: "msg-1",
                    ATTR_USER_MESSAGE_TITLE: 123,
                    ATTR_USER_MESSAGE_MESSAGE: "Hello",
                    ATTR_USER_MESSAGE_BEHAVIOR_TYPE: "DISMISSIBLE",
                    ATTR_USER_MESSAGE_CATEGORY: "INFO",
                }
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "attribute_invalid_multilang"
    assert exc_info.value.translation_placeholders == {"attribute": "title"}

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_delete_user_message_request(
            hass, SimpleNamespace(data={ATTR_USER_MESSAGE_ID: None})
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "attribute_invalid_string"
    assert exc_info.value.translation_placeholders == {
        "attribute": "user_message_id",
        "action": "delete_user_message_request",
    }


@pytest.mark.asyncio
async def test_entity_targeted_services_raise_on_failure() -> None:
    """Verify play_sound and activate_party_mode raise errors on incompatible or failing entities."""
    hass, coordinator, _ = _make_hass_with_client()

    # Incompatible / missing entity -> ServiceValidationError
    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["switch.nonexistent"],
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                }
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_not_found"
    assert "switch.nonexistent" in exc_info.value.translation_placeholders["entities"]

    # Failing entity API call -> HomeAssistantError
    climate_entity = MagicMock()
    climate_entity.entity_id = "climate.living_room"
    climate_entity.async_activate_party_mode = AsyncMock(
        side_effect=HcuApiError("Party mode rejected")
    )
    coordinator.entities = {Platform.CLIMATE: [climate_entity]}

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["climate.living_room"],
                    ATTR_TEMPERATURE: 21.0,
                    ATTR_DURATION: 3600,
                }
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_failed"
    assert "climate.living_room" in exc_info.value.translation_placeholders["entities"]


@pytest.mark.asyncio
async def test_multi_entity_services_process_all_entities_before_raising(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A failing or incompatible entity must not stop the remaining entities."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    client = MagicMock()
    coordinator = MagicMock()
    coordinator.client = client
    coordinator.entities = {}
    mock_config_entry.runtime_data = coordinator

    failing = MagicMock()
    failing.entity_id = "light.doorbell_1"
    failing.async_play_sound = AsyncMock(side_effect=HcuApiError("offline"))
    healthy = MagicMock()
    healthy.entity_id = "light.doorbell_2"
    healthy.async_play_sound = AsyncMock()
    coordinator.entities = {Platform.LIGHT: [failing, healthy]}

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: [
                        "light.doorbell_1",
                        "switch.unknown",
                        "light.doorbell_2",
                    ],
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                }
            ),
        )

    healthy.async_play_sound.assert_awaited_once()
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_failed"
    assert "light.doorbell_1" in exc_info.value.translation_placeholders["entities"]
    assert (
        "switch.unknown (not found)"
        in exc_info.value.translation_placeholders["entities"]
    )
    assert "light.doorbell_2" not in exc_info.value.translation_placeholders["entities"]

    # All entities succeed -> no exception
    failing.async_play_sound = AsyncMock()
    await async_handle_play_sound(
        hass,
        SimpleNamespace(
            data={
                ATTR_ENTITY_ID: ["light.doorbell_1", "light.doorbell_2"],
                ATTR_SOUND_FILE: "SOUNDFILE_001",
                ATTR_VOLUME: 0.5,
                ATTR_DURATION: 5,
            }
        ),
    )


@pytest.mark.asyncio
async def test_switch_on_with_time_reports_hcu_rejection_from_real_entity() -> None:
    """A real HcuSwitch whose client rejects the call must make the action fail.

    The entity restores its state and re-raises, so the action does not look
    successful, and the other targeted entity is still switched on.
    """
    hass, coordinator, _ = _make_hass_with_client()

    device = {
        "id": "3014F711A000000000000001",
        "label": "Pump",
        "type": "PLUGABLE_SWITCH",
        "permanentlyReachable": True,
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "label": "Pump",
                "on": False,
            },
        },
    }
    entity_client = MagicMock()
    entity_client.get_device_by_address = MagicMock(return_value=device)
    entity_client.async_set_switch_state = AsyncMock(
        side_effect=HcuApiError("rejected")
    )
    entity_coordinator = MagicMock()
    entity_coordinator.config_entry.data = {}
    entity_coordinator.config_entry.options = {}

    failing = HcuSwitch(entity_coordinator, entity_client, device, "1")
    failing.entity_id = "switch.pump"
    failing.async_write_ha_state = MagicMock()

    healthy = MagicMock()
    healthy.entity_id = "switch.light"
    healthy.async_turn_on_with_time = AsyncMock()
    coordinator.entities = {Platform.SWITCH: [failing, healthy]}

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_switch_on_with_time(
            hass,
            SimpleNamespace(
                data={ATTR_ENTITY_ID: ["switch.pump", "switch.light"], "on_time": 30}
            ),
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_failed"
    assert "switch.pump" in exc_info.value.translation_placeholders["entities"]
    assert failing.is_on is False  # optimistic state restored
    healthy.async_turn_on_with_time.assert_awaited_once_with(on_time=30)


@pytest.mark.asyncio
async def test_entity_targeted_actions_accept_single_string_entity_id() -> None:
    """A single entity_id passed as a plain string must not be split into characters."""
    hass, coordinator, _ = _make_hass_with_client()
    climate_entity = MagicMock()
    climate_entity.entity_id = "climate.keller"
    climate_entity.async_activate_party_mode = AsyncMock()
    coordinator.entities = {Platform.CLIMATE: [climate_entity]}

    await async_handle_activate_party_mode(
        hass,
        SimpleNamespace(
            service="activate_party_mode",
            data={
                ATTR_ENTITY_ID: "climate.keller",
                ATTR_TEMPERATURE: 21.0,
                ATTR_DURATION: 3600,
            },
        ),
    )
    climate_entity.async_activate_party_mode.assert_awaited_once()


@pytest.mark.asyncio
async def test_entity_targeted_actions_require_entity_id() -> None:
    """Missing entity_id (e.g. device or area target only) raises a validation error."""
    hass, _, _ = _make_hass_with_client()

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                service="play_sound",
                data={
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                },
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_entity_specified"
    assert exc_info.value.translation_placeholders == {"service": "play_sound"}

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                service="activate_party_mode",
                data={ATTR_TEMPERATURE: 21.0, ATTR_DURATION: 3600},
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_entity_specified"
    assert exc_info.value.translation_placeholders == {"service": "activate_party_mode"}

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_switch_on_with_time(
            hass, SimpleNamespace(service="switch_on_with_time", data={"on_time": 5})
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "no_entity_specified"
    assert exc_info.value.translation_placeholders == {"service": "switch_on_with_time"}


@pytest.mark.asyncio
async def test_malformed_entity_id_is_reported_not_crashing() -> None:
    """An invalid entity ID is reported as a validation error, not a ValueError."""
    hass, _, _ = _make_hass_with_client()
    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                service="play_sound",
                data={
                    ATTR_ENTITY_ID: ["not-an-entity-id"],
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                },
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_not_found"
    assert "not-an-entity-id" in exc_info.value.translation_placeholders["entities"]


@pytest.mark.asyncio
async def test_multi_entity_mixed_invalid_reasons_raises_entities_invalid(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """When invalid entities have mixed reasons, entities_invalid is raised with all entity ids."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    client = MagicMock()
    coordinator = MagicMock()
    coordinator.client = client
    coordinator.entities = {}
    mock_config_entry.runtime_data = coordinator

    # switch.no_sound exists but lacks async_play_sound (reason: no_sound)
    switch_entity = MagicMock()
    switch_entity.entity_id = "switch.no_sound"
    del switch_entity.async_play_sound
    coordinator.entities = {Platform.SWITCH: [switch_entity]}

    # switch.missing does not exist (reason: not_found)
    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["switch.no_sound", "switch.missing"],
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                }
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_invalid"
    assert (
        "switch.no_sound (no sound capability)"
        in exc_info.value.translation_placeholders["entities"]
    )
    assert (
        "switch.missing (not found)"
        in exc_info.value.translation_placeholders["entities"]
    )


@pytest.mark.asyncio
async def test_multi_entity_mixed_reasons_german_translation(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """When invalid entities have mixed reasons and language is German, German reasons are composed."""
    hass.config.language = "de"
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    client = MagicMock()
    coordinator = MagicMock()
    coordinator.client = client
    coordinator.entities = {}
    mock_config_entry.runtime_data = coordinator

    # switch.no_sound exists but lacks async_play_sound (reason: no_sound)
    switch_entity = MagicMock()
    switch_entity.entity_id = "switch.no_sound"
    del switch_entity.async_play_sound
    coordinator.entities = {Platform.SWITCH: [switch_entity]}

    # switch.missing does not exist (reason: not_found)
    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                service="play_sound",
                data={
                    ATTR_ENTITY_ID: ["switch.no_sound", "switch.missing"],
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                },
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_invalid"
    entities_text = exc_info.value.translation_placeholders["entities"]
    assert "switch.no_sound (keine Tonausgabe)" in entities_text
    assert "switch.missing (nicht gefunden)" in entities_text


@pytest.mark.asyncio
async def test_activate_party_mode_without_end_time_or_duration_names_missing_fields() -> (
    None
):
    """Calling activate_party_mode without end_time or duration raises party_mode_needs_end_time_or_duration."""
    hass, coordinator, _ = _make_hass_with_client()
    climate_entity = MagicMock()
    climate_entity.entity_id = "climate.living_room"
    climate_entity.async_activate_party_mode = AsyncMock(
        side_effect=ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="party_mode_needs_end_time_or_duration",
        )
    )
    coordinator.entities = {Platform.CLIMATE: [climate_entity]}

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                service="activate_party_mode",
                data={
                    ATTR_ENTITY_ID: ["climate.living_room"],
                    ATTR_TEMPERATURE: 21.0,
                },
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "party_mode_needs_end_time_or_duration"


@pytest.mark.asyncio
async def test_single_entity_not_found_gives_entities_not_found() -> None:
    """Targeting a single nonexistent entity raises entities_not_found specifically."""
    hass, _coordinator, _ = _make_hass_with_client()

    with pytest.raises(ServiceValidationError) as exc_info:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                service="activate_party_mode",
                data={
                    ATTR_ENTITY_ID: ["climate.nonexistent"],
                    ATTR_TEMPERATURE: 21.0,
                    ATTR_DURATION: 3600,
                },
            ),
        )
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_not_found"
    assert "climate.nonexistent" in exc_info.value.translation_placeholders["entities"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("end_time", "expected"),
    [
        ("2026-12-31 18:00", "2026_12_31 18:00"),
        # The HCU's own format is accepted as well.
        ("2026_12_31 18:00", "2026_12_31 18:00"),
        # An offset is converted to Home Assistant's local time (UTC here).
        ("2026-12-31T18:00:00+01:00", "2026_12_31 17:00"),
    ],
)
async def test_vacation_mode_end_time_is_sent_in_hcu_format(
    end_time: str, expected: str
) -> None:
    hass, _coordinator, client = _make_hass_with_client()
    previous = dt_util.get_default_time_zone()
    dt_util.set_default_time_zone(dt_util.UTC)
    try:
        await async_handle_activate_vacation_mode(
            hass,
            SimpleNamespace(data={ATTR_TEMPERATURE: 16.0, ATTR_END_TIME: end_time}),
        )
    finally:
        dt_util.set_default_time_zone(previous)

    assert client.async_activate_vacation.await_args.kwargs["end_time"] == expected


@pytest.mark.asyncio
async def test_service_error_aggregation_multiple_entities_play_sound(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_handle_play_sound aggregates errors across entities without aborting early."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    client = MagicMock()
    coordinator = MagicMock()
    coordinator.client = client
    mock_config_entry.runtime_data = coordinator

    entity1 = MagicMock()
    entity1.entity_id = "switch.sound1"
    entity1.async_play_sound = AsyncMock(
        side_effect=HomeAssistantError("Device unreachable")
    )

    entity2 = MagicMock()
    entity2.entity_id = "switch.sound2"
    entity2.async_play_sound = AsyncMock(return_value=None)

    entity3 = MagicMock()
    entity3.entity_id = "switch.sound3"
    entity3.async_play_sound = AsyncMock(side_effect=HcuApiError("API error"))

    coordinator.entities = {Platform.SWITCH: [entity1, entity2, entity3]}

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                service="play_sound",
                data={
                    ATTR_ENTITY_ID: ["switch.sound1", "switch.sound2", "switch.sound3"],
                    ATTR_SOUND_FILE: "SOUNDFILE_001",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                },
            ),
        )

    # All three entities were invoked despite entity1 failing
    entity1.async_play_sound.assert_awaited_once()
    entity2.async_play_sound.assert_awaited_once()
    entity3.async_play_sound.assert_awaited_once()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_failed"
    assert "switch.sound1" in exc_info.value.translation_placeholders["entities"]
    assert "switch.sound3" in exc_info.value.translation_placeholders["entities"]


@pytest.mark.asyncio
async def test_service_error_aggregation_mixed_validation_and_api_error_switch_on_with_time(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_handle_switch_on_with_time aggregates invalid and failed entities."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    client = MagicMock()
    coordinator = MagicMock()
    coordinator.client = client
    mock_config_entry.runtime_data = coordinator

    # entity1 succeeds
    entity1 = MagicMock()
    entity1.entity_id = "switch.ok"
    entity1.async_turn_on_with_time = AsyncMock(return_value=None)

    # entity2 fails with HomeAssistantError
    entity2 = MagicMock()
    entity2.entity_id = "switch.fail"
    entity2.async_turn_on_with_time = AsyncMock(
        side_effect=HomeAssistantError("Timeout")
    )

    coordinator.entities = {Platform.SWITCH: [entity1, entity2]}

    # Target switch.ok, switch.fail, and switch.missing (which causes invalid target)
    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_switch_on_with_time(
            hass,
            SimpleNamespace(
                service="switch_on_with_time",
                data={
                    ATTR_ENTITY_ID: ["switch.ok", "switch.fail", "switch.missing"],
                    "on_time": 60,
                },
            ),
        )

    entity1.async_turn_on_with_time.assert_awaited_once()
    entity2.async_turn_on_with_time.assert_awaited_once()

    # When both invalid and failed exist, _raise_collected_errors raises entities_failed listing both
    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_failed"
    assert "switch.fail" in exc_info.value.translation_placeholders["entities"]
    assert "switch.missing" in exc_info.value.translation_placeholders["entities"]


@pytest.mark.asyncio
async def test_service_error_aggregation_activate_party_mode(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test async_handle_activate_party_mode aggregates errors and invokes all entities."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    client = MagicMock()
    coordinator = MagicMock()
    coordinator.client = client
    mock_config_entry.runtime_data = coordinator

    c1 = MagicMock()
    c1.entity_id = "climate.c1"
    c1.async_activate_party_mode = AsyncMock(
        side_effect=HomeAssistantError("Party mode failed")
    )

    c2 = MagicMock()
    c2.entity_id = "climate.c2"
    c2.async_activate_party_mode = AsyncMock(return_value=None)

    coordinator.entities = {Platform.CLIMATE: [c1, c2]}

    with pytest.raises(HomeAssistantError) as exc_info:
        await async_handle_activate_party_mode(
            hass,
            SimpleNamespace(
                service="activate_party_mode",
                data={
                    ATTR_ENTITY_ID: ["climate.c1", "climate.c2"],
                    ATTR_TEMPERATURE: 21.0,
                    ATTR_DURATION: 3600,
                },
            ),
        )

    c1.async_activate_party_mode.assert_awaited_once()
    c2.async_activate_party_mode.assert_awaited_once()
    assert exc_info.value.translation_key == "entities_failed"


async def test_play_sound_validates_sound_file(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Only sound files the HCU accepts (Connect API 6.8.1.30) are sent."""
    mock_config_entry.add_to_hass(hass)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    coordinator = MagicMock()
    chime = MagicMock()
    chime.entity_id = "light.doorbell"
    chime.async_play_sound = AsyncMock()
    coordinator.entities = {Platform.LIGHT: [chime]}
    mock_config_entry.runtime_data = coordinator

    def call(sound_file: str) -> SimpleNamespace:
        return SimpleNamespace(
            data={
                ATTR_ENTITY_ID: ["light.doorbell"],
                ATTR_SOUND_FILE: sound_file,
                ATTR_VOLUME: 0.5,
                ATTR_DURATION: 5,
            }
        )

    for invalid in ("SOUND_01", "ALARM_01", "SOUNDFILE_000", "SOUNDFILE_253", ""):
        with pytest.raises(ServiceValidationError) as exc_info:
            await async_handle_play_sound(hass, call(invalid))
        assert exc_info.value.translation_key == "invalid_sound_file"
        assert exc_info.value.translation_placeholders == {"value": invalid}
    chime.async_play_sound.assert_not_awaited()

    for valid in (
        "INTERNAL_SOUNDFILE",
        "RANDOM_SOUNDFILE",
        "SOUNDFILE_001",
        "SOUNDFILE_252",
    ):
        chime.async_play_sound.reset_mock()
        await async_handle_play_sound(hass, call(valid))
        assert chime.async_play_sound.await_args.kwargs["sound_file"] == valid

    # Lowercase input is accepted and sent in the form the HCU expects.
    chime.async_play_sound.reset_mock()
    await async_handle_play_sound(hass, call(" soundfile_007 "))
    assert chime.async_play_sound.await_args.kwargs["sound_file"] == "SOUNDFILE_007"
