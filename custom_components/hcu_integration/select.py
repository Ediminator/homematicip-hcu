# custom_components/hcu_integration/select.py
"""Select platform for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import aiohttp
from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HcuApiClient, HcuApiError
from .entity import HcuBaseEntity, HcuGroupBaseEntity

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
    _attr_options = ["permanent_off", "permanent_on"]
    _attr_icon = "mdi:power-settings"
    _attr_translation_key = "hcu_power_up_switch_state"

    _API_VALUE = {"permanent_off": "PERMANENT_OFF", "permanent_on": "PERMANENT_ON"}
    _HA_VALUE = {"PERMANENT_OFF": "permanent_off", "PERMANENT_ON": "permanent_on"}

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
        self._apply_translation_key("hcu_power_up_switch_state")
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_powerUpSwitchState"

    @property
    def current_option(self) -> str | None:
        raw = self._channel.get(self._feature)
        return self._HA_VALUE.get(raw) if raw else None

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        api_value = self._API_VALUE[option]
        try:
            await self._client.async_set_power_up_switch_state(
                self._device_id, self._channel_index, api_value
            )
        except aiohttp.ClientResponseError as err:
            if err.status == 400:
                _LOGGER.error(
                    "Failed to set powerUpSwitchState for %s channel %s (HTTP 400): "
                    "The App User may not have sufficient permissions. "
                    "In the Homematic IP app go to Settings → User management → User overview "
                    "and set the 'Home Assistant Integration' user to 'Normaler Benutzer' (Normal User). "
                    "Original error: %s",
                    self._device_id, self._channel_index, err,
                )
            else:
                _LOGGER.error(
                    "Failed to set powerUpSwitchState for %s channel %s: %s",
                    self._device_id, self._channel_index, err,
                )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error(
                "Failed to set powerUpSwitchState for %s channel %s: %s",
                self._device_id, self._channel_index, err,
            )


class HcuAlarmSignalAcoustic(RestoreEntity, HcuGroupBaseEntity, SelectEntity):
    """Select entity to trigger a test acoustic signal on an ALARM_SWITCHING group."""

    PLATFORM = Platform.SELECT
    _attr_has_entity_name = True
    _attr_translation_key = "alarm_test_signal_acoustic"
    _attr_icon = "mdi:alarm-bell"

    _attr_options = [
        "disable_acoustic_signal",
        "frequency_rising",
        "frequency_falling",
        "frequency_rising_and_falling",
        "frequency_alternating_low_high",
        "frequency_alternating_low_mid_high",
        "frequency_highon_off",
        "frequency_highon_longoff",
        "frequency_lowon_off_highon_off",
        "frequency_lowon_longoff_highon_longoff",
        "low_battery",
        "disarmed",
        "internally_armed",
        "externally_armed",
        "delayed_internally_armed",
        "delayed_externally_armed",
        "event",
        "error",
    ]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict,
    ) -> None:
        super().__init__(coordinator, client, group_data)
        del self._attr_name  # let translation_key supply the entity name component
        self._attr_unique_id = f"{self._group_id}_test_signal_acoustic"
        self._current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if last_state.state in self._attr_options:
                self._current_option = last_state.state

    @property
    def current_option(self) -> str | None:
        return self._current_option

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        api_value = option.upper()
        try:
            await self._client.async_test_alarm_signal_acoustic(self._group_id, api_value)
            self._current_option = option
            self.async_write_ha_state()
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to test acoustic signal for %s: %s", self.name, err)


class HcuAlarmSignalOptical(RestoreEntity, HcuGroupBaseEntity, SelectEntity):
    """Select entity to trigger a test optical signal on an ALARM_SWITCHING group."""

    PLATFORM = Platform.SELECT
    _attr_has_entity_name = True
    _attr_translation_key = "alarm_test_signal_optical"
    _attr_icon = "mdi:alarm-light-outline"

    _attr_options = [
        "disable_optical_signal",
        "blinking_alternately_repeating",
        "blinking_both_repeating",
        "double_flashing_repeating",
        "flashing_both_repeating",
        "confirmation_signal_0",
        "confirmation_signal_1",
        "confirmation_signal_2",
    ]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict,
    ) -> None:
        super().__init__(coordinator, client, group_data)
        del self._attr_name  # let translation_key supply the entity name component
        self._attr_unique_id = f"{self._group_id}_test_signal_optical"
        self._current_option: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if last_state.state in self._attr_options:
                self._current_option = last_state.state

    @property
    def current_option(self) -> str | None:
        return self._current_option

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        api_value = option.upper()
        try:
            await self._client.async_test_alarm_signal_optical(self._group_id, api_value)
            self._current_option = option
            self.async_write_ha_state()
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to test optical signal for %s: %s", self.name, err)
