# custom_components/hcu_integration/update.py
"""Update platform for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import logging

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    """Set up the update platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.UPDATE):
        async_add_entities(entities)


class HcuFirmwareUpdate(HcuBaseEntity, UpdateEntity):
    """Read-only firmware update entity (shows versions, no install)."""

    PLATFORM = Platform.UPDATE

    _attr_device_class = UpdateDeviceClass.FIRMWARE
    _attr_entity_category = EntityCategory.DIAGNOSTIC  # or EntityCategory.CONFIG
    _attr_translation_key = "hcu_firmware"
    # No install support -> no supported_features, no async_install implemented.
    _attr_supported_features: set[UpdateEntityFeature] = set()

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        # Unique per device (not channel)
        self._attr_unique_id = f"{self._device_id}_firmware_update"
        
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Nothing special needed; properties read from coordinator-backed data.
        super()._handle_coordinator_update()

    @property
    def installed_version(self) -> str | None:
        """Currently installed firmware version."""
        value = self._device.get("firmwareVersion")
        return str(value) if value is not None else None

    @property
    def latest_version(self) -> str | None:
        """Latest available firmware version."""
        value = self._device.get("availableFirmwareVersion")
        return str(value) if value is not None else None
