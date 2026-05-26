# custom_components/hcu_integration/services.py
"""Service handlers for the Homematic IP Local (HCU) integration."""
from __future__ import annotations

import logging
import time
from functools import partial
from typing import Any, TYPE_CHECKING
from collections.abc import Mapping


from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, ServiceCall, split_entity_id
from homeassistant.util import dt as dt_util

from .api import HcuApiClient, HcuApiError
from .const import (
    ATTR_COOLING,
    ATTR_DURATION,
    ATTR_ENABLED,
    ATTR_END_TIME,
    ATTR_ON_TIME,
    ATTR_RULE_ID,
    ATTR_SOUND_FILE,
    ATTR_VOLUME,
    ATTR_PATH,
    ATTR_BODY,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_MESSAGE,
    ATTR_USER_MESSAGE_TITLE,
    ATTR_USER_MESSAGE_BEHAVIOR_TYPE,
    ATTR_USER_MESSAGE_CATEGORY,
    API_PATHS,
    DOMAIN,
    SERVICE_ACTIVATE_ECO_MODE,
    SERVICE_ACTIVATE_PARTY_MODE,
    SERVICE_ACTIVATE_VACATION_MODE,
    SERVICE_DEACTIVATE_ABSENCE_MODE,
    SERVICE_PLAY_SOUND,
    SERVICE_SET_COOLING_MODE,
    SERVICE_SET_RULE_STATE,
    SERVICE_SWITCH_ON_WITH_TIME,
    SERVICE_SEND_API_COMMAND,
    SERVICE_USER_MESSAGE,
    SERVICE_USER_MESSAGE_DELETE,

)

if TYPE_CHECKING:
    from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

# Platform mapping for entity lookup
PLATFORM_MAP = {
    "switch": Platform.SWITCH,
    "light": Platform.LIGHT,
    "climate": Platform.CLIMATE,
    "button": Platform.BUTTON,
}

# Single source of truth for service names
INTEGRATION_SERVICES = [
    SERVICE_PLAY_SOUND,
    SERVICE_SET_RULE_STATE,
    SERVICE_ACTIVATE_PARTY_MODE,
    SERVICE_ACTIVATE_VACATION_MODE,
    SERVICE_ACTIVATE_ECO_MODE,
    SERVICE_DEACTIVATE_ABSENCE_MODE,
    SERVICE_SWITCH_ON_WITH_TIME,
    SERVICE_SEND_API_COMMAND,
    SERVICE_SET_COOLING_MODE,
    SERVICE_USER_MESSAGE,
    SERVICE_USER_MESSAGE_DELETE,
]


def _get_entity_from_entity_id(hass: HomeAssistant, entity_id: str) -> Entity | None:
    """Get entity object from entity_id across all coordinators."""
    entity_domain, _ = split_entity_id(entity_id)
    platform = PLATFORM_MAP.get(entity_domain)

    if not platform:
        return None

    return next(
        (
            entity
            for coordinator in hass.data.get(DOMAIN, {}).values()
            for entity in coordinator.entities.get(platform, [])
            if hasattr(entity, "entity_id") and entity.entity_id == entity_id
        ),
        None,
    )


def _get_client_for_service(hass: HomeAssistant) -> HcuApiClient:
    """Get the API client for service calls."""
    for coordinator in hass.data.get(DOMAIN, {}).values():
        return coordinator.client
    raise ValueError("No HCU client available")


async def async_handle_play_sound(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the play_sound service call."""
    for entity_id in call.data[ATTR_ENTITY_ID]:
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity or not hasattr(entity, "async_play_sound"):
            _LOGGER.warning(
                "Cannot play sound on %s: not a compatible HCU device with sound capability",
                entity_id,
            )
            continue

        try:
            await entity.async_play_sound(
                sound_file=call.data[ATTR_SOUND_FILE],
                volume=call.data[ATTR_VOLUME],
                duration=call.data[ATTR_DURATION],
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Error playing sound on %s: %s", entity_id, err)


async def async_handle_set_rule_state(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_rule_state service call."""
    rule_id = call.data[ATTR_RULE_ID]
    enabled = call.data[ATTR_ENABLED]

    try:
        client = _get_client_for_service(hass)
        await client.async_enable_simple_rule(rule_id=rule_id, enabled=enabled)
        _LOGGER.info("Set rule %s state to %s", rule_id, enabled)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error setting rule %s state: %s", rule_id, err)
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)


async def async_handle_activate_party_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the activate_party_mode service call."""
    for entity_id in call.data[ATTR_ENTITY_ID]:
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity or not hasattr(entity, "async_activate_party_mode"):
            _LOGGER.warning(
                "Cannot activate party mode on %s: not a compatible HCU climate entity",
                entity_id,
            )
            continue

        try:
            await entity.async_activate_party_mode(
                temperature=call.data[ATTR_TEMPERATURE],
                end_time_str=call.data.get(ATTR_END_TIME),
                duration=call.data.get(ATTR_DURATION),
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Error activating party mode on %s: %s", entity_id, err)
        except ValueError as err:
            _LOGGER.error("Invalid parameter for party mode on %s: %s", entity_id, err)


async def async_handle_activate_vacation_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the activate_vacation_mode service call."""
    try:
        client = _get_client_for_service(hass)
        end_time_str = call.data[ATTR_END_TIME]
        
        # Parse the datetime string provided by user
        dt_obj = dt_util.parse_datetime(end_time_str)
        if dt_obj is None:
            raise ValueError(f"Invalid datetime string for end_time: {end_time_str}")
        
        # HCU API expects format 'YYYY_%m_%d %H:%M'
        formatted_end_time = dt_obj.strftime("%Y_%m_%d %H:%M")
        
        await client.async_activate_vacation(
            temperature=call.data[ATTR_TEMPERATURE],
            end_time=formatted_end_time,
        )
        _LOGGER.info("Activated vacation mode until %s", end_time_str)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error activating vacation mode: %s", err)
    except ValueError as err:
        _LOGGER.error("Invalid parameter for vacation mode: %s", err)


async def async_handle_activate_eco_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the activate_eco_mode service call."""
    try:
        client = _get_client_for_service(hass)
        await client.async_activate_absence_permanent()
        _LOGGER.info("Activated eco mode")
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error activating eco mode: %s", err)
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)


async def async_handle_deactivate_absence_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the deactivate_absence_mode service call."""
    try:
        client = _get_client_for_service(hass)
        await client.async_deactivate_absence()
        _LOGGER.info("Deactivated absence mode")
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error deactivating absence mode: %s", err)
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)

async def async_handle_switch_on_with_time(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the switch_on_with_time service call."""
    on_time = call.data.get(ATTR_ON_TIME)
    if on_time is None:
        _LOGGER.error("Required attribute '%s' missing for switch_on_with_time", ATTR_ON_TIME)
        return

    for entity_id in call.data.get(ATTR_ENTITY_ID, []):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity:
            _LOGGER.warning("Entity %s not found", entity_id)
            continue

        if not hasattr(entity, "async_turn_on_with_time"):
            _LOGGER.warning("Entity %s does not support timed on", entity_id)
            continue

        try:
            await entity.async_turn_on_with_time(on_time=on_time)
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Error calling switch_on_with_time for %s: %s", entity_id, err)

async def async_handle_send_api_command(hass: HomeAssistant, call: ServiceCall) -> None:
    body = call.data.get(ATTR_BODY)
    path = call.data.get(ATTR_PATH)

    if not isinstance(body, dict):
        if body is None:
            _LOGGER.error("Required attribute '%s' missing for send_api_command", ATTR_BODY)
        else:
            _LOGGER.error("Attribute '%s' must be an object/dictionary for send_api_command", ATTR_BODY)
        return

    if not isinstance(path, str):
        if path is None:
            _LOGGER.error("Required attribute '%s' missing for send_api_command", ATTR_PATH)
        else:
            _LOGGER.error("Attribute '%s' must be a string for send_api_command", ATTR_PATH)
        return
    
    try:
        client = _get_client_for_service(hass)
        await client.async_send_api_command(
            path=path,
            body=body,
        )
        
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error calling send_api_command for path %s: %s", path, err)
    


async def async_handle_set_cooling_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_cooling_mode service call."""
    cooling = call.data.get(ATTR_COOLING)

    if not isinstance(cooling, bool):
        _LOGGER.error("Required attribute '%s' must be a boolean for set_cooling_mode", ATTR_COOLING)
        return

    try:
        client = _get_client_for_service(hass)
        await client.async_send_api_command(
            path=API_PATHS["SET_COOLING"],
            body={ATTR_COOLING: cooling},
        )
        _LOGGER.info("Set cooling mode to %s", cooling)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error setting cooling mode: %s", err)
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)


def _as_multilang(value: Any, field_name: str) -> dict[str, str] | None:
    """Return value as multilingual dict.

    - dict -> unchanged
    - str -> build {"de": value, "en": value}
    """
    if isinstance(value, str):
        return {
            "de": value,
            "en": value,
        }

    if isinstance(value, Mapping):
        if not all(isinstance(k, str) for k in value):
            _LOGGER.error("All keys in '%s' must be strings", field_name)
            return None

        if not all(isinstance(v, str) for v in value.values()):
            _LOGGER.error("All values in '%s' must be strings", field_name)
            return None

        return dict(value)

    _LOGGER.error("Attribute '%s' must be either a string or a dictionary", field_name)
    return None


async def async_create_user_message_request(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    user_message_id = call.data.get(ATTR_USER_MESSAGE_ID)
    raw_message = call.data.get(ATTR_USER_MESSAGE_MESSAGE)
    raw_title = call.data.get(ATTR_USER_MESSAGE_TITLE)
    behavior_type = call.data.get(ATTR_USER_MESSAGE_BEHAVIOR_TYPE)
    message_category = call.data.get(ATTR_USER_MESSAGE_CATEGORY)

    title = _as_multilang(raw_title, ATTR_USER_MESSAGE_TITLE)
    if title is None:
        return

    message = _as_multilang(raw_message, ATTR_USER_MESSAGE_MESSAGE)
    if message is None:
        return

    body = {
        "messageCategory": message_category,
        "userMessageId": user_message_id,
        "title": title,
        "message": message,
        "behaviorType": behavior_type,
        "timestamp": int(time.time()),
    }

    try:
        client = _get_client_for_service(hass)
        await client.async_create_user_message_request(body=body)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error calling create_user_message_request: %s", err)
    
async def async_delete_user_message_request(hass: HomeAssistant, call: ServiceCall) -> None:
    user_message_id = call.data.get(ATTR_USER_MESSAGE_ID)

    if not isinstance(user_message_id, str):
        if user_message_id is None:
            _LOGGER.error("Required attribute '%s' missing for delete_user_message_request", ATTR_USER_MESSAGE_ID)
        else:
            _LOGGER.error("Attribute '%s' must be a string for delete_user_message_request", ATTR_USER_MESSAGE_ID)
        return
    
    try:
        client = _get_client_for_service(hass)
        await client.async_delete_user_message_request(
            user_message_id=user_message_id,
        )
        
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error calling delete_user_message_request for ID %s: %s", user_message_id, err)
        
def async_register_services(hass: HomeAssistant) -> None:
    """Register all HCU integration services."""
    service_handlers = {
        SERVICE_PLAY_SOUND: async_handle_play_sound,
        SERVICE_SET_RULE_STATE: async_handle_set_rule_state,
        SERVICE_ACTIVATE_PARTY_MODE: async_handle_activate_party_mode,
        SERVICE_ACTIVATE_VACATION_MODE: async_handle_activate_vacation_mode,
        SERVICE_ACTIVATE_ECO_MODE: async_handle_activate_eco_mode,
        SERVICE_DEACTIVATE_ABSENCE_MODE: async_handle_deactivate_absence_mode,
        SERVICE_SWITCH_ON_WITH_TIME: async_handle_switch_on_with_time,
        SERVICE_SEND_API_COMMAND: async_handle_send_api_command,
        SERVICE_SET_COOLING_MODE: async_handle_set_cooling_mode,
        SERVICE_USER_MESSAGE: async_create_user_message_request,
        SERVICE_USER_MESSAGE_DELETE: async_delete_user_message_request,
    }

    assert set(service_handlers.keys()) == set(INTEGRATION_SERVICES), \
        "Service handler keys must match INTEGRATION_SERVICES list"

    for service_name, handler in service_handlers.items():
        hass.services.async_register(
            DOMAIN,
            service_name,
            partial(handler, hass),
        )

    _LOGGER.debug("Registered %d HCU services", len(service_handlers))
    
def async_unregister_services(hass: HomeAssistant) -> None:
    """Unregister all HCU integration services."""
    for service_name in INTEGRATION_SERVICES:
        hass.services.async_remove(DOMAIN, service_name)

    _LOGGER.debug("Unregistered HCU services")
