# custom_components/hcu_integration/climate.py
"""Climate platform for the Homematic IP HCU integration."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
    PRESET_BOOST,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, Platform, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import HcuApiClient, HcuApiError
from .const import (
    ABSENCE_TYPE_PERIOD,
    ABSENCE_TYPE_PERMANENT,
    CONF_COMFORT_TEMPERATURE,
    DEFAULT_COMFORT_TEMPERATURE,
    DEFAULT_MAX_TEMP,
    DEFAULT_MIN_TEMP,
    PRESET_ECO,
    PRESET_PARTY,
)
from .entity import HcuGroupBaseEntity

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the climate platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.CLIMATE):
        async_add_entities(entities)


class HcuClimate(HcuGroupBaseEntity, ClimateEntity):
    """Representation of a Homematic IP HCU heating group."""

    PLATFORM = Platform.CLIMATE
    _attr_translation_key = "hcu_climate"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict[str, Any],
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the HCU Climate entity."""
        super().__init__(coordinator, client, group_data)
        self._config_entry = config_entry
        self._default_profile_name = "Standard"
        self._default_profile_index = "PROFILE_1"
        
        self._attr_preset_mode = None
        self._profiles: dict[str, str] = {}
        self._update_attributes_from_group_data()
    
    def _is_cooling(self) -> bool:
        """Return whether cooling is currently active."""
        return (
            self._group.get("cooling") is True
        )
    
    def _is_effective_cooling(self) -> bool:
        """Return whether cooling is currently active and not ignored."""
        return (
            self._group.get("cooling") is True
            and self._group.get("coolingIgnored") is not True
        )
    
    def _is_cooling_blocked_or_ignored(self) -> bool:
        """Return whether cooling is active but ignored or not allowed."""
        return (
            not self._group.get("coolingAllowed", True)
            or self._group.get("coolingIgnored", False)
        )
        
    @property
    def _indoor_climate_data(self) -> dict:
        """Return indoor climate data."""
        return(
            self._client.state.get("home", {})
            .get("functionalHomes", {})
            .get("INDOOR_CLIMATE", {})
        )
    
    def _is_eco_mode_active(self) -> bool:
        """Return currently eco mode"""
        return(
            self._indoor_climate_data.get("absenceType") in (ABSENCE_TYPE_PERIOD, ABSENCE_TYPE_PERMANENT)
            and self._group.get("ecoAllowed") is True
        )
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes_from_group_data()
        super()._handle_coordinator_update()

    def _update_attributes_from_group_data(self) -> None:
        """Update all HA state attributes from the latest group data."""
        # Update temperature limits from group data with fallback to HCU defaults
        self._attr_min_temp = self._group.get("minTemperature", DEFAULT_MIN_TEMP)
        self._attr_max_temp = self._group.get("maxTemperature", DEFAULT_MAX_TEMP)

        control_mode = self._group.get("controlMode")
        target_temp = self._group.get("setPointTemperature")
        
        if self._is_cooling():
            if self._is_cooling_blocked_or_ignored():
                self._attr_hvac_modes = [HVACMode.OFF]
            elif self._is_effective_cooling():
                self._attr_hvac_modes = [HVACMode.AUTO, HVACMode.COOL, HVACMode.OFF]
        else:
            self._attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]

        # Prevent state flapping during optimistic updates
        if (
            self._attr_assumed_state
            and self._attr_hvac_mode == HVACMode.OFF
            and control_mode == "MANUAL"
            and target_temp is not None
            and target_temp > self.min_temp
        ):
            return

        # Determine HVAC mode
        if not self._group.get("controllable", True):
            self._attr_hvac_mode = HVACMode.OFF
        else:
            if control_mode == "MANUAL":
                self._attr_hvac_mode = (
                    HVACMode.COOL if self._is_effective_cooling() else HVACMode.HEAT
                )
            elif control_mode in ("AUTOMATIC", "ECO"):
                self._attr_hvac_mode = HVACMode.AUTO
            else:
                self._attr_hvac_mode = HVACMode.OFF

        # Determine Target Temperature
        if self._is_eco_mode_active():
            self._attr_target_temperature = self._indoor_climate_data.get("ecoTemperature")
        else:
            self._attr_target_temperature = self._group.get("setPointTemperature")

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        if (humidity := self._group.get("humidity")) is not None:
            return humidity

        # Fallback: Find humidity from a device in the group
        for channel_ref in self._group.get("channels", []):
            device_id, channel_index = channel_ref.get("deviceId"), str(
                channel_ref.get("channelIndex")
            )
            if device := self._client.get_device_by_address(device_id):
                if channel := device.get("functionalChannels", {}).get(channel_index):
                    if (humidity := channel.get("humidity")) is not None:
                        return humidity
        return None

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        if (temp := self._group.get("actualTemperature")) is not None:
            return temp

        # Fallback: Find temperature from a device in the group
        for channel_ref in self._group.get("channels", []):
            device_id, channel_index = channel_ref.get("deviceId"), str(
                channel_ref.get("channelIndex")
            )
            if device := self._client.get_device_by_address(device_id):
                if channel := device.get("functionalChannels", {}).get(channel_index):
                    if (
                        temp := channel.get("actualTemperature")
                        or channel.get("valveActualTemperature")
                    ) is not None:
                        return temp
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the optional state attributes."""
        attributes = super().extra_state_attributes or {}
        if (valve_pos := self.current_valve_position) is not None:
            attributes |= {"valve_position": valve_pos}
        if (window_state := self._group.get("windowState")) is not None:
            attributes |= {"window_state": window_state}
        if (cooling := self._group.get("cooling")) is not None:
            attributes |= {"cooling": cooling}
        if (cooling_ignored := self._group.get("coolingIgnored")) is not None:
            attributes |= {"cooling_ignored": cooling_ignored}
        if (cooling_allowed := self._group.get("coolingAllowed")) is not None:
            attributes |= {"cooling_allowed": cooling_allowed}
        attributes |= {"is_cooling_blocked_or_ignored": self._is_cooling_blocked_or_ignored()}
        return attributes

    @property
    def current_valve_position(self) -> int | None:
        """Return the current valve position."""
        # Fallback: Find valve position from a device in the group
        valve_positions = []
        for channel_ref in self._group.get("channels", []):
            device_id, channel_index = channel_ref.get("deviceId"), str(
                channel_ref.get("channelIndex")
            )
            if device := self._client.get_device_by_address(device_id):
                if channel := device.get("functionalChannels", {}).get(channel_index):
                    if (valve_pos := channel.get("valvePosition")) is not None:
                        valve_positions.append(valve_pos)

        if not valve_positions:
            return None

        # Return the maximum valve position to represent the heating demand of the group.
        return int(round(max(valve_positions) * 100))

    
    @property
    def hvac_action(self) -> HVACAction:
        """Return the current HVAC action."""
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
    
        valve_pos = self.current_valve_position
        if valve_pos is None:
            return HVACAction.IDLE
    
        if self._is_cooling():
            if self._is_cooling_blocked_or_ignored():
                return HVACAction.OFF
            elif self._is_effective_cooling() and valve_pos > 0:
                return HVACAction.COOLING
            else: 
                return HVACAction.IDLE
        else:
            return HVACAction.HEATING if valve_pos > 0 else HVACAction.IDLE
        
    @property
    def hvac_mode(self) -> HVACMode:
        """Return the current HVAC Mode."""
        if self._attr_assumed_state and self._attr_hvac_mode is not None:
            return self._attr_hvac_mode

        if self._is_cooling() and self._is_cooling_blocked_or_ignored():
            return HVACMode.OFF
            
        control_mode = self._group.get("controlMode")
        if control_mode in ("AUTOMATIC", "ECO"):
            return HVACMode.AUTO
        if control_mode == "OFF":
            return HVACMode.OFF
        if control_mode == "MANUAL":
            return HVACMode.COOL if self._is_effective_cooling() else HVACMode.HEAT
        return HVACMode.OFF
        
    @property
    def preset_modes_map(self) -> dict[str, str]:
        """Return mapping of profile name -> index, dynamically from group data."""
        profiles: dict[str, str] = {}
        default_name = "Standard"
        for profile in self._group.get("profiles", {}).values():
            if profile.get("enabled") and profile.get("visible"):
                profile_index = profile["index"]
                profile_name = profile.get("name")
                if profile_index == "PROFILE_1":
                    default_name = profile_name or "Standard"
                    profiles[default_name] = profile_index
                elif profile_name:
                    profiles[profile_name] = profile_index
        self._default_profile_name = default_name
        return profiles
    
    @property
    def preset_mode(self) -> str:
        """Return the current preset mode."""
        
        if self._attr_assumed_state and self._attr_preset_mode is not None:
            return self._attr_preset_mode

        if self._is_cooling():
            if self._is_cooling_blocked_or_ignored():
                return PRESET_ECO

        current_map = self.preset_modes_map
        if self._group.get("boostMode"):
            return PRESET_BOOST
        elif self._is_eco_mode_active():
            return PRESET_ECO
        elif self._group.get("partyMode"):
            return PRESET_PARTY
        else:
            active_profile_index = self._group.get("activeProfile")
            for name, index in current_map.items():
                if index == active_profile_index:
                    return name
            return self._default_profile_name
            
    @property
    def preset_modes(self) -> list[str]:
        """Return available preset modes."""
        if self._is_cooling():
            if self._is_cooling_blocked_or_ignored():
                return [PRESET_ECO]
            elif self._is_effective_cooling():
                return [PRESET_BOOST, PRESET_ECO, PRESET_PARTY, *self.preset_modes_map.keys()]
        else:
            return [PRESET_BOOST, PRESET_ECO, PRESET_PARTY, *self.preset_modes_map.keys()]
                
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        
        if self._is_cooling():
            if self._is_cooling_blocked_or_ignored():
                return

        self._attr_assumed_state = True
        self._attr_target_temperature = temperature

        # Only update HVAC mode if we're explicitly turning heating off (temp at minimum)
        # or if we're not in AUTO mode (to avoid disrupting scheduled operation)
        if temperature <= self.min_temp:
            self._attr_hvac_mode = HVACMode.OFF
        elif self._attr_hvac_mode not in (HVACMode.AUTO, HVACMode.HEAT):
            self._attr_hvac_mode = HVACMode.HEAT

        self.async_write_ha_state()

        # Only switch to MANUAL control mode if we're in HEAT mode (manual operation)
        # If in AUTO mode, keep AUTO and let the setpoint be a temporary override
        # that will revert at the next scheduled temperature change
        if self._attr_hvac_mode == HVACMode.HEAT:
            if self._group.get("controlMode") != "MANUAL":
                await self._client.async_set_group_control_mode(self._group_id, "MANUAL")

        await self._client.async_set_group_setpoint_temperature(
            self._group_id, temperature
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        self._attr_assumed_state = True
        self._attr_hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            self._attr_target_temperature = self.min_temp
            self.async_write_ha_state()
            if self._group.get("controlMode") != "MANUAL":
                await self._client.async_set_group_control_mode(self._group_id, "MANUAL")
            if self._group.get("setPointTemperature") != self.min_temp:
                await self._client.async_set_group_setpoint_temperature(
                    self._group_id, self.min_temp
                )

        elif hvac_mode == HVACMode.AUTO:
            self.async_write_ha_state()
            if self._group.get("controlMode") != "AUTOMATIC":
                await self._client.async_set_group_control_mode(
                    self._group_id, "AUTOMATIC"
                )

        elif hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            comfort_temp = self._config_entry.options.get(
                CONF_COMFORT_TEMPERATURE, DEFAULT_COMFORT_TEMPERATURE
            )
            #self._attr_target_temperature = comfort_temp
            self.async_write_ha_state()

            if self._group.get("controlMode") != "MANUAL":
                await self._client.async_set_group_control_mode(self._group_id, "MANUAL")

            #await self._client.async_set_group_setpoint_temperature(
            #    self._group_id, comfort_temp
            #)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set new preset mode."""
        current_preset = self.preset_mode
        self._attr_assumed_state = True
        self._attr_preset_mode = preset_mode
        self.async_write_ha_state()
        
        try:
            if preset_mode == PRESET_BOOST:
                await self._client.async_set_group_boost(
                    group_id=self._group_id, boost=True
                )
            
            #This Action must be executed globally
            #elif preset_mode == PRESET_ECO:
            #    Disable Set EcoMode from Heating Group
            #    await self._client.async_activate_absence_permanent()
            #elif preset_mode == PRESET_PARTY:
            #    Disable Set PRESET_PARTY from Heating Group
            #    comfort_temp = self._config_entry.options.get(
            #        CONF_COMFORT_TEMPERATURE, DEFAULT_COMFORT_TEMPERATURE
            #    )
            #    end_time = dt_util.now() + timedelta(hours=4)
            #    await self.async_activate_party_mode(
            #        temperature=comfort_temp,
            #        end_time_str=end_time.strftime("%Y_%m_%d %H:%M"),
            #    )

            elif preset_mode in self.preset_modes_map:
                if current_preset == PRESET_BOOST:
                    await self._client.async_set_group_boost(
                        group_id=self._group_id, boost=False
                    )
                #elif current_preset == PRESET_ECO:
                    #await self._client.async_deactivate_absence()
                    #This Action must be executed globally
                #elif current_preset == PRESET_PARTY:
                    #await self._client.async_deactivate_vacation()
                    #This Action must be executed globally

                if self._group.get("controlMode") != "AUTOMATIC":
                    await self._client.async_set_group_control_mode(
                        group_id=self._group_id, mode="AUTOMATIC"
                    )

                await self._client.async_set_group_active_profile(
                    group_id=self._group_id, profile_index=self.preset_modes_map[preset_mode]
                )
            self._attr_assumed_state = False
            self._attr_preset_mode = None
            self.async_write_ha_state()
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to set preset mode: %s", err)
            self._attr_assumed_state = False
            self._attr_preset_mode = None
            self.async_write_ha_state()

    async def async_activate_party_mode(
        self,
        temperature: float,
        end_time_str: str | None = None,
        duration: int | None = None,
    ) -> None:
        """Service call to activate party mode."""
        if not end_time_str and not duration:
            raise ValueError(
                "Either end_time or duration must be provided for party mode."
            )

        end_time = end_time_str or (
            dt_util.now() + timedelta(seconds=duration)
        ).strftime("%Y_%m_%d %H:%M")

        self._attr_assumed_state = True
        self._attr_preset_mode = PRESET_PARTY
        self.async_write_ha_state()

        try:
            await self._client.async_activate_group_party_mode(
                group_id=self._group_id,
                temperature=temperature,
                end_time=end_time,
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to activate party mode: %s", err)
            self._attr_assumed_state = False
            self.async_write_ha_state()
