"""Tests for Issue 175: duplicate window sensors on multi mode input channels."""

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
            "1": { # Button configuration -> Should NOT create Window sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_KEY_BEHAVIOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "2": { # Switch configuration -> Should NOT create Window sensor
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_SWITCH_BEHAVIOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            },
            "3": { # Contact configuration (Window)
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "channelRole": CHANNEL_ROLE_WINDOW_SENSOR,
                "windowState": "CLOSED",
                "groups": ["room-1"],
            },
            "4": { # Contact configuration (Door)
                "functionalChannelType": "MULTI_MODE_INPUT_CHANNEL",
                "multiModeInputMode": MULTI_MODE_INPUT_BINARY_BEHAVIOR,
                "channelRole": CHANNEL_ROLE_DOOR_SENSOR,
                "windowState": "OPEN",
                "groups": ["room-1"],
            }
        }
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
