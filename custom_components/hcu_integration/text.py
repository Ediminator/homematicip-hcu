# custom_components/hcu_integration/text.py
"""Text entities for the HCU integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.components.text import TextEntity, TextMode
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_DEVICE_PINS
from .entity import HcuBaseEntity

if TYPE_CHECKING:
    from .api import HcuApiClient
    from .coordinator import HcuConfigEntry, HcuCoordinator

_LOGGER = logging.getLogger(__name__)


# State is pushed by the HCU, so there is no polling to limit, and actions may
# run in parallel.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HcuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the text platform from a config entry."""
    coordinator = config_entry.runtime_data
    coordinator.async_register_platform(Platform.TEXT, async_add_entities)
    if entities := coordinator.entities.get(Platform.TEXT):
        async_add_entities(entities)


class HcuDevicePin(HcuBaseEntity, TextEntity):
    """PIN input field for a Pull Latch button."""

    PLATFORM = Platform.TEXT
    _attr_pattern = "[0-9]*"
    _attr_translation_key = "hcu_device_pin"
    _attr_mode = TextMode.PASSWORD
    _attr_native_min = 0
    _attr_native_max = 20
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        self._config_entry = coordinator.config_entry
        self._attr_unique_id = f"{self._device_id}_device_pin"
        self._pin_key = self._device_id

    def _stored_pin(self) -> str:
        return self._config_entry.options.get(CONF_DEVICE_PINS, {}).get(
            self._pin_key, ""
        )

    @property
    def native_value(self) -> str:
        pin = self._stored_pin()
        return "*" * len(pin) if pin else ""

    async def async_set_value(self, value: str) -> None:
        # If the submitted value is all asterisks matching the current masked length,
        # the user confirmed without changing the PIN — skip the update.
        current_pin = self._stored_pin()
        if value == current_pin or (
            value and len(value) == len(current_pin) and set(value) == {"*"}
        ):
            return

        new_pins = dict(self._config_entry.options.get(CONF_DEVICE_PINS, {}))
        if value:
            new_pins[self._pin_key] = value
        else:
            new_pins.pop(self._pin_key, None)
        self.hass.config_entries.async_update_entry(
            self._config_entry,
            options={**self._config_entry.options, CONF_DEVICE_PINS: new_pins},
        )
        self.async_write_ha_state()
