# custom_components/hcu_integration/util.py
"""Utility helpers for the Homematic IP HCU integration."""

from datetime import datetime
import hashlib
import json
import logging
import re
import ssl
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.translation import async_get_translations
from homeassistant.util import dt as dt_util

from .const import (
    ACCESS_DENIED_ERROR_CODES,
    ACCESS_DENIED_ERROR_STRINGS,
    DEVICE_TYPE_PLUGIN_EXTERNAL,
    DOCS_URL_LOCK_PIN_CONFIG,
    DOMAIN,
    HCU_ERROR_CODE_TRANSLATION_KEYS,
    HCU_ERROR_CODES_WITH_CODE_PLACEHOLDER,
    HCU_REASON_TRANSLATION_KEYS,
    HOMEMATIC_MODEL_PREFIXES,
    HUE_MODEL_TOKEN,
    INVALID_PIN_ERROR_CODES,
    INVALID_PIN_ERROR_STRINGS,
    LOCK_AUTH_ERROR_MSG,
    MANUFACTURER_3RD_PARTY,
    MANUFACTURER_EQ3,
    MANUFACTURER_HUE,
    PLUGIN_ID_HUE,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .coordinator import HcuCoordinator

_LOGGER = logging.getLogger(__name__)

# Date and time format of the Connect API, e.g. activatePartyMode endTime
# (section 6.8.2.1) and activateVacation endTime: "yyyy_MM_dd HH:mm".
HCU_DATETIME_FORMAT = "%Y_%m_%d %H:%M"

# An HCU SGTIN is 96 bits written as 24 hexadecimal characters.
_SGTIN_SEPARATORS = re.compile(r"[\s-]")
_SGTIN_PATTERN = re.compile(r"[0-9A-F]{24}")

# Fixed salt the App User flow appends to the SGTIN to derive CLIENTAUTH.
_CLIENT_AUTH_SALT = "jiLpVitHvWnIGD1yo7MA"


def normalize_sgtin(value: str) -> str:
    """Return an SGTIN without spaces or dashes, in upper case.

    The label on the HCU prints the SGTIN in dash-separated blocks
    ("3014-F711-A000-..."). CLIENTAUTH is derived from the plain 24-character
    form, as homematicip-rest-api does when it asks for the access point ID.
    """
    return _SGTIN_SEPARATORS.sub("", value).upper()


def is_valid_sgtin(value: str) -> bool:
    """Return True if a normalized SGTIN has 24 hexadecimal characters."""
    return _SGTIN_PATTERN.fullmatch(value) is not None


def compute_client_auth(access_point_id: str) -> str:
    """Return the App User CLIENTAUTH header value for an SGTIN."""
    return (
        hashlib.sha512((access_point_id + _CLIENT_AUTH_SALT).encode("utf-8"))
        .hexdigest()
        .upper()
    )


def format_hcu_end_time(value: str) -> str:
    """Return an end time in the HCU's local "yyyy_MM_dd HH:mm" format.

    Accepts any date and time Home Assistant can parse (for example
    "2026-12-24 23:00" or an ISO string with an offset) and the HCU's own
    format ("2026_12_24 23:00"). A value with an offset is converted to
    Home Assistant's time zone, which the HCU uses as local time.
    """
    parsed = dt_util.parse_datetime(value)
    if parsed is None:
        try:
            parsed = datetime.strptime(value, HCU_DATETIME_FORMAT)
        except ValueError:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_end_time",
                translation_placeholders={"value": value},
            ) from None
    if parsed.tzinfo is not None:
        parsed = dt_util.as_local(parsed)
    return parsed.strftime(HCU_DATETIME_FORMAT)


# Cache key for storing SSL context in hass.data
_SSL_CONTEXT_CACHE_KEY = "hcu_integration_ssl_context"


async def create_unverified_ssl_context(hass: HomeAssistant) -> ssl.SSLContext:
    """Create an SSL context that does not verify certificates, in a non-blocking way.

    The SSL context is cached in hass.data to avoid recreating it on every call.
    """
    # Check if SSL context is already cached
    if _SSL_CONTEXT_CACHE_KEY in hass.data:
        return hass.data[_SSL_CONTEXT_CACHE_KEY]

    def _create_context() -> ssl.SSLContext:
        """The actual SSL context creation to run in executor."""
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    # Create and cache the context
    context = await hass.async_add_executor_job(_create_context)
    hass.data[_SSL_CONTEXT_CACHE_KEY] = context
    return context


def get_security_home(home: dict[str, Any]) -> dict[str, Any]:
    """Return the SECURITY_AND_ALARM functional home, or {} if there is none."""
    for functional_home in (home.get("functionalHomes") or {}).values():
        if (
            isinstance(functional_home, dict)
            and functional_home.get("solution") == "SECURITY_AND_ALARM"
        ):
            return functional_home
    return {}


def get_device_manufacturer(device_data: dict) -> str:
    """Determine the manufacturer of a device.

    Corrects cases where 3rd party devices (like Philips Hue) are reported as 'eQ-3'.
    """
    # 1. Check for Hue-specific identifiers first, as they are the most reliable.
    plugin_id = device_data.get("pluginId")
    if plugin_id == PLUGIN_ID_HUE:
        return MANUFACTURER_HUE

    # 2. Trust explicit OEM if it's not the default "eQ-3"
    # This is more accurate than loose model name matching
    oem = device_data.get("oem")
    if oem and oem != MANUFACTURER_EQ3:
        return oem

    # 3. Check loose model name match for Hue
    model_type = device_data.get("modelType") or ""
    if HUE_MODEL_TOKEN in model_type:
        return MANUFACTURER_HUE

    # 4. Check Device Type/Archetype for generic "External" status
    # "PLUGIN_EXTERNAL" strongly implies a 3rd party integration
    if device_data.get("type") == DEVICE_TYPE_PLUGIN_EXTERNAL:
        return MANUFACTURER_3RD_PARTY

    # 5. Check for standard Homematic IP prefix
    if model_type.startswith(HOMEMATIC_MODEL_PREFIXES):
        return MANUFACTURER_EQ3

    # 6. Default
    # If it has no 'oem' field and didn't match above, we assume it's a standard device
    # (or legacy one) and return "eQ-3" to match previous behavior
    return MANUFACTURER_EQ3


def get_group_type(group_data: dict) -> str | None:
    """Determine the type of a group."""
    return group_data.get("type")


class HcuApiError(Exception):
    """Custom exception for API errors returned by the HCU."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Initialize the HCU API error with optional Connect API metadata."""
        super().__init__(message)
        self.error_code = error_code
        self.status_code = status_code


def extract_hcu_error_code(text: str) -> str | None:
    """Extract a Connect API errorCode string from an HCU JSON error body."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if isinstance(top_code := data.get("errorCode"), str) and top_code:
        return top_code
    body = data.get("body")
    if (
        isinstance(body, dict)
        and isinstance(inner_code := body.get("errorCode"), str)
        and inner_code
    ):
        return inner_code
    return None


def handle_lock_api_error(
    err: Exception,
    entity_name: str,
    pin: str | None,
) -> str | None:
    """
    Handle standard lock API authentication and state errors across lock platforms.
    Returns the type of error matched, or None if unhandled.
    """
    error_code = err.error_code if isinstance(err, HcuApiError) else None
    error_str_lower = str(err).lower()

    # Check for invalid PIN errors
    if error_code in INVALID_PIN_ERROR_CODES or any(
        s in error_str_lower for s in INVALID_PIN_ERROR_STRINGS
    ):
        if not pin:
            _LOGGER.warning(
                "Lock '%s' requires a PIN to function. "
                "Please configure it: Settings → Devices & Services → "
                "Homematic IP Local (HCU) → CONFIGURE → Enter Authorization PIN. "
                "See %s for details.",
                entity_name,
                DOCS_URL_LOCK_PIN_CONFIG,
            )
        return "invalid_pin"

    # Check for access denied / permission errors
    if (
        error_code in ACCESS_DENIED_ERROR_CODES
        or any(e in error_str_lower for e in ACCESS_DENIED_ERROR_STRINGS)
        or "no permission" in error_str_lower
    ):
        _LOGGER.error(LOCK_AUTH_ERROR_MSG, f"lock '{entity_name}'")
        return "access_denied"

    # Check for motor jam errors
    if "jammed" in error_str_lower or "jam" in error_str_lower:
        _LOGGER.error(
            "Lock '%s' is jammed and cannot complete the operation. "
            "Check the lock mechanism for obstructions.",
            entity_name,
        )
        return "jammed"

    return None


# runtime_data is set before the platforms are set up, so entities (and actions
# targeting them) already exist while the entry is still SETUP_IN_PROGRESS.
_COORDINATOR_STATES = (ConfigEntryState.LOADED, ConfigEntryState.SETUP_IN_PROGRESS)


def get_entry_coordinator(entry: ConfigEntry | None) -> "HcuCoordinator | None":
    """Return the coordinator of a loaded (or loading) config entry, or None."""
    if entry is None or entry.state not in _COORDINATOR_STATES:
        return None
    return getattr(entry, "runtime_data", None)


def iter_coordinators(hass: HomeAssistant) -> "Iterator[HcuCoordinator]":
    """Yield the coordinators of all loaded (or loading) entries of this integration."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if (coordinator := get_entry_coordinator(entry)) is not None:
            yield coordinator


def app_user_rights_hint(err: Exception) -> str:
    """Return a log hint for raising the app user's role, or "" for other errors."""
    if "CLIENT_ACCESS_DENIED" not in str(err):
        return ""
    return (
        " The HCU denied access (CLIENT_ACCESS_DENIED): the app user may not "
        "have sufficient permissions. If User rights is turned on in the "
        "Homematic IP app, go to Settings → User management → User overview and "
        "set the 'Home Assistant Integration' user to Normal user or Administrator."
    )


def command_failed(entity_id: str | None, err: Exception) -> HomeAssistantError:
    """Return the error raised when the HCU rejects or misses an entity command."""
    entity_str = str(entity_id)
    if isinstance(err, HcuApiError) and err.error_code:
        if key := HCU_ERROR_CODE_TRANSLATION_KEYS.get(err.error_code):
            placeholders: dict[str, str] = {"entity": entity_str}
            if err.error_code in HCU_ERROR_CODES_WITH_CODE_PLACEHOLDER:
                placeholders["code"] = err.error_code
            return HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=key,
                translation_placeholders=placeholders,
            )
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="command_failed",
            translation_placeholders={"entity": entity_str, "error": err.error_code},
        )
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="command_failed",
        translation_placeholders={"entity": entity_str, "error": str(err)},
    )


async def async_format_hcu_error(hass: HomeAssistant, err: Exception) -> str:
    """Return a localized human-readable reason for an HCU error."""
    if not isinstance(err, HcuApiError) or not err.error_code:
        return str(err)
    reason_key = HCU_REASON_TRANSLATION_KEYS.get(err.error_code)
    if not reason_key:
        return err.error_code
    translations = await async_get_translations(
        hass, hass.config.language, "exceptions", {DOMAIN}
    )
    if msg := translations.get(f"component.{DOMAIN}.exceptions.{reason_key}.message"):
        if err.error_code in HCU_ERROR_CODES_WITH_CODE_PLACEHOLDER:
            return msg.format(code=err.error_code)
        return msg
    return err.error_code


def lock_error_to_exception(
    err_type: str | None,
    entity_id: str | None,
    err: Exception,
) -> HomeAssistantError:
    """Return the error for a failed lock or door command (see handle_lock_api_error)."""
    if err_type == "invalid_pin":
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_invalid_pin",
            translation_placeholders={"entity": str(entity_id)},
        )
    if err_type == "access_denied":
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_access_denied",
            translation_placeholders={"entity": str(entity_id)},
        )
    if err_type == "jammed":
        return HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_jammed",
            translation_placeholders={"entity": str(entity_id)},
        )
    return command_failed(entity_id, err)
