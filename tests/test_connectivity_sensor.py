"""State-machine tests for the battery device connectivity binary sensor."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.coordinator import HcuCoordinator

from .test_dynamic_devices import _make_client

SLEEP = "custom_components.hcu_integration.coordinator.asyncio.sleep"
BATTERY_DEVICE_ID = "3014F711A0000000000000CD"


def _device_changed_event(device_id: str, unreach: bool) -> dict:
    """Build an HMIP_SYSTEM_EVENT DEVICE_CHANGED payload updating channel 0 unreach."""
    return {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {
                    "0": {
                        "pushEventType": "DEVICE_CHANGED",
                        "device": {
                            "id": device_id,
                            "functionalChannels": {
                                "0": {
                                    "functionalChannelType": "DEVICE_BASE",
                                    "unreach": unreach,
                                }
                            },
                        },
                    }
                }
            }
        },
    }


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_connectivity_sensor_state_follows_unreach(
    hass: HomeAssistant,
) -> None:
    """Battery device connectivity stays available as off when unreachable, unavailable on drop."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        options={},
        unique_id="hcu-test-1",
    )
    entry.add_to_hass(hass)

    client = _make_client()
    client._state["devices"][BATTERY_DEVICE_ID] = {
        "id": BATTERY_DEVICE_ID,
        "type": "SMOKE_DETECTOR",
        "modelType": "HmIP-SWSD-2",
        "label": "Hallway Smoke Detector",
        "oem": "eQ-3",
        "permanentlyReachable": False,
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "index": 0,
                "unreach": False,
                "lowBat": False,
                "supportedOptionalFeatures": {"IOptionalFeatureLowBat": True},
            },
        },
    }

    with (
        patch("custom_components.hcu_integration.HcuApiClient", return_value=client),
        patch(
            "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator: HcuCoordinator = entry.runtime_data
    coordinator._initial_state_loaded = True

    ent_reg = er.async_get(hass)
    connectivity_entity_id = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BATTERY_DEVICE_ID}_0_unreach"
    )
    low_bat_entity_id = ent_reg.async_get_entity_id(
        "binary_sensor", DOMAIN, f"{BATTERY_DEVICE_ID}_0_lowBat"
    )
    assert connectivity_entity_id is not None
    assert low_bat_entity_id is not None

    connectivity_state = hass.states.get(connectivity_entity_id)
    low_bat_state = hass.states.get(low_bat_entity_id)
    assert connectivity_state is not None
    assert low_bat_state is not None
    assert connectivity_state.state == STATE_ON
    assert low_bat_state.state == STATE_OFF

    # Device becomes unreachable: connectivity shows off, other entities go unavailable.
    coordinator._handle_event_message(_device_changed_event(BATTERY_DEVICE_ID, True))
    await hass.async_block_till_done()

    connectivity_state = hass.states.get(connectivity_entity_id)
    low_bat_state = hass.states.get(low_bat_entity_id)
    assert connectivity_state is not None
    assert low_bat_state is not None
    assert connectivity_state.state == STATE_OFF
    assert low_bat_state.state == STATE_UNAVAILABLE

    # Device becomes reachable again.
    coordinator._handle_event_message(_device_changed_event(BATTERY_DEVICE_ID, False))
    await hass.async_block_till_done()

    connectivity_state = hass.states.get(connectivity_entity_id)
    low_bat_state = hass.states.get(low_bat_entity_id)
    assert connectivity_state is not None
    assert low_bat_state is not None
    assert connectivity_state.state == STATE_ON
    assert low_bat_state.state == STATE_OFF

    # HCU connection drops: connectivity goes unavailable.
    client.is_connected = False
    client.connect = AsyncMock()
    client.listen = AsyncMock(side_effect=ConnectionError("HCU went away"))
    with (
        patch(SLEEP, AsyncMock(side_effect=asyncio.CancelledError)),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._listen_for_events()
    await hass.async_block_till_done()

    connectivity_state = hass.states.get(connectivity_entity_id)
    assert connectivity_state is not None
    assert connectivity_state.state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(entry.entry_id)
