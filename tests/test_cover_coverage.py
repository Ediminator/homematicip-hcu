"""Coverage tests for HCU cover platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from custom_components.hcu_integration.const import API_PATHS
from custom_components.hcu_integration.cover import (
    HcuCover,
    HcuCoverGroup,
    HcuGarageDoorCover,
    _level_to_position,
    async_setup_entry,
)


def _create_cover(
    hass: HomeAssistant,
    *,
    device_id: str = "cover-dev-1",
    channel_index: str = "1",
    channel_data: dict | None = None,
    device_type: str = "SHUTTER_CONTACT",
) -> tuple[HcuCover, MagicMock, MagicMock]:
    """Create an HcuCover test entity with mocks."""
    ch_data = {
        "functionalChannelType": "SHUTTER_CHANNEL",
        "label": "Window Shutter",
        "shutterLevel": 0.0,
        "processing": False,
    }
    if channel_data:
        ch_data.update(channel_data)

    device = {
        "id": device_id,
        "label": "Cover Device",
        "type": device_type,
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            channel_index: ch_data,
        },
    }

    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {device_id: device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_set_shutter_level = AsyncMock()
    client.async_set_primary_shading_level = AsyncMock()
    client.async_set_slats_level = AsyncMock()
    client.async_stop_cover = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {device_id: device}
    coordinator.client = client
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}

    cover = HcuCover(coordinator, client, device, channel_index)
    cover.hass = hass
    cover.async_write_ha_state = MagicMock()
    return cover, coordinator, client


def _create_garage(
    hass: HomeAssistant,
    *,
    stateful: bool = True,
    ventilation: bool = True,
    channel_overrides: dict | None = None,
) -> tuple[HcuGarageDoorCover, MagicMock, MagicMock]:
    """Create an HcuGarageDoorCover test entity."""
    ch_data = {
        "functionalChannelType": "DOOR_CHANNEL",
        "label": "Garage Door",
        "ventilationPositionSupported": ventilation,
    }
    if stateful:
        ch_data["doorState"] = "CLOSED"
        ch_data["doorMotion"] = "NONE"
    if channel_overrides:
        ch_data.update(channel_overrides)

    device = {
        "id": "garage-dev-1",
        "label": "Garage",
        "type": "GARAGE_DOOR_CONTROLLER",
        "functionalChannels": {"1": ch_data},
    }

    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {"garage-dev-1": device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_send_door_command = AsyncMock()
    client.async_toggle_garage_door_state = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"garage-dev-1": device}
    coordinator.client = client
    coordinator.config_entry = MagicMock()

    cover = HcuGarageDoorCover(coordinator, client, device, "1")
    cover.hass = hass
    cover.async_write_ha_state = MagicMock()
    return cover, coordinator, client


def test_level_to_position() -> None:
    """Test _level_to_position with None and values."""
    assert _level_to_position(None) is None
    assert _level_to_position(0.0) == 100
    assert _level_to_position(1.0) == 0
    assert _level_to_position(0.3) == 70


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test cover async_setup_entry with and without entities."""
    entry = MagicMock()
    coordinator = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    # Case 1: No entities
    coordinator.entities = {}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

    # Case 2: Entities present
    entity = MagicMock()
    coordinator.entities = {Platform.COVER: [entity]}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([entity])


def test_cover_is_closed_none(hass: HomeAssistant) -> None:
    """Test is_closed returns None when position is None."""
    cover, _, _ = _create_cover(hass, channel_data={"shutterLevel": None})
    assert cover.is_closed is None


def test_cover_direction_settle_lifecycle(hass: HomeAssistant) -> None:
    """Test schedule, cancel, and settled callback for direction settle."""
    cover, _, _ = _create_cover(hass)

    # Schedule settle check
    cover._schedule_direction_settle_check()
    assert cover._settle_unsub is not None

    # Cancel settle check
    cover._cancel_direction_settle_check()
    assert cover._settle_unsub is None

    # Schedule without hass
    cover.hass = None
    cover._schedule_direction_settle_check()
    assert cover._settle_unsub is None

    # Settled callback when processing=True writes state
    cover.hass = hass
    cover._channel["processing"] = True
    cover._async_direction_settled(None)
    cover.async_write_ha_state.assert_called_once()

    # async_will_remove_from_hass cancels settle check
    cover._schedule_direction_settle_check()
    import asyncio

    asyncio.run(cover.async_will_remove_from_hass())
    assert cover._settle_unsub is None


async def test_cover_set_position_unknown_current(hass: HomeAssistant) -> None:
    """Test async_set_cover_position when current_cover_position is None."""
    cover, _, client = _create_cover(hass, channel_data={"shutterLevel": None})
    cover._attr_assumed_state = False
    await cover.async_set_cover_position(**{ATTR_POSITION: 50})
    assert cover.assumed_state is True
    assert cover._optimistic_direction is None
    client.async_set_shutter_level.assert_awaited_once_with("cover-dev-1", 1, 0.5)

    cover._attr_assumed_state = False
    await cover.async_stop_cover()
    assert cover.assumed_state is True
    client.async_stop_cover.assert_awaited_with("cover-dev-1", 1)


async def test_cover_tilt_unsupported_or_unknown_level(hass: HomeAssistant) -> None:
    """Test cover tilt methods when tilt unsupported or current level unknown."""
    # 1. Tilt unsupported (no slatsLevel in channel)
    cover_no_tilt, _, client_no_tilt = _create_cover(
        hass, channel_data={"shutterLevel": 0.5}
    )
    assert not (cover_no_tilt.supported_features & CoverEntityFeature.SET_TILT_POSITION)

    await cover_no_tilt.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 50})
    await cover_no_tilt.async_open_cover_tilt()
    await cover_no_tilt.async_close_cover_tilt()
    await cover_no_tilt.async_stop_cover_tilt()
    client_no_tilt.async_set_slats_level.assert_not_awaited()
    client_no_tilt.async_stop_cover.assert_not_awaited()

    # 2. Tilt supported, but level is None
    cover_tilt_no_level, _, client_no_level = _create_cover(
        hass,
        channel_data={
            "slatsLevel": 0.5,
            "blindModeActive": True,
            "shutterLevel": None,
        },
    )
    assert cover_tilt_no_level.supported_features & CoverEntityFeature.SET_TILT_POSITION

    await cover_tilt_no_level.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 50})
    await cover_tilt_no_level.async_open_cover_tilt()
    await cover_tilt_no_level.async_close_cover_tilt()
    client_no_level.async_set_slats_level.assert_not_awaited()


def test_stateless_garage_door_properties(hass: HomeAssistant) -> None:
    """Test HcuGarageDoorCover when stateless (no doorState in channel)."""
    garage, _, _ = _create_garage(hass, stateful=False, ventilation=False)
    assert garage.name == "Garage Door"
    assert garage.has_entity_name is True
    assert garage.supported_features == (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )
    assert garage.is_closed is None
    assert garage.is_opening is False
    assert garage.is_closing is False
    assert garage.current_cover_position is None
    assert garage.current_cover_tilt_position is None


def test_stateful_garage_door_unexpected_states(hass: HomeAssistant) -> None:
    """Test HcuGarageDoorCover current positions with unknown door states."""
    garage, _, _ = _create_garage(
        hass, stateful=True, channel_overrides={"doorState": "UNKNOWN_STATE"}
    )
    assert garage.current_cover_position is None
    assert garage.current_cover_tilt_position is None

    # Tilt position when ventilation not supported
    garage_no_vent, _, _ = _create_garage(hass, stateful=True, ventilation=False)
    assert garage_no_vent.current_cover_tilt_position is None


async def test_garage_door_actions_stateless_and_stateful(
    hass: HomeAssistant,
) -> None:
    """Test open, close, stop, and tilt actions for stateful and stateless garage doors."""
    # Stateful
    garage_stateful, _, client_s = _create_garage(hass, stateful=True, ventilation=True)

    await garage_stateful.async_open_cover()
    client_s.async_send_door_command.assert_awaited_once_with("garage-dev-1", 1, "OPEN")

    client_s.async_send_door_command.reset_mock()
    await garage_stateful.async_close_cover()
    client_s.async_send_door_command.assert_awaited_once_with(
        "garage-dev-1", 1, "CLOSE"
    )

    client_s.async_send_door_command.reset_mock()
    await garage_stateful.async_stop_cover()
    client_s.async_send_door_command.assert_awaited_once_with("garage-dev-1", 1, "STOP")

    client_s.async_send_door_command.reset_mock()
    await garage_stateful.async_open_cover_tilt()
    client_s.async_send_door_command.assert_awaited_once_with(
        "garage-dev-1", 1, "PARTIAL_OPEN"
    )

    client_s.async_send_door_command.reset_mock()
    await garage_stateful.async_close_cover_tilt()
    client_s.async_send_door_command.assert_awaited_once_with(
        "garage-dev-1", 1, "CLOSE"
    )

    client_s.async_send_door_command.reset_mock()
    await garage_stateful.async_stop_cover_tilt()
    client_s.async_send_door_command.assert_awaited_once_with("garage-dev-1", 1, "STOP")

    # Stateless
    garage_stateless, _, client_sl = _create_garage(
        hass, stateful=False, ventilation=False
    )

    await garage_stateless.async_open_cover()
    client_sl.async_toggle_garage_door_state.assert_awaited_once_with("garage-dev-1", 1)

    client_sl.async_toggle_garage_door_state.reset_mock()
    await garage_stateless.async_close_cover()
    client_sl.async_toggle_garage_door_state.assert_awaited_once_with("garage-dev-1", 1)

    # Stop on stateless returns early
    await garage_stateless.async_stop_cover()
    client_sl.async_send_door_command.assert_not_awaited()

    # Tilt when ventilation not supported returns early
    client_sl.async_toggle_garage_door_state.reset_mock()
    await garage_stateless.async_open_cover_tilt()
    await garage_stateless.async_close_cover_tilt()
    await garage_stateless.async_stop_cover_tilt()
    client_sl.async_send_door_command.assert_not_awaited()
    client_sl.async_toggle_garage_door_state.assert_not_awaited()


async def test_cover_group_methods_and_shutter_level_fallback(
    hass: HomeAssistant,
) -> None:
    """Test HcuCoverGroup open, close, stop, set_position, tilt, and shutterLevel fallback."""
    group_data = {
        "id": "grp-shutter-1",
        "type": "SHUTTER",
        "label": "Living Room Covers",
        "primaryShadingLevel": None,
        "shutterLevel": 0.3,
        "secondaryShadingLevel": None,
    }

    client = MagicMock()
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.async_group_control = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass

    cover_group = HcuCoverGroup(coordinator, client, group_data)
    cover_group.hass = hass
    cover_group.async_write_ha_state = MagicMock()

    # Position fallback to None
    assert cover_group.is_closed is None

    # Fallback to shutterLevel in _get_group_primary_level
    assert cover_group._get_group_primary_level() == 0.3

    # Open cover group
    cover_group._attr_assumed_state = False
    await cover_group.async_open_cover()
    assert cover_group.assumed_state is True
    client.async_group_control.assert_awaited_with(
        API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
        "grp-shutter-1",
        {"primaryShadingLevel": 0.0},
    )

    # Close cover group
    cover_group._attr_assumed_state = False
    await cover_group.async_close_cover()
    assert cover_group.assumed_state is True
    client.async_group_control.assert_awaited_with(
        API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
        "grp-shutter-1",
        {"primaryShadingLevel": 1.0},
    )

    # Stop cover group
    cover_group._attr_assumed_state = False
    await cover_group.async_stop_cover()
    assert cover_group.assumed_state is True
    client.async_group_control.assert_awaited_with(
        API_PATHS["STOP_GROUP_COVER"], "grp-shutter-1"
    )

    # Set cover position
    cover_group._attr_assumed_state = False
    await cover_group.async_set_cover_position(**{ATTR_POSITION: 40})
    assert cover_group.assumed_state is True
    client.async_group_control.assert_awaited_with(
        API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
        "grp-shutter-1",
        {"primaryShadingLevel": 0.6},
    )

    # Stop cover tilt
    cover_group._attr_assumed_state = False
    client.async_group_control.reset_mock()
    await cover_group.async_stop_cover_tilt()
    assert cover_group.assumed_state is True
    client.async_group_control.assert_awaited_once_with(
        API_PATHS["STOP_GROUP_COVER"], "grp-shutter-1"
    )


def test_cover_naming_multiple_channels(hass: HomeAssistant) -> None:
    """Test naming when no label and multiple channels exist."""
    device = {
        "id": "cover-dev-multi",
        "label": "Cover Dev",
        "type": "SHUTTER_CONTACT",
        "functionalChannels": {
            "1": {"functionalChannelType": "SHUTTER_CHANNEL", "label": None},
            "2": {"functionalChannelType": "SHUTTER_CHANNEL", "label": None},
        },
    }
    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device)
    coordinator = MagicMock()
    cover = HcuCover(coordinator, client, device, "1")
    assert cover.unique_id == "cover-dev-multi_1_cover"


def test_cover_is_closed_true(hass: HomeAssistant) -> None:
    """Test is_closed returns True when shutterLevel is 1.0 (pos 0)."""
    cover, _, _ = _create_cover(hass, channel_data={"shutterLevel": 1.0})
    assert cover.is_closed is True


async def test_cover_tilt_actions_with_valid_level(hass: HomeAssistant) -> None:
    """Test open, close, and stop cover tilt with valid level."""
    cover, _, client = _create_cover(
        hass,
        channel_data={
            "slatsLevel": 0.5,
            "blindModeActive": True,
            "shutterLevel": 0.2,
        },
    )
    # Open tilt
    await cover.async_open_cover_tilt()
    client.async_set_slats_level.assert_awaited_with(
        "cover-dev-1", 1, 0.0, shutter_level=0.2
    )

    # Close tilt
    await cover.async_close_cover_tilt()
    client.async_set_slats_level.assert_awaited_with(
        "cover-dev-1", 1, 1.0, shutter_level=0.2
    )

    # Set tilt position
    cover._attr_assumed_state = False
    await cover.async_set_cover_tilt_position(**{ATTR_TILT_POSITION: 70})
    client.async_set_slats_level.assert_awaited_with(
        "cover-dev-1", 1, 0.3, shutter_level=0.2
    )
    assert cover.assumed_state is True

    # Stop tilt
    await cover.async_stop_cover_tilt()
    client.async_stop_cover.assert_awaited_with("cover-dev-1", 1)


def test_stateful_garage_door_motions_and_closed(hass: HomeAssistant) -> None:
    """Test is_closed, is_opening, and is_closing for stateful garage door."""
    garage_opening, _, _ = _create_garage(
        hass,
        stateful=True,
        channel_overrides={"doorState": "OPEN", "doorMotion": "OPENING"},
    )
    assert garage_opening.name == "Garage Door"
    assert garage_opening.has_entity_name is True
    assert garage_opening.is_closed is False
    assert garage_opening.is_opening is True
    assert garage_opening.is_closing is False

    garage_closing, _, _ = _create_garage(
        hass,
        stateful=True,
        channel_overrides={"doorState": "CLOSED", "doorMotion": "CLOSING"},
    )
    assert garage_closing.is_closed is True
    assert garage_closing.is_opening is False
    assert garage_closing.is_closing is True
