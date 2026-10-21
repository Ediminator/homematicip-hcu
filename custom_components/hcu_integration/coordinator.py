# custom_components/hcu_integration/coordinator.py
"""Coordinator for the Homematic IP Local (HCU) integration."""

from __future__ import annotations

import asyncio
from functools import partial
import json
import logging
import random
from typing import Any

import aiohttp
import getmac
from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    issue_registry as ir,
)
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from zeroconf import IPVersion

from . import event
from .api import HcuApiClient, HcuApiError
from .const import (
    ATTR_USER_MESSAGE_ACKNOWLEDGEMENT_TYPE,
    ATTR_USER_MESSAGE_ID,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_ADVANCED_DEBUGGING,
    CONF_AUTH_TYPE,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    CONF_ZEROCONF_NAME,
    CONF_ZEROCONF_TYPE,
    DEFAULT_ADVANCED_DEBUGGING,
    DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE,
    DEVICE_CHANNEL_EVENT_TYPES,
    DOMAIN,
    EVENT_USER_MESSAGE_ACKNOWLEDGEMENT,
    MSG_TYPE_USER_MESSAGE_ACK,
    SWITCHING_GROUP_TYPES,
    WEBSOCKET_CONNECT_TIMEOUT,
    WEBSOCKET_RECONNECT_INITIAL_DELAY,
    WEBSOCKET_RECONNECT_JITTER_MAX,
    WEBSOCKET_RECONNECT_MAX_DELAY,
)
from .discovery import (
    _resolve_translation_prefixes,
    async_discover_entities_for_device,
    async_discover_entities_for_group,
)
from .ha_entity_bridge import HaEntityBridge

_LOGGER = logging.getLogger(__name__)


class HcuCoordinator(DataUpdateCoordinator[set[str]]):
    """Manages the HCU API client and data updates."""

    # Always set in __init__; DataUpdateCoordinator declares it as optional.
    config_entry: ConfigEntry

    def __init__(
        self, hass: HomeAssistant, client: HcuApiClient, entry: ConfigEntry
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self.config_entry = entry
        self.client = client
        self.entities: dict[Platform, list[Entity]] = {}
        self._event_entities: dict[tuple[str, str], event.TriggerableEvent] = {}
        self._platform_callbacks: dict[Platform, AddEntitiesCallback] = {}
        self._connected_event = asyncio.Event()
        self._pending_device_reload_task: asyncio.Task | None = None
        self._known_device_ids: set[str] = set()
        # Switching groups that arrived before all of their member devices.
        self._pending_group_ids: set[str] = set()
        self.advanced_debugging = self.config_entry.options.get(
            CONF_ADVANCED_DEBUGGING,
            DEFAULT_ADVANCED_DEBUGGING,
        )
        self._previous_data = dict(self.config_entry.data)
        self._previous_options = dict(self.config_entry.options)
        self._initial_state_loaded = False
        self.hcu_device_entry_id: str | None = None
        self._ha_bridge: HaEntityBridge | None = None

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

    def async_register_platform(
        self, platform: Platform, async_add_entities: AddEntitiesCallback
    ) -> None:
        """Register platform add_entities callback for dynamic entity addition."""
        self._platform_callbacks[platform] = async_add_entities

    def _handle_dynamic_inclusions(self, included_ids: set[str]) -> None:
        """Discover and add entities for newly included devices or groups dynamically."""
        if not included_ids:
            return

        # Collect existing unique_ids to guarantee idempotency
        existing_unique_ids = {
            e.unique_id
            for platform_entities in self.entities.values()
            for e in platform_entities
            if getattr(e, "unique_id", None) is not None
        }

        all_new_entities: dict[Platform, list[Entity]] = {}
        devices_state = self.client.state.get("devices", {})
        groups_state = self.client.state.get("groups", {})

        # A switching group becomes a light group only if all members are
        # lights, which discovery can only tell once the members are known.
        # Hold such groups back and retry them when new devices arrive.
        ids_to_discover = set(included_ids)
        if any(item_id in devices_state for item_id in included_ids):
            ids_to_discover |= self._pending_group_ids
        for item_id in list(ids_to_discover):
            group = groups_state.get(item_id)
            if group is not None and self._has_unknown_members(group, devices_state):
                self._pending_group_ids.add(item_id)
                ids_to_discover.discard(item_id)
            else:
                self._pending_group_ids.discard(item_id)

        for item_id in ids_to_discover:
            item_entities: dict[Platform, list[Entity]] = {}
            if item_id in devices_state:
                item_entities = async_discover_entities_for_device(
                    self.client, self.config_entry, self, item_id
                )
            elif item_id in groups_state:
                item_entities = async_discover_entities_for_group(
                    self.client, self.config_entry, self, item_id
                )

            for plat, ents in item_entities.items():
                all_new_entities.setdefault(plat, []).extend(ents)

        if not any(all_new_entities.values()):
            return

        _resolve_translation_prefixes(all_new_entities)

        # Filter out duplicates and dispatch to platforms
        for plat, ents in all_new_entities.items():
            to_add: list[Entity] = []
            for e in ents:
                uid = getattr(e, "unique_id", None)
                if uid is not None:
                    if uid in existing_unique_ids:
                        continue
                    existing_unique_ids.add(uid)
                to_add.append(e)

            if not to_add:
                continue

            self.entities.setdefault(plat, []).extend(to_add)

            # Register TriggerableEvent entities for push button handling
            for e in to_add:
                if isinstance(e, event.TriggerableEvent):
                    lookup_key = self._get_visible_channel_idx(
                        e._device_id, e._channel_index_str
                    )
                    self._event_entities[(e._device_id, lookup_key)] = e

            add_callback = self._platform_callbacks.get(plat)
            if add_callback:
                add_callback(to_add)

    @staticmethod
    def _has_unknown_members(
        group: dict[str, Any], devices_state: dict[str, Any]
    ) -> bool:
        """Return True for a switching group whose member devices are not all known."""
        if group.get("type") not in SWITCHING_GROUP_TYPES:
            return False
        return any(
            isinstance(ref, dict) and ref.get("deviceId") not in devices_state
            for ref in group.get("channels") or []
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
            except TimeoutError:
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
                self.hass,
                self._listen_for_plugin_events(),
                name="HCU Plugin WebSocket Listener",
            )

        try:
            initial_state = await self.client.get_system_state()
            if not initial_state or not initial_state.get("devices"):
                _LOGGER.error("Connected but failed to get valid initial state")
                self._create_setup_issue("Connected but no devices found in HCU state")
                return False
        except (TimeoutError, HcuApiError, ConnectionError, aiohttp.ClientError) as err:
            _LOGGER.error("Failed to get initial state: %s", err)
            self._create_setup_issue(str(err))
            return False

        await self._register_hcu_device()

        state = self.client.state
        all_ids = set(state.get("devices", {}).keys()) | set(
            state.get("groups", {}).keys()
        )
        if home_id := (state.get("home") or {}).get("id"):
            all_ids.add(home_id)
        self.async_set_updated_data(all_ids)

        self._known_device_ids = set(state.get("devices", {}).keys())
        self._initial_state_loaded = True
        self._delete_setup_issue()
        return True

    async def _async_update_data(self) -> set[str]:
        """Fetch the latest data from the HCU."""
        try:
            await self.client.get_system_state()
            state = self.client.state
            all_ids = set(state.get("devices", {}).keys()) | set(
                state.get("groups", {}).keys()
            )
            if home_id := (state.get("home") or {}).get("id"):
                all_ids.add(home_id)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        else:
            return all_ids

    async def _async_known_hosts(self) -> set[str]:
        """Return every IPv4 address currently known for the HCU.

        Starts with the configured host and, if the entry was set up via
        zeroconf, re-queries zeroconf for the service so addresses on other
        interfaces (e.g. the HCU is reachable over both WLAN and Ethernet)
        are included too.
        """
        hosts: set[str] = set()
        if host := self.config_entry.data.get(CONF_HOST):
            hosts.add(host)

        name = self.config_entry.data.get(CONF_ZEROCONF_NAME)
        type_ = self.config_entry.data.get(CONF_ZEROCONF_TYPE)
        if name and type_:
            try:
                aiozc = await zeroconf.async_get_async_instance(self.hass)
                info = await aiozc.async_get_service_info(type_, name, timeout=3000)
            except Exception:  # noqa: BLE001 - best effort: extra addresses are optional
                info = None
            if info:
                hosts.update(info.parsed_addresses(IPVersion.V4Only))

        return hosts

    async def _register_hcu_device(self) -> None:
        """Register the HCU as a device in Home Assistant."""
        device_registry = dr.async_get(self.hass)
        hcu_device_id = self.client.hcu_device_id

        if not hcu_device_id:
            _LOGGER.warning("Could not determine HCU device ID from state")
            return

        hcu_device = self.client.state.get("devices", {}).get(hcu_device_id, {})

        # The Homematic IP API does not expose the HCU's MAC address(es), so
        # they are resolved from the local ARP table via IP instead. This
        # only succeeds once the OS has an ARP entry for a given host (i.e.
        # after we've actually talked to it, which is guaranteed for the
        # configured host at this point, but not necessarily for other
        # addresses found via zeroconf).
        connections: set[tuple[str, str]] = set()
        for host in await self._async_known_hosts():
            try:
                mac = await self.hass.async_add_executor_job(
                    partial(getmac.get_mac_address, ip=host)
                )
            except Exception:  # noqa: BLE001 - best effort: the MAC is optional metadata
                mac = None
            # getmac returns the null MAC as a placeholder in some failure
            # cases; storing it would make Home Assistant treat every device
            # with the same unresolved lookup as this HCU.
            if mac and mac != "00:00:00:00:00:00":
                connections.add((dr.CONNECTION_NETWORK_MAC, dr.format_mac(mac)))

        device_entry = device_registry.async_get_or_create(
            config_entry_id=self.config_entry.entry_id,
            identifiers={(DOMAIN, hcu_device_id)},
            connections=connections,
            manufacturer=hcu_device.get("oem", "eQ-3"),
            model=hcu_device.get("modelType", "HCU"),
            serial_number=hcu_device.get("id"),
            name=hcu_device.get("label", "Homematic IP HCU"),
            sw_version=hcu_device.get("firmwareVersion", ""),
        )
        self.hcu_device_entry_id = device_entry.id

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
                    events, ensure_ascii=False, indent=2, sort_keys=True, default=str
                )
                _LOGGER.debug("HMIP_SYSTEM_EVENT:\n%s", pretty)
            except (TypeError, ValueError):
                _LOGGER.debug("HMIP_SYSTEM_EVENT: (repr): %r", events)

        result = self.client.process_events(events)
        if self.advanced_debugging:
            _LOGGER.debug(
                "process_events result — updated=%s included=%s excluded=%s",
                result.updated,
                result.included,
                result.excluded,
            )

        if not self._initial_state_loaded:
            return

        if result.included:
            self._handle_dynamic_inclusions(result.included)

        if result.excluded:
            auto_reload = self.config_entry.options.get(
                CONF_AUTO_RELOAD_ON_DEVICE_CHANGE, DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE
            )
            if auto_reload:
                _LOGGER.info(
                    "Device removed (%s) — reloading integration", result.excluded
                )
                self.hass.async_create_task(
                    self.hass.config_entries.async_reload(self.config_entry.entry_id)
                )
                return

        if result.reload_required:
            auto_reload = self.config_entry.options.get(
                CONF_AUTO_RELOAD_ON_DEVICE_CHANGE, DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE
            )
            if auto_reload and not self._pending_device_reload_task:
                _LOGGER.info(
                    "Device config changed (%s) — reloading integration in 10 s",
                    result.reload_required,
                )

                async def _delayed_reload_cfg() -> None:
                    await asyncio.sleep(10)
                    self._pending_device_reload_task = None
                    # Schedule instead of awaiting: the reload unloads the
                    # entry, which cancels this background task.
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

                # A background task of the entry is cancelled when the entry is
                # unloaded, so the reload does not run after unload.
                self._pending_device_reload_task = (
                    self.config_entry.async_create_background_task(
                        self.hass, _delayed_reload_cfg(), name="HCU delayed reload"
                    )
                )

        device_channel_event_ids = self._handle_device_channel_events(events)

        all_updated = result.all_ids | device_channel_event_ids
        if all_updated:
            self.async_set_updated_data(all_updated)

    def _get_visible_channel_idx(self, device_id: str, channel_idx: str) -> str:
        """Return visibleChannelIndex for a channel if available, otherwise channel_idx."""
        channel = (
            self.client.state.get("devices", {})
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

            # Eventtype Normalization
            if event_type and event_type.startswith("KEY_"):
                event_type = event_type[4:]
            event_type = event_type.lower() if event_type else None
            if event_type == "door_bell_sensor_event":
                event_type = "ring"

            if not device_id or not channel_idx or not event_type:
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
                    if isinstance(e, event.TriggerableEvent)
                    and e._device_id == device_id
                    and (
                        e._channel_index_str == channel_idx
                        or self._get_visible_channel_idx(
                            device_id, e._channel_index_str
                        )
                        == channel_idx
                    )
                ),
                None,
            )
            if entity:
                self._event_entities[key] = entity
            else:
                _LOGGER.warning(
                    "Event entity not found: device=%s, channel=%s",
                    device_id,
                    channel_idx,
                )
                return

        entity.handle_trigger(event_type)

    async def _async_refresh_state_after_reconnect(self) -> None:
        """Load the full HCU state again after the WebSocket reconnected.

        The HCU does not repeat events that were sent while the connection was
        down, so entities would keep outdated values until their device changes
        again. Devices and groups that appeared meanwhile get their entities;
        devices that disappeared are handled like a DEVICE_REMOVED event.
        """
        state = self.client.state
        old_ids = set(state.get("devices", {})) | set(state.get("groups", {}))
        try:
            await self.client.get_system_state()
        except (TimeoutError, HcuApiError, ConnectionError, aiohttp.ClientError) as err:
            _LOGGER.warning(
                "Could not refresh the HCU state after reconnecting: %s", err
            )
            return

        state = self.client.state
        new_ids = set(state.get("devices", {})) | set(state.get("groups", {}))
        _LOGGER.debug("Refreshed the HCU state after reconnecting")

        if added := new_ids - old_ids:
            self._handle_dynamic_inclusions(added)

        removed = old_ids - new_ids
        if removed and self.config_entry.options.get(
            CONF_AUTO_RELOAD_ON_DEVICE_CHANGE, DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE
        ):
            _LOGGER.info(
                "Devices removed while disconnected (%s) — reloading integration",
                removed,
            )
            self.hass.config_entries.async_schedule_reload(self.config_entry.entry_id)
            return

        all_ids = set(new_ids)
        if home_id := (state.get("home") or {}).get("id"):
            all_ids.add(home_id)
        self.async_set_updated_data(all_ids)

    async def _listen_for_events(self) -> None:
        """WebSocket listener with auto-reconnection."""
        reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY
        unavailable_logged = False

        auth_type = self.config_entry.data.get(CONF_AUTH_TYPE, AUTH_TYPE_PLUGIN)
        is_primary_plugin_channel = auth_type not in (AUTH_TYPE_APP, AUTH_TYPE_DUAL)
        connected_before = False

        while True:
            try:
                await self.client.connect()
                self.client.register_event_callback(self._handle_event_message)
                self._connected_event.set()
                reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY
                if connected_before and self._initial_state_loaded:
                    # Events sent while the connection was down are lost.
                    # Started as a task: in Plugin mode the response arrives
                    # through listen() below.
                    self.config_entry.async_create_background_task(
                        self.hass,
                        self._async_refresh_state_after_reconnect(),
                        name="HCU state refresh after reconnect",
                    )
                connected_before = True
                if unavailable_logged:
                    _LOGGER.info("WebSocket reconnected to HCU")
                    unavailable_logged = False
                else:
                    _LOGGER.info("WebSocket connected to HCU")
                if is_primary_plugin_channel:
                    # Speak first, per the Connect API docs ("send
                    # PluginStateResponse upon startup") — fired concurrently
                    # so listen() below is already reading for the response.
                    self.hass.async_create_task(
                        self.client.announce_plugin_ready(),
                        name="HCU Plugin ready announce",
                    )
                await self.client.listen()

            except (TimeoutError, ConnectionError, aiohttp.ClientError) as e:
                if not unavailable_logged:
                    _LOGGER.warning(
                        "WebSocket disconnected: %s. Reconnecting in %ds",
                        e,
                        reconnect_delay,
                    )
                    unavailable_logged = True
                else:
                    _LOGGER.debug(
                        "WebSocket reconnect failed: %s. Retrying in %ds",
                        e,
                        reconnect_delay,
                    )
            except asyncio.CancelledError:
                _LOGGER.info("WebSocket listener cancelled")
                break
            except Exception:
                if not unavailable_logged:
                    _LOGGER.exception(
                        "WebSocket error. Reconnecting in %ds", reconnect_delay
                    )
                    unavailable_logged = True
                else:
                    _LOGGER.debug(
                        "WebSocket error during reconnect. Retrying in %ds",
                        reconnect_delay,
                        exc_info=True,
                    )

            if self.client.is_connected:
                await self.client.disconnect()

            self._connected_event.clear()

            jitter = random.uniform(0, WEBSOCKET_RECONNECT_JITTER_MAX)
            await asyncio.sleep(reconnect_delay + jitter)
            reconnect_delay = min(reconnect_delay * 2, WEBSOCKET_RECONNECT_MAX_DELAY)

    async def _listen_for_plugin_events(self) -> None:
        """DualBridge: Plugin User WebSocket listener with auto-reconnection."""
        reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY
        unavailable_logged = False

        while True:
            try:
                await self.client.connect_plugin()
                reconnect_delay = WEBSOCKET_RECONNECT_INITIAL_DELAY
                if unavailable_logged:
                    _LOGGER.info("DualBridge: Plugin WebSocket reconnected")
                    unavailable_logged = False
                else:
                    _LOGGER.info("DualBridge: Plugin WebSocket connected")
                # Speak first, per the Connect API docs ("send
                # PluginStateResponse upon startup") — fired concurrently so
                # listen_plugin() below is already reading for the response.
                self.hass.async_create_task(
                    self.client.announce_plugin_ready(),
                    name="HCU Plugin ready announce",
                )
                await self.client.listen_plugin()

            except (TimeoutError, ConnectionError, aiohttp.ClientError) as e:
                if not unavailable_logged:
                    _LOGGER.warning(
                        "DualBridge Plugin WebSocket disconnected: %s. Reconnecting in %ds",
                        e,
                        reconnect_delay,
                    )
                    unavailable_logged = True
                else:
                    _LOGGER.debug(
                        "DualBridge Plugin WebSocket reconnect failed: %s. Retrying in %ds",
                        e,
                        reconnect_delay,
                    )
            except asyncio.CancelledError:
                _LOGGER.info("DualBridge Plugin WebSocket listener cancelled")
                break
            except Exception:
                if not unavailable_logged:
                    _LOGGER.exception(
                        "DualBridge Plugin WebSocket error. Reconnecting in %ds",
                        reconnect_delay,
                    )
                    unavailable_logged = True
                else:
                    _LOGGER.debug(
                        "DualBridge Plugin WebSocket error during reconnect. Retrying in %ds",
                        reconnect_delay,
                        exc_info=True,
                    )

            if self.client.is_plugin_connected:
                await self.client.disconnect_plugin()

            jitter = random.uniform(0, WEBSOCKET_RECONNECT_JITTER_MAX)
            await asyncio.sleep(reconnect_delay + jitter)
            reconnect_delay = min(reconnect_delay * 2, WEBSOCKET_RECONNECT_MAX_DELAY)


type HcuConfigEntry = ConfigEntry[HcuCoordinator]
