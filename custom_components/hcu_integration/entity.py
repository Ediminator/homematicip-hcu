# custom_components/hcu_integration/entity.py
"""Base entity for the Homematic IP HCU integration."""
from __future__ import annotations
from typing import TYPE_CHECKING, Any
import logging

from homeassistant.const import STATE_ON
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ENTITY_PREFIX, HOMEMATIC_MODEL_PREFIXES, CONF_ADVANCED_ATTRIBUTES, CONF_PIN, CONF_DEVICE_PINS, CONF_CLIENT_ID, HMIP_ON_TIME_INFINITE
from .api import HcuApiClient, HcuApiError
from .util import get_device_manufacturer

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


class HcuEntityPrefixMixin:
    """Mixin to provide entity prefix property for all HCU entities."""

    coordinator: "HcuCoordinator"  # Type hint for the coordinator

    @property
    def _entity_prefix(self) -> str:
        """Get the entity name prefix from config entry."""
        return self.coordinator.config_entry.data.get(CONF_ENTITY_PREFIX, "")

    def _apply_prefix(self, base_name: str) -> str:
        """Apply entity prefix to a base name."""
        if prefix := self._entity_prefix:
            return f"{prefix} {base_name}"
        return base_name


class SwitchStateMixin:
    """Mixin to provide common switch-like state handling with optimistic updates."""

    _state_channel_key: str = "on"  # Default channel key, subclasses can override
    _attr_is_on: bool
    _attr_assumed_state: bool
    _channel: dict[str, Any]
    name: str | None  # From Entity base class

    def _init_switch_state(self) -> None:
        """Initialize the switch state from channel data."""
        self._attr_is_on = self._channel.get(self._state_channel_key, False)

    @property
    def is_on(self) -> bool:
        """Return True if the switch is on."""
        return self._attr_is_on

    def _sync_switch_state_from_coordinator(self) -> None:
        """Sync switch state from coordinator data."""
        self._attr_is_on = self._channel.get(self._state_channel_key, False)

    async def _call_switch_api(self, turn_on: bool) -> None:
        """Call the API to set the switch state. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement _call_switch_api")

    async def _async_set_optimistic_state(self, turn_on: bool, entity_type: str) -> None:
        """Set the state with optimistic updates and error handling."""
        self._attr_is_on = turn_on
        self._attr_assumed_state = True
        self.async_write_ha_state()  # type: ignore[attr-defined]
        try:
            await self._call_switch_api(turn_on)
        except (HcuApiError, ConnectionError) as err:
            action = "on" if turn_on else "off"
            _LOGGER.error("Failed to turn %s %s %s: %s", action, entity_type, self.name, err)
            self._attr_is_on = not turn_on  # Revert to previous state
            self._attr_assumed_state = False
            self.async_write_ha_state()  # type: ignore[attr-defined]

class HcuAccessMixin:
    """Mixin for entities that need PIN lookup and ACCESS_AUTHORIZATION_CHANNEL resolution."""

    coordinator: "HcuCoordinator"
    _attr_unique_id: str | None
    _device_id: str
    _channel_index: int
    _device: dict
    _channel: dict
    _client: "HcuApiClient"
    name: str | None
    hass: Any

    def _get_pin(self) -> str | None:
        """Return the PIN: device-specific first, then global config PIN as fallback."""
        config_entry = self.coordinator.config_entry
        pins = config_entry.options.get(CONF_DEVICE_PINS, {})
        if device_pin := pins.get(self._device.get("id")):
            _LOGGER.debug("Device '%s': using specified device pin", self.name)
            return device_pin
        if global_pin := config_entry.data.get(CONF_PIN):
            _LOGGER.debug("Device '%s': using global PIN from config entry", self.name)
            return global_pin
        _LOGGER.debug("Device '%s': no PIN available", self.name)
        return None

    def _find_authorization_channel(self) -> tuple[int, str] | None:
        """Find the ACCESS_AUTHORIZATION_CHANNEL index belonging to this channel."""
        config_entry = self.coordinator.config_entry
        client_id = config_entry.data.get(CONF_CLIENT_ID)
        if not client_id:
            _LOGGER.error("No clientId found for this integration. Triggering reconfiguration flow.")
            config_entry.async_start_reauth(self.hass)
            return None

        channels = self._device.get("functionalChannels", {})
        switch_group_index = self._channel.get("groupIndex")

        candidates: list[tuple[int, list[str]]] = []
        for ch_idx, ch_data in channels.items():
            if (
                ch_data.get("functionalChannelType") == "ACCESS_AUTHORIZATION_CHANNEL"
                and ch_data.get("groupIndex") == switch_group_index
            ):
                candidates.append((int(ch_idx), list(ch_data.get("groups") or [])))

        if not candidates:
            return None

        profiled: list[tuple[int, str]] = []
        client_authorized = False
        for ch_idx, group_ids in candidates:
            for group_id in group_ids:
                group = self._client.get_group_by_id(str(group_id)) or {}
                if (
                    group.get("type") == "ACCESS_AUTHORIZATION_PROFILE"
                    and group.get("authorizationPinAssigned") is True
                    and client_id in group.get("clientIds", [])
                ):
                    client_authorized = True
                    profiled.append((ch_idx, group.get("label", "")))

        if not client_authorized:
            _LOGGER.error(
                "The Home Assistant Integration is not authorized to control device '%s' channel %s. "
                "Either the integration is not added to an Access Authorization Profile, "
                "or no PIN is stored in the profile. "
                "Please open the Homematic IP app, go to → More → Access authorisations, "
                "add the 'Home Assistant Integration' user to the authorisation profile and ensure a PIN is set, "
                "then reload the integration in Home Assistant.",
                self._device_id,
                self._channel_index,
            )
            return None

        ir.async_delete_issue(
            hass=self.hass,
            domain=DOMAIN,
            issue_id=f"access_authorization_{self._device_id}_{self._channel_index}",
        )

        if len(profiled) > 1:
            _LOGGER.warning(
                "Multiple ACCESS_AUTHORIZATION_PROFILEs found for %s channel %s. Using first match.",
                self._device_id,
                self._channel_index,
            )

        return profiled[0]

class HcuBaseEntity(CoordinatorEntity["HcuCoordinator"], HcuEntityPrefixMixin, Entity):
    """Base class for entities tied to a specific Homematic IP device channel."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
        **kwargs: Any,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._client = client
        self._device_id = device_data["id"]
        self._channel_index_str = str(channel_index)
        self._channel_index = int(channel_index)
        self._attr_assumed_state = False
        
    def _set_entity_name(
        self,
        channel_label: str | None = None,
        feature_name: str | None = None,
    ) -> None:
        """
        Set the entity name based on the channel label and feature.

        This central helper ensures consistent naming across all platforms.
        Applies entity prefix if configured for multi-home setups.
        """
        base_name: str

        if feature_name:
            # This is a "feature" entity (sensor, binary_sensor, button)
            if channel_label:
                # Sensor on a labeled channel: "Channel Label Feature Name"
                # (e.g., "Living Room Thermostat Temperature")
                base_name = f"{channel_label} {feature_name}"
                self._attr_has_entity_name = False
            else:
                # Sensor on an unlabeled channel: "Feature Name"
                # (e.g., "Low Battery" on a device)
                base_name = feature_name
                self._attr_has_entity_name = True
        else:
            # This is a "main" entity (switch, light, cover, lock)
            if channel_label:
                # Main entity on a labeled channel: "Channel Label"
                # (e.g., "Ceiling Light")
                base_name = channel_label
                self._attr_has_entity_name = False
            else:
                # Main entity on an unlabeled channel (e.g., FROLL, PSM-2)
                # Use the device's label, model type, or device ID as fallback.
                # Setting has_entity_name to True makes it a standalone entity name.
                # The prefix will be applied by the logic below.
                # (e.g., "HmIP-PSM-2" or "House1 HmIP-PSM-2" if prefixed)
                base_name = self._device.get("label") or self._device.get("modelType") or self._device_id
                self._attr_has_entity_name = True

        # Apply prefix to base name
        if self._entity_prefix:
            was_child_entity = self._attr_has_entity_name
            # If a prefix is configured, we must disable has_entity_name and manually
            # construct the full name. This forces Home Assistant to generate the
            # Entity ID from the full prefixed name (e.g., domain.prefix_device_feature)
            # instead of appending the prefix to the ID suffix (domain.device_prefix_feature).
            self._attr_has_entity_name = False
            
            # If we are disabling has_entity_name, we need to ensure the base_name
            # is fully qualified (includes device name if it was just a feature name).
            # However, the logic above for base_name already handles this distinction
            # based on whether it's a feature or main entity and whether it has a channel label.
            # The only case where base_name might be "too simple" is if it was relying on
            # the device name being prepended by HA (has_entity_name=True cases).
            
            if was_child_entity:
                 # If it was going to be a child entity, base_name is just the feature name.
                 # We need to prepend the device name/label to make it a full name before prefixing.
                 device_label = self._device.get("label") or self._device.get("modelType") or self._device_id
                 if base_name != device_label:
                     base_name = f"{device_label} {base_name}"
                 else:
                     base_name = device_label

            self._attr_name = self._apply_prefix(base_name)
        else:
            self._attr_name = base_name

    @property
    def _device(self) -> dict[str, Any]:
        """Return the latest parent device data from the client's state cache."""
        return self._client.get_device_by_address(self._device_id) or {}

    @property
    def _channel(self) -> dict[str, Any]:
        """Return the latest channel data from the parent device's data structure."""
        return self._device.get("functionalChannels", {}).get(self._channel_index_str, {})
    
    def _get_meta_group_label_from_channel_data(self, channel_data: dict[str, Any]) -> str | None:
        """Finds the meta group label from a given channel's group list."""
        for gid in channel_data.get("groups") or []:
            if g := self._client.get_group_by_id(str(gid)):
                if (g.get("type") or "").upper() == "META":
                    return g.get("label")
        return None


    @property
    def _meta_group_label(self) -> str | None:
        """Return the meta group label from channel 0 or fall back to the current channel."""
        ch0 = (self._device.get("functionalChannels") or {}).get("0") or {}
        label = self._get_meta_group_label_from_channel_data(ch0)
        return label if label is not None else self._get_meta_group_label_from_channel_data(self._channel)
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for the Home Assistant device registry."""
        hcu_device_id = self._client.hcu_device_id
    
        # If the entity belongs to the HCU itself, link it to the main HCU device
        if self._device_id in self._client.hcu_part_device_ids:
            return DeviceInfo(
                identifiers={(DOMAIN, hcu_device_id)},
            )
        
        model_type = self._device.get("modelType")
        meta = self._meta_group_label
        
        device_info_kwargs = dict(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device.get("label", "Unknown Device"),
            manufacturer=get_device_manufacturer(self._device),
            model=model_type,
            sw_version=self._device.get("firmwareVersion"),
            via_device=(DOMAIN, hcu_device_id),
        )
    
        if model_type and model_type.lower().startswith(tuple(p.lower() for p in HOMEMATIC_MODEL_PREFIXES)):
            device_info_kwargs["serial_number"] = self._device_id
            
        if meta is not None:
            device_info_kwargs["suggested_area"] = meta
        
        return DeviceInfo(**device_info_kwargs)
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = (super().extra_state_attributes or {}) | {
            "device_id": self._device_id,
            "channel_index": self._channel_index,
            "functional_channel_type": self._channel.get("functionalChannelType"),
            "is_group": False,
        }

        if self.coordinator.config_entry.options.get(CONF_ADVANCED_ATTRIBUTES, False):
            meta = self._meta_group_label
            if meta is not None:
                attrs["meta"] = meta
            if hasattr(self, "_attr_name"):
                attrs["attr_name"] = self._attr_name
            if hasattr(self, "_attr_has_entity_name"):
                attrs["attr_has_entity_name"] = self._attr_has_entity_name
            if hasattr(self, "_attr_translation_key"):
                attrs["attr_translation_key"] = self._attr_translation_key
            if hasattr(self, "object_id_base"):
                attrs["object_id_base"] = self.object_id_base
            if hasattr(self, "suggested_object_id"):
                attrs["suggested_object_id"] = self.suggested_object_id
            switchVisualization = self._channel.get("switchVisualization")
            if switchVisualization is not None:
                attrs["switch_visualization"] = switchVisualization
            channelRole = self._channel.get("channelRole")
            if channelRole is not None:
                attrs["channel_role"] = channelRole
        
        return attrs
    
    @property
    def available(self) -> bool:
        """Return True if the entity is available.

        Note: We intentionally do NOT check 'not self._channel' here because:
        - self._channel returns an empty dict {} when channel data is missing
        - Empty dicts are falsy in Python, causing false unavailability
        - Many channels may have sparse data or be temporarily omitted from HCU updates
        - This is normal behavior for devices like weather sensors (HmIP-SWO-PR) and sirens
        - Device reachability checks (permanentlyReachable and maintenance channel) are sufficient
        """
        if not self._client.is_connected or not self._device:
            return False

        # Devices that are permanently reachable (e.g., wired/powered devices)
        # are always available when connected
        if self._device.get("permanentlyReachable", False):
            return True

        # For non-permanently-reachable devices (e.g., battery-powered),
        # check the maintenance channel's reachability status
        maintenance_channel = self._device.get("functionalChannels", {}).get("0", {})
        return not maintenance_channel.get("unreach", False)


    def _get_internal_on_time(self) -> float | None:
        """Return onTime if the companion 'Use Internal On Time' config switch is ON, else None."""
        companion_uid = f"{self._device_id}_{self._channel_index}_use_internal_on_time"
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id("switch", DOMAIN, companion_uid)
        if entity_id is None:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state != STATE_ON:
            return None
        internal_link = self._channel.get("internalLinkConfiguration") or {}
        on_time = self._channel.get("onTime") or internal_link.get("onTime") or 0
        if on_time == 0 or on_time == HMIP_ON_TIME_INFINITE:
            return None
        return float(on_time)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._device_id in self.coordinator.data:
            self._attr_assumed_state = False
            self.async_write_ha_state()


class HcuGroupBaseEntity(CoordinatorEntity["HcuCoordinator"], HcuEntityPrefixMixin, Entity):
    """Base class for entities that represent a Homematic IP group."""

    _attr_should_poll = False
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the group base entity."""
        super().__init__(coordinator)
        self._client = client
        self._group_id = group_data["id"]
        self._attr_assumed_state = False

        # Centralized naming logic for all group entities
        label = group_data.get("label") or self._group_id
        self._attr_name = self._apply_prefix(self._format_label(label))
        self._attr_unique_id = self._group_id

    @staticmethod
    def _format_label(label: str) -> str:
        """Format ALL_CAPS_UNDERSCORED labels to Title Case."""
        if label and label.isupper() and "_" in label:
            return label.replace("_", " ").strip().title()
        return label

    @property
    def _group(self) -> dict[str, Any]:
        """Return the latest group data from the client's state cache."""
        return self._client.get_group_by_id(self._group_id) or {}
    
    @property
    def _meta_group_label(self) -> str | None:
        if metaGroupId := self._group.get("metaGroupId"):
            if metaGroup := self._client.get_group_by_id(str(metaGroupId)):
                return metaGroup.get("label")
        return None
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for this virtual group entity."""
        hcu_device_id = self._client.hcu_device_id
        group_type = self._group.get("type", "Group").replace("_", " ").title()
        model_name = f"{group_type} Group"
        meta = self._meta_group_label
    
        group_label = self._format_label(self._group.get("label", "Unknown Group"))

        device_info_kwargs = dict(
            identifiers={(DOMAIN, self._group_id)},
            entry_type=dr.DeviceEntryType.SERVICE,
            name=group_label,
            manufacturer="Homematic IP",
            model=model_name,
            via_device=(DOMAIN, hcu_device_id)
        )
    
        if meta is not None:
            device_info_kwargs["suggested_area"] = meta
         
        return DeviceInfo(**device_info_kwargs)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = (super().extra_state_attributes or {}) | {
            "type": self._group.get("type"),
            "is_group": True
        }
        meta = self._meta_group_label
        if meta is not None:
            attrs["meta"] = meta
        
        return attrs
    
    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self._client.is_connected and bool(self._group)


    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._group_id in self.coordinator.data:
            self._attr_assumed_state = False
            self.async_write_ha_state()


class SwitchingGroupMixin:
    """Mixin for group entities that support on/off switching (switch and light groups).

    This mixin provides common state management logic for groups that use the
    /hmip/group/switching/setState API endpoint.
    """

    _attr_is_on: bool | None
    _attr_assumed_state: bool
    _group_id: str
    _client: HcuApiClient

    def _init_switching_group_state(self, group_data: dict[str, Any]) -> None:
        """Initialize switching group state from group data."""
        self._attr_is_on = group_data.get("on")

    @callback
    def _sync_switching_group_state(self) -> None:
        """Sync state from coordinator data."""
        # Access _group through the group entity interface
        self._attr_is_on = self._group.get("on")  # type: ignore[attr-defined]

    async def _async_set_switching_group_state(self, turn_on: bool) -> None:
        """Set switching group state with optimistic update and error handling."""
        # Store previous state for rollback on error
        previous_state = self._attr_is_on

        # Optimistic update
        self._attr_is_on = turn_on
        self._attr_assumed_state = True
        # async_write_ha_state is available from Entity base class
        self.async_write_ha_state()  # type: ignore[attr-defined]

        try:
            await self._client.async_set_switching_group_state(self._group_id, turn_on)
        except (HcuApiError, ConnectionError) as err:
            # Revert to previous state on error
            self._attr_is_on = previous_state
            self._attr_assumed_state = False
            self.async_write_ha_state()  # type: ignore[attr-defined]
            _LOGGER.error(
                "Failed to set switching group %s state to %s: %s",
                self._group_id, turn_on, err
            )


class HcuSwitchingGroupBase(SwitchingGroupMixin, HcuGroupBaseEntity):
    """Base class for switching group entities (switch and light groups).

    This class consolidates the shared implementation for both HcuSwitchGroup
    and HcuLightGroup, eliminating code duplication while allowing subclasses
    to customize platform-specific attributes.
    """

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the switching group base."""
        super().__init__(coordinator, client, group_data)
        self._init_switching_group_state(group_data)
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_switching_group_state()
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the group on."""
        await self._async_set_switching_group_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the group off."""
        await self._async_set_switching_group_state(False)


class HcuHomeBaseEntity(CoordinatorEntity["HcuCoordinator"], HcuEntityPrefixMixin, Entity):
    """Base class for entities tied to the global 'home' object."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
    ) -> None:
        """Initialize the home base entity."""
        super().__init__(coordinator)
        self._client = client
        self._hcu_device_id = self._client.hcu_device_id
        self._home_uuid = self._client.state.get("home", {}).get("id")
        self._attr_assumed_state = False

    @property
    def _home(self) -> dict[str, Any]:
        """Return the latest home data from the client's state cache."""
        return self._client.state.get("home", {})

    @property
    def device_info(self) -> DeviceInfo:
        """Link this entity to the main HCU device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._hcu_device_id)},
        )
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return (super().extra_state_attributes or {}) | {"is_group": False}
    
    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return self._client.is_connected and bool(self._home)

    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._home_uuid in self.coordinator.data:
            self._attr_assumed_state = False
            self.async_write_ha_state()
