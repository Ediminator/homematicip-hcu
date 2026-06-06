# custom_components/hcu_integration/select.py
"""Select platform for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HcuApiClient, HcuApiError
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
    """Set up the select platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.SELECT):
        async_add_entities(entities)


class HcuPowerUpSwitchState(HcuBaseEntity, SelectEntity):
    """Select entity for the powerUpSwitchState device configuration."""

    PLATFORM = Platform.SELECT
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_entity_registry_enabled_default = False
    _attr_options = ["PERMANENT_OFF", "PERMANENT_ON"]
    _attr_icon = "mdi:power-settings"

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
        feature: str,
        mapping: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        self._feature = feature
        channel_label = self._channel.get("label")
        self._set_entity_name(channel_label=channel_label, feature_name=mapping.get("name", "Power-up Switch State"))
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_powerUpSwitchState"

    @property
    def current_option(self) -> str | None:
        return self._channel.get(self._feature)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        try:
            await self._client.async_set_power_up_switch_state(
                self._device_id, self._channel_index, option
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error(
                "Failed to set powerUpSwitchState for %s channel %s: %s",
                self._device_id, self._channel_index, err,
            )
