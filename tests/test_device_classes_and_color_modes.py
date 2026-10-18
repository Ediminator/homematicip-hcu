"""Device classes and light color modes derived from HCU device data."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.light import ColorMode
from homeassistant.components.switch import SwitchDeviceClass
import pytest

from custom_components.hcu_integration.cover import HcuCover
from custom_components.hcu_integration.light import HcuLight
from custom_components.hcu_integration.switch import HcuSwitch

DEVICE_ID = "3014F711A0000000000000AA"


def _device(device_type: str, channel: dict) -> dict:
    return {
        "id": DEVICE_ID,
        "label": "Test device",
        "type": device_type,
        "modelType": "HmIP-TEST",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"label": "Channel", **channel},
        },
    }


@pytest.mark.parametrize(
    ("channel", "expected"),
    [
        ({"dimLevel": 0.5, "hue": 120, "saturationLevel": 1.0}, ColorMode.HS),
        ({"dimLevel": 0.5, "colorTemperature": 3000}, ColorMode.COLOR_TEMP),
        ({"dimLevel": 0.5}, ColorMode.BRIGHTNESS),
        ({"on": True}, ColorMode.ONOFF),
    ],
)
def test_light_color_mode_follows_supported_modes(
    mock_coordinator: MagicMock,
    mock_hcu_client: MagicMock,
    channel: dict,
    expected: ColorMode,
) -> None:
    device = _device(
        "BRAND_DIMMER", {"functionalChannelType": "DIMMER_CHANNEL", **channel}
    )
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device)

    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")

    assert light.supported_color_modes == {expected}
    assert light.color_mode == expected


@pytest.mark.parametrize(
    ("device_type", "expected"),
    [
        ("PLUGABLE_SWITCH", SwitchDeviceClass.OUTLET),
        ("FULL_FLUSH_SWITCH_16", SwitchDeviceClass.SWITCH),
        ("BRAND_DIMMER", None),
        # A cover device class from the shared map is never used for a switch.
        ("BLIND_ACTUATOR", None),
    ],
)
def test_switch_device_class(
    mock_coordinator: MagicMock,
    mock_hcu_client: MagicMock,
    device_type: str,
    expected: SwitchDeviceClass | None,
) -> None:
    device = _device(
        device_type, {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
    )
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device)

    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")

    assert switch.device_class == expected


@pytest.mark.parametrize(
    ("device_type", "expected"),
    [
        ("SHUTTER_ACTUATOR", CoverDeviceClass.SHUTTER),
        ("GARAGE_DOOR_MODULE", CoverDeviceClass.GARAGE),
        # A switch device class from the shared map is never used for a cover.
        ("PLUGABLE_SWITCH", None),
    ],
)
def test_cover_device_class(
    mock_coordinator: MagicMock,
    mock_hcu_client: MagicMock,
    device_type: str,
    expected: CoverDeviceClass | None,
) -> None:
    device = _device(
        device_type,
        {"functionalChannelType": "SHUTTER_CHANNEL", "shutterLevel": 0.0},
    )
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device)

    cover = HcuCover(mock_coordinator, mock_hcu_client, device, "1")

    assert cover.device_class == expected
