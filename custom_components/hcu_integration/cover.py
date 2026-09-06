# custom_components/hcu_integration/cover.py
"""Cover platform for the Homematic IP HCU integration."""
from typing import TYPE_CHECKING, Any
import logging
import time
from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

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

# How long a locally commanded (optimistic) movement direction is trusted over
# the HCU-reported lastShadingDirection. Covers the ~1-2s the HCU needs to
# correct a stale direction after a command (see issue #433), while still
# letting a real external override (wall switch, native app) during an
# ongoing HA-commanded move win back the display within a few seconds instead
# of being stuck for the rest of that move.
OPTIMISTIC_DIRECTION_GRACE_SECONDS = 3.0

# How long to wait after processing first flips to True before trusting the
# raw lastShadingDirection field at all. The HCU's own direction data can be
# stale/wrong for the first moment or two of a move regardless of who
# triggered it (HA, native app, wall switch) - see issue #433 and its
# native-app follow-up. Since there is no local optimistic direction for
# externally triggered moves, we simply don't show a direction until it has
# had time to settle, rather than risk showing the wrong one.
DIRECTION_SETTLE_SECONDS = 3.0

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

        # Optimistic movement direction, set locally when HA issues a move command.
        # The HCU briefly reports the *previous* movement's lastShadingDirection
        # after processing flips to True, before pushing the corrected value a
        # moment later. Overriding with the direction we just commanded avoids
        # that flicker. It is cleared once the coordinator confirms the move has
        # actually finished (see _handle_coordinator_update below), and it also
        # expires on its own after OPTIMISTIC_DIRECTION_GRACE_SECONDS so that a
        # real external override (wall switch, native app) taking over an
        # ongoing HA-commanded move isn't masked for the rest of that move.
        self._optimistic_direction: str | None = None
        self._optimistic_direction_set_at: float | None = None

        # Wall-clock time (monotonic) this move started, i.e. when we first
        # saw processing=True. Used to hold back the raw lastShadingDirection
        # field for DIRECTION_SETTLE_SECONDS (see constant above) for moves
        # that have no local optimistic direction to rely on instead.
        self._processing_started_at: float | None = None
        self._settle_unsub: Any = None

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

    def _set_optimistic_direction(self, direction: str | None) -> None:
        """Set (or clear) the locally commanded direction override, timestamped for expiry."""
        self._optimistic_direction = direction
        self._optimistic_direction_set_at = time.monotonic() if direction is not None else None

    @property
    def _active_optimistic_direction(self) -> str | None:
        """Return the optimistic direction if it hasn't expired yet, else None.

        The expiry ensures that a real external override (wall switch, native
        app) taking over an already-running HA-commanded move eventually wins
        back the displayed direction, instead of being masked indefinitely
        until the HCU reports processing=False.
        """
        if self._optimistic_direction is None or self._optimistic_direction_set_at is None:
            return None
        if time.monotonic() - self._optimistic_direction_set_at > OPTIMISTIC_DIRECTION_GRACE_SECONDS:
            return None
        return self._optimistic_direction

    @property
    def _raw_direction_settled(self) -> bool:
        """Whether enough time has passed since this move started for a
        stale/wrong lastShadingDirection to have self-corrected. Only
        consulted when there is no local optimistic direction, i.e. for
        moves HA didn't itself command (native app, wall switch)."""
        if self._processing_started_at is None:
            return True
        return time.monotonic() - self._processing_started_at >= DIRECTION_SETTLE_SECONDS

    @property
    def is_opening(self) -> bool:
        if self._channel.get("processing") != True:
            return False
        if (direction := self._active_optimistic_direction) is not None:
            return direction == "opening"
        if not self._raw_direction_settled:
            return False
        return self._channel.get("lastShadingDirection") == "LIGHTER"

    @property
    def is_closing(self) -> bool:
        if self._channel.get("processing") != True:
            return False
        if (direction := self._active_optimistic_direction) is not None:
            return direction == "closing"
        if not self._raw_direction_settled:
            return False
        return self._channel.get("lastShadingDirection") == "DARKER"

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        pos = self.current_cover_position
        if pos is None:
            return None
        return pos == 0

    def _cancel_direction_settle_check(self) -> None:
        """Cancel a pending settle-check callback, if any."""
        if self._settle_unsub is not None:
            self._settle_unsub()
            self._settle_unsub = None

    def _schedule_direction_settle_check(self) -> None:
        """Force a state refresh once DIRECTION_SETTLE_SECONDS has passed.

        Without this, if the HCU sends no further push during the settle
        window, the entity would keep showing no direction until some
        unrelated update happens to trigger a refresh.
        """
        self._cancel_direction_settle_check()
        if self.hass is None:
            return
        self._settle_unsub = async_call_later(
            self.hass, DIRECTION_SETTLE_SECONDS, self._async_direction_settled
        )

    @callback
    def _async_direction_settled(self, _now: Any) -> None:
        """Callback fired once the settle window has elapsed."""
        self._settle_unsub = None
        if self._channel.get("processing") == True:
            self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Clean up any pending settle-check callback."""
        self._cancel_direction_settle_check()
        await super().async_will_remove_from_hass()

    def _handle_coordinator_update(self) -> None:
        """Track when the current move started and clear stale overrides once it ends."""
        if self._device_id in self.coordinator.data:
            processing = self._channel.get("processing") == True
            if processing:
                if self._processing_started_at is None:
                    self._processing_started_at = time.monotonic()
                    self._schedule_direction_settle_check()
            else:
                self._processing_started_at = None
                self._cancel_direction_settle_check()
                self._set_optimistic_direction(None)
        super()._handle_coordinator_update()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self._attr_assumed_state = True
        self._set_optimistic_direction("opening")
        await self._async_set_level(self._device_id, self._channel_index, 0.0)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        self._attr_assumed_state = True
        self._set_optimistic_direction("closing")
        await self._async_set_level(self._device_id, self._channel_index, 1.0)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        self._attr_assumed_state = True
        self._set_optimistic_direction(None)
        await self._client.async_stop_cover(self._device_id, self._channel_index)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Move the cover to a specific position."""
        position = kwargs.get(ATTR_POSITION, 100)
        self._attr_assumed_state = True
        current_position = self.current_cover_position
        if current_position is None:
            self._set_optimistic_direction(None)
        elif position > current_position:
            self._set_optimistic_direction("opening")
        elif position < current_position:
            self._set_optimistic_direction("closing")
        else:
            self._set_optimistic_direction(None)
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
        self._is_ventilationPositionSupported = self._channel.get(
            "ventilationPositionSupported", False
        )
        if self._is_ventilationPositionSupported:
            self._attr_supported_features |= CoverEntityFeature.OPEN_TILT

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

    async def async_open_cover_tilt(self, **kwargs) -> None:
        if not self._is_ventilationPositionSupported:
            return
        self._attr_assumed_state = True
        await self._client.async_send_door_command(
            self._device_id, self._channel_index, "PARTIAL_OPEN"
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
            {"shutterLevel": shutter_level, "slatsLevel": secondary_level, "secondaryShadingLevel": secondary_level},
        )
    
    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close tilt position."""
        shutter_level = self._group.get("shutterLevel")
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SECONDARY_SHADING_LEVEL"],
            self._group_id,
            {"shutterLevel": shutter_level, "slatsLevel": 1.0, "secondaryShadingLevel": 1.0},
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open tilt position."""
        shutter_level = self._group.get("shutterLevel")
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_SECONDARY_SHADING_LEVEL"],
            self._group_id,
            {"shutterLevel": shutter_level, "slatsLevel": 0.0, "secondaryShadingLevel": 0.0},
        )
        
    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop cover tilt."""
        self._attr_assumed_state = True
        await self._client.async_group_control(
            API_PATHS["STOP_GROUP_COVER"], self._group_id
        )
