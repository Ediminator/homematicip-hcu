# custom_components/hcu_integration/diagnostics.py
"""Diagnostics support for the Homematic IP HCU integration."""

from __future__ import annotations

import re
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .api import HcuApiClient
from .const import (
    CONF_ACCESS_POINT_ID,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_CLIENT_ID,
    CONF_DEVICE_PINS,
    CONF_HCU_SGTIN,
    CONF_PIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_UNIQUE_PLUGIN_ID,
    CONF_ZEROCONF_NAME,
    DOMAIN,
)

# Keys to redact from the config_entry (credentials and hardware identifiers)
TO_REDACT_CONFIG = {
    CONF_HOST,
    CONF_PLUGIN_TOKEN,
    CONF_APP_TOKEN,
    CONF_PIN,
    CONF_DEVICE_PINS,
    CONF_HCU_SGTIN,
    CONF_ZEROCONF_NAME,
    CONF_ACCESS_POINT_ID,
    CONF_APP_CLIENT_ID,
    CONF_PLUGIN_CLIENT_ID,
    CONF_CLIENT_ID,
    CONF_UNIQUE_PLUGIN_ID,
    "sgtin",
}

# Keys to redact from the HCU state data (sensitive personal/location/hardware data)
TO_REDACT_STATE = {
    "authtoken",
    "authToken",
    "pin",
    "authorizationPin",
    "display",  # Can contain user-set text
    "homeId",
    "accessPointId",
    "sgtin",
    "clientAuth",
    "city",
    "latitude",
    "longitude",
    # SECURITY_AND_ALARM: the last app client that changed the activation
    # mode (its label is usually the phone name) and the alarm call numbers,
    # which users can set to personal numbers.
    "clientId",
    "clientLabel",
    "intrusionAlarmPhoneNumber",
    "safetyAlarmPhoneNumber",
}

# Keys to redact from the Home Assistant device/entity registry dump.
TO_REDACT_HA: set[str] = {
    "sgtin",
    "pin",
    "authorizationPin",
}

# Homematic IP device IDs are SGTINs: 24 hex characters starting with 3014F7.
# They are hardware serial numbers and appear as dict keys, in "id"/"deviceId"
# fields and inside unique IDs, so they are replaced throughout the output.
_SGTIN_RE = re.compile(r"(?<![0-9A-Fa-f])3014F7[0-9A-Fa-f]{18}(?![0-9A-Fa-f])")


class _DeviceIdPseudonymizer:
    """Replace device IDs with stable placeholders (device_001, device_002, ...).

    Keeping the same placeholder for the same device everywhere preserves the
    links between devices, channels, groups and entities in the dump.
    """

    def __init__(self, known_ids: list[str]) -> None:
        self._map: dict[str, str] = {}
        # Only long IDs are replaced as substrings; short IDs could match
        # unrelated text. SGTINs not in the list are caught by _SGTIN_RE.
        for device_id in sorted(set(known_ids)):
            if _SGTIN_RE.fullmatch(device_id) or len(device_id) >= 16:
                self._placeholder(device_id)

    def _placeholder(self, device_id: str) -> str:
        if device_id not in self._map:
            self._map[device_id] = f"device_{len(self._map) + 1:03d}"
        return self._map[device_id]

    def _scrub_str(self, value: str) -> str:
        for device_id, placeholder in self._map.items():
            if device_id in value:
                value = value.replace(device_id, placeholder)
        return _SGTIN_RE.sub(lambda m: self._placeholder(m.group(0)), value)

    def scrub(self, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                (self._scrub_str(k) if isinstance(k, str) else k): self.scrub(v)
                for k, v in data.items()
            }
        if isinstance(data, list):
            return [self.scrub(item) for item in data]
        if isinstance(data, str):
            return self._scrub_str(data)
        return data


def _correlate(
    hass: HomeAssistant,
    devices_by_identifier: dict[str, dr.DeviceEntry],
    entity_registry: er.EntityRegistry,
    hcu_items: dict[str, Any],
) -> dict[str, Any]:
    """Correlate raw HCU devices or groups with HA registry devices and entities."""
    correlated: dict[str, Any] = {}

    for item_id, hcu_data in hcu_items.items():
        ha_device = devices_by_identifier.get(item_id)
        device_info: dict[str, Any] = {}
        entities: list[dict[str, Any]] = []

        if ha_device:
            device_info = {
                "id": ha_device.id,
                "manufacturer": ha_device.manufacturer,
                "model": ha_device.model,
                "name": ha_device.name,
                "sw_version": ha_device.sw_version,
                "via_device_id": ha_device.via_device_id,
                "area_id": ha_device.area_id,
                "name_by_user": ha_device.name_by_user,
                "disabled_by": ha_device.disabled_by,
            }

            for entity in er.async_entries_for_device(entity_registry, ha_device.id):
                state = hass.states.get(entity.entity_id)
                entities.append(
                    {
                        "entity_id": entity.entity_id,
                        "unique_id": entity.unique_id,
                        "state": async_redact_data(state.as_dict(), TO_REDACT_HA)
                        if state
                        else "NOT_FOUND",
                        "disabled_by": entity.disabled_by,
                    }
                )

        correlated[item_id] = {
            "hcu_data": async_redact_data(hcu_data, TO_REDACT_STATE),
            "ha_device": async_redact_data(device_info, TO_REDACT_HA)
            or "NOT_IN_REGISTRY",
            "ha_entities": async_redact_data(entities, TO_REDACT_HA),
        }

    return correlated


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data
    client: HcuApiClient = coordinator.client

    redacted_config = {
        "title": config_entry.title,
        "data": async_redact_data(dict(config_entry.data), TO_REDACT_CONFIG),
        "options": async_redact_data(dict(config_entry.options), TO_REDACT_CONFIG),
    }

    # Look devices up within this config entry. A global identifier lookup
    # (DeviceRegistry.async_get_device) is deprecated because identifiers are
    # only unique per config entry.
    device_registry = dr.async_get(hass)
    devices_by_identifier: dict[str, dr.DeviceEntry] = {}
    for device in dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    ):
        for domain, identifier in device.identifiers:
            if domain == DOMAIN:
                devices_by_identifier[identifier] = device

    entity_registry = er.async_get(hass)
    hcu_devices = client.state.get("devices", {})
    home = client.state.get("home") or {}

    result = {
        "generated_at": dt_util.utcnow().isoformat(),
        "config_entry": redacted_config,
        # Only the functional homes (security, climate, access control, ...):
        # they hold the alarm and absence flags. The rest of the home object
        # (location, weather, clients) is not needed for troubleshooting.
        "home": {
            "functionalHomes": async_redact_data(
                home.get("functionalHomes", {}), TO_REDACT_STATE
            ),
        },
        "devices": _correlate(
            hass, devices_by_identifier, entity_registry, hcu_devices
        ),
        "groups": _correlate(
            hass, devices_by_identifier, entity_registry, client.state.get("groups", {})
        ),
    }
    return _DeviceIdPseudonymizer(list(hcu_devices)).scrub(result)
