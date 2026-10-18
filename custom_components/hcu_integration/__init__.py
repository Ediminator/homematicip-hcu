# custom_components/hcu_integration/__init__.py
"""The Homematic IP Local (HCU) integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import event
from .api import HcuApiClient
from .const import (
    AUTH_TYPE_PLUGIN,
    CONF_ADVANCED_DEBUGGING,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_AUTH_PORT,
    CONF_AUTH_TYPE,
    CONF_DEV,
    CONF_DEVICE_PINS,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    CONF_HA_DEVICES,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_UNIQUE_PLUGIN_ID,
    CONF_WEBSOCKET_PORT,
    DEFAULT_ADVANCED_DEBUGGING,
    DEFAULT_DEV,
    DEFAULT_DISABLE_UNCONFIGURED_CHANNELS,
    DOMAIN,
    PLATFORMS,
    PLUGIN_ID,
)
from .coordinator import HcuConfigEntry, HcuCoordinator
from .discovery import async_discover_entities
from .ha_entity_bridge import HaEntityBridge
from .services import async_register_services
from .util import get_entry_coordinator

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the HCU component.

    Services are entry-independent: they are registered once here, before
    any config entry is set up, and never unregistered. This avoids a race
    where entities from a config entry become available (and start firing
    state changes that automations react to) before the services they call
    exist — or stop existing while entities are still around during a
    reload. `_get_client_for_service()` raises a clear error if a service
    is called without a loaded config entry.
    """
    async_register_services(hass)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to latest version."""
    _LOGGER.info("Migrating HCU config entry from version %d", entry.version)

    if entry.version > 6:
        _LOGGER.warning(
            "Config entry is from a newer version (%d) — downgrading to v6. "
            "Some settings from the newer version may be lost.",
            entry.version,
        )
        hass.config_entries.async_update_entry(entry, version=6)
        return True

    new_data = dict(entry.data)

    # v1 → v2: remove legacy configurable ports, rename fields
    _remove = {CONF_AUTH_PORT, CONF_WEBSOCKET_PORT, "system_pin"}
    _rename = {
        "token": CONF_PLUGIN_TOKEN,
        "client_id": CONF_PLUGIN_CLIENT_ID,
        "access_point_id": CONF_HCU_SGTIN,
    }
    new_data = {_rename.get(k, k): v for k, v in new_data.items() if k not in _remove}

    # Ensure all v2 fields exist with safe defaults
    new_data.setdefault(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN)
    new_data.setdefault(CONF_APP_TOKEN, "")
    new_data.setdefault(CONF_APP_CLIENT_ID, "")
    new_data.setdefault(CONF_HCU_SGTIN, "")

    # v2 → v3: remove global PIN (lock PIN configuration removed from UI)
    new_data.pop("pin", None)

    # v3 → v4: enable disable_unconfigured_channels for all existing entries
    new_options = dict(entry.options)
    new_options.setdefault(
        CONF_DISABLE_UNCONFIGURED_CHANNELS, DEFAULT_DISABLE_UNCONFIGURED_CHANNELS
    )

    # v4 → v5: add dev flag (developer mode disabled by default)
    new_options.setdefault(CONF_DEV, DEFAULT_DEV)

    hass.config_entries.async_update_entry(
        entry, data=new_data, options=new_options, version=6
    )
    _LOGGER.info("Migrated HCU config entry to v6")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: HcuConfigEntry) -> bool:
    """Set up Homematic IP Local (HCU) from a config entry."""
    # CONF_UNIQUE_PLUGIN_ID is only ever set while re-pairing with developer
    # mode enabled (see const.py); every other entry falls back to PLUGIN_ID.
    plugin_id = entry.data.get(CONF_UNIQUE_PLUGIN_ID) or PLUGIN_ID

    client = HcuApiClient(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PLUGIN_TOKEN, ""),
        async_get_clientsession(hass),
        client_id=entry.data.get(CONF_PLUGIN_CLIENT_ID, ""),
        auth_type=entry.data.get(CONF_AUTH_TYPE, ""),
        access_point_id=entry.data.get(CONF_HCU_SGTIN, ""),
        app_token=entry.data.get(CONF_APP_TOKEN, ""),
        advanced_debugging=entry.options.get(
            CONF_ADVANCED_DEBUGGING, DEFAULT_ADVANCED_DEBUGGING
        ),
        plugin_id=plugin_id,
    )

    ha_devices = entry.options.get(CONF_HA_DEVICES, [])
    bridge = HaEntityBridge(hass, ha_devices, client._send_message, client.plugin_id)
    client.set_ha_entity_bridge(bridge)

    coordinator = HcuCoordinator(hass, client, entry)
    coordinator._ha_bridge = bridge

    if not await coordinator.async_setup():
        await client.disconnect()
        await client.disconnect_plugin()
        raise ConfigEntryNotReady(
            f"Failed to connect to Homematic IP HCU at {entry.data[CONF_HOST]}"
        )

    entry.runtime_data = coordinator
    bridge.start_listening()

    coordinator.entities = await async_discover_entities(
        hass, client, entry, coordinator
    )

    coordinator._event_entities = {}
    for e in coordinator.entities.get(Platform.EVENT, []):
        if not isinstance(e, event.TriggerableEvent):
            continue
        lookup_key = coordinator._get_visible_channel_idx(
            e._device_id, e._channel_index_str
        )
        coordinator._event_entities[(e._device_id, lookup_key)] = e

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    if entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN) == AUTH_TYPE_PLUGIN:
        _LOGGER.info(
            "This entry uses Plugin User only. "
            "Reconfigure to 'DualBridge' to also enable App User features (e.g. getCurrentState via REST)."
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HcuConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator = entry.runtime_data

    if hasattr(coordinator, "_ha_bridge") and coordinator._ha_bridge:
        coordinator._ha_bridge.stop_listening()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await coordinator.client.disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: HcuConfigEntry) -> None:
    """Reload config entry when options are updated (excluding runtime PIN updates)."""
    coordinator = get_entry_coordinator(entry)
    if coordinator is not None:
        prev_data = coordinator._previous_data
        prev_opts = {
            k: v
            for k, v in coordinator._previous_options.items()
            if k != CONF_DEVICE_PINS
        }
        curr_opts = {k: v for k, v in entry.options.items() if k != CONF_DEVICE_PINS}
        pins_changed = coordinator._previous_options.get(
            CONF_DEVICE_PINS
        ) != entry.options.get(CONF_DEVICE_PINS)
        coordinator._previous_data = dict(entry.data)
        coordinator._previous_options = dict(entry.options)
        if prev_data == dict(entry.data) and prev_opts == curr_opts and pins_changed:
            _LOGGER.debug(
                "Skipping integration reload for entry %s (only device PINs changed)",
                entry.entry_id,
            )
            return
    await hass.config_entries.async_reload(entry.entry_id)
