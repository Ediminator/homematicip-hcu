# custom_components/hcu_integration/sensor.py
"""Sensor platform for the Homematic IP HCU integration."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import HcuApiClient
from .entity import HcuBaseEntity, HcuHomeBaseEntity
from .const import (
    HMIP_ON_TIME_INFINITE,
)

if TYPE_CHECKING:
    from . import HcuCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.SENSOR):
        async_add_entities(entities)


class HcuHomeSensor(HcuHomeBaseEntity, SensorEntity):
    """Representation of a sensor tied to the HCU 'home' object."""

    PLATFORM = Platform.SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        feature: str,
        mapping: dict,
    ):
        super().__init__(coordinator, client)
        self._feature = feature

        base_name = f"Homematic IP HCU {mapping['name']}"
        self._attr_name = self._apply_prefix(base_name)
        self._attr_unique_id = f"{self._hcu_device_id}_{self._feature}"
        self._attr_device_class = mapping.get("device_class")
        self._attr_native_unit_of_measurement = mapping.get("unit")
        self._attr_state_class = mapping.get("state_class")
        self._attr_icon = mapping.get("icon")

        if "entity_registry_enabled_default" in mapping:
            self._attr_entity_registry_enabled_default = mapping[
                "entity_registry_enabled_default"
            ]

    @property
    def native_value(self) -> float | str | None:
        value = self._home.get(self._feature)
        if value is None:
            return None

        # carrierSense and dutyCycle are already in percentage from HCU
        if self._feature in ("carrierSense", "dutyCycle"):
            return round(value, 1)

        return value


class HcuGenericSensor(HcuBaseEntity, SensorEntity):
    """Representation of a generic HCU sensor for a physical device."""

    PLATFORM = Platform.SENSOR
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
        self._base_mapping = mapping

        # ENHANCED: Smart naming for energy counters based on type
        feature_name = self._get_smart_feature_name()
        
        self._set_entity_name(
            channel_label=self._channel.get("label"),
            feature_name=feature_name
        )

        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_{self._feature}"
        self._attr_device_class = mapping.get("device_class")
        self._attr_native_unit_of_measurement = mapping.get("unit")
        self._attr_state_class = mapping.get("state_class")
        self._attr_icon = mapping.get("icon")
        self._attr_suggested_display_precision = mapping.get("suggested_display_precision") 
        self._attr_entity_category = mapping.get("entity_category")

        if "entity_registry_enabled_default" in mapping:
            self._attr_entity_registry_enabled_default = mapping[
                "entity_registry_enabled_default"
            ]

    def _get_smart_feature_name(self) -> str:
        """Generate smart feature name based on channel data."""
        # For energy counters, use the type information if available
        if self._feature.startswith("energyCounter"):
            counter_type_key = f"{self._feature}Type"
            counter_type = self._channel.get(counter_type_key, "UNKNOWN")
            
            # Map API counter types to user-friendly names
            type_name_map = {
                "ENERGY_COUNTER_USAGE_HIGH_TARIFF": "Energy Usage (High Tariff)",
                "ENERGY_COUNTER_USAGE_LOW_TARIFF": "Energy Usage (Low Tariff)",
                "ENERGY_COUNTER_INPUT_SINGLE_TARIFF": "Energy Feed-in",
                "ENERGY_COUNTER_INPUT_HIGH_TARIFF": "Energy Feed-in (High Tariff)",
                "ENERGY_COUNTER_INPUT_LOW_TARIFF": "Energy Feed-in (Low Tariff)",
                "UNKNOWN": self._base_mapping["name"],
            }
            
            return type_name_map.get(counter_type, self._base_mapping["name"])
        
        return self._base_mapping["name"]

    @property
    def native_value(self) -> float | str | None:
        """Return the sensor value, with special handling for certain features."""
        channel_data = self._channel
        internal_link_config = channel_data.get("internalLinkConfiguration") or {}
        channel_data = {**channel_data, **internal_link_config}
        
        value = channel_data.get(self._feature)
        if value is None:
            return None
        if self._feature == "valvePosition":
            return round(value * 100.0, 1)
        if self._feature == "vaporAmount":
            return round(value, 2)
        if self._feature == "dutyCycleLevel":
            return round(value, 1)
        if self._feature == "onTime":
            if value == HMIP_ON_TIME_INFINITE:
                return 0
            return round(value, 0)
        return value


class HcuTemperatureSensor(HcuGenericSensor):
    """
    Representation of an HCU temperature sensor.
    This class is designed to handle temperature readings from thermostats
    and external temperature sensors, using the feature attribute to determine
    which temperature field to read (actualTemperature, valveActualTemperature,
    temperatureExternalOne, temperatureExternalTwo, etc.).
    """

    @property
    def native_value(self) -> float | str | None:
        """Return the temperature value from the configured feature."""
        return self._channel.get(self._feature)


class HcuWindowStateSensor(HcuGenericSensor):
    """
    Representation of an HCU window state sensor (HmIP-SRH and similar).

    This sensor shows the actual window state as its value: OPEN, TILTED, or CLOSED.
    This complements the binary sensor which can only show on/off.
    """
    
    _attr_translation_key = "hcu_tiltwindow"
    PLATFORM = Platform.SENSOR

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        feature: str = "windowState",
        mapping: dict | None = None,
    ):
        
        if mapping is None:
            mapping = {
                "name": "State",
                "device_class": SensorDeviceClass.ENUM
            }
            
        super().__init__(coordinator, client, device_data, channel_index, feature, mapping)
        self._attr_options = ["open", "tilted", "closed"]
        
    @property
    def native_value(self) -> str | None:
        """Return the window state: open, tilted, or closed."""
        state = self._channel.get(self._feature)
        if state in ("OPEN", "TILTED", "CLOSED"):
            return state.lower()
        return state

class HcuTimestampSensor(HcuGenericSensor):
    """
    Representation of an HCU timestamp sensor 
    (used to map raw millisecond UNIX timestamps to proper Home Assistant datetime objects).
    """
    
    @property
    def native_value(self) -> str | None:
        """Return the timestamp as an isoformat string."""
        value = self._channel.get(self._feature)
        
        if value is None:
            return None
            
        try:
            # Ensure the value is numeric
            timestamp_ms = float(value)
            
            # Prevent absurdly large numbers from crashing datetime parsing
            if timestamp_ms <= 0 or timestamp_ms > 253402300799000: # Year 9999
                return None
                
            dt = dt_util.utc_from_timestamp(timestamp_ms / 1000.0)
            return dt.isoformat()
        except (ValueError, TypeError, OverflowError):
            return None
