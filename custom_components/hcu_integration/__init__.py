# custom_components/hcu_integration/__init__.py
"""The Homematic IP Local (HCU) integration."""
from __future__ import annotations

import aiohttp
import asyncio
import logging
import random
import json
from typing import Any, cast

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HcuApiClient, HcuApiError
from .const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_PORT,
    CONF_AUTH_TYPE,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_WEBSOCKET_PORT,
    CONF_ADVANCED_DEBUGGING,
    CHANNEL_TYPE_MULTI_MODE_INPUT_TRANSMITTER,
    DEFAULT_HCU_AUTH_PORT,
    DEFAULT_HCU_WEBSOCKET_PORT,
    DEVICE_CHANNEL_EVENT_ONLY_TYPES,
    DEVICE_CHANNEL_EVENT_TYPES,
    DOMAIN,
    MULTI_FUNCTION_CHANNEL_DEVICES,
    PLATFORMS,
    ATTR_USER_MESSAGE_ID,
    ATTR_USER_MESSAGE_ACKNOWLEDGEMENT_TYPE,
    EVENT_USER_MESSAGE_ACKNOWLEDGEMENT,
    MSG_TYPE_USER_MESSAGE_ACK,
    WEBSOCKET_CONNECT_TIMEOUT,
    WEBSOCKET_RECONNECT_INITIAL_DELAY,
    WEBSOCKET_RECONNECT_JITTER_MAX,
    WEBSOCKET_RECONNECT_MAX_DELAY,
)

from .discovery import async_discover_entities
from .services import (
    INTEGRATION_SERVICES,
    async_register_services,
    async_unregister_services,
)
from . import event

_LOGGER = logging.getLogger(__name__)

type HcuData = dict[str, "HcuCoordinator"]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

SERVICE_ENTRIES_KEY = f"{DOMAIN}_service_entries"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the HCU component."""
    return True

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to latest version."""
    _LOGGER.info("Migrating HCU config entry from version %d", entry.version)

    if entry.version > 2:
        _LOGGER.warning(
            "Config entry is from a newer version (%d) — downgrading to v2. "
            "Some settings from the newer version may be lost.",
            entry.version,
        )
        hass.config_entries.async_update_entry(entry, version=2)
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

    hass.config_entries.async_update_entry(entry, data=new_data, version=2)
    _LOGGER.info("Migrated HCU config entry to v2")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homematic IP Local (HCU) from a config entry."""
    client = HcuApiClient(
        hass,
        entry.data[CONF_HOST],
        entry.data.get(CONF_PLUGIN_TOKEN, ""),
        async_get_clientsession(hass),
        client_id=entry.data.get(CONF_PLUGIN_CLIENT_ID, ""),
        auth_type=entry.data.get(CONF_AUTH_TYPE, ""),
        access_point_id=entry.data.get(CONF_HCU_SGTIN, ""),
        app_token=entry.data.get(CONF_APP_TOKEN, ""),
    )

    coordinator = HcuCoordinator(hass, client, entry)

    domain_data = cast(HcuData, hass.data.setdefault(DOMAIN, {}))
    domain_data[entry.entry_id] = coordinator
    if not await coordinator.async_setup():
        return False

    coordinator.entities = await async_discover_entities(hass, client, entry, coordinator)

    coordinator._event_entities = {}
    for e in coordinator.entities.get(Platform.EVENT, []):
        if not hasattr(e, "handle_trigger"):
            continue
        lookup_key = coordinator._get_visible_channel_idx(e._device_id, e._channel_index_str)
        coordinator._event_entities[(e._device_id, lookup_key)] = e

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services (only once for first config entry)
    service_entries: set[str] = hass.data.setdefault(SERVICE_ENTRIES_KEY, set())
    if not service_entries:
        async_register_services(hass)
    service_entries.add(entry.entry_id)

    entry.add_update_listener(async_reload_entry)

    if entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN) == AUTH_TYPE_PLUGIN:
        _LOGGER.info(
            "This entry uses Plugin User only. "
            "Reconfigure to 'DualBridge' to also enable App User features (e.g. getCurrentState via REST)."
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: HcuCoordinator = hass.data[DOMAIN][entry.entry_id]

    if SERVICE_ENTRIES_KEY in hass.data:
        service_entries: set[str] = hass.data[SERVICE_ENTRIES_KEY]
        service_entries.discard(entry.entry_id)

        if not service_entries:
            async_unregister_services(hass)
            hass.data.pop(SERVICE_ENTRIES_KEY, None)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        await coordinator.client.disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


class HcuCoordinator(DataUpdateCoordinator[set[str]]):
    """Manages the HCU API client and data updates."""

    def __init__(
        self, hass: HomeAssistant, client: HcuApiClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.config_entry = entry
        self.client = client
        self.entities: dict[Platform, list[Entity]] = {}
        self._event_entities: dict[tuple[str, str], event.TriggerableEvent] = {}
        self._connected_event = asyncio.Event()
        self.advanced_debugging = self.config_entry.options.get(
            CONF_ADVANCED_DEBUGGING,
            False,
        )
        self._previous_options = dict(self.config_entry.options)
        self._initial_state_loaded = False

    def _create_setup_issue(self, reason: str) -> None:
        """Create a repair issue indicating setup failure."""
        auth_type = self.config_entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN)
        auth_labels = {
            AUTH_TYPE_PLUGIN: "Plugin User",
            AUTH_TYPE_APP: "App User",
            AUTH_TYPE_DUAL: "DualBridge (App + Plugin)",
        }
        ir.async_create_issue(
            hass=self.hass,
            domain=DOMAIN,
            issue_id=f"setup_failed_{self.config_entry.entry_id}",
            is_fixable=True,
            severity=ir.IssueSeverity.ERROR,
            translation_key="setup_failed",
            translation_placeholders={
                "host": self.config_entry.data[CONF_HOST],
                "auth_mode": auth_labels.get(auth_type, auth_type),
                "reason": reason,
            },
            data={"entry_id": self.config_entry.entry_id},
        )

    def _delete_setup_issue(self) -> None:
        """Remove the setup failure repair issue if it exists."""
        ir.async_delete_issue(
            self.hass, DOMAIN, f"setup_failed_{self.config_entry.entry_id}"
        )

    async def async_setup(self) -> bool:
        """Initialize the coordinator and establish the initial connection."""
        auth_type = self.config_entry.data.get(CONF_AUTH_TYPE)
        is_app_user = auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL)
        is_dual = auth_type == AUTH_TYPE_DUAL

        self.config_entry.async_create_background_task(
            self.hass, self._listen_for_events(), name="HCU WebSocket Listener"
        )

        if not is_app_user:
            _LOGGER.debug("Waiting for WebSocket connection...")
            try:
                await asyncio.wait_for(
                    self._connected_event.wait(), timeout=WEBSOCKET_CONNECT_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.error(
                    "WebSocket connection timeout after %ds", WEBSOCKET_CONNECT_TIMEOUT
                )
                self._create_setup_issue(
                    f"WebSocket connection timed out after {WEBSOCKET_CONNECT_TIMEOUT}s"
                )
                return False


        if is_dual:
            # DualBridge: start Plugin User WebSocket in background (optional channel).
            # Failure here is non-fatal — App User provides full state and commands.
            self.config_entry.async_create_background_task(
                self.hass, self._listen_for_plugin_events(), name="HCU Plugin WebSocket Listener"
            )

        try:
            initial_state = await self.client.get_system_state()
            if not initial_state or not initial_state.get("devices"):
                _LOGGER.error("Connected but failed to get valid initial state")
                self._create_setup_issue("Connected but no devices found in HCU state")
                return False
        except (HcuApiError, ConnectionError, asyncio.TimeoutError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to get initial state: %s", err)
            self._create_setup_issue(str(err))
            return False

        self._register_hcu_device()

        state = self.client.state
        all_ids = set(state.get("devices", {}).keys()) | set(state.get("groups", {}).keys())
        if home_id := state.get("home", {}).get("id"):
            all_ids.add(home_id)
        self.async_set_updated_data(all_ids)

        self._initial_state_loaded = True
        self._delete_setup_issue()
        return True

    async def _async_update_data(self) -> set[str]:
        """Fetch the latest data from the HCU."""
        try:
            await self.client.get_system_state()
            state = self.client.state
            all_ids = set(state.get("devices", {}).keys()) | set(state.get("groups", {}).keys())
            if home_id := state.get("home", {}).get("id"):
                all_ids.add(home_id)
            return all_ids
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err

    def _register_hcu_device(self) -> None:
        """Register the HCU as a device in Home Assistant."""
        device_registry = dr.async_get(self.hass)
        hcu_device_id = self.client.hcu_device_id

        if not hcu_device_id:
            _LOGGER.warning("Could not determine HCU device ID from state")
            return

        hcu_device = self.client.state.get("devices", {}).get(hcu_device_id, {})
        device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, hcu_device_id)},
            manufacturer=hcu_device.get("oem", "eQ-3"),
            model=hcu_device.get("modelType", "HCU"),
            serial_number=hcu_device.get("id"),
            name=hcu_device.get("label", "Homematic IP HCU"),
            sw_version=hcu_device.get("firmwareVersion", ""),
        )

    def _handle_event_message(self, msg: dict[str, Any]) -> None:
        """Process incoming event messages from the HCU."""
        msg_type = msg.get("type")

        if msg_type == MSG_TYPE_USER_MESSAGE_ACK:
            self._handle_user_message_ack(msg)
            return

        # App User WebSocket sends events directly: {"events": {"0": {...}}}
        # Plugin User wraps them: {"type": "HMIP_SYSTEM_EVENT", "body": {"eventTransaction": {"events": {...}}}}
        if msg_type is None and "events" in msg:
            events = msg.get("events", {})
        elif msg_type == "HMIP_SYSTEM_EVENT":
            body = msg.get("body", {})
            events = body.get("eventTransaction", {}).get("events", {})
        else:
            return
        if not events:
            return

        # Always process state updates before the initial-state guard check so that
        # the cache stays current. Entity updates are skipped until initial state is loaded.
        if self.advanced_debugging and self._initial_state_loaded:
            try:
                pretty = json.dumps(
                    events,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str
                )
                _LOGGER.debug("HMIP_SYSTEM_EVENT:\n%s", pretty)
            except Exception:
                _LOGGER.debug("HMIP_SYSTEM_EVENT: (repr): %r", events)

        updated_ids = self.client.process_events(events)

        if not self._initial_state_loaded:
            return

        device_channel_event_ids = self._handle_device_channel_events(events)

        all_updated = updated_ids | device_channel_event_ids
        if all_updated:
            self.async_set_updated_data(all_updated)

    def _get_visible_channel_idx(self, device_id: str, channel_idx: str) -> str:
        """Return visibleChannelIndex for a channel if available, otherwise channel_idx."""
        channel = (
            self.client.state
            .get("devices", {})
            .get(device_id, {})
            .get("functionalChannels", {})
            .get(channel_idx, {})
        )
        visible = channel.get("visibleChannelIndex")
        return str(visible) if visible is not None else channel_idx

    def _handle_device_channel_events(self, events: dict[str, Any]) -> set[str]:
        """Handle DEVICE_CHANNEL_EVENT type events (stateless buttons)."""
        updated_device_ids: set[str] = set()

        for event_data in events.values():
            if not isinstance(event_data, dict):
                continue

            if event_data.get("pushEventType") != "DEVICE_CHANNEL_EVENT":
                continue

            _LOGGER.debug("Raw DEVICE_CHANNEL_EVENT from HCU: %s", event_data)

            device_id = event_data.get("deviceId")
            channel_idx = str(event_data.get("channelIndex", ""))
            event_type = event_data.get("channelEventType")

            #Eventtype Normalization
            if event_type and event_type.startswith("KEY_"):
                event_type = event_type[4:]
            event_type = event_type.lower() if event_type else None
            if event_type == "door_bell_sensor_event":
                event_type = "ring"

            if not all([device_id, channel_idx, event_type]):
                continue

            if event_type not in DEVICE_CHANNEL_EVENT_TYPES:
                _LOGGER.debug("Unknown channel event type: %s", event_type)
                continue

            self._fire_button_event(device_id, channel_idx, event_type)
            self._trigger_event_entity(device_id, channel_idx, event_type)
            updated_device_ids.add(device_id)

        return updated_device_ids

    def _handle_user_message_ack(self, msg: dict[str, Any]) -> None:
        """Handle USER_MESSAGE_ACK_EVENT from HCU."""
        body = msg.get("body") or {}
        user_message_id = body.get("userMessageId")
        ack_type = body.get("ackType")
        if isinstance(ack_type, str):
            ack_type = ack_type.strip('"')

        if not user_message_id:
            _LOGGER.debug("USER_MESSAGE_ACK_EVENT missing userMessageId, skipping")
            return

        _LOGGER.debug(
            "USER_MESSAGE_ACK_EVENT: id=%s, ackType=%s", user_message_id, ack_type
        )

        self.hass.bus.async_fire(
            EVENT_USER_MESSAGE_ACKNOWLEDGEMENT,
            {
                ATTR_USER_MESSAGE_ID: user_message_id,
                ATTR_USER_MESSAGE_ACKNOWLEDGEMENT_TYPE: ack_type,
            },
        )

    def _extract_event_channels(self, events: dict[str, Any]) -> set[tuple[str, str]]:
        """Extract channels that support button events from DEVICE_CHANGED events."""
        event_channels: set[tuple[str, str]] = set()

        for event_data in events.values():
            if not isinstance(event_data, dict):
                continue

            if event_data.get("pushEventType") != "DEVICE_CHANGED":
                continue

            device = event_data.get("device", {})
            device_id = device.get("id")
            device_type = device.get("type", "")

            if not device_id:
                continue

            channels = device.get("functionalChannels", {})
            for ch_idx, ch_data in channels.items():
                channel_type = ch_data.get("functionalChannelType", "")

        return event_channels

    def _fire_button_event(
        self, device_id: str, channel_idx: str, event_type: str
    ) -> None:
        """Fire a button event to Home Assistant event bus."""
        self.hass.bus.async_fire(
            f"{DOMAIN}_event",
            {"device_id": device_id, "subtype": channel_idx, "type": event_type},
        )

    def _trigger_event_entity(
        self, device_id: str, channel_idx: str, event_type: str | None = None
    ) -> None:
        """Trigger an event entity for a device/channel."""
        key = (device_id, channel_idx)
        entity = self._event_entities.get(key)
        
        if not entity:
            entity = next(
                (
                    e
                    for e in self.entities.get(Platform.EVENT, [])
                    if hasattr(e, "handle_trigger")
                    and e._device_id == device_id
                    and (
                        e._channel_index_str == channel_idx
                        or self._get_visible_channel_idx(device_id, e._channel_index_str) == channel_idx
                    )
                ),
                None,
            )
            if entity:
                self._event_entities[key] = entity
            else:
                _LOGGER.warning(
                    "Event entity not found: device=%s, channel=%s", device_id, channel_idx
                )
                return

        entity.handle_trigger(event_type)

    async def _listen_for_events(self) -> None:
        """WebSocket listener with auto-reconnection."""
        reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY

        while True:
            try:
                await self.client.connect()
                self.client.register_event_callback(self._handle_event_message)
                self._connected_event.set()
                reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY

                _LOGGER.info("WebSocket connected to HCU")
                await self.client.listen()

            except (ConnectionError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                _LOGGER.warning("WebSocket disconnected: %s. Reconnecting in %ds", e, reconnect_delay)
            except asyncio.CancelledError:
                _LOGGER.info("WebSocket listener cancelled")
                break
            except Exception:
                _LOGGER.exception("WebSocket error. Reconnecting in %ds", reconnect_delay)

            if self.client.is_connected:
                await self.client.disconnect()

            self._connected_event.clear()

            jitter = random.uniform(0, WEBSOCKET_RECONNECT_JITTER_MAX)
            await asyncio.sleep(reconnect_delay + jitter)
            reconnect_delay = min(reconnect_delay * 2, WEBSOCKET_RECONNECT_MAX_DELAY)

    async def _listen_for_plugin_events(self) -> None:
        """DualBridge: Plugin User WebSocket listener with auto-reconnection."""
        reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY

        while True:
            try:
                await self.client.connect_plugin()
                reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY
                _LOGGER.info("DualBridge: Plugin WebSocket connected")
                await self.client.listen_plugin()

            except (ConnectionError, asyncio.TimeoutError, aiohttp.ClientError) as e:
                _LOGGER.warning(
                    "DualBridge Plugin WebSocket disconnected: %s. Reconnecting in %ds",
                    e, reconnect_delay,
                )
            except asyncio.CancelledError:
                _LOGGER.info("DualBridge Plugin WebSocket listener cancelled")
                break
            except Exception:
                _LOGGER.exception("DualBridge Plugin WebSocket error. Reconnecting in %ds", reconnect_delay)

            if self.client.is_plugin_connected:
                await self.client.disconnect_plugin()

            jitter = random.uniform(0, WEBSOCKET_RECONNECT_JITTER_MAX)
            await asyncio.sleep(reconnect_delay + jitter)
            reconnect_delay = min(reconnect_delay * 2, WEBSOCKET_RECONNECT_MAX_DELAY)
