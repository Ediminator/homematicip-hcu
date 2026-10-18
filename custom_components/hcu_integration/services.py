# custom_components/hcu_integration/services.py
"""Service handlers for the Homematic IP Local (HCU) integration."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from functools import partial
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, ServiceCall, split_entity_id
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util

from .api import HcuApiClient, HcuApiError
from .const import (
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
    ATTR_VOLUME,
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
    try:
        entity_domain, _ = split_entity_id(entity_id)
    except ValueError:
        return None
    platform = PLATFORM_MAP.get(entity_domain)

    if not platform:
        return None

    return next(
        (
            entity
            for entry in hass.config_entries.async_loaded_entries(DOMAIN)
            for entity in entry.runtime_data.entities.get(platform, [])
            if hasattr(entity, "entity_id") and entity.entity_id == entity_id
        ),
        None,
    )


def _extract_entity_ids(call: ServiceCall) -> list[str]:
    """Return the targeted entity IDs as a list.

    Scripts and automations often pass a single entity as a plain string;
    iterating over that string would yield single characters.
    """
    raw = call.data.get(ATTR_ENTITY_ID)
    if isinstance(raw, str):
        entity_ids = [e.strip() for e in raw.split(",") if e.strip()]
    elif isinstance(raw, (list, tuple, set)):
        entity_ids = [str(e) for e in raw if e]
    else:
        entity_ids = []
    if not entity_ids:
        raise ServiceValidationError(
            f"No entity_id given for {call.service}. Target one or more entities "
            "(device and area targets are not supported by this action)."
        )
    return entity_ids


def _get_client_for_service(hass: HomeAssistant) -> HcuApiClient:
    """Get the API client for service calls."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        return entry.runtime_data.client
    raise ValueError("No HCU client available")


def _raise_collected_errors(
    service: str, invalid: list[str], failed: list[str]
) -> None:
    """Raise one error after all targeted entities were processed.

    Entities that are incompatible or not found are validation problems
    (ServiceValidationError). If any entity failed while talking to the HCU,
    a HomeAssistantError is raised that lists every problem.
    """
    if failed:
        raise HomeAssistantError(
            f"{service} failed for: " + "; ".join(failed + invalid)
        )
    if invalid:
        raise ServiceValidationError(
            f"{service} could not be applied to: " + "; ".join(invalid)
        )


async def async_handle_play_sound(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the play_sound service call."""
    invalid: list[str] = []
    failed: list[str] = []
    for entity_id in _extract_entity_ids(call):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity or not hasattr(entity, "async_play_sound"):
            _LOGGER.warning(
                "Cannot play sound on %s: not a compatible HCU device with sound capability",
                entity_id,
            )
            invalid.append(f"{entity_id} (no sound capability)")
            continue

        try:
            await entity.async_play_sound(
                sound_file=call.data[ATTR_SOUND_FILE],
                volume=call.data[ATTR_VOLUME],
                duration=call.data[ATTR_DURATION],
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Error playing sound on %s: %s", entity_id, err)
            failed.append(f"{entity_id} ({err})")

    _raise_collected_errors(SERVICE_PLAY_SOUND, invalid, failed)


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
        raise HomeAssistantError(f"Error setting rule {rule_id} state: {err}") from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(f"No HCU available: {err}") from err


async def async_handle_activate_party_mode(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the activate_party_mode service call."""
    invalid: list[str] = []
    failed: list[str] = []
    for entity_id in _extract_entity_ids(call):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity or not hasattr(entity, "async_activate_party_mode"):
            _LOGGER.warning(
                "Cannot activate party mode on %s: not a compatible HCU climate entity",
                entity_id,
            )
            invalid.append(f"{entity_id} (not an HCU climate entity)")
            continue

        try:
            await entity.async_activate_party_mode(
                temperature=call.data[ATTR_TEMPERATURE],
                end_time_str=call.data.get(ATTR_END_TIME),
                duration=call.data.get(ATTR_DURATION),
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Error activating party mode on %s: %s", entity_id, err)
            failed.append(f"{entity_id} ({err})")
        except ValueError as err:
            _LOGGER.error("Invalid parameter for party mode on %s: %s", entity_id, err)
            invalid.append(f"{entity_id} ({err})")

    _raise_collected_errors(SERVICE_ACTIVATE_PARTY_MODE, invalid, failed)


def _parse_end_time(value: str) -> datetime:
    """Parse an end time; raise ValueError if it is not a valid datetime."""
    dt_obj = dt_util.parse_datetime(value)
    if dt_obj is None:
        raise ValueError(f"Invalid datetime string for end_time: {value}")
    return dt_obj


async def async_handle_activate_vacation_mode(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the activate_vacation_mode service call."""
    try:
        client = _get_client_for_service(hass)
        end_time_str = call.data[ATTR_END_TIME]

        dt_obj = _parse_end_time(end_time_str)

        # HCU API expects format 'YYYY_%m_%d %H:%M'
        formatted_end_time = dt_obj.strftime("%Y_%m_%d %H:%M")

        await client.async_activate_vacation(
            temperature=call.data[ATTR_TEMPERATURE],
            end_time=formatted_end_time,
        )
        _LOGGER.info("Activated vacation mode until %s", end_time_str)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error activating vacation mode: %s", err)
        raise HomeAssistantError(f"Error activating vacation mode: {err}") from err
    except ValueError as err:
        _LOGGER.error("Invalid parameter for vacation mode: %s", err)
        raise ServiceValidationError(
            f"Invalid parameter for vacation mode: {err}"
        ) from err


async def async_handle_activate_eco_mode(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the activate_eco_mode service call."""
    try:
        client = _get_client_for_service(hass)
        await client.async_activate_absence_permanent()
        _LOGGER.info("Activated eco mode")
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error activating eco mode: %s", err)
        raise HomeAssistantError(f"Error activating eco mode: {err}") from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(f"No HCU available: {err}") from err


async def async_handle_deactivate_absence_mode(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the deactivate_absence_mode service call."""
    try:
        client = _get_client_for_service(hass)
        await client.async_deactivate_absence()
        _LOGGER.info("Deactivated absence mode")
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error deactivating absence mode: %s", err)
        raise HomeAssistantError(f"Error deactivating absence mode: {err}") from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(f"No HCU available: {err}") from err


async def async_handle_switch_on_with_time(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the switch_on_with_time service call."""
    on_time = call.data.get(ATTR_ON_TIME)
    if on_time is None:
        _LOGGER.error(
            "Required attribute '%s' missing for switch_on_with_time", ATTR_ON_TIME
        )
        raise ServiceValidationError(
            f"Required attribute '{ATTR_ON_TIME}' missing for switch_on_with_time"
        )

    invalid: list[str] = []
    failed: list[str] = []
    for entity_id in _extract_entity_ids(call):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity:
            _LOGGER.warning("Entity %s not found", entity_id)
            invalid.append(f"{entity_id} (not found)")
            continue

        if not hasattr(entity, "async_turn_on_with_time"):
            _LOGGER.warning("Entity %s does not support timed on", entity_id)
            invalid.append(f"{entity_id} (timed on not supported)")
            continue

        try:
            await entity.async_turn_on_with_time(on_time=on_time)
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error(
                "Error calling switch_on_with_time for %s: %s", entity_id, err
            )
            failed.append(f"{entity_id} ({err})")

    _raise_collected_errors(SERVICE_SWITCH_ON_WITH_TIME, invalid, failed)


async def async_handle_send_api_command(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the send_api_command service call."""
    body = call.data.get(ATTR_BODY)
    path = call.data.get(ATTR_PATH)

    if not isinstance(body, dict):
        if body is None:
            _LOGGER.error(
                "Required attribute '%s' missing for send_api_command", ATTR_BODY
            )
        else:
            _LOGGER.error(
                "Attribute '%s' must be an object/dictionary for send_api_command",
                ATTR_BODY,
            )
        raise ServiceValidationError(
            f"Attribute '{ATTR_BODY}' must be an object/dictionary for send_api_command"
        )

    if not isinstance(path, str):
        if path is None:
            _LOGGER.error(
                "Required attribute '%s' missing for send_api_command", ATTR_PATH
            )
        else:
            _LOGGER.error(
                "Attribute '%s' must be a string for send_api_command", ATTR_PATH
            )
        raise ServiceValidationError(
            f"Attribute '{ATTR_PATH}' must be a string for send_api_command"
        )

    try:
        client = _get_client_for_service(hass)
        await client.async_send_api_command(
            path=path,
            body=body,
        )
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error calling send_api_command for path %s: %s", path, err)
        raise HomeAssistantError(
            f"Error calling send_api_command for path {path}: {err}"
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(f"No HCU available: {err}") from err


async def async_handle_set_cooling_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_cooling_mode service call."""
    cooling = call.data.get(ATTR_COOLING)

    if not isinstance(cooling, bool):
        _LOGGER.error(
            "Required attribute '%s' must be a boolean for set_cooling_mode",
            ATTR_COOLING,
        )
        raise ServiceValidationError(
            f"Required attribute '{ATTR_COOLING}' must be a boolean for set_cooling_mode"
        )

    try:
        client = _get_client_for_service(hass)
        await client.async_send_api_command(
            path=API_PATHS["SET_COOLING"],
            body={ATTR_COOLING: cooling},
        )
        _LOGGER.info("Set cooling mode to %s", cooling)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error setting cooling mode: %s", err)
        raise HomeAssistantError(f"Error setting cooling mode: {err}") from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(f"No HCU available: {err}") from err


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
    """Handle the user_message service call."""
    user_message_id = call.data.get(ATTR_USER_MESSAGE_ID)
    raw_message = call.data.get(ATTR_USER_MESSAGE_MESSAGE)
    raw_title = call.data.get(ATTR_USER_MESSAGE_TITLE)
    behavior_type = call.data.get(ATTR_USER_MESSAGE_BEHAVIOR_TYPE)
    message_category = call.data.get(ATTR_USER_MESSAGE_CATEGORY)

    title = _as_multilang(raw_title, ATTR_USER_MESSAGE_TITLE)
    if title is None:
        raise ServiceValidationError(
            f"Attribute '{ATTR_USER_MESSAGE_TITLE}' must be a string or dictionary of strings"
        )

    message = _as_multilang(raw_message, ATTR_USER_MESSAGE_MESSAGE)
    if message is None:
        raise ServiceValidationError(
            f"Attribute '{ATTR_USER_MESSAGE_MESSAGE}' must be a string or dictionary of strings"
        )

    body = {
        "messageCategory": message_category,
        "userMessageId": user_message_id,
        "title": title,
        "message": message,
        "behaviorType": behavior_type,
        "timestamp": int(time.time() * 1000),
    }

    try:
        client = _get_client_for_service(hass)
        await client.async_create_user_message_request(body=body)
    except (HcuApiError, ConnectionError) as err:
        _LOGGER.error("Error calling create_user_message_request: %s", err)
        raise HomeAssistantError(
            f"Error calling create_user_message_request: {err}"
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(f"No HCU available: {err}") from err


async def async_delete_user_message_request(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the user_message_delete service call."""
    user_message_id = call.data.get(ATTR_USER_MESSAGE_ID)

    if not isinstance(user_message_id, str):
        if user_message_id is None:
            _LOGGER.error(
                "Required attribute '%s' missing for delete_user_message_request",
                ATTR_USER_MESSAGE_ID,
            )
        else:
            _LOGGER.error(
                "Attribute '%s' must be a string for delete_user_message_request",
                ATTR_USER_MESSAGE_ID,
            )
        raise ServiceValidationError(
            f"Attribute '{ATTR_USER_MESSAGE_ID}' must be a string for delete_user_message_request"
        )

    try:
        client = _get_client_for_service(hass)
        await client.async_delete_user_message_request(
            user_message_id=user_message_id,
        )
    except (HcuApiError, ConnectionError) as err:
        raise HomeAssistantError(
            f"Failed to delete user message {user_message_id}: {err}"
        ) from err
    except ValueError as err:
        raise ServiceValidationError(f"No HCU available: {err}") from err


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

    assert set(service_handlers.keys()) == set(INTEGRATION_SERVICES), (
        "Service handler keys must match INTEGRATION_SERVICES list"
    )

    for service_name, handler in service_handlers.items():
        hass.services.async_register(
            DOMAIN,
            service_name,
            partial(handler, hass),
        )

    _LOGGER.debug("Registered %d HCU services", len(service_handlers))
