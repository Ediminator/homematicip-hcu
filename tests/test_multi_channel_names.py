"""Names of entities on devices with several unlabeled channels.

Home Assistant uses `_attr_name` whenever it is set, even to None, and then
ignores the translation key. Unlabeled channels of multi-channel devices must
still be told apart ("<device> Switch 2"), while single-channel devices keep
the plain device name.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, ProcessEventsResult
from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.event import HcuButtonEvent

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")


def _base_channel() -> dict:
    return {"functionalChannelType": "DEVICE_BASE", "index": 0}


def _device(device_id: str, device_type: str, label: str, channels: dict) -> dict:
    return {
        "id": device_id,
        "type": device_type,
        "modelType": device_type,
        "label": label,
        "oem": "eQ-3",
        "firmwareVersion": "1.0.0",
        "functionalChannels": {"0": _base_channel(), **channels},
    }


# Channels assigned to a room, as they are once set up in the Homematic IP app.
ROOM = ["room-1"]


def _switch_channel(index: int) -> dict:
    return {
        "functionalChannelType": "SWITCH_CHANNEL",
        "index": index,
        "groups": ROOM,
        "on": False,
    }


def _dimmer_channel(index: int) -> dict:
    return {
        "functionalChannelType": "DIMMER_CHANNEL",
        "index": index,
        "groups": ROOM,
        "dimLevel": 0.0,
    }


def _blind_channel(index: int) -> dict:
    return {
        "functionalChannelType": "SHUTTER_CHANNEL",
        "index": index,
        "groups": ROOM,
        "shutterLevel": 0.0,
    }


DEVICES = {
    "dev-switch-2": _device(
        "dev-switch-2",
        "PRINTED_CIRCUIT_BOARD_SWITCH_2",
        "Garden Actuator",
        {"1": _switch_channel(1), "2": _switch_channel(2)},
    ),
    "dev-switch-1": _device(
        "dev-switch-1", "PLUGABLE_SWITCH", "Coffee Plug", {"1": _switch_channel(1)}
    ),
    "dev-dimmer-2": _device(
        "dev-dimmer-2",
        "DIN_RAIL_DIMMER_3",
        "Hall Dimmer",
        {"1": _dimmer_channel(1), "2": _dimmer_channel(2)},
    ),
    "dev-blind-2": _device(
        "dev-blind-2",
        "DIN_RAIL_BLIND_4",
        "Bedroom Blinds",
        {"1": _blind_channel(1), "2": _blind_channel(2)},
    ),
}


def _make_client() -> MagicMock:
    client = MagicMock(spec=HcuApiClient)
    client.state = {"home": {"id": "home-1"}, "devices": DEVICES, "groups": {}}
    client.hcu_device_id = "hcu-1"
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.plugin_id = "de.homeassistant.hcu.integration"
    client.get_device_by_address = MagicMock(side_effect=DEVICES.get)
    client.get_group_by_id = MagicMock(return_value=None)
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    return client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def client() -> Generator[MagicMock]:
    mock_client = _make_client()
    with patch(
        "custom_components.hcu_integration.HcuApiClient", return_value=mock_client
    ):
        yield mock_client


async def _friendly_names(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> dict[str, str]:
    """Set up the entry and return unique_id -> friendly name."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    names = {}
    for entry in er.async_entries_for_config_entry(registry, config_entry.entry_id):
        state = hass.states.get(entry.entity_id)
        if state is not None:
            names[entry.unique_id] = state.attributes["friendly_name"]
    return names


@pytest.mark.parametrize(
    ("language", "switch", "light", "cover"),
    [("en", "Switch", "Light", "Cover"), ("de", "Schalter", "Licht", "Rollladen")],
)
async def test_unlabeled_channels_are_numbered(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
    language: str,
    switch: str,
    light: str,
    cover: str,
) -> None:
    hass.config.language = language

    names = await _friendly_names(hass, config_entry)

    assert names["dev-switch-2_1_on"] == f"Garden Actuator {switch} 1"
    assert names["dev-switch-2_2_on"] == f"Garden Actuator {switch} 2"
    assert names["dev-dimmer-2_1_light"] == f"Hall Dimmer {light} 1"
    assert names["dev-dimmer-2_2_light"] == f"Hall Dimmer {light} 2"
    assert names["dev-blind-2_1_cover"] == f"Bedroom Blinds {cover} 1"
    assert names["dev-blind-2_2_cover"] == f"Bedroom Blinds {cover} 2"


async def test_single_channel_device_keeps_device_name(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    names = await _friendly_names(hass, config_entry)

    assert names["dev-switch-1_1_on"] == "Coffee Plug"


async def test_labeled_channel_uses_its_label(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    DEVICES["dev-switch-2"]["functionalChannels"]["2"]["label"] = "Pond Pump"
    try:
        names = await _friendly_names(hass, config_entry)
    finally:
        del DEVICES["dev-switch-2"]["functionalChannels"]["2"]["label"]

    assert names["dev-switch-2_1_on"] == "Garden Actuator Switch 1"
    assert names["dev-switch-2_2_on"] == "Garden Actuator Pond Pump"


@pytest.mark.parametrize(("key_count", "expected"), [(2, " 4"), (1, "")])
def test_button_event_name_uses_visible_channel_index(
    mock_coordinator: MagicMock,
    mock_hcu_client: MagicMock,
    key_count: int,
    expected: str,
) -> None:
    channels = {
        str(i): {"functionalChannelType": "KEY_CHANNEL", "visibleChannelIndex": i + 2}
        for i in range(1, key_count + 1)
    }
    device = _device("dev-remote", "REMOTE_CONTROL_8", "Remote", channels)
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device)

    entity = HcuButtonEvent(
        mock_coordinator, mock_hcu_client, device, "2" if key_count == 2 else "1"
    )

    assert entity.translation_key == "hcu_button_event"
    assert entity.translation_placeholders == {"channel_index": expected}
    # With several keys the translated "Button <n>" applies; a single key
    # keeps the device name.
    assert hasattr(entity, "_attr_name") is (key_count == 1)
