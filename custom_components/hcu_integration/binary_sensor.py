# custom_components/hcu_integration/binary_sensor.py
"""Binary sensor platform for the Homematic IP HCU integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any
from datetime import datetime

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import HcuApiClient
from .const import (
    ABSENCE_TYPE_NOT_ABSENT,
    ABSENCE_TYPE_PARTY,
    ABSENCE_TYPE_PERIOD,
    ABSENCE_TYPE_PERMANENT,
    ABSENCE_TYPE_VACATION,
)
from .entity import HcuBaseEntity, HcuHomeBaseEntity, HcuGroupBaseEntity

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.BINARY_SENSOR):
        async_add_entities(entities)


class HcuBinarySensor(HcuBaseEntity, BinarySensorEntity):
    """
    Representation of a generic Homematic IP HCU binary sensor.
    This class is the foundation for all binary sensors in the integration.
    """

    PLATFORM = Platform.BINARY_SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        feature: str,
        mapping: dict,
    ):
        super().__init__(coordinator, client, device_data, channel_index)
        self._feature = feature
        self._on_state = mapping.get("on_state")

        # REFACTOR: Correctly call the centralized naming helper for feature entities.
        self._set_entity_name(
            channel_label=self._channel.get("label"), feature_name=mapping["name"]
        )
        
        self._attr_entity_category = mapping.get("entity_category")
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_{self._feature}"
        self._attr_device_class = mapping.get("device_class")

        if "entity_registry_enabled_default" in mapping:
            self._attr_entity_registry_enabled_default = mapping[
                "entity_registry_enabled_default"
            ]

    @property
    def is_on(self) -> bool | None:
        """
        Return true if the binary sensor is on.
        """
        value = self._channel.get(self._feature)
        if value is None:
            return None
            
        return self._is_on_from_value(value)

    def _is_on_from_value(self, value: Any) -> bool:
        """
        Determine the boolean state from the raw value.
        Subclasses can override this to provide specific logic.
        """
        # Rule 1 from bot: Do not hardcode state values, such as on_state, for sensors if the value
        # can be configured by the user in the external application.
        # Here we use the configurable _on_state if provided by the mapping.
        if self._on_state:
            return value == self._on_state
        return bool(value)


class HcuWindowBinarySensor(HcuBinarySensor):
    """
    Representation of a Homematic IP HCU window sensor.
    This class provides specialized logic for window sensors.
    """
    
    _attr_translation_key = "hcu_window"
    
    def _is_on_from_value(self, value: Any) -> bool:
        """
        Return true if the window is open or tilted.
        """
        return value in ("OPEN", "TILTED")

class HcuSmokeBinarySensor(HcuBinarySensor):
    """
    Representation of a Homematic IP HCU smoke detector.
    This class provides specialized logic for smoke detectors.
    """

    def _is_on_from_value(self, value: Any) -> bool:
        """
        Return true if the smoke detector alarm is active.
        """
        return value in ("PRIMARY_ALARM", "SECONDARY_ALARM")


class HcuUnreachBinarySensor(HcuBinarySensor):
    """
    Representation of a Homematic IP HCU device's reachability.
    This class provides specialized logic for the 'unreach' status.
    """
    
    def _is_on_from_value(self, value: Any) -> bool:
        """
        Return true if the device is connected.
        The API's 'unreach' property is `True` when the device is unreachable.
        For Home Assistant's `connectivity` device class, `is_on` should be
        `True` when the device is connected, so we must invert the value.
        """
        return not value


class HcuVacationModeBinarySensor(HcuHomeBaseEntity, BinarySensorEntity):
    """Representation of the HCU's system-wide Vacation Mode."""

    PLATFORM = Platform.BINARY_SENSOR
    _attr_has_entity_name = False
    _attr_icon = "mdi:palm-tree"

    def __init__(self, coordinator: "HcuCoordinator", client: HcuApiClient):
        """Initialize the Vacation Mode sensor."""
        super().__init__(coordinator, client)
        self._attr_name = self._apply_prefix("Vacation Mode")
        self._attr_unique_id = f"{self._hcu_device_id}_vacation_mode"
        self._update_attributes()

    @property
    def is_on(self) -> bool:
        """Return true if vacation mode is active."""
        if self._attr_extra_state_attributes.get("type") != ABSENCE_TYPE_VACATION:
            return False

        start_time = self._attr_extra_state_attributes.get("start_time")
        if not start_time:
            return False

        try:
            start_time_dt = datetime.fromisoformat(start_time)
            return dt_util.utcnow() >= start_time_dt
        except ValueError:
            _LOGGER.warning("Invalid start_time format: %s", start_time)
            return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the vacation mode sensor."""
        return (super().extra_state_attributes or {}) | (self._attr_extra_state_attributes or {})

    def _update_attributes(self) -> None:
        """Update the entity's attributes."""
        heating_home = self._home.get("functionalHomes", {}).get("INDOOR_CLIMATE", {})

        # get the HA timezone info
        ha_tz = dt_util.get_default_time_zone()

        def _parse_hcu_datetime(time_str: str | None, name: str) -> datetime | None:
            """Parse HCU datetime string and make it timezone-aware."""
            if not time_str:
                return None
            try:
                # HCU time is given in format "YYYY_MM_DD HH:MM"
                dt_obj = datetime.strptime(time_str, "%Y_%m_%d %H:%M")
                return dt_obj.replace(tzinfo=ha_tz)
            except ValueError:
                _LOGGER.warning("Could not parse HCU %s time: %s", name, time_str)
                return None

        _type = heating_home.get("absenceType")

        if _type in (ABSENCE_TYPE_PARTY, ABSENCE_TYPE_NOT_ABSENT):
            # PARTY mode is not an absence, so reset all attributes.
            self._attr_extra_state_attributes = {
                "start_time": None,
                "end_time": None,
                "type": None,
                "target_temperature": None,
            }
            return

        # Handle other absence types.
        _start_time = _parse_hcu_datetime(heating_home.get("absenceStartTime"), "start")
        _end_time = _parse_hcu_datetime(heating_home.get("absenceEndTime"), "end")
        _temp = None

        if _type == ABSENCE_TYPE_VACATION:
            _temp = heating_home.get("lastVacationTemperature")
        elif _type in (ABSENCE_TYPE_PERIOD, ABSENCE_TYPE_PERMANENT):
            _temp = heating_home.get("ecoTemperature")

        self._attr_extra_state_attributes = {
            "start_time": _start_time.isoformat() if _start_time else None,
            "end_time": _end_time.isoformat() if _end_time else None,
            "type": _type,
            "target_temperature": _temp,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        super()._handle_coordinator_update()


class HcuGroupBinarySensor(HcuGroupBaseEntity, BinarySensorEntity):
    """Base class for Homematic IP HCU group binary sensors."""

    PLATFORM = Platform.BINARY_SENSOR

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict,
    ):
        """Initialize the group binary sensor."""
        super().__init__(coordinator, client, group_data)


class HcuHeatDemandBinarySensorGroup(HcuGroupBinarySensor):
    """
    Representation of a Homematic IP HCU boiler/pump heat demand group.
    """
    
    _attr_device_class = BinarySensorDeviceClass.HEAT
    
    def __init__(self, coordinator: "HcuCoordinator", client: HcuApiClient, group_data: dict):
        super().__init__(coordinator, client, group_data)
        if not group_data.get("label"):
            group_type = group_data.get("type")
            fallback_names = {
                "HEATING_COOLING_DEMAND_BOILER": "Boiler Heat Demand",
                "HEATING_COOLING_DEMAND_PUMP": "Pump Heat Demand",
            }
            fallback_name = fallback_names.get(group_type, "Heat Demand")
            self._attr_name = self._apply_prefix(fallback_name)

    @property
    def is_on(self) -> bool:
        """Return true if there is an active heat demand."""
        return bool(self._group.get("heatDemand"))
