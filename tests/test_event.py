"""Unit tests for the HCU event platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.event import EventDeviceClass
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.event import (
    HcuButtonEvent,
    HcuDoorbellEvent,
    TriggerableEvent,
    async_setup_entry,
)


def _make_doorbell_entity(
    device_data: dict,
    channel_index: str = "1",
) -> HcuDoorbellEvent:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuDoorbellEvent(coordinator, client, device_data, channel_index)
    entity._trigger_event = MagicMock()
    return entity


def _make_button_entity(
    device_data: dict,
    channel_index: str = "1",
) -> HcuButtonEvent:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuButtonEvent(coordinator, client, device_data, channel_index)
    entity._trigger_event = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_event_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.EVENT: [mock_entity]}
    entry.runtime_data = mock_coordinator

    added = []

    def mock_add_entities(entities: list) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == [mock_entity]

    # Empty list
    mock_coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == []


def test_doorbell_event_properties_and_trigger() -> None:
    """Test doorbell event initialization and triggering."""
    device_data = {
        "id": "dev-doorbell-1",
        "label": "Front Doorbell",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOORBELL_CHANNEL",
                "label": "Front Chime",
                "visibleChannelIndex": 1,
            },
        },
    }
    entity = _make_doorbell_entity(device_data, "1")

    assert isinstance(entity, TriggerableEvent)
    assert entity.device_class == EventDeviceClass.DOORBELL
    assert entity.event_types == ["ring"]
    assert entity.unique_id == "dev-doorbell-1_1_doorbell_event"
    assert entity.has_entity_name is True
    assert entity.name == "Front Chime"

    # Trigger with and without event_type argument
    entity.handle_trigger()
    entity._trigger_event.assert_called_with("ring")

    entity.handle_trigger("custom_param")
    entity._trigger_event.assert_called_with("ring")


def test_doorbell_event_without_visible_channel_index() -> None:
    """Test doorbell event fallback when visibleChannelIndex is None."""
    device_data = {
        "id": "dev-doorbell-2",
        "label": "Back Doorbell",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "2": {
                "functionalChannelType": "DOORBELL_CHANNEL",
                "label": "Back Chime",
            },
        },
    }
    entity = _make_doorbell_entity(device_data, "2")
    assert entity.unique_id == "dev-doorbell-2_2_doorbell_event"
    assert entity.has_entity_name is True
    assert entity.name == "Back Chime"


def test_button_event_with_label() -> None:
    """Test button event initialization when channel has a label."""
    device_data = {
        "id": "dev-remote-1",
        "label": "Key Ring Remote",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "KEY_CHANNEL",
                "label": "Top Button",
                "visibleChannelIndex": 1,
            },
        },
    }
    entity = _make_button_entity(device_data, "1")

    assert isinstance(entity, TriggerableEvent)
    assert entity.device_class == EventDeviceClass.BUTTON
    assert entity.event_types == [
        "press_short",
        "press_long",
        "press_long_start",
        "press_long_stop",
    ]
    assert entity.unique_id == "dev-remote-1_1_button_event"
    assert entity.has_entity_name is True
    assert entity.name == "Top Button"

    # Trigger handling
    entity.handle_trigger("press_short")
    entity._trigger_event.assert_called_with("press_short")

    # None event_type should be ignored
    entity._trigger_event.reset_mock()
    entity.handle_trigger(None)
    entity._trigger_event.assert_not_called()


def test_button_event_multi_channel_unlabeled() -> None:
    """Test button event with unlabeled multi-channel device."""
    device_data = {
        "id": "dev-switch-4",
        "label": "Wall Switch 4",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "KEY_CHANNEL",
                "visibleChannelIndex": 1,
            },
            "2": {
                "functionalChannelType": "KEY_CHANNEL",
                "visibleChannelIndex": 2,
            },
        },
    }
    entity1 = _make_button_entity(device_data, "1")
    assert entity1.unique_id == "dev-switch-4_1_button_event"
    assert entity1.translation_key == "hcu_button_event"
    assert entity1.translation_placeholders == {"channel_index": " 1"}

    # Without visibleChannelIndex
    device_data_no_visible = {
        "id": "dev-switch-4b",
        "label": "Wall Switch 4b",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "KEY_CHANNEL"},
            "2": {"functionalChannelType": "KEY_CHANNEL"},
        },
    }
    entity_no_vis = _make_button_entity(device_data_no_visible, "2")
    assert entity_no_vis.unique_id == "dev-switch-4b_2_button_event"
    assert entity_no_vis.translation_key == "hcu_button_event"
    assert entity_no_vis.translation_placeholders == {"channel_index": " 2"}


def test_button_event_single_channel_unlabeled() -> None:
    """Test button event with unlabeled single-channel device."""
    device_data = {
        "id": "dev-button-1",
        "label": "Single Button",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "KEY_CHANNEL",
            },
        },
    }
    entity = _make_button_entity(device_data, "1")
    assert entity.translation_placeholders == {"channel_index": ""}
    assert entity.unique_id == "dev-button-1_1_button_event"
