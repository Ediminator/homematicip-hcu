# custom_components/hcu_integration/event.py
from typing import TYPE_CHECKING, Any, Protocol

from homeassistant.components.event import (
    EventDeviceClass,
    EventEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HcuBaseEntity
from .api import HcuApiClient

if TYPE_CHECKING:
    from . import HcuCoordinator


class TriggerableEvent(Protocol):
    """Protocol for event entities that can be triggered by the coordinator.

    Event entities implementing this protocol can be registered with the
    coordinator and triggered generically without type-specific logic.
    """

    _device_id: str
    _channel_index_str: str

    def handle_trigger(self) -> None:
        """Handle an event trigger from the coordinator."""
        ...


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the event platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.EVENT):
        async_add_entities(entities)


class HcuDoorbellEvent(HcuBaseEntity, EventEntity):
    """Representation of a Homematic IP HCU doorbell event entity."""

    PLATFORM = Platform.EVENT

    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["press"]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        # Set entity name using the centralized naming helper
        # Use channel label directly without feature name to avoid redundancy
        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index_str}_doorbell_event"

    @callback
    def handle_trigger(self) -> None:
        """Handle an event trigger from the coordinator."""
        self._trigger_event("press")


class HcuButtonEvent(HcuBaseEntity, EventEntity):
    """Representation of a Homematic IP HCU button event entity."""

    PLATFORM = Platform.EVENT
    
    _attr_translation_key = "hcu_button_event"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["press", "press_short", "press_long", "press_long_start", "press_long_stop"]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        channel_label = self._channel.get("label")
        if channel_label:
            self._set_entity_name(channel_label=channel_label)
        else:
            self._attr_has_entity_name = True
            count = self._get_functional_channel_count()
            suffix = f" {self._channel_index}" if count > 1 else ""
            self._attr_translation_placeholders = {"channel_index": suffix}

        self._attr_unique_id = f"{self._device_id}_{self._channel_index_str}_button_event"

    @callback
    def handle_trigger(self, event_type: str | None = None) -> None:
        """Handle an event trigger from the coordinator."""
        # Use a generic "press" for timestamp-based events (where event_type is None)
        # and as a fallback for unexpected event types.
        normalized_event = event_type.lower().replace("key_", "") if event_type else "press"
        if normalized_event in self._attr_event_types:
            self._trigger_event(normalized_event)
        else:
            self._trigger_event("press")
