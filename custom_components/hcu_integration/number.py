# custom_components/hcu_integration/number.py
"""Number platform for the Homematic IP HCU integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    Platform,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import HcuApiClient, HcuApiError
from .const import API_PATHS
from .entity import HcuBaseEntity, HcuGroupBaseEntity
from .util import app_user_rights_hint, command_failed

_LOGGER = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .coordinator import HcuConfigEntry, HcuCoordinator


# State is pushed by the HCU, so there is no polling to limit, and actions may
# run in parallel.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HcuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the number platform from a config entry."""
    coordinator = config_entry.runtime_data
    coordinator.async_register_platform(Platform.NUMBER, async_add_entities)
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
    _attr_native_min_value = 0.0
    _attr_native_max_value = 16383.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(
            channel_label=self._channel.get("label"),
            feature_name="Ramp Time",
            translation_key="ramp_time",
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
    def native_value(self) -> float | None:
        return self._attr_native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()

    def _handle_coordinator_update(self) -> None:
        pass


class HcuTemperatureOffset(HcuBaseEntity, NumberEntity):
    """Offset the thermostat adds to its measured temperature."""

    PLATFORM = Platform.NUMBER
    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = -3.5
    _attr_native_max_value = 3.5
    _attr_native_step = 0.5
    # No temperature device class: HA would convert the offset like an absolute
    # temperature for Fahrenheit users (0 °C offset → 32 °F).
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
        feature: str,
        mapping: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, client, device_data, channel_index)
        self._feature = feature
        self._set_entity_name(
            channel_label=self._channel.get("label"),
            feature_name=mapping["name"],
            translation_key=mapping["translation_key"],
        )
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_{feature}"

    @property
    def native_value(self) -> float | None:
        return self._channel.get(self._feature)

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._client.async_set_temperature_offset(
                self._device_id, self._channel_index, value
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error(
                "Failed to set temperatureOffset for %s channel %s: %s%s",
                self._device_id,
                self._channel_index,
                err,
                app_user_rights_hint(err),
            )
            raise command_failed(self.entity_id, err) from err


class _HcuHeatingGroupNumber(HcuGroupBaseEntity, NumberEntity):
    """A setting of a room (HEATING group) that the HCU stores under one field."""

    PLATFORM = Platform.NUMBER
    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.BOX
    _feature: str
    _path_key: str

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, client, group_data)
        del self._attr_name  # the translation key names the entity
        self._attr_unique_id = f"{self._group_id}_{self._feature}"

    @property
    def native_value(self) -> float | None:
        return self._group.get(self._feature)

    async def async_set_native_value(self, value: float) -> None:
        try:
            await self._client.async_group_control(
                API_PATHS[self._path_key],
                self._group_id,
                {self._feature: self._to_api(value)},
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error(
                "Failed to set %s for group %s: %s%s",
                self._feature,
                self._group_id,
                err,
                app_user_rights_hint(err),
            )
            raise command_failed(self.entity_id, err) from err

    def _to_api(self, value: float) -> float | int:
        return value


class _HcuHeatingGroupTemperature(_HcuHeatingGroupNumber):
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = 5.0
    _attr_native_max_value = 30.0
    _attr_native_step = 0.5


class HcuBoostDuration(_HcuHeatingGroupNumber):
    _attr_translation_key = "boost_duration"
    _attr_device_class = NumberDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_native_min_value = 5
    _attr_native_max_value = 30
    _attr_native_step = 5
    _feature = "boostDuration"
    _path_key = "SET_GROUP_BOOST_DURATION"

    def _to_api(self, value: float) -> int:
        return int(value)


class HcuWindowOpenTemperature(_HcuHeatingGroupTemperature):
    _attr_translation_key = "window_open_temperature"
    _feature = "windowOpenTemperature"
    _path_key = "SET_GROUP_WINDOW_OPEN_TEMPERATURE"


class HcuMinTemperature(_HcuHeatingGroupTemperature):
    _attr_translation_key = "min_temperature"
    _feature = "minTemperature"
    _path_key = "SET_GROUP_MIN_TEMPERATURE"


class HcuMaxTemperature(_HcuHeatingGroupTemperature):
    _attr_translation_key = "max_temperature"
    _feature = "maxTemperature"
    _path_key = "SET_GROUP_MAX_TEMPERATURE"
