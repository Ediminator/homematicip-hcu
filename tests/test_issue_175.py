"""Tests for Issue 175: duplicate window sensors on multi mode input channels and role mapping interaction."""

from unittest.mock import MagicMock
from homeassistant.const import Platform
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from custom_components.hcu_integration.discovery import async_discover_entities
from custom_components.hcu_integration.binary_sensor import HcuWindowBinarySensor
from custom_components.hcu_integration import HcuCoordinator
from custom_components.hcu_integration.const import (
    MULTI_MODE_INPUT_KEY_BEHAVIOR,
    MULTI_MODE_INPUT_SWITCH_BEHAVIOR,
    MULTI_MODE_INPUT_BINARY_BEHAVIOR,
    CHANNEL_ROLE_DOOR_SENSOR,
    CHANNEL_ROLE_WINDOW_SENSOR,
)


async def test_duplicate_window_sensor_filtered(hass, mock_hcu_client, mock_config_entry):
    """Test that windowState is ignored when multiModeInputMode is KEY_BEHAVIOR or SWITCH_BEHAVIOR."""
    # Setup mock device with channels configurations
    device = {
        "id": "test_fci6",
        "type": "HMIP-FCI6",
        "modelType": "HMIP-FCI6",
        "label": "Test Input Module",
        "functionalChannels": {
            "1": {  # Button configuration -> Should NOT create Window sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_KEY_BEHAVIOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "2": {  # Switch configuration -> Should NOT create Window sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_SWITCH_BEHAVIOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            },
            "3": {  # Contact configuration (Window)
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "channelRole": CHANNEL_ROLE_WINDOW_SENSOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "4": {  # Contact configuration (Door)
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "channelRole": CHANNEL_ROLE_DOOR_SENSOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            },
        },
    }

    mock_hcu_client.state = {"devices": {"test_fci6": device}}
    mock_coordinator = MagicMock(spec=HcuCoordinator)
    mock_coordinator.config_entry = mock_config_entry

    entities = await async_discover_entities(hass, mock_hcu_client, mock_config_entry, mock_coordinator)

    binary_sensors = entities.get(Platform.BINARY_SENSOR, [])

    # Assertions
    # Channels 1 and 2 should be filtered out. Channels 3 and 4 should be created.
    assert len(binary_sensors) == 2, f"Expected 2 binary sensors, got {len(binary_sensors)}"

    # Check device classes
    window_sensor = next((e for e in binary_sensors if e._channel_index == 3), None)
    door_sensor = next((e for e in binary_sensors if e._channel_index == 4), None)

    assert window_sensor is not None
    assert type(window_sensor) is HcuWindowBinarySensor
    assert window_sensor.device_class == BinarySensorDeviceClass.WINDOW

    assert door_sensor is not None
    assert type(door_sensor) is HcuWindowBinarySensor
    assert door_sensor.device_class == BinarySensorDeviceClass.DOOR


async def test_role_mapping_with_multimode_mode_filters(hass, mock_hcu_client, mock_config_entry):
    """Test that role-mapped channels still respect multiModeInputMode filters.
    
    1. A channel role mapped to HcuButtonEvent (KEY_OR_SWITCH_FOR_GROUP) or HcuDoorbellEvent (DOOR_BELL_INPUT)
       must NOT create event entities when multiModeInputMode is BINARY_BEHAVIOR.
    2. A channel role mapped to HcuWindowBinarySensor (WINDOW_SENSOR/DOOR_SENSOR)
       must NOT create window sensors when multiModeInputMode is KEY_BEHAVIOR or SWITCH_BEHAVIOR.
    3. A channel with role KEY_OR_SWITCH_FOR_GROUP and KEY_BEHAVIOR should create an event entity.
    4. Channels with role WINDOW_SENSOR / DOOR_SENSOR and BINARY_BEHAVIOR should create appropriate binary sensors.
    """
    device = {
        "id": "test_fci6_roles",
        "type": "HMIP-FCI6",
        "modelType": "HMIP-FCI6",
        "label": "Test Input Module with Roles",
        "functionalChannels": {
            "1": {
                # Role is KEY_OR_SWITCH_FOR_GROUP, but mode is BINARY_BEHAVIOR (security contact)
                # Event entity should be skipped
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "2": {
                # Role is DOOR_BELL_INPUT, but mode is BINARY_BEHAVIOR
                # Doorbell event entity should be skipped
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "DOOR_BELL_INPUT",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            },
            "3": {
                # Role is WINDOW_SENSOR, but mode is KEY_BEHAVIOR (configured as button)
                # Window binary sensor should be skipped
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "WINDOW_SENSOR",
                "multiModeInputMode": MULTI_MODE_INPUT_KEY_BEHAVIOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "4": {
                # Role is DOOR_SENSOR, but mode is SWITCH_BEHAVIOR (configured as switch)
                # Door binary sensor should be skipped
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "DOOR_SENSOR",
                "multiModeInputMode": MULTI_MODE_INPUT_SWITCH_BEHAVIOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            },
            "5": {
                # Role is KEY_OR_SWITCH_FOR_GROUP, and mode is KEY_BEHAVIOR
                # Should create event entity, but NOT windowState binary sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
                "multiModeInputMode": MULTI_MODE_INPUT_KEY_BEHAVIOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "6": {
                # Role is WINDOW_SENSOR and mode is BINARY_BEHAVIOR
                # Should create window binary sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "WINDOW_SENSOR",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "7": {
                # Role is DOOR_SENSOR and mode is BINARY_BEHAVIOR
                # Should create door binary sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "channelRole": "DOOR_SENSOR",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            },
        },
    }

    mock_hcu_client.state = {"devices": {"test_fci6_roles": device}}
    mock_coordinator = MagicMock(spec=HcuCoordinator)
    mock_coordinator.config_entry = mock_config_entry

    entities = await async_discover_entities(hass, mock_hcu_client, mock_config_entry, mock_coordinator)

    binary_sensors = entities.get(Platform.BINARY_SENSOR, [])
    events = entities.get(Platform.EVENT, [])

    # Channels 6 & 7 (binary mode with contact role) should create binary sensors
    # Channels 1, 2 (no contact role), and 3, 4, 5 (key/switch mode) should NOT create binary sensors
    binary_sensor_channels = {e._channel_index for e in binary_sensors}
    assert binary_sensor_channels == {6, 7}, f"Unexpected binary sensor channels: {binary_sensor_channels}"

    window_sensor = next((e for e in binary_sensors if e._channel_index == 6), None)
    door_sensor = next((e for e in binary_sensors if e._channel_index == 7), None)
    assert window_sensor.device_class == BinarySensorDeviceClass.WINDOW
    assert door_sensor.device_class == BinarySensorDeviceClass.DOOR

    # Channel 5 (key mode with KEY_OR_SWITCH_FOR_GROUP) should create an event entity
    # Channels 1 & 2 (binary mode) should NOT create event entities
    event_channels = {e._channel_index_str for e in events}
    assert event_channels == {"5"}, f"Unexpected event channels: {event_channels}"
