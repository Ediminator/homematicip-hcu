"""Comprehensive coverage tests for custom_components/hcu_integration/light.py."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntityFeature,
)
from homeassistant.const import STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    API_PATHS,
    DOMAIN,
    HMIP_COLOR_BLACK,
    HMIP_COLOR_BLUE,
    HMIP_COLOR_GREEN,
    HMIP_COLOR_PURPLE,
    HMIP_COLOR_RED,
    HMIP_COLOR_TURQUOISE,
    HMIP_COLOR_WHITE,
    HMIP_COLOR_YELLOW,
    HMIP_OPTICAL_SIGNAL_BEHAVIOURS,
    HMIP_RGB_COLOR_MAP,
)
from custom_components.hcu_integration.light import (
    HcuLight,
    HcuLightGroup,
    HcuNotificationLight,
    HcuSwitchLight,
    _convert_hs_to_simple_rgb,
    async_setup_entry,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}
    coordinator.data = {}
    return coordinator


@pytest.fixture
def mock_hcu_client():
    """Create a mock HCU client."""
    client = MagicMock()
    client.is_connected = True
    client.hcu_device_id = "hcu_main"
    client.hcu_part_device_ids = set()
    client.async_set_dim_level = AsyncMock()
    client.async_set_hue_saturation = AsyncMock()
    client.async_set_color_temperature = AsyncMock()
    client.async_device_control = AsyncMock()
    client.async_set_sound_file = AsyncMock()
    client.async_set_switching_group_state = AsyncMock()
    return client


def test_convert_hs_to_simple_rgb_all_ranges():
    """Test _convert_hs_to_simple_rgb for all hue sectors and low saturation."""
    # Low saturation -> WHITE
    assert _convert_hs_to_simple_rgb((0, 10)) == HMIP_COLOR_WHITE
    assert _convert_hs_to_simple_rgb((180, 19.9)) == HMIP_COLOR_WHITE

    # Hue < 30 -> RED
    assert _convert_hs_to_simple_rgb((0, 80)) == HMIP_COLOR_RED
    assert _convert_hs_to_simple_rgb((29, 80)) == HMIP_COLOR_RED

    # Hue >= 345 -> RED
    assert _convert_hs_to_simple_rgb((345, 80)) == HMIP_COLOR_RED
    assert _convert_hs_to_simple_rgb((359, 80)) == HMIP_COLOR_RED

    # 30 <= hue < 90 -> YELLOW
    assert _convert_hs_to_simple_rgb((30, 80)) == HMIP_COLOR_YELLOW
    assert _convert_hs_to_simple_rgb((60, 80)) == HMIP_COLOR_YELLOW
    assert _convert_hs_to_simple_rgb((89, 80)) == HMIP_COLOR_YELLOW

    # 90 <= hue < 150 -> GREEN
    assert _convert_hs_to_simple_rgb((90, 80)) == HMIP_COLOR_GREEN
    assert _convert_hs_to_simple_rgb((120, 80)) == HMIP_COLOR_GREEN
    assert _convert_hs_to_simple_rgb((149, 80)) == HMIP_COLOR_GREEN

    # 150 <= hue < 210 -> TURQUOISE
    assert _convert_hs_to_simple_rgb((150, 80)) == HMIP_COLOR_TURQUOISE
    assert _convert_hs_to_simple_rgb((180, 80)) == HMIP_COLOR_TURQUOISE
    assert _convert_hs_to_simple_rgb((209, 80)) == HMIP_COLOR_TURQUOISE

    # 210 <= hue < 270 -> BLUE
    assert _convert_hs_to_simple_rgb((210, 80)) == HMIP_COLOR_BLUE
    assert _convert_hs_to_simple_rgb((240, 80)) == HMIP_COLOR_BLUE
    assert _convert_hs_to_simple_rgb((269, 80)) == HMIP_COLOR_BLUE

    # 270 <= hue < 345 -> PURPLE
    assert _convert_hs_to_simple_rgb((270, 80)) == HMIP_COLOR_PURPLE
    assert _convert_hs_to_simple_rgb((300, 80)) == HMIP_COLOR_PURPLE
    assert _convert_hs_to_simple_rgb((344, 80)) == HMIP_COLOR_PURPLE


async def test_async_setup_entry_lights():
    """Test async_setup_entry adds light entities from coordinator."""
    hass = MagicMock()
    mock_entity = MagicMock()
    coordinator = MagicMock()
    coordinator.entities = {Platform.LIGHT: [mock_entity]}

    config_entry = MagicMock()
    config_entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    await async_setup_entry(hass, config_entry, async_add_entities)
    async_add_entities.assert_called_once_with([mock_entity])

    # When no light entities
    coordinator.entities = {}
    async_add_entities.reset_mock()
    await async_setup_entry(hass, config_entry, async_add_entities)
    async_add_entities.assert_not_called()


def test_hcu_light_modes_and_features(mock_coordinator, mock_hcu_client):
    """Test color mode and feature detection across different device channel capabilities."""
    # Color temperature mode
    dev_ct = {
        "id": "dev_ct",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "colorTemperature": 3000,
                "minimalColorTemperature": 2200,
                "maximumColorTemperature": 6000,
                "dimLevel": 0.5,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_ct
    light_ct = HcuLight(mock_coordinator, mock_hcu_client, dev_ct, "1")
    assert light_ct.color_mode == ColorMode.COLOR_TEMP
    assert light_ct.min_color_temp_kelvin == 2200
    assert light_ct.max_color_temp_kelvin == 6000
    assert light_ct.color_temp_kelvin == 3000
    assert light_ct.supported_features & LightEntityFeature.TRANSITION

    # Simple RGB (BSL) with optical signal behaviour
    dev_bsl = {
        "id": "dev_bsl",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "OPTICAL_SIGNAL_CHANNEL",
                "simpleRGBColorState": "RED",
                "dimLevel": 0.8,
                "opticalSignalBehaviour": "BLINKING",
                "supportedOptionalFeatures": {
                    "IFeatureOpticalSignalBehaviourState": True
                },
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_bsl
    light_bsl = HcuLight(mock_coordinator, mock_hcu_client, dev_bsl, "1")
    assert light_bsl.color_mode == ColorMode.HS
    assert light_bsl.supported_features & LightEntityFeature.EFFECT
    assert light_bsl.effect_list == list(HMIP_OPTICAL_SIGNAL_BEHAVIOURS)
    assert light_bsl.effect == "blinking"
    assert light_bsl.hs_color == HMIP_RGB_COLOR_MAP["RED"]
    assert light_bsl.brightness == int(0.8 * 255)
    assert light_bsl.is_on is True

    # When opticalSignalBehaviour is OFF, light is off regardless of dimLevel
    dev_bsl["functionalChannels"]["1"]["opticalSignalBehaviour"] = "OFF"
    assert light_bsl.is_on is False

    # Standard RGB device (hue and saturationLevel)
    dev_rgb = {
        "id": "dev_rgb",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "hue": 120,
                "saturationLevel": 0.75,
                "dimLevel": 0.4,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_rgb
    light_rgb = HcuLight(mock_coordinator, mock_hcu_client, dev_rgb, "1")
    assert light_rgb.color_mode == ColorMode.HS
    assert light_rgb.hs_color == (120.0, 75.0)

    # Missing hue/saturation returns None
    dev_rgb["functionalChannels"]["1"]["hue"] = None
    assert light_rgb.hs_color is None

    # simpleRGBColorState unknown returns None
    dev_bsl["functionalChannels"]["1"]["simpleRGBColorState"] = "UNKNOWN_COLOR"
    assert light_bsl.hs_color is None


async def test_hcu_light_turn_on_with_time(
    mock_coordinator, mock_hcu_client, caplog: pytest.LogCaptureFixture
):
    """Test HcuLight.async_turn_on_with_time success and error rollback."""
    device = {
        "id": "dev_dimmer",
        "functionalChannels": {
            "1": {"functionalChannelType": "DIMMER_CHANNEL", "dimLevel": 0.5}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")
    light.async_write_ha_state = MagicMock()

    # When light is on (dimLevel 0.5), preserves brightness (0.5)
    await light.async_turn_on_with_time(60.0)
    mock_hcu_client.async_set_dim_level.assert_called_once_with(
        "dev_dimmer", 1, pytest.approx(127 / 255.0, 0.01), on_time=60.0
    )
    assert light._attr_assumed_state is True

    # When light is off (dimLevel 0.0), defaults to 1.0 (100%)
    device["functionalChannels"]["1"]["dimLevel"] = 0.0
    mock_hcu_client.async_set_dim_level.reset_mock()
    await light.async_turn_on_with_time(30.0)
    mock_hcu_client.async_set_dim_level.assert_called_once_with(
        "dev_dimmer", 1, 1.0, on_time=30.0
    )

    # Error handling
    mock_hcu_client.async_set_dim_level.side_effect = HcuApiError(
        "Communication timeout"
    )
    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(HcuApiError, match="Communication timeout"),
    ):
        await light.async_turn_on_with_time(10.0)
    assert light._attr_assumed_state is False
    assert "Failed to turn on" in caplog.text


async def test_hcu_light_turn_on_internal_on_time_delegation(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test async_turn_on calls async_turn_on_with_time when internal on-time switch is enabled."""
    device = {
        "id": "dev_timer_light",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "dimLevel": 0.0,
                "onTime": 45.0,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")
    light.hass = hass
    light.async_write_ha_state = MagicMock()

    reg = er.async_get(hass)
    comp = reg.async_get_or_create(
        "switch",
        DOMAIN,
        "dev_timer_light_1_use_internal_on_time",
        suggested_object_id="timer_light",
    )
    hass.states.async_set(comp.entity_id, STATE_ON)

    await light.async_turn_on()
    mock_hcu_client.async_set_dim_level.assert_called_once_with(
        "dev_timer_light", 1, 1.0, on_time=45.0
    )


async def test_hcu_light_turn_on_simple_rgb_bsl(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test async_turn_on for simple RGB devices with optical signal behaviours (HmIP-BSL)."""
    device = {
        "id": "dev_bsl",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "OPTICAL_SIGNAL_CHANNEL",
                "simpleRGBColorState": "GREEN",
                "dimLevel": 0.0,
                "opticalSignalBehaviour": "OFF",
                "supportedOptionalFeatures": {
                    "IFeatureOpticalSignalBehaviourState": True
                },
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")
    light.hass = hass
    light.async_write_ha_state = MagicMock()

    # Call with HS color and transition
    await light.async_turn_on(
        **{
            ATTR_BRIGHTNESS: 255,
            ATTR_HS_COLOR: (240.0, 100.0),  # Blue
            ATTR_TRANSITION: 2.5,
            ATTR_EFFECT: "blinking",
        }
    )
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_OPTICAL_SIGNAL_BEHAVIOUR_WITH_TIME"],
        "dev_bsl",
        1,
        {
            "simpleRGBColorState": HMIP_COLOR_BLUE,
            "dimLevel": 1.0,
            "opticalSignalBehaviour": "BLINKING",
            "rampTime": 2.5,
        },
    )

    # Call without effect or transition: preserves/turns on to "ON"
    mock_hcu_client.async_device_control.reset_mock()
    await light.async_turn_on(**{ATTR_BRIGHTNESS: 128})
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_OPTICAL_SIGNAL_BEHAVIOUR"],
        "dev_bsl",
        1,
        {
            "simpleRGBColorState": "GREEN",
            "dimLevel": pytest.approx(128 / 255.0, 0.01),
            "opticalSignalBehaviour": "ON",
        },
    )

    # Call when current signal is non-OFF (e.g. FLASHING) preserves it
    device["functionalChannels"]["1"]["opticalSignalBehaviour"] = "FLASHING"
    mock_hcu_client.async_device_control.reset_mock()
    await light.async_turn_on()
    assert (
        mock_hcu_client.async_device_control.call_args[0][3]["opticalSignalBehaviour"]
        == "FLASHING"
    )

    # Fallback to WHITE when color is black or missing
    device["functionalChannels"]["1"]["simpleRGBColorState"] = HMIP_COLOR_BLACK
    mock_hcu_client.async_device_control.reset_mock()
    await light.async_turn_on()
    assert (
        mock_hcu_client.async_device_control.call_args[0][3]["simpleRGBColorState"]
        == HMIP_COLOR_WHITE
    )


async def test_hcu_light_turn_on_standard_modes(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test async_turn_on for standard HS color, color temperature, and simple dimmer."""
    # HS color device
    dev_hs = {
        "id": "dev_hs",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "hue": 0,
                "saturationLevel": 1.0,
                "dimLevel": 0.5,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_hs
    light_hs = HcuLight(mock_coordinator, mock_hcu_client, dev_hs, "1")
    light_hs.hass = hass
    await light_hs.async_turn_on(
        **{ATTR_HS_COLOR: (180.0, 60.0), ATTR_BRIGHTNESS: 200, ATTR_TRANSITION: 1.5}
    )
    mock_hcu_client.async_set_hue_saturation.assert_called_once_with(
        "dev_hs", 1, 180, 0.6, pytest.approx(200 / 255.0, 0.01), 1.5
    )

    # Color temperature device
    dev_ct = {
        "id": "dev_ct",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "colorTemperature": 2700,
                "dimLevel": 0.5,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_ct
    light_ct = HcuLight(mock_coordinator, mock_hcu_client, dev_ct, "1")
    light_ct.hass = hass
    await light_ct.async_turn_on(**{ATTR_COLOR_TEMP_KELVIN: 4000, ATTR_BRIGHTNESS: 150})
    mock_hcu_client.async_set_color_temperature.assert_called_once_with(
        "dev_ct", 1, 4000, pytest.approx(150 / 255.0, 0.01), None
    )

    # Simple dimmer device
    dev_dim = {
        "id": "dev_dim",
        "functionalChannels": {
            "1": {"functionalChannelType": "DIMMER_CHANNEL", "dimLevel": 0.2}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_dim
    light_dim = HcuLight(mock_coordinator, mock_hcu_client, dev_dim, "1")
    light_dim.hass = hass
    await light_dim.async_turn_on(**{ATTR_BRIGHTNESS: 50, ATTR_TRANSITION: 0.5})
    mock_hcu_client.async_set_dim_level.assert_called_once_with(
        "dev_dim", 1, pytest.approx(50 / 255.0, 0.01), 0.5
    )


async def test_hcu_light_turn_off(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test async_turn_off for BSL and standard dimmer lights."""
    # BSL light turn off
    dev_bsl = {
        "id": "dev_bsl",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "OPTICAL_SIGNAL_CHANNEL",
                "simpleRGBColorState": "YELLOW",
                "dimLevel": 0.7,
                "opticalSignalBehaviour": "ON",
                "supportedOptionalFeatures": {
                    "IFeatureOpticalSignalBehaviourState": True
                },
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_bsl
    light_bsl = HcuLight(mock_coordinator, mock_hcu_client, dev_bsl, "1")
    light_bsl.hass = hass
    light_bsl.async_write_ha_state = MagicMock()

    await light_bsl.async_turn_off(**{ATTR_TRANSITION: 3.0})
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_OPTICAL_SIGNAL_BEHAVIOUR_WITH_TIME"],
        "dev_bsl",
        1,
        {
            "simpleRGBColorState": "YELLOW",
            "dimLevel": 0.0,
            "opticalSignalBehaviour": "OFF",
            "rampTime": 3.0,
        },
    )

    # Without transition
    mock_hcu_client.async_device_control.reset_mock()
    await light_bsl.async_turn_off()
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_OPTICAL_SIGNAL_BEHAVIOUR"],
        "dev_bsl",
        1,
        {
            "simpleRGBColorState": "YELLOW",
            "dimLevel": 0.0,
            "opticalSignalBehaviour": "OFF",
        },
    )

    # Standard dimmer turn off
    dev_dim = {
        "id": "dev_dim",
        "functionalChannels": {
            "1": {"functionalChannelType": "DIMMER_CHANNEL", "dimLevel": 0.5}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = dev_dim
    light_dim = HcuLight(mock_coordinator, mock_hcu_client, dev_dim, "1")
    light_dim.hass = hass
    await light_dim.async_turn_off()
    mock_hcu_client.async_set_dim_level.assert_called_once_with("dev_dim", 1, 0.0, None)


def test_hcu_switch_light_initialization(mock_coordinator, mock_hcu_client):
    """Test HcuSwitchLight inherits from HcuSwitch and LightEntity."""
    device = {
        "id": "dev_sw_light",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "on": True,
                "label": "Chandelier",
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    switch_light = HcuSwitchLight(mock_coordinator, mock_hcu_client, device, "1")
    assert switch_light.PLATFORM == Platform.LIGHT
    assert switch_light.device_class is None
    assert switch_light.color_mode == ColorMode.ONOFF
    assert switch_light.supported_color_modes == {ColorMode.ONOFF}
    assert switch_light.name == "Chandelier"


async def test_hcu_notification_light_lifecycle(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test HcuNotificationLight properties, turn_on, turn_off, and play_sound."""
    device = {
        "id": "dev_notif",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "dimLevel": 0.6,
                "simpleRGBColorState": "PURPLE",
                "on": True,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    notif = HcuNotificationLight(mock_coordinator, mock_hcu_client, device, "1")
    notif.hass = hass

    assert notif.PLATFORM == Platform.LIGHT
    assert notif.color_mode == ColorMode.HS
    assert notif.supported_color_modes == {ColorMode.HS}
    assert notif.is_on is True
    assert notif.brightness == int(0.6 * 255)
    assert notif.hs_color == HMIP_RGB_COLOR_MAP["PURPLE"]

    # Turn on with HS color and transition
    await notif.async_turn_on(
        **{ATTR_HS_COLOR: (120.0, 100.0), ATTR_BRIGHTNESS: 200, ATTR_TRANSITION: 1.0}
    )
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_SIMPLE_RGB_COLOR_STATE_WITH_TIME"],
        "dev_notif",
        1,
        {
            "simpleRGBColorState": HMIP_COLOR_GREEN,
            "dimLevel": pytest.approx(200 / 255.0, 0.01),
            "rampTime": 1.0,
        },
    )

    # Turn on without kwargs (uses current brightness 0.6, preserves color, no transition)
    mock_hcu_client.async_device_control.reset_mock()
    await notif.async_turn_on()
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
        "dev_notif",
        1,
        {
            "simpleRGBColorState": "PURPLE",
            "dimLevel": pytest.approx(notif.brightness / 255.0, 0.01),
        },
    )

    # Turn off with transition
    mock_hcu_client.async_device_control.reset_mock()
    await notif.async_turn_off(**{ATTR_TRANSITION: 2.0})
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_SIMPLE_RGB_COLOR_STATE_WITH_TIME"],
        "dev_notif",
        1,
        {
            "simpleRGBColorState": HMIP_COLOR_BLACK,
            "dimLevel": 0.0,
            "rampTime": 2.0,
        },
    )

    # Turn off without transition
    mock_hcu_client.async_device_control.reset_mock()
    await notif.async_turn_off()
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
        "dev_notif",
        1,
        {
            "simpleRGBColorState": HMIP_COLOR_BLACK,
            "dimLevel": 0.0,
        },
    )

    # Play sound
    await notif.async_play_sound("alarm.mp3", 0.9, 15.0)
    mock_hcu_client.async_set_sound_file.assert_called_once_with(
        device_id="dev_notif",
        channel_index=1,
        sound_file="alarm.mp3",
        volume=0.9,
        duration=15.0,
    )


def test_hcu_light_group(mock_coordinator, mock_hcu_client):
    """Test HcuLightGroup attributes and platform."""
    group_data = {"id": "grp_light", "label": "Living Room Lights", "on": False}
    mock_hcu_client.get_group_by_id.return_value = group_data

    group = HcuLightGroup(mock_coordinator, mock_hcu_client, group_data)
    assert group.PLATFORM == Platform.LIGHT
    assert group.color_mode == ColorMode.ONOFF
    assert group.supported_color_modes == {ColorMode.ONOFF}


def test_hcu_light_effect_non_string(mock_coordinator, mock_hcu_client):
    """Test HcuLight.effect returns None when opticalSignalBehaviour is not a string."""
    device = {
        "id": "dev_bsl_effect",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "OPTICAL_SIGNAL_CHANNEL",
                "supportedOptionalFeatures": {
                    "IFeatureOpticalSignalBehaviourState": True
                },
                "opticalSignalBehaviour": None,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")
    assert light.effect is None


async def test_hcu_light_turn_on_empty_optical_signal(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test async_turn_on when optical_signal is falsy (empty effect) uses simple RGB state path."""
    device = {
        "id": "dev_bsl_no_signal",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "OPTICAL_SIGNAL_CHANNEL",
                "simpleRGBColorState": "BLUE",
                "dimLevel": 0.5,
                "supportedOptionalFeatures": {
                    "IFeatureOpticalSignalBehaviourState": True
                },
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")
    light.hass = hass
    light.async_write_ha_state = MagicMock()

    await light.async_turn_on(**{ATTR_EFFECT: ""})
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
        "dev_bsl_no_signal",
        1,
        {
            "simpleRGBColorState": "BLUE",
            "dimLevel": pytest.approx(light.brightness / 255.0, 0.01),
        },
    )


async def test_hcu_notification_light_additional_branches(
    mock_coordinator, mock_hcu_client, hass: HomeAssistant
):
    """Test HcuNotificationLight label naming, missing color fallback, and default brightness when off."""
    device = {
        "id": "dev_notif_extra",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "label": "Front Chime Light",
                "dimLevel": 0.0,
                "on": False,
                "simpleRGBColorState": None,
            }
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    notif = HcuNotificationLight(mock_coordinator, mock_hcu_client, device, "1")
    notif.hass = hass

    # Channel label naming
    assert notif.name == "Front Chime Light"

    # hs_color when simpleRGBColorState is None
    assert notif.hs_color is None

    # async_turn_on when off and no brightness specified -> defaults to 255 and WHITE color
    await notif.async_turn_on()
    mock_hcu_client.async_device_control.assert_called_once_with(
        API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
        "dev_notif_extra",
        1,
        {
            "simpleRGBColorState": HMIP_COLOR_WHITE,
            "dimLevel": 1.0,
        },
    )
