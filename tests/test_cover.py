"""Tests for the HCU Cover platform."""
from unittest.mock import AsyncMock, MagicMock
import pytest

from homeassistant.components.cover import (
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    CoverDeviceClass,
    CoverEntityFeature,
)

from custom_components.hcu_integration.cover import HcuCover, HcuCoverGroup, TILT_FEATURES
from custom_components.hcu_integration.const import API_PATHS

# Feature constants for test assertions
BASIC_COVER_FEATURES = (
    CoverEntityFeature.OPEN
    | CoverEntityFeature.CLOSE
    | CoverEntityFeature.STOP
    | CoverEntityFeature.SET_POSITION
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    return coordinator

@pytest.fixture
def mock_hcu_client():
    """Create a mock HCU client."""
    client = MagicMock()
    return client

async def test_cover_group_properties_shutter(mock_coordinator, mock_hcu_client):
    """Test cover group position reading (SHUTTER)."""
    group_data = {
        "id": "group-id",
        "type": "SHUTTER",
        "label": "Test Shutter Group",
        "primaryShadingLevel": 0.0, # Open
        "shutterLevel": 0.5, # Should be ignored
    }
    
    mock_hcu_client.get_group_by_id = MagicMock(return_value=group_data)

    cover = HcuCoverGroup(mock_coordinator, mock_hcu_client, group_data)
    
    # Verify device class is SHUTTER
    assert cover.device_class == CoverDeviceClass.SHUTTER
    
    # Check initial position
    assert cover.current_cover_position == 100 
    
    # Update data
    group_data["primaryShadingLevel"] = 0.5
    assert cover.current_cover_position == 50
    
    group_data["primaryShadingLevel"] = 1.0 # Closed
    assert cover.current_cover_position == 0
    assert cover.is_closed is True

async def test_cover_group_properties_blind(mock_coordinator, mock_hcu_client):
    """Test cover group position and tilt reading (BLIND)."""
    group_data = {
        "id": "group-id",
        "type": "BLIND",
        "label": "Test Blind Group",
        "primaryShadingLevel": 0.25,
        "secondaryShadingLevel": 0.75,
        "shutterLevel": 0.0, # Should be ignored
    }
    
    mock_hcu_client.get_group_by_id = MagicMock(return_value=group_data)

    cover = HcuCoverGroup(mock_coordinator, mock_hcu_client, group_data)
    
    # Verify supported features include all TILT capabilities
    assert cover.supported_features & CoverEntityFeature.SET_TILT_POSITION
    assert cover.supported_features & CoverEntityFeature.OPEN_TILT
    assert cover.supported_features & CoverEntityFeature.CLOSE_TILT
    assert cover.supported_features & CoverEntityFeature.STOP_TILT
    
    # Verify device class is BLIND
    assert cover.device_class == CoverDeviceClass.BLIND

    # 0.25 level = 75% open
    assert cover.current_cover_position == 75
    
    # 0.75 level = 25% open (tilt)
    assert cover.current_cover_tilt_position == 25

@pytest.mark.parametrize(
    "level, expected_position",
    [
        (0.004, 100),  # (1 - 0.004) * 100 = 99.6 -> round(99.6) = 100
        (0.006, 99),   # (1 - 0.006) * 100 = 99.4 -> round(99.4) = 99
    ],
)
async def test_cover_device_rounding(
    mock_coordinator, mock_hcu_client, level, expected_position
):
    """Test rounding logic for single devices."""
    device_data = {
        "id": "device-id",
        "type": "HMIP-BROLL",
        "functionalChannels": {
            "1": {
                "label": "Shutter Channel",
                "shutterLevel": level,
            }
        },
    }

    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    assert cover.current_cover_position == expected_position

@pytest.mark.parametrize(
    "level, expected_position",
    [
        (0.004, 100),  # 0.4% -> 99.6% open -> 100
        (0.006, 99),   # 0.6% -> 99.4% open -> 99
    ],
)
async def test_cover_group_rounding(
    mock_coordinator, mock_hcu_client, level, expected_position
):
    """Test rounding logic for groups."""
    group_data = {
        "id": "group-id",
        "type": "SHUTTER",
        "primaryShadingLevel": level,
    }

    mock_hcu_client.get_group_by_id = MagicMock(return_value=group_data)

    cover = HcuCoverGroup(mock_coordinator, mock_hcu_client, group_data)
    assert cover.current_cover_position == expected_position

async def test_cover_tilt_rounding(mock_coordinator, mock_hcu_client):
    """Test rounding logic for tilt (device)."""
    device_data = {
        "id": "device-id",
        "type": "HMIP-BBL", # Blind
        "functionalChannels": {
            "1": {
                "label": "Blind Channel",
                "shutterLevel": 0.0,
                "slatsLevel": 0.505, # 50.5% -> 49.5% open -> round to 50
            }
        }
    }
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    
    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    
    # (1 - 0.505) * 100 = 0.495 * 100 = 49.5 -> round(49.5) = 50 
    # (Note: python 3 rounds to nearest even number for .5 constraints, so 49.5 -> 50, 50.5 -> 50)
    # Let's check a clear case: 0.506 -> 0.494 * 100 = 49.4 -> 49
    
    assert cover.current_cover_tilt_position == 50
    
    device_data["functionalChannels"]["1"]["slatsLevel"] = 0.506
    assert cover.current_cover_tilt_position == 49

async def test_cover_device_blind_class(mock_coordinator, mock_hcu_client):
    """Test device class detection for blind devices."""
    device_data = {
        "id": "device-id",
        "type": "HMIP-BBL", # Blind
        "functionalChannels": {
            "1": {
                "label": "Blind Channel",
                "shutterLevel": 0.0,
                "slatsLevel": 0.0,
            }
        }
    }
    
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    
    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    
    assert cover.device_class == CoverDeviceClass.BLIND
    assert cover.supported_features & CoverEntityFeature.SET_TILT_POSITION

async def test_cover_device_tilt_passes_shutter_level(mock_coordinator, mock_hcu_client):
    """Test that setting tilt position passes the current shutter level."""
    # Setup device using primaryShadingLevel to verify dynamic property usage
    device_data = {
        "id": "device-id",
        "type": "HMIP-BBL", 
        "functionalChannels": {
            "1": {
                "label": "Blind Channel",
                "primaryShadingLevel": 0.4, # 40% closed (60% open)
                "slatsLevel": 0.0,
            }
        }
    }
    
    mock_hcu_client.async_set_slats_level = AsyncMock()
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    
    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    
    # Verify level property detection
    assert cover._level_property == "primaryShadingLevel"
    
    # Set tilt to 50% (0.5 level)
    await cover.async_set_cover_tilt_position(tilt_position=50)
    
    # Check if async_set_slats_level was called with correct shutter_level
    mock_hcu_client.async_set_slats_level.assert_called_once_with(
        "device-id", 1, 0.5, shutter_level=0.4
    )


async def test_cover_group_with_none_secondary_shading_level(mock_coordinator, mock_hcu_client):
    """Test that groups with secondaryShadingLevel=None are classified as SHUTTER.

    This tests the fix for issue #207: BROLL-only groups were incorrectly imported
    as blinds because the API returns secondaryShadingLevel key with None value
    for groups without tilt support.
    """
    group_data = {
        "id": "group-id",
        "type": "SHUTTER",
        "label": "BROLL Group",
        "primaryShadingLevel": 0.0,
        "secondaryShadingLevel": None,  # Key present but None - no tilt support
    }

    mock_hcu_client.get_group_by_id = MagicMock(return_value=group_data)

    cover = HcuCoverGroup(mock_coordinator, mock_hcu_client, group_data)

    # Verify device class is SHUTTER (not BLIND)
    assert cover.device_class == CoverDeviceClass.SHUTTER

    # Verify basic cover features are supported
    assert cover.supported_features == BASIC_COVER_FEATURES

    # Verify tilt position returns None
    assert cover.current_cover_tilt_position is None

    # Verify position still works correctly
    assert cover.current_cover_position == 100  # 0.0 level = fully open


def _make_shutter_device(processing=False, last_shading_direction=None, shutter_level=0.0):
    """Build a minimal BROLL device_data dict for direction tests."""
    return {
        "id": "device-id",
        "type": "HMIP-BROLL",
        "functionalChannels": {
            "1": {
                "label": "Shutter Channel",
                "shutterLevel": shutter_level,
                "processing": processing,
                "lastShadingDirection": last_shading_direction,
            }
        },
    }


async def test_cover_direction_falls_back_to_hcu_data_without_local_command(
    mock_coordinator, mock_hcu_client
):
    """Without a locally issued command (e.g. movement started via the native app),
    is_opening/is_closing should reflect the HCU-reported lastShadingDirection as before.
    """
    device_data = _make_shutter_device(processing=True, last_shading_direction="DARKER")
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    assert cover.is_closing is True
    assert cover.is_opening is False


async def test_cover_direction_not_moving_reports_neither(mock_coordinator, mock_hcu_client):
    """When the HCU reports processing=False, neither opening nor closing should be true,
    regardless of a stale lastShadingDirection value."""
    device_data = _make_shutter_device(processing=False, last_shading_direction="LIGHTER")
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    assert cover.is_opening is False
    assert cover.is_closing is False


async def test_cover_external_move_direction_held_back_until_settled(
    mock_coordinator, mock_hcu_client
):
    """Regression test for the native-app follow-up to issue #433: the direction
    flicker also happens for moves HA never commanded (native app, wall switch),
    where there is no local optimistic direction to fall back on. Since neither
    lastShadingDirection nor current_cover_position are guaranteed to arrive
    quickly or reliably from the HCU, we simply hold back showing any direction
    for DIRECTION_SETTLE_SECONDS after a move starts, instead of risking the
    wrong one.
    """
    device_data = _make_shutter_device(processing=False)
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    cover.async_write_ha_state = MagicMock()  # entity is not attached to hass in this test
    mock_coordinator.data = {"device-id": device_data}

    # Movement starts from the native app - HA was never told, so there is no
    # local optimistic direction. The HCU's lastShadingDirection is wrong/stale
    # right after processing flips to True.
    device_data["functionalChannels"]["1"]["processing"] = True
    device_data["functionalChannels"]["1"]["lastShadingDirection"] = "LIGHTER"
    cover._handle_coordinator_update()

    # Still within the settle window: neither direction is shown, rather than
    # risking the (currently wrong) raw value.
    assert cover.is_opening is False
    assert cover.is_closing is False

    # A moment later the HCU corrects itself, still within the settle window -
    # still held back.
    device_data["functionalChannels"]["1"]["lastShadingDirection"] = "DARKER"
    cover._handle_coordinator_update()
    assert cover.is_opening is False
    assert cover.is_closing is False

    # Simulate the settle window having elapsed: the (by now correct) raw
    # value is trusted.
    cover._processing_started_at -= 999
    assert cover.is_closing is True
    assert cover.is_opening is False

    # Movement ends: settle tracking resets for the next move.
    device_data["functionalChannels"]["1"]["processing"] = False
    cover._handle_coordinator_update()
    assert cover.is_closing is False
    assert cover.is_opening is False
    assert cover._processing_started_at is None


async def test_cover_close_command_overrides_stale_direction_flicker(
    mock_coordinator, mock_hcu_client
):
    """Regression test for issue #433: after HA commands a close, the HCU may briefly
    push processing=True together with the *previous* movement's lastShadingDirection
    (LIGHTER/opening) before correcting it a moment later. The optimistic direction we
    set locally on command must win over that stale value so is_closing/is_opening
    never flicker to the wrong direction.
    """
    device_data = _make_shutter_device(processing=False, last_shading_direction="LIGHTER")
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    mock_hcu_client.async_set_shutter_level = AsyncMock()

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    await cover.async_close_cover()

    # HCU push #1: processing flips to True, but direction still stale ("LIGHTER"/opening)
    device_data["functionalChannels"]["1"]["processing"] = True
    device_data["functionalChannels"]["1"]["lastShadingDirection"] = "LIGHTER"
    assert cover.is_closing is True
    assert cover.is_opening is False

    # HCU push #2: direction corrected to "DARKER"/closing - still consistent
    device_data["functionalChannels"]["1"]["lastShadingDirection"] = "DARKER"
    assert cover.is_closing is True
    assert cover.is_opening is False

    # Movement finishes: coordinator confirms processing=False, clearing the override
    device_data["functionalChannels"]["1"]["processing"] = False
    mock_coordinator.data = {"device-id": device_data}
    cover.async_write_ha_state = MagicMock()  # entity is not attached to hass in this test
    cover._handle_coordinator_update()

    assert cover._optimistic_direction is None
    assert cover.is_closing is False
    assert cover.is_opening is False


async def test_cover_open_command_sets_optimistic_direction(mock_coordinator, mock_hcu_client):
    """async_open_cover should set the optimistic direction to 'opening'."""
    device_data = _make_shutter_device(processing=False)
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    mock_hcu_client.async_set_shutter_level = AsyncMock()

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    await cover.async_open_cover()

    assert cover._optimistic_direction == "opening"


async def test_cover_stop_command_clears_optimistic_direction(mock_coordinator, mock_hcu_client):
    """async_stop_cover should drop any locally assumed direction."""
    device_data = _make_shutter_device(processing=False)
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    mock_hcu_client.async_set_shutter_level = AsyncMock()
    mock_hcu_client.async_stop_cover = AsyncMock()

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")
    await cover.async_close_cover()
    assert cover._optimistic_direction == "closing"

    await cover.async_stop_cover()
    assert cover._optimistic_direction is None


async def test_cover_external_override_wins_back_after_grace_window(
    mock_coordinator, mock_hcu_client
):
    """If something else (wall switch, native app) takes over an ongoing
    HA-commanded move and reverses direction, our local override must not mask
    that indefinitely - it should expire and let the real HCU-reported
    direction win back the display.
    """
    device_data = _make_shutter_device(processing=False, last_shading_direction="LIGHTER")
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    mock_hcu_client.async_set_shutter_level = AsyncMock()

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    await cover.async_close_cover()
    device_data["functionalChannels"]["1"]["processing"] = True

    # Someone else takes over mid-move and reverses direction; the HCU now
    # correctly reports "LIGHTER" (opening), but our override still says closing.
    device_data["functionalChannels"]["1"]["lastShadingDirection"] = "LIGHTER"
    assert cover.is_closing is True  # still within the grace window
    assert cover.is_opening is False

    # Simulate the grace window having elapsed without a processing=False update
    cover._optimistic_direction_set_at -= 999

    assert cover.is_closing is False
    assert cover.is_opening is True  # real HCU data wins back


async def test_cover_set_position_infers_direction(mock_coordinator, mock_hcu_client):
    """async_set_cover_position should infer opening/closing from the target vs. current position."""
    # shutterLevel 0.5 -> current_cover_position 50
    device_data = _make_shutter_device(processing=False, shutter_level=0.5)
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)
    mock_hcu_client.async_set_shutter_level = AsyncMock()

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    # Target position 80 > current 50 -> opening (moving towards fully open)
    await cover.async_set_cover_position(position=80)
    assert cover._optimistic_direction == "opening"

    # Target position 20 < current 50 -> closing
    await cover.async_set_cover_position(position=20)
    assert cover._optimistic_direction == "closing"

    # Target position equals current -> no movement, no direction
    await cover.async_set_cover_position(position=50)
    assert cover._optimistic_direction is None


async def test_cover_device_with_none_slats_level(mock_coordinator, mock_hcu_client):
    """Test that devices with slatsLevel=None are reclassified from BLIND to SHUTTER.

    This tests the fix for issue #207: HmIPW-DRBL4 devices were incorrectly
    displayed as blinds because the API returns slatsLevel key with None value
    for channels without tilt/slats configured. Devices initially classified as
    BLIND (from device type mapping) but without actual tilt support should be
    reclassified as SHUTTER.
    """
    device_data = {
        "id": "device-id",
        "type": "WIRED_DIN_RAIL_BLIND_4",  # Mapped to BLIND in const.py
        "label": "02_DRBL4",
        "functionalChannels": {
            "1": {
                "label": "Channel 1",
                "functionalChannelType": "BLIND_CHANNEL",
                "shutterLevel": 0.5,
                "slatsLevel": None,  # Key present but None - no tilt configured
                "slatsReferenceTime": 0.0,
            }
        },
    }

    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device_data, "1")

    # Verify device class is SHUTTER (reclassified from BLIND due to no tilt support)
    assert cover.device_class == CoverDeviceClass.SHUTTER

    # Verify basic cover features are supported
    assert cover.supported_features == BASIC_COVER_FEATURES

    # Verify tilt position returns None
    assert cover.current_cover_tilt_position is None

    # Verify position works correctly
    assert cover.current_cover_position == 50  # 0.5 level = 50% open
