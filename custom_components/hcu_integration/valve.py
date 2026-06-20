# custom_components/hcu_integration/valve.py
"""Valve platform for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.valve import ValveDeviceClass, ValveEntity, ValveEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HcuApiClient, HcuApiError
from .const import DOMAIN, HMIP_ON_TIME_INFINITE
from .entity import HcuBaseEntity

import logging

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HcuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the valve platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.VALVE):
        async_add_entities(entities)


class HcuWateringSwitch(HcuBaseEntity, ValveEntity):
    """Valve entity for a Homematic IP HCU watering actuator channel."""

    PLATFORM = Platform.VALVE
    _attr_icon = "mdi:water"
    _attr_device_class = ValveDeviceClass.WATER
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(channel_label=self._channel.get("label"))
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_watering"
        self._is_closed: bool = not self._channel.get("wateringActive", False)

    @property
    def is_closed(self) -> bool | None:
        return self._is_closed

    def _get_internal_on_time(self) -> float | None:
        """Return wateringOnTime if the companion 'Use Internal On Time' switch is ON, else None."""
        companion_uid = f"{self._device_id}_{self._channel_index}_use_internal_on_time"
        registry = er.async_get(self.hass)
        entity_id = registry.async_get_entity_id("switch", DOMAIN, companion_uid)
        if entity_id is None:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state != STATE_ON:
            return None
        on_time = self._channel.get("wateringOnTime") or 0
        if on_time == 0 or on_time == HMIP_ON_TIME_INFINITE:
            return None
        return float(on_time)

    @callback
    def _handle_coordinator_update(self) -> None:
        self._is_closed = not self._channel.get("wateringActive", False)
        self.async_write_ha_state()

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve (start watering)."""
        if on_time := self._get_internal_on_time():
            await self.async_turn_on_with_time(on_time)
            return
        self._is_closed = False
        self._attr_assumed_state = True
        self.async_write_ha_state()
        try:
            await self._client.async_set_watering_switch_state(
                self._device_id, self._channel_index, True
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to open valve %s: %s", self.name, err)
            self._is_closed = True
            self._attr_assumed_state = False
            self.async_write_ha_state()

    async def async_close_valve(self, **kwargs: Any) -> None:
        """Close the valve (stop watering)."""
        self._is_closed = True
        self._attr_assumed_state = True
        self.async_write_ha_state()
        try:
            await self._client.async_set_watering_switch_state(
                self._device_id, self._channel_index, False
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to close valve %s: %s", self.name, err)
            self._is_closed = False
            self._attr_assumed_state = False
            self.async_write_ha_state()

    async def async_turn_on_with_time(self, on_time: float) -> None:
        """Open the valve for a specific duration."""
        self._is_closed = False
        self._attr_assumed_state = True
        self.async_write_ha_state()
        try:
            await self._client.async_set_watering_switch_state(
                self._device_id, self._channel_index, True, on_time=on_time
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to open valve %s with time: %s", self.name, err)
            self._is_closed = True
            self._attr_assumed_state = False
            self.async_write_ha_state()
