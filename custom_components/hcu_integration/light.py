# custom_components/hcu_integration/light.py
"""Support for Homematic IP light entities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ATTR_TRANSITION,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .switch import HcuSwitch
from .entity import HcuBaseEntity, HcuSwitchingGroupBase
from .api import HcuApiClient, HcuApiError
from .const import (
    API_PATHS,
    HMIP_RGB_COLOR_MAP,
    HMIP_COLOR_BLACK,
    HMIP_COLOR_WHITE,
    HMIP_COLOR_RED,
    HMIP_COLOR_BLUE,
    HMIP_COLOR_GREEN,
    HMIP_COLOR_YELLOW,
    HMIP_COLOR_PURPLE,
    HMIP_COLOR_TURQUOISE,
    HMIP_OPTICAL_SIGNAL_BEHAVIOURS,
)

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)

# Saturation threshold below which colors are considered white (low saturation = desaturated)
_LOW_SATURATION_THRESHOLD = 20


def _convert_hs_to_simple_rgb(hs_color: tuple[float, float]) -> str:
    """Convert HA HS color (0-360, 0-100) to the closest Homematic IP simple RGB color name.

    Maps to the 8 colors officially supported by the HCU API:
    BLACK, BLUE, GREEN, TURQUOISE, RED, PURPLE, YELLOW, WHITE

    Note: ORANGE is NOT supported by the HCU API despite appearing in some device specs.
    The orange hue range (15-45°) is split between RED and YELLOW based on proximity.

    Hue ranges are divided to approximate standard color wheel positions while accounting
    for the absence of ORANGE support.

    Args:
        hs_color: Tuple of (hue, saturation) where hue is 0-360 degrees and saturation is 0-100%.

    Returns:
        One of the HMIP_COLOR_* constants representing the closest supported color.
    """
    hue, sat = hs_color

    # If saturation is very low, it's white
    if sat < _LOW_SATURATION_THRESHOLD:
        return HMIP_COLOR_WHITE

    # Hue ranges (0-360 degrees) mapped to 7 supported colors
    # Note: ORANGE removed - hues 0-30 map to RED, 30-90 map to YELLOW
    if hue < 30 or hue >= 345:      # 0 degrees (Red)
        return HMIP_COLOR_RED
    elif 30 <= hue < 90:            # ~60 degrees (Yellow, expanded to include orange range)
        return HMIP_COLOR_YELLOW
    elif 90 <= hue < 150:           # ~120 degrees (Green)
        return HMIP_COLOR_GREEN
    elif 150 <= hue < 210:          # ~180 degrees (Turquoise/Cyan)
        return HMIP_COLOR_TURQUOISE
    elif 210 <= hue < 270:          # ~240 degrees (Blue)
        return HMIP_COLOR_BLUE
    else:  # 270 <= hue < 345        # ~300 degrees (Purple/Magenta)
        return HMIP_COLOR_PURPLE


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform from a config entry."""
    coordinator: HcuCoordinator = hass.data[config_entry.domain][config_entry.entry_id]
    if entities := coordinator.entities.get(Platform.LIGHT):
        async_add_entities(entities)


class HcuLight(HcuBaseEntity, LightEntity):
    """Representation of a Homematic IP light."""

    PLATFORM = Platform.LIGHT
    _attr_translation_key = "hcu_light"
    
    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        **kwargs,
    ):
        """Initialize the light entity."""
        super().__init__(coordinator, client, device_data, channel_index)

        self._set_entity_name(channel_label=self._channel.get("label"))
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_light"

        # Determine supported color modes based on channel capabilities
        supported_modes = set()

        # Check for RGB color support (BSL backlight uses simpleRGBColorState)
        self._has_simple_rgb = "simpleRGBColorState" in self._channel
        has_dim_level = "dimLevel" in self._channel

        # Check for color modes first (HS color takes precedence over simple brightness)
        if self._channel.get("hue") is not None or self._has_simple_rgb:
            # HS color mode implicitly includes brightness control
            supported_modes.add(ColorMode.HS)
        elif "colorTemperature" in self._channel:
            # Color temperature mode implicitly includes brightness control
            supported_modes.add(ColorMode.COLOR_TEMP)
            self._attr_min_color_temp_kelvin = self._channel.get("minimalColorTemperature", 2000)
            self._attr_max_color_temp_kelvin = self._channel.get("maximumColorTemperature", 6500)
        elif has_dim_level:
            # Only use BRIGHTNESS mode if no color mode is supported
            supported_modes.add(ColorMode.BRIGHTNESS)
        else:
            # Simple on/off light with no dimming or color
            supported_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = supported_modes

        # Add transition support for all dimmable modes (HS, COLOR_TEMP, BRIGHTNESS)
        if has_dim_level:
            self._attr_supported_features |= LightEntityFeature.TRANSITION

        # Check for optical signal behavior support (HmIP-BSL and similar devices)
        optional_features = self._channel.get("supportedOptionalFeatures", {})
        self._supports_optical_signal = optional_features.get("IFeatureOpticalSignalBehaviourState", False)
        if self._supports_optical_signal:
            self._attr_supported_features |= LightEntityFeature.EFFECT
            self._attr_effect_list = list(HMIP_OPTICAL_SIGNAL_BEHAVIOURS)

    @property
    def color_mode(self) -> ColorMode | str | None:
        """Return the current active color mode."""
        if ColorMode.HS in self.supported_color_modes:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in self.supported_color_modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in self.supported_color_modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        # For BSL-like devices, opticalSignalBehaviour being OFF means the light is off,
        # regardless of dimLevel.
        if self._supports_optical_signal:
            if self._channel.get("opticalSignalBehaviour") == "OFF":
                return False

        dim_level = self._channel.get("dimLevel")
        if dim_level is not None:
            return dim_level > 0.0
        return self._channel.get("on", False)

    @property
    def brightness(self) -> int | None:
        """Return the brightness (0-255)."""
        dim_level = self._channel.get("dimLevel")
        return int(dim_level * 255) if dim_level is not None else None

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        return self._channel.get("colorTemperature")

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation."""
        # For devices with simpleRGBColorState (e.g., BSL backlight)
        if self._has_simple_rgb:
            rgb_state = self._channel.get("simpleRGBColorState")
            if rgb_state and rgb_state in HMIP_RGB_COLOR_MAP:
                return HMIP_RGB_COLOR_MAP[rgb_state]
            return None

        # For devices with hue/saturation (e.g., RGBW lights)
        hue = self._channel.get("hue")
        saturation = self._channel.get("saturationLevel")
        if hue is None or saturation is None:
            return None
        return (float(hue), float(saturation) * 100)

    @property
    def effect(self) -> str | None:
        """Return the current optical signal behavior effect."""
        if self._supports_optical_signal:
            effect = self._channel.get("opticalSignalBehaviour")
            if isinstance(effect, str):
                return effect.lower()
        return None

    def _hs_to_simple_rgb(self, hs_color: tuple[float, float]) -> str:
        """Convert HA HS color to the closest Homematic IP simple RGB color name.

        Delegates to the module-level _convert_hs_to_simple_rgb() helper function.
        """
        return _convert_hs_to_simple_rgb(hs_color)

    async def async_turn_on_with_time(self, on_time: float) -> None:
        """Turn the light on for a specific duration using the configured internal on-time."""
        self._attr_assumed_state = True
        self.async_write_ha_state()
        try:
            current_brightness = self.brightness if self.is_on else None
            dim_level = (current_brightness or 255) / 255.0
            await self._client.async_set_dim_level(
                self._device_id, self._channel_index, dim_level, on_time=on_time
            )
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to turn on %s with time: %s", self.name, err)
            self._attr_assumed_state = False
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on with optional color, temperature, brightness, or effect adjustments."""
        if not kwargs and (on_time := self._get_internal_on_time()):
            await self.async_turn_on_with_time(on_time)
            return

        # Default to current brightness if the light is on, otherwise 100%.
        current_brightness = self.brightness if self.is_on else None
        target_brightness = kwargs.get(ATTR_BRIGHTNESS, current_brightness or 255)
        dim_level = target_brightness / 255.0

        ramp_time = kwargs.get(ATTR_TRANSITION)

        # Handle Simple RGB devices (e.g., HmIP-BSL)
        if self._has_simple_rgb and self._supports_optical_signal:
            # 1. Determine Color
            rgb_color = self._channel.get("simpleRGBColorState")
            if ATTR_HS_COLOR in kwargs:
                rgb_color = self._hs_to_simple_rgb(kwargs[ATTR_HS_COLOR])
            
            # Fallback for color if missing or black (default to white)
            if not rgb_color or rgb_color == HMIP_COLOR_BLACK:
                rgb_color = HMIP_COLOR_WHITE

            # 2. Determine Optical Signal Behaviour (The "ON" switch for BSL LEDs/Effects)
            optical_signal = None
            if ATTR_EFFECT in kwargs:
                # If an effect is specified in the service call, use it directly.
                optical_signal = kwargs[ATTR_EFFECT].upper()
            else:
                # If no effect is specified, turn the light on if it's off, or preserve its current non-OFF state.
                current_signal = self._channel.get("opticalSignalBehaviour")
                if current_signal == "OFF" or current_signal is None:
                    optical_signal = "ON"
                else:
                    # Preserve existing non-OFF behavior (e.g., if blinking, keep blinking)
                    optical_signal = current_signal

            # 3. Build Payload for consolidated call
            payload = {
                "simpleRGBColorState": rgb_color,
                "dimLevel": dim_level
            }
            
            if optical_signal:
                payload["opticalSignalBehaviour"] = optical_signal
                base_path_key = "SET_OPTICAL_SIGNAL_BEHAVIOUR"
                time_path_key = "SET_OPTICAL_SIGNAL_BEHAVIOUR_WITH_TIME"
            else:
                base_path_key = "SET_SIMPLE_RGB_COLOR_STATE"
                time_path_key = "SET_SIMPLE_RGB_COLOR_STATE_WITH_TIME"
            # 4. Determine Path (With or Without Time)
            if ramp_time is not None:
                path = API_PATHS[time_path_key]
                payload["rampTime"] = ramp_time
            else:
                path = API_PATHS[base_path_key]
            
             # Set optimistic state for immediate feedback
            self._attr_assumed_state = True
            self.async_write_ha_state()

            await self._client.async_device_control(
                path,
                self._device_id,
                self._channel_index,
                payload
            )
            return

        # Handle Standard RGB/Dimmer Devices
        if ATTR_HS_COLOR in kwargs and ColorMode.HS in self.supported_color_modes:
            hue = int(kwargs[ATTR_HS_COLOR][0])
            saturation = kwargs[ATTR_HS_COLOR][1] / 100.0
            await self._client.async_set_hue_saturation(
                self._device_id, self._channel_index, hue, saturation, dim_level, ramp_time
            )
        elif ATTR_COLOR_TEMP_KELVIN in kwargs and ColorMode.COLOR_TEMP in self.supported_color_modes:
            color_temp = kwargs[ATTR_COLOR_TEMP_KELVIN]
            await self._client.async_set_color_temperature(
                self._device_id, self._channel_index, color_temp, dim_level, ramp_time
            )
        else:
            # Simple Dimmer or Switch
            await self._client.async_set_dim_level(
                self._device_id, self._channel_index, dim_level, ramp_time
            )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        ramp_time = kwargs.get(ATTR_TRANSITION)
        
        if self._has_simple_rgb and self._supports_optical_signal:
            payload = {
                # Preserve color state, set dim to 0, and set signal to OFF
                "simpleRGBColorState": self._channel.get("simpleRGBColorState", HMIP_COLOR_BLACK),
                "dimLevel": 0.0,
                "opticalSignalBehaviour": "OFF"
            }

            if self._supports_optical_signal:
                base_path_key = "SET_OPTICAL_SIGNAL_BEHAVIOUR"
                time_path_key = "SET_OPTICAL_SIGNAL_BEHAVIOUR_WITH_TIME"
            else:
                base_path_key = "SET_SIMPLE_RGB_COLOR_STATE"
                time_path_key = "SET_SIMPLE_RGB_COLOR_STATE_WITH_TIME"
            
            if ramp_time is not None:
                path = API_PATHS[time_path_key]
                payload["rampTime"] = ramp_time
            else:
                path = API_PATHS[base_path_key]

            # Set optimistic state for immediate feedback
            self._attr_assumed_state = True
            self.async_write_ha_state()

            await self._client.async_device_control(
                path,
                self._device_id,
                self._channel_index,
                payload
            )
        else:
            await self._client.async_set_dim_level(self._device_id, self._channel_index, 0.0, ramp_time)

class HcuSwitchLight(HcuSwitch, LightEntity):
    """Switch channel registered as a Light entity in Home Assistant."""
    PLATFORM = Platform.LIGHT

    def __init__(self, coordinator, client, device_data, channel_index):
        super().__init__(coordinator, client, device_data, channel_index)
        # Clear any switch-specific device class set by HcuSwitch.__init__
        self._attr_device_class = None
        # Only on/off supported – no dimming or color
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_supported_color_modes = {ColorMode.ONOFF}

class HcuNotificationLight(HcuBaseEntity, LightEntity):
    """Representation of a Homematic IP notification light (e.g., HmIP-MP3P)."""

    PLATFORM = Platform.LIGHT
    _attr_supported_color_modes = {ColorMode.HS}
    _attr_color_mode = ColorMode.HS

    # RGB color mappings for Homematic IP notification devices
    # Based on official HCU API - only 8 colors supported:
    # BLACK, BLUE, GREEN, TURQUOISE, RED, PURPLE, YELLOW, WHITE
    _COLOR_MAP = {
        HMIP_COLOR_BLACK: (0, 0, 0),
        HMIP_COLOR_BLUE: (240, 100, 50),
        HMIP_COLOR_GREEN: (120, 100, 50),
        HMIP_COLOR_TURQUOISE: (180, 100, 50),
        HMIP_COLOR_RED: (0, 100, 50),
        HMIP_COLOR_PURPLE: (300, 100, 50),
        HMIP_COLOR_YELLOW: (60, 100, 50),
        HMIP_COLOR_WHITE: (0, 0, 100),
        # NOTE: ORANGE removed - not supported by HCU API
    }

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        **kwargs,
    ):
        """Initialize the notification light entity."""
        super().__init__(coordinator, client, device_data, channel_index)
        self._set_entity_name(channel_label=self._channel.get("label"))
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_light"

    @property
    def is_on(self) -> bool:
        """Return True if the light is on."""
        dim_level = self._channel.get("dimLevel")
        if dim_level is not None:
            return dim_level > 0.0
        return self._channel.get("on", False)

    @property
    def brightness(self) -> int | None:
        """Return the brightness (0-255)."""
        dim_level = self._channel.get("dimLevel")
        return int(dim_level * 255) if dim_level is not None else None

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation based on the current RGB color state."""
        rgb_state = self._channel.get("simpleRGBColorState")
        if rgb_state and rgb_state in HMIP_RGB_COLOR_MAP:
            return HMIP_RGB_COLOR_MAP[rgb_state]
        return None
            

        if rgb_state in self._COLOR_MAP:
            h, s, _ = self._COLOR_MAP[rgb_state]
            return (float(h), float(s))

        return None

    def _hs_to_simple_rgb(self, hs_color: tuple[float, float]) -> str:
        """Convert HS color to the closest Homematic IP simple RGB color.

        Delegates to the module-level _convert_hs_to_simple_rgb() helper function.
        """
        return _convert_hs_to_simple_rgb(hs_color)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the notification light on."""
        
        # Default to current brightness if the light is on, otherwise 100%.
        current_brightness = self.brightness if self.is_on else None

        if ATTR_BRIGHTNESS in kwargs:
            target_brightness = kwargs[ATTR_BRIGHTNESS]
        elif current_brightness is not None:
            target_brightness = current_brightness
        else:
            target_brightness = 255  # 100%
        
        # Clamp + compute dim level
        target_brightness = max(0, min(255, int(target_brightness)))
        dim_level = target_brightness / 255.0

        # 1. Determine Color
        rgb_color = self._channel.get("simpleRGBColorState")
        if ATTR_HS_COLOR in kwargs:
            rgb_color = self._hs_to_simple_rgb(kwargs[ATTR_HS_COLOR])
            
        # Fallback for color if missing or black (default to white)
        if not rgb_color or rgb_color == HMIP_COLOR_BLACK:
            rgb_color = HMIP_COLOR_WHITE
        
        payload = {
            "simpleRGBColorState": rgb_color,
            "dimLevel": dim_level
        }
        await self._client.async_device_control(
            API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
            self._device_id,
            self._channel_index,
            payload
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the notification light off."""
        await self._client.async_device_control(
            API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
            self._device_id,
            self._channel_index,
            {"simpleRGBColorState": HMIP_COLOR_BLACK}
        )

    async def async_play_sound(
        self, sound_file: str, volume: float, duration: float
    ) -> None:
        """Play a sound on this notification device (service call handler)."""
        await self._client.async_set_sound_file(
            device_id=self._device_id,
            channel_index=self._channel_index,
            sound_file=sound_file,
            volume=volume,
            duration=duration,
        )

class HcuLightGroup(HcuSwitchingGroupBase, LightEntity):
    """Representation of a Homematic IP HCU light group."""

    PLATFORM = Platform.LIGHT

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the HCU light group."""
        super().__init__(coordinator, client, group_data)

        # Light groups typically only support on/off for the group
        # (even if they contain dimmers, the group control is usually simple)
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
