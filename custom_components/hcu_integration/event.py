# custom_components/hcu_integration/event.py
"""Event entities for the Homematic IP HCU integration."""
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

    _attr_translation_key = "hcu_doorbell_event"
    _attr_device_class = EventDeviceClass.DOORBELL
    _attr_event_types = ["ring"]

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

        visible_index = self._channel.get("visibleChannelIndex")
        if visible_index is None:
            visible_index = self._channel_index_str
        self._attr_unique_id = f"{self._device_id}_{visible_index}_doorbell_event"

    @callback
    def handle_trigger(self, event_type: str | None = None) -> None:
        """Handle an event trigger from the coordinator."""
        self._trigger_event("ring")


class HcuButtonEvent(HcuBaseEntity, EventEntity):
    """Representation of a Homematic IP HCU button event entity."""

    PLATFORM = Platform.EVENT
    
    _attr_translation_key = "hcu_button_event"
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ["press_short", "press_long", "press_long_start", "press_long_stop"]

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict[str, Any],
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(channel_label=self._channel.get("label"))
        visible_index = self._channel.get("visibleChannelIndex")
        if visible_index is None:
            visible_index = self._channel_index_str
        self._attr_unique_id = f"{self._device_id}_{visible_index}_button_event"

    @callback
    def handle_trigger(self, event_type: str | None = None) -> None:
        """Handle an event trigger from the coordinator."""
        self._trigger_event(event_type)
