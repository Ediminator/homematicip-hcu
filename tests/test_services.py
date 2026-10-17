"""Unit tests for the Homematic IP HCU service handlers."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

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
    hass.data = {DOMAIN: {"entry-1": coordinator}}
    return hass, coordinator, client


@pytest.mark.asyncio
async def test_services_raise_validation_error_when_no_hcu_client() -> None:
    """Verify service handlers raise ServiceValidationError when no HCU is configured."""
    hass = MagicMock()
    hass.data = {DOMAIN: {}}
    call = SimpleNamespace(data={ATTR_RULE_ID: "r1", ATTR_ENABLED: True})

    with pytest.raises(ServiceValidationError):
        await async_handle_set_rule_state(hass, call)

    with pytest.raises(ServiceValidationError):
        await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))

    with pytest.raises(ServiceValidationError):
        await async_handle_deactivate_absence_mode(hass, SimpleNamespace(data={}))


@pytest.mark.asyncio
async def test_services_raise_home_assistant_error_on_api_failure() -> None:
    """Verify service handlers propagate HcuApiError as HomeAssistantError."""
    hass, coordinator, client = _make_hass_with_client()
    client.async_enable_simple_rule.side_effect = HcuApiError("HCU rejected rule")
    client.async_activate_absence_permanent.side_effect = HcuApiError("Eco failed")
    client.async_deactivate_absence.side_effect = ConnectionError("Disconnected")

    with pytest.raises(HomeAssistantError):
        await async_handle_set_rule_state(
            hass, SimpleNamespace(data={ATTR_RULE_ID: "r1", ATTR_ENABLED: True})
        )

    with pytest.raises(HomeAssistantError):
        await async_handle_activate_eco_mode(hass, SimpleNamespace(data={}))

    with pytest.raises(HomeAssistantError):
        await async_handle_deactivate_absence_mode(hass, SimpleNamespace(data={}))


@pytest.mark.asyncio
async def test_service_validation_errors_for_invalid_inputs() -> None:
    """Verify service handlers raise ServiceValidationError on invalid parameters."""
    hass, coordinator, _ = _make_hass_with_client()

    with pytest.raises(ServiceValidationError):
        await async_handle_activate_vacation_mode(
            hass,
            SimpleNamespace(
                data={ATTR_TEMPERATURE: 16.0, ATTR_END_TIME: "not-a-valid-date"}
            ),
        )

    with pytest.raises(ServiceValidationError):
        await async_handle_switch_on_with_time(
            hass, SimpleNamespace(data={ATTR_ENTITY_ID: ["switch.test"]})
        )

    with pytest.raises(ServiceValidationError):
        await async_handle_send_api_command(
            hass, SimpleNamespace(data={ATTR_PATH: "/hmip/test", ATTR_BODY: "invalid"})
        )

    with pytest.raises(ServiceValidationError):
        await async_handle_set_cooling_mode(
            hass, SimpleNamespace(data={ATTR_COOLING: "not_a_bool"})
        )

    with pytest.raises(ServiceValidationError):
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

    with pytest.raises(ServiceValidationError):
        await async_delete_user_message_request(
            hass, SimpleNamespace(data={ATTR_USER_MESSAGE_ID: None})
        )


@pytest.mark.asyncio
async def test_entity_targeted_services_raise_on_failure() -> None:
    """Verify play_sound and activate_party_mode raise errors on incompatible or failing entities."""
    hass, coordinator, _ = _make_hass_with_client()

    # Incompatible / missing entity -> ServiceValidationError
    with pytest.raises(ServiceValidationError):
        await async_handle_play_sound(
            hass,
            SimpleNamespace(
                data={
                    ATTR_ENTITY_ID: ["switch.nonexistent"],
                    ATTR_SOUND_FILE: "SOUND_01",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                }
            ),
        )

    # Failing entity API call -> HomeAssistantError
    climate_entity = MagicMock()
    climate_entity.entity_id = "climate.living_room"
    climate_entity.async_activate_party_mode = AsyncMock(
        side_effect=HcuApiError("Party mode rejected")
    )
    coordinator.entities = {Platform.CLIMATE: [climate_entity]}

    with pytest.raises(HomeAssistantError):
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


@pytest.mark.asyncio
async def test_multi_entity_services_process_all_entities_before_raising() -> None:
    """A failing or incompatible entity must not stop the remaining entities."""
    hass, coordinator, _ = _make_hass_with_client()

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
                    ATTR_SOUND_FILE: "SOUND_01",
                    ATTR_VOLUME: 0.5,
                    ATTR_DURATION: 5,
                }
            ),
        )

    healthy.async_play_sound.assert_awaited_once()
    message = str(exc_info.value)
    assert "light.doorbell_1" in message
    assert "switch.unknown" in message
    assert "light.doorbell_2" not in message

    # All entities succeed -> no exception
    failing.async_play_sound = AsyncMock()
    await async_handle_play_sound(
        hass,
        SimpleNamespace(
            data={
                ATTR_ENTITY_ID: ["light.doorbell_1", "light.doorbell_2"],
                ATTR_SOUND_FILE: "SOUND_01",
                ATTR_VOLUME: 0.5,
                ATTR_DURATION: 5,
            }
        ),
    )
