"""Coverage tests for HCU siren platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.siren import SirenEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import CHANNEL_TYPE_ALARM_SIREN
from custom_components.hcu_integration.siren import HcuSiren, async_setup_entry


def _create_siren(
    hass: HomeAssistant,
    *,
    device_id: str = "siren-dev-1",
    channel_index: str = "1",
    groups: dict | None = None,
    channel_data: dict | None = None,
    device_channels: dict | None = None,
    device_overrides: dict | None = None,
) -> tuple[HcuSiren, MagicMock, MagicMock]:
    """Create an HcuSiren test entity with mocks."""
    ch_data = {
        "functionalChannelType": CHANNEL_TYPE_ALARM_SIREN,
        "label": "Indoor Siren",
    }
    if channel_data:
        ch_data.update(channel_data)

    func_channels = {
        "0": {"functionalChannelType": "DEVICE_BASE"},
        channel_index: ch_data,
    }
    if device_channels:
        func_channels.update(device_channels)

    device = {
        "id": device_id,
        "label": "Alarm Siren",
        "type": "ALARM_SIREN_INDOOR",
        "permanentlyReachable": True,
        "functionalChannels": func_channels,
    }
    if device_overrides:
        device.update(device_overrides)

    client = MagicMock()
    client.is_connected = True
    client.state = {
        "devices": {device_id: device},
        "groups": groups or {},
    }
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_set_alarm_switching_group_state = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {device_id: device}
    coordinator.client = client
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}

    siren = HcuSiren(coordinator, client, device, channel_index)
    siren.hass = hass
    return siren, coordinator, client


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test platform setup with and without siren entities."""
    entry = MagicMock()
    coordinator = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    # Case 1: No siren entities
    coordinator.entities = {}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

    # Case 2: Siren entities present
    siren_entity = MagicMock()
    coordinator.entities = {Platform.SIREN: [siren_entity]}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([siren_entity])


def test_siren_naming_and_features(hass: HomeAssistant) -> None:
    """Test naming fallback and supported features."""
    device_channels = {
        "1": {"functionalChannelType": CHANNEL_TYPE_ALARM_SIREN, "label": None},
        "2": {"functionalChannelType": CHANNEL_TYPE_ALARM_SIREN, "label": None},
    }
    siren, _, _ = _create_siren(
        hass,
        channel_index="1",
        channel_data={"label": None},
        device_channels=device_channels,
    )
    assert siren.unique_id == "siren-dev-1_1_siren"
    assert (
        siren.supported_features
        == SirenEntityFeature.TURN_ON | SirenEntityFeature.TURN_OFF
    )


def test_find_alarm_switching_group_selection(hass: HomeAssistant) -> None:
    """Test group discovery: single disabled group, multiple groups with/without audio."""
    device_id = "siren-dev-1"

    # Single group with audio disabled
    groups_single_silent = {
        "grp-silent": {
            "id": "grp-silent",
            "type": "ALARM_SWITCHING",
            "label": "Silent Group",
            "acousticFeedbackEnabled": False,
            "on": False,
            "channels": [{"deviceId": device_id, "channelIndex": 1}],
        }
    }
    siren1, _, _ = _create_siren(hass, groups=groups_single_silent)
    assert siren1._alarm_group_id == "grp-silent"

    # Multiple groups: one audio-enabled, one silent -> prefers audio-enabled
    groups_mixed = {
        "grp-silent": {
            "id": "grp-silent",
            "type": "ALARM_SWITCHING",
            "label": "Silent Group",
            "acousticFeedbackEnabled": False,
            "channels": [{"deviceId": device_id, "channelIndex": 1}],
        },
        "grp-audio": {
            "id": "grp-audio",
            "type": "ALARM_SWITCHING",
            "label": "Audio Group",
            "acousticFeedbackEnabled": True,
            "channels": [{"deviceId": device_id, "channelIndex": 1}],
        },
    }
    siren2, _, _ = _create_siren(hass, groups=groups_mixed)
    assert siren2._alarm_group_id == "grp-audio"

    # Multiple groups: all silent -> selects first alphabetically by ID
    groups_all_silent = {
        "grp-b": {
            "id": "grp-b",
            "type": "ALARM_SWITCHING",
            "label": "B",
            "acousticFeedbackEnabled": False,
            "channels": [{"deviceId": device_id, "channelIndex": 1}],
        },
        "grp-a": {
            "id": "grp-a",
            "type": "ALARM_SWITCHING",
            "label": "A",
            "acousticFeedbackEnabled": False,
            "channels": [{"deviceId": device_id, "channelIndex": 1}],
        },
    }
    siren3, _, _ = _create_siren(hass, groups=groups_all_silent)
    assert siren3._alarm_group_id == "grp-a"


def test_siren_availability_diagnostics(hass: HomeAssistant) -> None:
    """Test available property diagnostics for various unavailability states."""
    siren, _, client = _create_siren(
        hass,
        channel_data={"functionalChannelType": "WRONG_CHANNEL_TYPE"},
    )
    # Available when connected and device exists
    assert siren.available is True

    # 1. Client disconnected
    client.is_connected = False
    assert siren.available is False

    # 2. Device missing from state
    client.is_connected = True
    client.get_device_by_address.return_value = None
    client.state["devices"] = {}
    assert siren.available is False

    # 3. Device unreachable (battery powered sleeping / unreach)
    unreachable_device = {
        "id": "siren-dev-1",
        "permanentlyReachable": False,
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "unreach": True}
        },
    }
    client.get_device_by_address.return_value = unreachable_device
    client.state["devices"] = {"siren-dev-1": unreachable_device}
    assert siren.available is False


def test_siren_coordinator_update(hass: HomeAssistant) -> None:
    """Test coordinator update syncing group on state."""
    groups = {
        "grp-1": {
            "id": "grp-1",
            "type": "ALARM_SWITCHING",
            "on": False,
            "channels": [{"deviceId": "siren-dev-1", "channelIndex": 1}],
        }
    }
    siren, _, _client = _create_siren(hass, groups=groups)
    siren.async_write_ha_state = MagicMock()
    assert siren.is_on is False

    # Update group state to on
    groups["grp-1"]["on"] = True
    siren._handle_coordinator_update()
    assert siren.is_on is True

    # When assumed_state is True, does not overwrite
    siren._attr_assumed_state = True
    groups["grp-1"]["on"] = False
    siren._handle_coordinator_update()
    assert siren.is_on is True


async def test_siren_actions_and_error_handling(hass: HomeAssistant) -> None:
    """Test async_turn_on, async_turn_off and error rollbacks."""
    groups = {
        "grp-1": {
            "id": "grp-1",
            "type": "ALARM_SWITCHING",
            "on": False,
            "channels": [{"deviceId": "siren-dev-1", "channelIndex": 1}],
        }
    }
    siren, _, client = _create_siren(hass, groups=groups)
    siren.async_write_ha_state = MagicMock()

    # Turn on
    await siren.async_turn_on()
    client.async_set_alarm_switching_group_state.assert_awaited_with(
        group_id="grp-1", on=True
    )
    assert siren.is_on is True
    assert siren.assumed_state is False

    # Turn off
    await siren.async_turn_off()
    client.async_set_alarm_switching_group_state.assert_awaited_with(
        group_id="grp-1", on=False
    )
    assert siren.is_on is False
    assert siren.assumed_state is False

    # Turn on with ConnectionError -> reverts state
    client.async_set_alarm_switching_group_state.side_effect = ConnectionError(
        "Network down"
    )
    with pytest.raises(ConnectionError):
        await siren.async_turn_on()
    assert siren.is_on is False
    assert siren.assumed_state is False

    # Turn off with HcuApiError -> reverts state
    siren._attr_is_on = True
    client.async_set_alarm_switching_group_state.side_effect = HcuApiError(
        "Command rejected"
    )
    with pytest.raises(HcuApiError):
        await siren.async_turn_off()
    assert siren.is_on is True
    assert siren.assumed_state is False

    # Turn off when no group configured raises HcuApiError
    siren_no_group, _, _ = _create_siren(hass, groups={})
    with pytest.raises(HcuApiError):
        await siren_no_group.async_turn_off()
