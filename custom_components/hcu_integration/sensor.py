# custom_components/hcu_integration/sensor.py
"""Sensor platform for the Homematic IP HCU integration."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .api import HcuApiClient
from .const import (
    HMIP_ON_TIME_INFINITE,
)
from .entity import HcuBaseEntity, HcuGroupBaseEntity, HcuHomeBaseEntity

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
    """Set up the sensor platform from a config entry."""
    coordinator = config_entry.runtime_data
    coordinator.async_register_platform(Platform.SENSOR, async_add_entities)
    if entities := coordinator.entities.get(Platform.SENSOR):
        async_add_entities(entities)


class HcuHomeSensor(HcuHomeBaseEntity, SensorEntity):
    """Representation of a sensor tied to the HCU 'home' object."""

    PLATFORM = Platform.SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        feature: str,
        mapping: dict,
    ):
        super().__init__(coordinator, client)
        self._feature = feature

        if translation_key := mapping.get("translation_key"):
            self._attr_translation_key = translation_key
            self._attr_translation_placeholders = {"channel": "", "channel_index": ""}
        else:
            self._attr_name = mapping["name"]
        self._attr_unique_id = f"{self._hcu_device_id}_{self._feature}"
        self._attr_device_class = mapping.get("device_class")
        self._attr_native_unit_of_measurement = mapping.get("unit")
        self._attr_state_class = mapping.get("state_class")

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


class HcuGroupOnTimeSensor(HcuGroupBaseEntity, SensorEntity):
    """Representation of the configured on-time of an Extended Linked Switching group."""

    PLATFORM = Platform.SENSOR
    _attr_has_entity_name = True
    _attr_translation_key = "hcu_group_on_time"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = "s"
    _attr_suggested_display_precision = 0
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        group_data: dict,
    ) -> None:
        super().__init__(coordinator, client, group_data)
        del self._attr_name  # let translation_key supply the entity name component
        self._attr_unique_id = f"{self._group_id}_on_time"

    @property
    def native_value(self) -> float | None:
        """Return the configured on-time in seconds."""
        value = self._group.get("onTime")
        if value is None:
            return None
        if value == HMIP_ON_TIME_INFINITE:
            return 0
        return round(value, 0)


ENERGY_COUNTER_TYPE_TRANSLATION_MAP: dict[str, tuple[str, str]] = {
    "ENERGY_COUNTER_USAGE_HIGH_TARIFF": (
        "energy_usage_high_tariff",
        "Energy Usage (High Tariff)",
    ),
    "ENERGY_COUNTER_USAGE_LOW_TARIFF": (
        "energy_usage_low_tariff",
        "Energy Usage (Low Tariff)",
    ),
    "ENERGY_COUNTER_INPUT_SINGLE_TARIFF": (
        "energy_feed_in",
        "Energy Feed-in",
    ),
    "ENERGY_COUNTER_INPUT_HIGH_TARIFF": (
        "energy_feed_in_high_tariff",
        "Energy Feed-in (High Tariff)",
    ),
    "ENERGY_COUNTER_INPUT_LOW_TARIFF": (
        "energy_feed_in_low_tariff",
        "Energy Feed-in (Low Tariff)",
    ),
}


class HcuGenericSensor(HcuBaseEntity, SensorEntity):
    """Representation of a generic HCU sensor for a physical device."""

    PLATFORM = Platform.SENSOR
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        feature: str,
        mapping: dict,
    ):
        super().__init__(coordinator, client, device_data, channel_index)
        self._feature = feature
        self._base_mapping = mapping

        translation_key = mapping.get("translation_key")
        if translation_key == "hcu_on_time":
            self._apply_translation_key(translation_key)
        else:
            smart_key, feature_name = self._get_smart_feature_info()
            self._set_entity_name(
                channel_label=self._channel.get("label"),
                feature_name=feature_name or mapping.get("name"),
                translation_key=smart_key or translation_key,
            )

        self._attr_unique_id = (
            f"{self._device_id}_{self._channel_index}_{self._feature}"
        )
        self._attr_device_class = mapping.get("device_class")
        self._attr_native_unit_of_measurement = mapping.get("unit")
        self._attr_state_class = mapping.get("state_class")
        self._attr_suggested_display_precision = mapping.get(
            "suggested_display_precision"
        )
        self._attr_entity_category = mapping.get("entity_category")

        if "entity_registry_enabled_default" in mapping:
            self._attr_entity_registry_enabled_default = mapping[
                "entity_registry_enabled_default"
            ]

    def _get_smart_feature_info(self) -> tuple[str | None, str | None]:
        """Generate smart translation key and fallback feature name based on channel data."""
        if self._feature.startswith("energyCounter"):
            counter_type_key = f"{self._feature}Type"
            counter_type = self._channel.get(counter_type_key, "UNKNOWN")
            if counter_type in ENERGY_COUNTER_TYPE_TRANSLATION_MAP:
                return ENERGY_COUNTER_TYPE_TRANSLATION_MAP[counter_type]

        return None, self._base_mapping.get("name")

    @property
    def native_value(self) -> float | str | datetime | None:
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
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        feature: str = "windowState",
        mapping: dict | None = None,
    ):

        if mapping is None:
            mapping = {"name": "State", "device_class": SensorDeviceClass.ENUM}

        super().__init__(
            coordinator, client, device_data, channel_index, feature, mapping
        )
        self._attr_unique_id = (
            f"{self._device_id}_{self._channel_index}_windowState_state"
        )
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
    def native_value(self) -> datetime | None:
        """Return the timestamp as a timezone-aware UTC datetime object."""
        value = self._channel.get(self._feature)

        if value is None:
            return None

        try:
            # Ensure the value is numeric
            timestamp_ms = float(value)

            # Prevent absurdly large numbers from crashing datetime parsing
            if timestamp_ms <= 0 or timestamp_ms > 253402300799000:  # Year 9999
                return None

            return dt_util.utc_from_timestamp(timestamp_ms / 1000.0)
        except (ValueError, TypeError, OverflowError):
            return None
