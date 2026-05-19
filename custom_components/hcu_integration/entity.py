# custom_components/hcu_integration/entity.py
from __future__ import annotations
from typing import TYPE_CHECKING, Any
import logging

from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ENTITY_PREFIX, HOMEMATIC_MODEL_PREFIXES, CONF_ADVANCED_ATTRIBUTES
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
        prefix = self.coordinator.config_entry.data.get(CONF_ENTITY_PREFIX, "")
        return prefix if isinstance(prefix, str) else ""

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
        """Set the entity name based on the channel label and feature.

        For unlabeled main entities (no channel_label, no feature_name), sets
        _attr_name=None and has_entity_name=True. Platform entities with a
        translation_key can override _attr_name afterward or skip this call
        entirely for the no-label case to let the translation provide the name.
        """
        base_name: str

        if feature_name:
            # Feature entity (sensor, binary_sensor, button)
            if channel_label:
                base_name = f"{channel_label} {feature_name}"
                self._attr_has_entity_name = False
            else:
                # Unlabeled channel: append channel index on channels > 1 to avoid
                # duplicate names when the same feature exists on multiple channels
                # (e.g. powerConsumption on both channels of a HmIP-PSM-2).
                if self._channel_index > 1:
                    base_name = f"{feature_name} {self._channel_index}"
                else:
                    base_name = feature_name
                self._attr_has_entity_name = True
        else:
            # Main entity (switch, light, cover, lock)
            if channel_label:
                base_name = channel_label
                self._attr_has_entity_name = False
            else:
                # No label: name=None + has_entity_name=True tells HA to show
                # just the device name. Platform entities override this when needed
                # (e.g., multi-channel disambiguation via _attr_name or placeholders).
                self._attr_name = None
                self._attr_has_entity_name = True
                return

        # Apply entity prefix for multi-home setups
        if self._entity_prefix:
            was_child_entity = self._attr_has_entity_name
            self._attr_has_entity_name = False
            if was_child_entity:
                device_label = self._device.get("label") or self._device.get("modelType") or self._device_id
                if base_name != device_label:
                    base_name = f"{device_label} {base_name}"
                else:
                    base_name = device_label
            self._attr_name = self._apply_prefix(base_name)
        else:
            self._attr_name = base_name

    def _get_functional_channel_count(self) -> int:
        """Count non-maintenance functional channels in this device.

        Used to decide whether to append a channel index for disambiguation
        when multiple channels of the same type exist without user labels.
        """
        return sum(
            1 for k, ch in (self._device.get("functionalChannels") or {}).items()
            if k != "0" and ch.get("functionalChannelType") != "DEVICE_BASE"
        )

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
    
        if model_type and model_type.startswith(HOMEMATIC_MODEL_PREFIXES):
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
            if hasattr(self, "object_id_base"):
                attrs["object_id_base"] = self.object_id_base
            if hasattr(self, "suggested_object_id"):
                attrs["suggested_object_id"] = self.suggested_object_id
            switchVisualization = self._channel.get("switchVisualization")
            if switchVisualization is not None:
                attrs["switchVisualization"] = switchVisualization
        
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
