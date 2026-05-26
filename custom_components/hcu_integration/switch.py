# custom_components/hcu_integration/switch.py
"""Switch platform for the Homematic IP HCU integration."""
from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

import logging
from .const import HMIP_DEVICE_TYPE_TO_DEVICE_CLASS, HMIP_ON_TIME_INFINITE, API_PATHS
from .entity import HcuBaseEntity, SwitchStateMixin, HcuSwitchingGroupBase
from .api import HcuApiClient, HcuApiError

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HcuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.SWITCH):
        async_add_entities(entities)


class HcuSwitch(SwitchStateMixin, HcuBaseEntity, SwitchEntity):
    """Representation of a standard Homematic IP HCU switch."""

    PLATFORM = Platform.SWITCH

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_on"

        device_type = self._device.get("type")
        switch_visualization = self._channel.get("switchVisualization")
        if switch_visualization == "OUTLET":
            self._attr_device_class = SwitchDeviceClass.OUTLET
        elif switch_visualization == "SWITCH":
            self._attr_device_class = SwitchDeviceClass.SWITCH
        else:
            self._attr_device_class = HMIP_DEVICE_TYPE_TO_DEVICE_CLASS.get(device_type)
        self._init_switch_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_switch_state_from_coordinator()
        super()._handle_coordinator_update()

    async def _call_switch_api(self, turn_on: bool) -> None:
        """Call the API to set the switch state."""
        await self._client.async_set_switch_state(
            self._device_id, self._channel_index, turn_on
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if on_time := self._get_internal_on_time():
            await self.async_turn_on_with_time(on_time)
            return
        await self._async_set_optimistic_state(True, "switch")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._async_set_optimistic_state(False, "switch")

    async def async_play_sound(
        self, sound_file: str, volume: float, duration: float
    ) -> None:
        """Service call to play a sound on this device."""
        await self._client.async_set_sound_file(
            device_id=self._device_id,
            channel_index=self._channel_index,
            sound_file=sound_file,
            volume=volume,
            duration=duration,
        )

    async def async_turn_on_with_time(self, on_time: float) -> None:
        """Turn the switch on for a specific duration."""
        # Store previous state for rollback
        previous_is_on = self._attr_is_on
        previous_assumed_state = self._attr_assumed_state

        # Optimistic update
        self._attr_is_on = True
        self._attr_assumed_state = True
        self.async_write_ha_state()
        
        try:
            await self._client.async_set_switch_state(
                self._device_id, self._channel_index, True, on_time=on_time
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to turn on %s with time: %s", self.name, err)
            # Revert to previous state
            self._attr_is_on = previous_is_on
            self._attr_assumed_state = previous_assumed_state
            self.async_write_ha_state()


class HcuWateringSwitch(SwitchStateMixin, HcuBaseEntity, SwitchEntity):
    """Representation of a Homematic IP HCU watering controller."""

    PLATFORM = Platform.SWITCH
    _attr_icon = "mdi:water"
    _state_channel_key = "wateringActive"

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_watering"
        self._init_switch_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_switch_state_from_coordinator()
        super()._handle_coordinator_update()

    async def _call_switch_api(self, turn_on: bool) -> None:
        """Call the API to set the watering switch state."""
        await self._client.async_set_watering_switch_state(
            self._device_id, self._channel_index, turn_on
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the watering on."""
        await self._async_set_optimistic_state(True, "watering switch")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the watering off."""
        await self._async_set_optimistic_state(False, "watering switch")

    async def async_turn_on_with_time(self, on_time: float) -> None:
        """Turn the switch on for a specific duration."""
        # Store previous state for rollback
        previous_is_on = self._attr_is_on
        previous_assumed_state = self._attr_assumed_state

        # Optimistic update
        self._attr_is_on = True
        self._attr_assumed_state = True
        self.async_write_ha_state()
        
        try:
            await self._client.async_set_watering_switch_state(
                self._device_id, self._channel_index, True, on_time=on_time
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to turn on %s with time: %s", self.name, err)
            # Revert to previous state
            self._attr_is_on = previous_is_on
            self._attr_assumed_state = previous_assumed_state
            self.async_write_ha_state()


class HcuConfigUseInternalOnTime(RestoreEntity, HcuBaseEntity, SwitchEntity):
    """HA-local config switch per channel: whether to use internal on-time when switching.

    State is stored in HA only (not in HCU). Default: off.
    """

    PLATFORM = Platform.SWITCH
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:timer-cog-outline"

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(channel_label=self._channel.get("label"), feature_name="Use Internal On Time")
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_use_internal_on_time"
        self._attr_is_on = False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            self._attr_is_on = last_state.state == STATE_ON

        if self._attr_is_on:
            internal_link = self._channel.get("internalLinkConfiguration") or {}
            on_time = self._channel.get("onTime") or internal_link.get("onTime") or 0
            if on_time == 0 or on_time == HMIP_ON_TIME_INFINITE:
                _LOGGER.debug(
                    "Disabling 'Use Internal On Time' for %s on startup: onTime is not configured (value: %s)",
                    self.name,
                    on_time,
                )
                self._attr_is_on = False

    @property
    def is_on(self) -> bool:
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        internal_link = self._channel.get("internalLinkConfiguration") or {}
        on_time = self._channel.get("onTime") or internal_link.get("onTime") or 0
        if on_time == 0 or on_time == HMIP_ON_TIME_INFINITE:
            _LOGGER.debug(
                "Cannot enable 'Use Internal On Time' for %s: onTime is not configured (value: %s)",
                self.name,
                on_time,
            )
            return
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        pass


class HcuSwitchGroup(HcuSwitchingGroupBase, SwitchEntity):
    """Representation of a Homematic IP HCU switching group."""

    PLATFORM = Platform.SWITCH
    
class HcuWateringGroup(HcuSwitchingGroupBase, SwitchEntity):
    """Representation of a Homematic IP HCU watering switching group."""

    PLATFORM = Platform.SWITCH

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the HCU Cover group."""
        super().__init__(coordinator, client, group_data)

    @property
    def is_on(self) -> bool | None:
        """Return if the water group is activ."""
        state = self._group.get("wateringActive")
        return state
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the watering on."""
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_WATERING_SWITCH_STATE"],
            self._group_id,
            {"wateringActive": True},
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the watering off."""
        await self._client.async_group_control(
            API_PATHS["SET_GROUP_WATERING_SWITCH_STATE"],
            self._group_id,
            {"wateringActive": False},
        )
    
    async def async_turn_on_with_time(self, on_time: float) -> None:
        """Turn the switch on for a specific duration."""
        # Store previous state for rollback
        previous_is_on = self._attr_is_on
        previous_assumed_state = self._attr_assumed_state

        # Optimistic update
        self._attr_is_on = True
        self._attr_assumed_state = True
        self.async_write_ha_state()
        
        try:
            await self._client.async_group_control(
                API_PATHS["SET_GROUP_WATERING_SWITCH_STATE_WITH_TIME"],
                self._group_id,
                {"wateringActive": True, "wateringTime": on_time},
                )
                
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to turn on %s with time: %s", self.name, err)
            # Revert to previous state
            self._attr_is_on = previous_is_on
            self._attr_assumed_state = previous_assumed_state
            self.async_write_ha_state()
