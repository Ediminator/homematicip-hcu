# custom_components/hcu_integration/cover.py
"""Cover platform for the Homematic IP HCU integration."""
from typing import TYPE_CHECKING, Any
import logging
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import HMIP_DEVICE_TYPE_TO_DEVICE_CLASS, API_PATHS
from .entity import HcuBaseEntity, HcuGroupBaseEntity
from .api import HcuApiClient

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)

# Tilt feature flags used by both individual covers and cover groups
TILT_FEATURES = (
    CoverEntityFeature.SET_TILT_POSITION
    | CoverEntityFeature.OPEN_TILT
    | CoverEntityFeature.CLOSE_TILT
    | CoverEntityFeature.STOP_TILT
)

def _level_to_position(level: float | None) -> int | None:
    """Convert HCU level (0.0-1.0, 1.0 is closed) to Home Assistant position (0-100, 0 is closed)."""
    if level is None:
        return None
    return round((1 - level) * 100)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the cover platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.COVER):
        async_add_entities(entities)


class HcuCover(HcuBaseEntity, CoverEntity):
    """Representation of an HCU Cover (shutter or blind) device channel."""

    PLATFORM = Platform.COVER

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        **kwargs: Any,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        # CRITICAL FIX: Explicitly call naming helper (restored from working version)
        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_cover"

        device_type = self._device.get("type")
        self._attr_device_class = HMIP_DEVICE_TYPE_TO_DEVICE_CLASS.get(device_type)

        # CRITICAL FIX: Restore dynamic level property detection
        # Some devices use primaryShadingLevel, others (BROLL/FROLL) use shutterLevel
        if "primaryShadingLevel" in self._channel:
            self._async_set_level = self._client.async_set_primary_shading_level
            self._level_property = "primaryShadingLevel"
        else:
            self._async_set_level = self._client.async_set_shutter_level
            self._level_property = "shutterLevel"

        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        
        # Check for tilt support: slatsLevel must be present AND have a valid (non-None)
        # value. The HCU API returns this key for all blind-capable devices (like DRBL4),
        # but with None value when slats/tilt are not actually configured.
        slats_level = self._channel.get("slatsLevel")
        device_name = self._device.get("label", self._device_id)
        if slats_level is not None:
            self._attr_supported_features |= TILT_FEATURES
            self._attr_device_class = CoverDeviceClass.BLIND
            _LOGGER.debug(
                "Device %s channel %s detected as BLIND with tilt support (slatsLevel=%s)",
                device_name,
                self._channel_index,
                slats_level,
            )
        elif self._attr_device_class == CoverDeviceClass.BLIND:
            # Device type mapping classified this as BLIND, but no tilt support is
            # available (slatsLevel is None). Reclassify as SHUTTER for consistency.
            self._attr_device_class = CoverDeviceClass.SHUTTER
            _LOGGER.debug(
                "Device %s channel %s reclassified from BLIND to SHUTTER (no tilt support)",
                device_name,
                self._channel_index,
            )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover."""
        return _level_to_position(self._channel.get(self._level_property))

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover."""
        return _level_to_position(self._channel.get("slatsLevel"))

    @property
    def is_opening(self) -> bool:
        return (self._channel.get("lastShadingDirection") == "LIGHTER" and self._channel.get("processing") == True)

    @property
    def is_closing(self) -> bool:
        return (self._channel.get("lastShadingDirection") == "DARKER" and self._channel.get("processing") == True)

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._attr_assumed_state = True
        await self._async_set_level(self._device_id, self._channel_index, 0.0)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._attr_assumed_state = True
        await self._async_set_level(self._device_id, self._channel_index, 1.0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._attr_assumed_state = True
        await self._client.async_stop_cover(self._device_id, self._channel_index)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION, 100)
        self._attr_assumed_state = True
        shutter_level = round((100 - position) / 100.0, 2)
        await self._async_set_level(self._device_id, self._channel_index, shutter_level)
        
    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Move the cover tilt to a specific position."""
        position = kwargs.get(ATTR_TILT_POSITION, 100)
        self._attr_assumed_state = True
        slats_level = round((100 - position) / 100.0, 2)
        
        # Pass current shutter level if available, as per API docs
        # We must fetch the level using the dynamic property to support both shutterLevel and primaryShadingLevel
        current_level = self._channel.get(self._level_property)
        if current_level is None:
            _LOGGER.warning(
                "Cannot set tilt position for %s: current level unknown",
                self.name,
            )
            return

        await self._client.async_set_slats_level(
            self._device_id, self._channel_index, slats_level, shutter_level=current_level
        )
    
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open tilt position."""
        self._attr_assumed_state = True
        current_level = self._channel.get(self._level_property)
        if current_level is None:
            _LOGGER.warning(
                "Cannot set tilt position for %s: current level unknown",
                self.name,
            )
            return

        await self._client.async_set_slats_level(
            self._device_id, self._channel_index, 0.0, shutter_level=current_level
        )
    
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close tilt position."""
        self._attr_assumed_state = True
        current_level = self._channel.get(self._level_property)
        if current_level is None:
            _LOGGER.warning(
                "Cannot set tilt position for %s: current level unknown",
                self.name,
            )
            return

        await self._client.async_set_slats_level(
            self._device_id, self._channel_index, 1.0, shutter_level=current_level
        )
        
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        self._attr_assumed_state = True
        await self._client.async_stop_cover(self._device_id, self._channel_index)

class HcuGarageDoorCover(HcuBaseEntity, CoverEntity):
    """Representation of an HCU Garage Door Cover."""

    PLATFORM = Platform.COVER

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        **kwargs,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        # REFACTOR: Correctly call the centralized naming helper.
        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_cover"

        device_type = self._device.get("type")
        self._attr_device_class = HMIP_DEVICE_TYPE_TO_DEVICE_CLASS.get(device_type)

        self._is_stateful = "doorState" in self._channel
        if self._is_stateful:
            self._attr_supported_features = (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
            )
        else:
            self._attr_supported_features = (
                CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
            )

    @property
    def is_closed(self) -> bool | None:
        if not self._is_stateful:
            return None
        return self._channel.get("doorState") == "CLOSED"

    @property
    def is_opening(self) -> bool:
        if not self._is_stateful:
            return False
        return self._channel.get("doorMotion") == "OPENING"

    @property
    def is_closing(self) -> bool:
        if not self._is_stateful:
            return False
        return self._channel.get("doorMotion") == "CLOSING"

    async def async_open_cover(self, **kwargs) -> None:
        self._attr_assumed_state = True
        if self._is_stateful:
            await self._client.async_send_door_command(
                self._device_id, self._channel_index, "OPEN"
            )
        else:
            await self._client.async_toggle_garage_door_state(
                self._device_id, self._channel_index
            )

    async def async_close_cover(self, **kwargs) -> None:
        self._attr_assumed_state = True
        if self._is_stateful:
            await self._client.async_send_door_command(
                self._device_id, self._channel_index, "CLOSE"
            )
        else:
            await self._client.async_toggle_garage_door_state(
                self._device_id, self._channel_index
            )

    async def async_stop_cover(self, **kwargs) -> None:
        if not self._is_stateful:
            return
        self._attr_assumed_state = True
        await self._client.async_send_door_command(
            self._device_id, self._channel_index, "STOP"
        )


class HcuCoverGroup(HcuGroupBaseEntity, CoverEntity):
    """Representation of an HCU Cover (shutter or blind) group."""

    PLATFORM = Platform.COVER

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the HCU Cover group."""
        super().__init__(coordinator, client, group_data)

        self._attr_supported_features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
            | CoverEntityFeature.SET_POSITION
        )
        
        # Check for tilt support: secondaryShadingLevel must be present AND have a valid
        # (non-None) value. The HCU API returns this key for all shutter groups, but with
        # None value for groups containing only roller shutters (BROLL) without tilt support.
        secondary_level = self._group.get("secondaryShadingLevel")
        group_name = self._group.get("label", self._group_id)
        if secondary_level is not None:
            self._attr_supported_features |= TILT_FEATURES
            self._attr_device_class = CoverDeviceClass.BLIND
            _LOGGER.debug(
                "Group %s detected as BLIND with tilt support (secondaryShadingLevel=%s)",
                group_name,
                secondary_level,
            )
        else:
            self._attr_device_class = CoverDeviceClass.SHUTTER
            _LOGGER.debug(
                "Group %s detected as SHUTTER without tilt support",
                group_name,
            )

    @property
    def current_cover_position(self) -> int | None:
        """Return current position of cover group."""
        return _level_to_position(self._group.get("primaryShadingLevel"))

    @property
    def current_cover_tilt_position(self) -> int | None:
        """Return current tilt position of cover group."""
        return _level_to_position(self._group.get("secondaryShadingLevel"))

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover group is closed."""
        position = self.current_cover_position
        if position is None:
            return None
        return position == 0

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover group."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            self._group_id,
            {"primaryShadingLevel": 0.0},
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover group."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            self._group_id,
            {"primaryShadingLevel": 1.0},
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover group."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["STOP_GROUP_COVER"], self._group_id
        )

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover group position."""
        position = kwargs[ATTR_POSITION]
        self._attr_assumed_state = True
        shutter_level = round((100 - position) / 100.0, 2)
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            self._group_id,
            {"primaryShadingLevel": shutter_level},
        )

    async def async_set_cover_tilt_position(self, **kwargs: Any) -> None:
        """Set the cover group tilt position."""
        position = kwargs[ATTR_TILT_POSITION]
        shutter_level = self._group.get("shutterLevel")
        self._attr_assumed_state = True
        secondary_level = round((100 - position) / 100.0, 2)
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SECONDARY_SHADING_LEVEL"],
            self._group_id,
            {"shutterLevel": shutter_level, "secondaryShadingLevel": secondary_level},
        )
    
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close tilt position."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            self._group_id,
            {"primaryShadingLevel": 1.0},
        )
        
    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open tilt position."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            self._group_id,
            {"primaryShadingLevel": 0.0},
        )
        
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["STOP_GROUP_COVER"], self._group_id
        )
