# custom_components/hcu_integration/diagnostics.py
"""Diagnostics support for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN, CONF_PIN
from .api import HcuApiClient

# Keys to redact from the config_entry (credentials)
TO_REDACT_CONFIG = {
    CONF_HOST,
    CONF_TOKEN,
    CONF_PIN,
}

# Keys to redact from the HCU state data (sensitive personal/location data)
TO_REDACT_STATE = {
    "authtoken",
    "pin",
    "authorizationPin",
    "display",  # Can contain user-set text
    "homeId",
    "city",
    "latitude",
    "longitude",
}

# Keys to redact from the Home Assistant device/entity registry dump.
TO_REDACT_HA: set[str] = set()


def _redact_data(data: Any, keys_to_redact: set[str]) -> Any:
    """Recursively redact sensitive data in a dictionary or list."""
    if isinstance(data, dict):
        redacted = data.copy()
        for key, value in redacted.items():
            if key in keys_to_redact and isinstance(value, (str, int, float)):
                redacted[key] = "**REDACTED**"
            elif isinstance(value, (dict, list)):
                redacted[key] = _redact_data(value, keys_to_redact)
        return redacted
    if isinstance(data, list):
        return [_redact_data(item, keys_to_redact) for item in data]
    return data


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    client: HcuApiClient = coordinator.client

    redacted_config = {
        "title": config_entry.title,
        "data": _redact_data(dict(config_entry.data), TO_REDACT_CONFIG),
        "options": _redact_data(dict(config_entry.options), TO_REDACT_CONFIG),
    }

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    # Correlate HCU raw data with Home Assistant device and entity data
    correlated_devices = {}
    hcu_devices = client.state.get("devices", {})

    for device_id, hcu_data in hcu_devices.items():
        ha_device = device_registry.async_get_device(identifiers={(DOMAIN, device_id)})
        device_info = {}
        entities = []

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

            ha_entities = er.async_entries_for_device(entity_registry, ha_device.id)
            for entity in ha_entities:
                state = hass.states.get(entity.entity_id)
                entities.append(
                    {
                        "entity_id": entity.entity_id,
                        "unique_id": entity.unique_id,
                        "state": _redact_data(state.as_dict(), TO_REDACT_HA)
                        if state
                        else "NOT_FOUND",
                        "disabled_by": entity.disabled_by,
                    }
                )

        correlated_devices[device_id] = {
            "hcu_data": _redact_data(hcu_data, TO_REDACT_STATE),
            "ha_device": _redact_data(device_info, TO_REDACT_HA)
            or "NOT_IN_REGISTRY",
            "ha_entities": _redact_data(entities, TO_REDACT_HA),
        }

    # Correlate HCU group data with Home Assistant virtual devices and entities
    correlated_groups = {}
    hcu_groups = client.state.get("groups", {})

    for group_id, hcu_group_data in hcu_groups.items():
        ha_device = device_registry.async_get_device(identifiers={(DOMAIN, group_id)})
        device_info = {}
        entities = []

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

            ha_entities = er.async_entries_for_device(entity_registry, ha_device.id)
            for entity in ha_entities:
                state = hass.states.get(entity.entity_id)
                entities.append(
                    {
                        "entity_id": entity.entity_id,
                        "unique_id": entity.unique_id,
                        "state": _redact_data(state.as_dict(), TO_REDACT_HA)
                        if state
                        else "NOT_FOUND",
                        "disabled_by": entity.disabled_by,
                    }
                )

        correlated_groups[group_id] = {
            "hcu_data": _redact_data(hcu_group_data, TO_REDACT_STATE),
            "ha_device": _redact_data(device_info, TO_REDACT_HA)
            or "NOT_IN_REGISTRY",
            "ha_entities": _redact_data(entities, TO_REDACT_HA),
        }

    return {
        "generated_at": dt_util.utcnow().isoformat(),
        "config_entry": redacted_config,
        "devices": correlated_devices,
        "groups": correlated_groups,
    }
