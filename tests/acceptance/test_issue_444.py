"""Acceptance tests for Issue 444: HmIP-DRBLI4 (MULTI_MODE_INPUT_BLIND_CHANNEL) cover support."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntityFeature,
)
from homeassistant.const import Platform

from custom_components.hcu_integration.const import (
    HMIP_CHANNEL_TYPE_TO_ENTITY,
    HMIP_DEVICE_TYPE_TO_DEVICE_CLASS,
)
from custom_components.hcu_integration.cover import (
    HcuCover,
)
from custom_components.hcu_integration.discovery import async_discover_entities


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.data = {}
    return coordinator


@pytest.fixture
def mock_hcu_client():
    """Create a mock HCU client."""
    client = MagicMock()
    client.async_set_shutter_level = AsyncMock()
    client.async_set_slats_level = AsyncMock()
    client.async_stop_cover = AsyncMock()
    return client


def test_constants_mapping():
    """Test that MULTI_MODE_INPUT_BLIND_CHANNEL and DIN_RAIL_BLIND_4 are correctly mapped in const.py."""
    assert "MULTI_MODE_INPUT_BLIND_CHANNEL" in HMIP_CHANNEL_TYPE_TO_ENTITY
    assert HMIP_CHANNEL_TYPE_TO_ENTITY["MULTI_MODE_INPUT_BLIND_CHANNEL"] == {"class": "HcuCover"}

    assert "DIN_RAIL_BLIND_4" in HMIP_DEVICE_TYPE_TO_DEVICE_CLASS
    assert HMIP_DEVICE_TYPE_TO_DEVICE_CLASS["DIN_RAIL_BLIND_4"] == CoverDeviceClass.BLIND


def test_hcu_cover_blind_mode_active_true(mock_coordinator, mock_hcu_client):
    """Test that blindModeActive=True enables tilt support and classifies as BLIND."""
    device_data = {
        "id": "drbli4-001",
        "type": "DIN_RAIL_BLIND_4",
        "label": "Jalousieaktor 1",
        "functionalChannels": {
            "1": {
                "label": "Wohnzimmer Jalousie",
                "functionalChannelType": "MULTI_MODE_INPUT_BLIND_CHANNEL",
                "channelRole": "SHADING_ACTUATOR",
                "shutterLevel": 0.2,  # 80% open
                "slatsLevel": 0.4,  # 60% open tilt
                "blindModeActive": True,
                "groups": ["group-living-room"],
            }
        },
    }
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    assert cover.device_class == CoverDeviceClass.BLIND
    assert cover.supported_features & CoverEntityFeature.SET_TILT_POSITION
    assert cover.supported_features & CoverEntityFeature.OPEN_TILT
    assert cover.supported_features & CoverEntityFeature.CLOSE_TILT
    assert cover.supported_features & CoverEntityFeature.STOP_TILT
    assert cover.current_cover_position == 80
    assert cover.current_cover_tilt_position == 60


def test_hcu_cover_blind_mode_active_false_reclassifies_as_shutter(
    mock_coordinator, mock_hcu_client
):
    """Test that blindModeActive=False disables tilt support and classifies as SHUTTER even if slatsLevel is present."""
    device_data = {
        "id": "drbli4-002",
        "type": "DIN_RAIL_BLIND_4",
        "label": "Jalousieaktor 2",
        "functionalChannels": {
            "1": {
                "label": "Schlafzimmer Rollladen",
                "functionalChannelType": "MULTI_MODE_INPUT_BLIND_CHANNEL",
                "channelRole": "SHADING_ACTUATOR",
                "shutterLevel": 0.5,
                "slatsLevel": 0.0,  # Present but blindModeActive is False -> roller shutter mode
                "blindModeActive": False,
                "groups": ["group-bedroom"],
            }
        },
    }
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    assert cover.device_class == CoverDeviceClass.SHUTTER
    assert not (cover.supported_features & CoverEntityFeature.SET_TILT_POSITION)
    assert not (cover.supported_features & CoverEntityFeature.OPEN_TILT)
    assert not (cover.supported_features & CoverEntityFeature.CLOSE_TILT)
    assert not (cover.supported_features & CoverEntityFeature.STOP_TILT)
    assert cover.current_cover_position == 50


async def test_hcu_cover_actuation_and_tilt(mock_coordinator, mock_hcu_client):
    """Test open, close, stop, set_position and tilt controls."""
    device_data = {
        "id": "drbli4-003",
        "type": "DIN_RAIL_BLIND_4",
        "label": "Küche Jalousie",
        "functionalChannels": {
            "1": {
                "label": "Küche Jalousie",
                "functionalChannelType": "MULTI_MODE_INPUT_BLIND_CHANNEL",
                "channelRole": "SHADING_ACTUATOR",
                "shutterLevel": 0.3,
                "slatsLevel": 0.5,
                "blindModeActive": True,
                "groups": ["group-kitchen"],
            }
        },
    }
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    # Set position (60% -> shutterLevel 0.40)
    await cover.async_set_cover_position(position=60)
    mock_hcu_client.async_set_shutter_level.assert_awaited_with("drbli4-003", 1, 0.4)

    # Set tilt position (80% -> slatsLevel 0.20, shutter_level preserved as 0.3)
    await cover.async_set_cover_tilt_position(tilt_position=80)
    mock_hcu_client.async_set_slats_level.assert_awaited_with(
        "drbli4-003", 1, 0.2, shutter_level=0.3
    )

    # Open tilt (slatsLevel 0.0)
    await cover.async_open_cover_tilt()
    mock_hcu_client.async_set_slats_level.assert_awaited_with(
        "drbli4-003", 1, 0.0, shutter_level=0.3
    )

    # Close tilt (slatsLevel 1.0)
    await cover.async_close_cover_tilt()
    mock_hcu_client.async_set_slats_level.assert_awaited_with(
        "drbli4-003", 1, 1.0, shutter_level=0.3
    )

    # Stop tilt
    await cover.async_stop_cover_tilt()
    mock_hcu_client.async_stop_cover.assert_awaited_with("drbli4-003", 1)


async def test_discovery_skips_unconfigured_channels(mock_coordinator, mock_hcu_client):
    """Test that discovery creates HcuCover for configured channels and skips unconfigured channels."""
    device_data = {
        "id": "drbli4-004",
        "type": "DIN_RAIL_BLIND_4",
        "label": "DRBLI4 Flur",
        "functionalChannels": {
            # Channel 1 is configured and assigned to a room
            "1": {
                "label": "Kanal 1",
                "functionalChannelType": "MULTI_MODE_INPUT_BLIND_CHANNEL",
                "channelRole": "SHADING_ACTUATOR",
                "shutterLevel": 0.0,
                "slatsLevel": 0.5,
                "blindModeActive": True,
                "groups": ["room-flur"],
            },
            # Channel 2 is unassigned (no groups, channelRole null)
            "2": {
                "label": "Kanal 2",
                "functionalChannelType": "MULTI_MODE_INPUT_BLIND_CHANNEL",
                "channelRole": None,
                "shutterLevel": 0.0,
                "slatsLevel": None,
                "groups": [],
            },
        },
    }
    mock_hcu_client.state = {"devices": {"drbli4-004": device_data}, "groups": {}}

    mock_entry = MagicMock()
    mock_entry.options = {}

    mock_hass = MagicMock()

    entities = await async_discover_entities(
        mock_hass, mock_hcu_client, mock_entry, mock_coordinator
    )

    cover_entities = entities.get(Platform.COVER, [])
    assert len(cover_entities) == 1
    discovered_cover = cover_entities[0]
    assert discovered_cover._device_id == "drbli4-004"
    assert discovered_cover._channel_index in (1, "1")
