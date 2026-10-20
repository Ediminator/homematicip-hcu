# custom_components/hcu_integration/services.py
"""Service handlers for the Homematic IP Local (HCU) integration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from functools import partial
import logging
import time
from typing import TYPE_CHECKING, Any

from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant, ServiceCall, split_entity_id
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.translation import async_get_translations
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
from .util import iter_coordinators

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
            for coordinator in iter_coordinators(hass)
            for entity in coordinator.entities.get(platform, [])
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
            translation_domain=DOMAIN,
            translation_key="no_entity_specified",
            translation_placeholders={"service": call.service},
        )
    return entity_ids


def _get_client_for_service(hass: HomeAssistant) -> HcuApiClient:
    """Get the API client for service calls."""
    for coordinator in iter_coordinators(hass):
        return coordinator.client
    raise ValueError("No HCU client available")


@dataclass(slots=True)
class _InvalidTarget:
    """Represents an invalid entity target during service execution."""

    entity_id: str
    reason: str
    exception: ServiceValidationError | None = None


REASON_TRANSLATION_KEYS: dict[str, str] = {
    "not_found": "reason_not_found",
    "no_sound": "reason_no_sound",
    "not_hcu_climate": "reason_not_hcu_climate",
    "timed_on_unsupported": "reason_timed_on_unsupported",
    "invalid_param": "reason_invalid_param",
}


async def _async_get_exception_translations(
    hass: HomeAssistant,
) -> dict[str, str]:
    """Get exception translation messages for the configured language."""
    translations = await async_get_translations(
        hass, hass.config.language, "exceptions", {DOMAIN}
    )
    prefix = f"component.{DOMAIN}.exceptions."
    suffix = ".message"
    return {
        k.removeprefix(prefix).removesuffix(suffix): v for k, v in translations.items()
    }


def _format_target_reason(
    target: _InvalidTarget,
    translations: dict[str, str],
) -> str:
    """Format the translated reason for an invalid target."""
    trans_key = REASON_TRANSLATION_KEYS.get(target.reason, target.reason)
    if trans_key in translations:
        return translations[trans_key]
    if target.exception is not None:
        return str(target.exception)
    return target.reason


async def _raise_collected_errors(
    hass: HomeAssistant,
    service: str,
    invalid: list[_InvalidTarget],
    failed: list[str],
) -> None:
    """Raise one error after all targeted entities were processed.

    Entities that are incompatible or not found are validation problems
    (ServiceValidationError). If any entity failed while talking to the HCU,
    a HomeAssistantError is raised that lists every problem.
    """
    if not failed and not invalid:
        return

    if failed:
        translations = await _async_get_exception_translations(hass) if invalid else {}
        invalid_details = [
            f"{t.entity_id} ({_format_target_reason(t, translations)})" for t in invalid
        ]
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="entities_failed",
            translation_placeholders={
                "service": service,
                "entities": "; ".join(failed + invalid_details),
            },
        )

    if invalid:
        if len(invalid) == 1:
            target = invalid[0]
            if target.exception is not None:
                raise target.exception

        distinct_reasons = {t.reason for t in invalid}
        if len(distinct_reasons) == 1:
            reason = next(iter(distinct_reasons))
            key_map = {
                "not_found": "entities_not_found",
                "no_sound": "entities_no_sound",
                "not_hcu_climate": "entities_not_hcu_climate",
                "timed_on_unsupported": "entities_timed_on_unsupported",
            }
            if reason in key_map:
                translation_key = key_map[reason]
                entities_str = ", ".join(t.entity_id for t in invalid)
            elif (first_exc := invalid[0].exception) is not None and all(
                t.exception is not None for t in invalid
            ):
                raise first_exc
            else:
                translation_key = "entities_invalid_param"
                entities_str = ", ".join(t.entity_id for t in invalid)
        else:
            translations = await _async_get_exception_translations(hass)
            translation_key = "entities_invalid"
            entities_str = "; ".join(
                f"{t.entity_id} ({_format_target_reason(t, translations)})"
                for t in invalid
            )

        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key=translation_key,
            translation_placeholders={
                "service": service,
                "entities": entities_str,
            },
        )


async def async_handle_play_sound(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the play_sound service call."""
    invalid: list[_InvalidTarget] = []
    failed: list[str] = []
    for entity_id in _extract_entity_ids(call):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity or not hasattr(entity, "async_play_sound"):
            _LOGGER.warning(
                "Cannot play sound on %s: not a compatible HCU device with sound capability",
                entity_id,
            )
            reason = "not_found" if not entity else "no_sound"
            invalid.append(_InvalidTarget(entity_id, reason))
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

    await _raise_collected_errors(hass, SERVICE_PLAY_SOUND, invalid, failed)


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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_rule_state_failed",
            translation_placeholders={"rule_id": rule_id, "error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


async def async_handle_activate_party_mode(
    hass: HomeAssistant, call: ServiceCall
) -> None:
    """Handle the activate_party_mode service call."""
    invalid: list[_InvalidTarget] = []
    failed: list[str] = []
    for entity_id in _extract_entity_ids(call):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity or not hasattr(entity, "async_activate_party_mode"):
            _LOGGER.warning(
                "Cannot activate party mode on %s: not a compatible HCU climate entity",
                entity_id,
            )
            reason = "not_found" if not entity else "not_hcu_climate"
            invalid.append(_InvalidTarget(entity_id, reason))
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
        except ServiceValidationError as err:
            _LOGGER.error("Invalid parameter for party mode on %s: %s", entity_id, err)
            invalid.append(
                _InvalidTarget(
                    entity_id,
                    err.translation_key or "invalid_param",
                    exception=err,
                )
            )
        except ValueError as err:
            _LOGGER.error("Invalid parameter for party mode on %s: %s", entity_id, err)
            invalid.append(_InvalidTarget(entity_id, "invalid_param"))

    await _raise_collected_errors(hass, SERVICE_ACTIVATE_PARTY_MODE, invalid, failed)


def _parse_end_time(value: str) -> datetime:
    """Parse an end time; raise ServiceValidationError if it is not a valid datetime."""
    dt_obj = dt_util.parse_datetime(value)
    if dt_obj is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_end_time",
            translation_placeholders={"value": value},
        )
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="activate_vacation_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("Invalid parameter for vacation mode: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_vacation_param",
            translation_placeholders={"error": str(err)},
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="activate_eco_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="deactivate_absence_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


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
            translation_domain=DOMAIN,
            translation_key="attribute_required",
            translation_placeholders={
                "attribute": ATTR_ON_TIME,
                "action": "switch_on_with_time",
            },
        )

    invalid: list[_InvalidTarget] = []
    failed: list[str] = []
    for entity_id in _extract_entity_ids(call):
        entity = _get_entity_from_entity_id(hass, entity_id)

        if not entity:
            _LOGGER.warning("Entity %s not found", entity_id)
            invalid.append(_InvalidTarget(entity_id, "not_found"))
            continue

        if not hasattr(entity, "async_turn_on_with_time"):
            _LOGGER.warning("Entity %s does not support timed on", entity_id)
            invalid.append(_InvalidTarget(entity_id, "timed_on_unsupported"))
            continue

        try:
            await entity.async_turn_on_with_time(on_time=on_time)
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error(
                "Error calling switch_on_with_time for %s: %s", entity_id, err
            )
            failed.append(f"{entity_id} ({err})")

    await _raise_collected_errors(hass, SERVICE_SWITCH_ON_WITH_TIME, invalid, failed)


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
            translation_domain=DOMAIN,
            translation_key="attribute_invalid_dict",
            translation_placeholders={
                "attribute": ATTR_BODY,
                "action": "send_api_command",
            },
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
            translation_domain=DOMAIN,
            translation_key="attribute_invalid_string",
            translation_placeholders={
                "attribute": ATTR_PATH,
                "action": "send_api_command",
            },
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
            translation_domain=DOMAIN,
            translation_key="send_api_command_failed",
            translation_placeholders={"path": path, "error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


async def async_handle_set_cooling_mode(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_cooling_mode service call."""
    cooling = call.data.get(ATTR_COOLING)

    if not isinstance(cooling, bool):
        _LOGGER.error(
            "Required attribute '%s' must be a boolean for set_cooling_mode",
            ATTR_COOLING,
        )
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="attribute_invalid_bool",
            translation_placeholders={
                "attribute": ATTR_COOLING,
                "action": "set_cooling_mode",
            },
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
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="set_cooling_mode_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


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
            translation_domain=DOMAIN,
            translation_key="attribute_invalid_multilang",
            translation_placeholders={"attribute": ATTR_USER_MESSAGE_TITLE},
        )

    message = _as_multilang(raw_message, ATTR_USER_MESSAGE_MESSAGE)
    if message is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="attribute_invalid_multilang",
            translation_placeholders={"attribute": ATTR_USER_MESSAGE_MESSAGE},
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
            translation_domain=DOMAIN,
            translation_key="create_user_message_failed",
            translation_placeholders={"error": str(err)},
        ) from err
    except ValueError as err:
        _LOGGER.error("No HCU available: %s", err)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


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
            translation_domain=DOMAIN,
            translation_key="attribute_invalid_string",
            translation_placeholders={
                "attribute": ATTR_USER_MESSAGE_ID,
                "action": "delete_user_message_request",
            },
        )

    try:
        client = _get_client_for_service(hass)
        await client.async_delete_user_message_request(
            user_message_id=user_message_id,
        )
    except (HcuApiError, ConnectionError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="delete_user_message_failed",
            translation_placeholders={
                "user_message_id": user_message_id,
                "error": str(err),
            },
        ) from err
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_hcu_available",
            translation_placeholders={"error": str(err)},
        ) from err


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
