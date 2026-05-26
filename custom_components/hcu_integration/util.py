# custom_components/hcu_integration/util.py
"""Utility helpers for the Homematic IP HCU integration."""
import ssl
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import (
    MANUFACTURER_EQ3,
    MANUFACTURER_HUE,
    MANUFACTURER_3RD_PARTY,
    PLUGIN_ID_HUE,
    DEVICE_TYPE_PLUGIN_EXTERNAL,
    HUE_MODEL_TOKEN,
    HOMEMATIC_MODEL_PREFIXES,
    INVALID_PIN_ERROR_STRINGS,
    ACCESS_DENIED_ERROR_STRINGS,
    LOCK_AUTH_ERROR_MSG,
    DOCS_URL_LOCK_PIN_CONFIG,
)
import logging

_LOGGER = logging.getLogger(__name__)

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

def get_group_type(group_data: dict) -> str:
    """Determine the type of a group."""
    return group_data.get("type")

def handle_lock_api_error(
    err: Exception,
    entity_name: str,
    pin: str | None,
) -> str | None:
    """
    Handle standard lock API authentication and state errors across lock platforms.
    Returns the type of error matched, or None if unhandled.
    """
    error_str_lower = str(err).lower()

    # Check for invalid PIN errors
    if any(s in error_str_lower for s in INVALID_PIN_ERROR_STRINGS):
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
    if any(e in error_str_lower for e in ACCESS_DENIED_ERROR_STRINGS) or "no permission" in error_str_lower:
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
