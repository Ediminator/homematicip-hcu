"""Tests for the drive light of garage door modules (HmIP-MOD-HO, #508)."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.light import ColorMode
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.cover import HcuGarageDoorCover
from custom_components.hcu_integration.discovery import _discover_entities_for_device
from custom_components.hcu_integration.light import HcuGarageDoorLight


def _mod_ho(
    channel_type: str = "DOOR_CHANNEL",
    channel_role: str | None = "GARAGE_DOOR_WITH_LIGHT",
    label: str | None = None,
) -> dict:
    channel: dict = {
        "functionalChannelType": channel_type,
        "doorState": "CLOSED",
        "on": False,
        "groups": ["group-garage"],
    }
    if channel_role is not None:
        channel["channelRole"] = channel_role
    if label is not None:
        channel["label"] = label
    return {
        "id": "dev-mod-ho",
        "type": "HOERMANN_DRIVES_MODULE",
        "label": "Garage",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": channel,
        },
    }


@pytest.mark.parametrize("channel_type", ["DOOR_CHANNEL", "GARAGE_DOOR_CHANNEL"])
def test_door_channel_with_light_creates_cover_and_light(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    channel_type: str,
) -> None:
    """A door channel with role GARAGE_DOOR_WITH_LIGHT gets a light next to the cover."""
    device = _mod_ho(channel_type)
    mock_hcu_client.get_device_by_address.return_value = device

    entities, valid_unique_ids = _discover_entities_for_device(
        device, mock_config_entry, mock_coordinator, mock_hcu_client
    )

    covers = entities[Platform.COVER]
    assert len(covers) == 1
    assert isinstance(covers[0], HcuGarageDoorCover)
    lights = entities[Platform.LIGHT]
    assert len(lights) == 1
    assert isinstance(lights[0], HcuGarageDoorLight)
    assert "dev-mod-ho_1_cover" in valid_unique_ids
    assert "dev-mod-ho_1_on" in valid_unique_ids


@pytest.mark.parametrize("channel_role", [None, "GARAGE_DOOR"])
def test_door_channel_without_light_role_creates_no_light(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    channel_role: str | None,
) -> None:
    """Door channels without the light role keep only the cover."""
    device = _mod_ho(channel_role=channel_role)
    mock_hcu_client.get_device_by_address.return_value = device

    entities, _ = _discover_entities_for_device(
        device, mock_config_entry, mock_coordinator, mock_hcu_client
    )

    assert len(entities[Platform.COVER]) == 1
    assert entities[Platform.LIGHT] == []


@pytest.mark.parametrize("label", [None, "Hörmann"])
def test_garage_door_light_name_and_modes(
    mock_hcu_client: MagicMock, mock_coordinator: MagicMock, label: str | None
) -> None:
    """The light is called "Light" whether or not the door channel has a label."""
    device = _mod_ho(label=label)
    mock_hcu_client.get_device_by_address.return_value = device

    light = HcuGarageDoorLight(mock_coordinator, mock_hcu_client, device, "1")

    assert light.PLATFORM == Platform.LIGHT
    assert light.unique_id == "dev-mod-ho_1_on"
    assert light.has_entity_name is True
    assert light.translation_key == "hcu_light"
    assert light._attr_translation_placeholders == {"channel_index": ""}
    assert not hasattr(light, "_attr_name")
    assert light.device_class is None
    assert light.color_mode == ColorMode.ONOFF
    assert light.supported_color_modes == {ColorMode.ONOFF}


def test_garage_door_light_follows_channel_state(
    mock_hcu_client: MagicMock, mock_coordinator: MagicMock
) -> None:
    """The light state is the channel's "on" field."""
    device = _mod_ho()
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuGarageDoorLight(mock_coordinator, mock_hcu_client, device, "1")
    light.async_write_ha_state = MagicMock()

    assert light.is_on is False

    device["functionalChannels"]["1"]["on"] = True
    light._handle_coordinator_update()

    assert light.is_on is True


async def test_garage_door_light_turn_on_and_off(
    mock_hcu_client: MagicMock, mock_coordinator: MagicMock, hass: HomeAssistant
) -> None:
    """Turning the light on and off sends setSwitchState for the door channel."""
    device = _mod_ho()
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuGarageDoorLight(mock_coordinator, mock_hcu_client, device, "1")
    light.hass = hass
    light.async_write_ha_state = MagicMock()

    await light.async_turn_on()
    mock_hcu_client.async_set_switch_state.assert_called_once_with(
        "dev-mod-ho", 1, True
    )
    assert light.is_on is True

    mock_hcu_client.async_set_switch_state.reset_mock()
    await light.async_turn_off()
    mock_hcu_client.async_set_switch_state.assert_called_once_with(
        "dev-mod-ho", 1, False
    )
    assert light.is_on is False
