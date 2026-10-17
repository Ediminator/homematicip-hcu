# custom_components/hcu_integration/diagnostics.py
"""Diagnostics support for the Homematic IP HCU integration."""
from __future__ import annotations

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
}

# Keys to redact from the Home Assistant device/entity registry dump.
TO_REDACT_HA: set[str] = {
    "sgtin",
    "pin",
    "authorizationPin",
}


def _correlate(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    hcu_items: dict[str, Any],
) -> dict[str, Any]:
    """Correlate raw HCU devices or groups with HA registry devices and entities."""
    correlated: dict[str, Any] = {}

    for item_id, hcu_data in hcu_items.items():
        ha_device = device_registry.async_get_device(identifiers={(DOMAIN, item_id)})
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
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    client: HcuApiClient = coordinator.client

    redacted_config = {
        "title": config_entry.title,
        "data": async_redact_data(dict(config_entry.data), TO_REDACT_CONFIG),
        "options": async_redact_data(dict(config_entry.options), TO_REDACT_CONFIG),
    }

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)

    return {
        "generated_at": dt_util.utcnow().isoformat(),
        "config_entry": redacted_config,
        "devices": _correlate(
            hass, device_registry, entity_registry, client.state.get("devices", {})
        ),
        "groups": _correlate(
            hass, device_registry, entity_registry, client.state.get("groups", {})
        ),
    }
