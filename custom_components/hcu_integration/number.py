# custom_components/hcu_integration/number.py
"""Number platform for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

import logging
from .api import HcuApiClient
from .entity import HcuBaseEntity

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from . import HcuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][config_entry.entry_id]
    if entities := coordinator.entities.get(Platform.NUMBER):
        async_add_entities(entities)


class HcuConfigRampTime(RestoreEntity, HcuBaseEntity, NumberEntity):
    """HA-local config number per channel: ramp time in seconds for dimming actors.

    State is stored in HA only (not in HCU). Default: 0.0 (disabled).
    When > 0, the value is passed as rampTime to the API on every turn_on/turn_off.
    """

    PLATFORM = Platform.NUMBER
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:timer-cog-outline"
    _attr_native_min_value = 0.0
    _attr_native_max_value = 255.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(
            channel_label=self._channel.get("label"),
            feature_name="Ramp Time",
        )
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_ramp_time"
        self._attr_native_value = 0.0

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) is not None:
            try:
                self._attr_native_value = float(last_state.state)
            except (ValueError, TypeError):
                self._attr_native_value = 0.0

    @property
    def native_value(self) -> float:
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        pass
