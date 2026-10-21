"""Turn on with the internal on time reports HCU failures like any other turn on."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.light import HcuLight
from custom_components.hcu_integration.switch import HcuSwitch

from .test_valve_coverage import _create_valve


@pytest.mark.parametrize("error", [HcuApiError("rejected"), ConnectionError("down")])
async def test_switch_turn_on_with_internal_on_time_raises(
    mock_coordinator, mock_hcu_client, error: Exception
) -> None:
    device = {
        "id": "dev_sw",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    mock_hcu_client.async_set_switch_state.side_effect = error
    switch = HcuSwitch(mock_coordinator, mock_hcu_client, device, "1")
    switch.entity_id = "switch.dev_sw"
    switch.async_write_ha_state = MagicMock()

    with (
        patch.object(switch, "_get_internal_on_time", return_value=30.0),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await switch.async_turn_on()

    assert exc_info.value.translation_key == "command_failed"
    assert switch.is_on is False


@pytest.mark.parametrize("error", [HcuApiError("rejected"), ConnectionError("down")])
async def test_light_turn_on_with_internal_on_time_raises(
    mock_coordinator, mock_hcu_client, error: Exception
) -> None:
    device = {
        "id": "dev_dimmer",
        "functionalChannels": {
            "1": {"functionalChannelType": "DIMMER_CHANNEL", "dimLevel": 0.0}
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device
    mock_hcu_client.async_set_dim_level.side_effect = error
    light = HcuLight(mock_coordinator, mock_hcu_client, device, "1")
    light.entity_id = "light.dev_dimmer"
    light.async_write_ha_state = MagicMock()

    with (
        patch.object(light, "_get_internal_on_time", return_value=30.0),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await light.async_turn_on()

    assert exc_info.value.translation_key == "command_failed"
    assert light.assumed_state is False


@pytest.mark.parametrize("error", [HcuApiError("rejected"), ConnectionError("down")])
async def test_valve_open_with_internal_on_time_raises(
    hass: HomeAssistant, error: Exception
) -> None:
    valve, _, client = _create_valve(hass)
    valve.entity_id = "valve.garden"
    valve.async_write_ha_state = MagicMock()
    client.async_set_watering_switch_state.side_effect = error

    with (
        patch.object(valve, "_get_internal_on_time", return_value=30.0),
        pytest.raises(HomeAssistantError) as exc_info,
    ):
        await valve.async_open_valve()

    assert exc_info.value.translation_key == "command_failed"
    assert valve.is_closed is True
