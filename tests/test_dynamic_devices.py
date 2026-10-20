"""Test dynamic device and group additions without integration reload."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient
from custom_components.hcu_integration.const import (
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

HCU_ID = "hcu-test-1"


def _make_client() -> HcuApiClient:
    client = MagicMock(spec=HcuApiClient)
    client._state = {
        "home": {"id": "home-1"},
        "devices": {
            HCU_ID: {
                "id": HCU_ID,
                "label": "Homematic IP HCU",
                "modelType": "HCU",
                "oem": "eQ-3",
                "firmwareVersion": "1.0.0",
                "functionalChannels": {"0": {"functionalChannelType": "DEVICE_BASE"}},
            }
        },
        "groups": {},
    }
    type(client).state = property(lambda self: self._state)
    client.hcu_device_id = HCU_ID
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.plugin_id = "de.homeassistant.hcu.integration"
    client._auth_type = "plugin"
    client.get_device_by_address = MagicMock(
        side_effect=lambda did: client._state["devices"].get(did)
    )
    client.get_group_by_id = MagicMock(
        side_effect=lambda gid: client._state["groups"].get(gid)
    )
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    client.process_events = lambda events: HcuApiClient.process_events(client, events)
    return client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        options={
            CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: True,
            CONF_DISABLE_UNCONFIGURED_CHANNELS: False,
        },
        unique_id=HCU_ID,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def client() -> Generator[HcuApiClient]:
    mock_client = _make_client()
    with patch(
        "custom_components.hcu_integration.HcuApiClient", return_value=mock_client
    ):
        yield mock_client


async def test_new_device_added_dynamically_without_reload(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: HcuApiClient
) -> None:
    """Test that a new device pushed via DEVICE_CHANGED gets entities without reloading."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True
    assert coordinator is not None

    with (
        patch.object(
            hass.config_entries, "async_reload", AsyncMock()
        ) as mock_async_reload,
        patch.object(
            hass.config_entries, "async_schedule_reload", MagicMock()
        ) as mock_schedule_reload,
    ):
        new_device_payload = {
            "id": "new-switch-1",
            "type": "PLUGABLE_SWITCH",
            "modelType": "HMIP-PS",
            "label": "New Living Room Plug",
            "oem": "eQ-3",
            "firmwareVersion": "1.2.0",
            "functionalChannels": {
                "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
                "1": {
                    "functionalChannelType": "SWITCH_CHANNEL",
                    "index": 1,
                    "groups": ["room-1"],
                    "on": False,
                },
            },
        }

        event_message = {
            "type": "HMIP_SYSTEM_EVENT",
            "body": {
                "eventTransaction": {
                    "events": {
                        "0": {
                            "pushEventType": "DEVICE_CHANGED",
                            "device": new_device_payload,
                        }
                    }
                }
            },
        }
        coordinator._handle_event_message(event_message)
        await hass.async_block_till_done()

        mock_async_reload.assert_not_called()
        mock_schedule_reload.assert_not_called()

        switch_state = hass.states.get("switch.new_living_room_plug")
        assert switch_state is not None
        assert switch_state.state == "off"

        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get_device_by_identifier(
            (DOMAIN, "new-switch-1"), config_entry.entry_id
        )
        assert device is not None
        assert device.name == "New Living Room Plug"


async def test_new_switching_group_added_dynamically(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: HcuApiClient
) -> None:
    """Test that a new switching group gets its entity without reloading."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True
    assert coordinator is not None

    with (
        patch.object(
            hass.config_entries, "async_reload", AsyncMock()
        ) as mock_async_reload,
        patch.object(
            hass.config_entries, "async_schedule_reload", MagicMock()
        ) as mock_schedule_reload,
    ):
        new_group_payload = {
            "id": "group-switch-1",
            "type": "SWITCHING",
            "label": "Kitchen Ceiling Lights",
            "channels": [{"deviceId": HCU_ID, "channelIndex": 2}],
            "on": False,
        }

        event_message = {
            "type": "HMIP_SYSTEM_EVENT",
            "body": {
                "eventTransaction": {
                    "events": {
                        "0": {
                            "pushEventType": "GROUP_CHANGED",
                            "group": new_group_payload,
                        }
                    }
                }
            },
        }
        coordinator._handle_event_message(event_message)
        await hass.async_block_till_done()

        mock_async_reload.assert_not_called()
        mock_schedule_reload.assert_not_called()

        group_state = hass.states.get("switch.kitchen_ceiling_lights")
        assert group_state is not None
        assert group_state.state == "off"


async def test_repeated_event_creates_no_duplicates(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: HcuApiClient
) -> None:
    """Repeating the same event creates no duplicate entities or errors."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True
    new_device_payload = {
        "id": "new-switch-dup",
        "type": "PLUGABLE_SWITCH",
        "modelType": "HMIP-PS",
        "label": "Duplicate Check Plug",
        "oem": "eQ-3",
        "firmwareVersion": "1.2.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "index": 1,
                "groups": ["room-1"],
                "on": False,
            },
        },
    }
    event_message = {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {
                    "0": {
                        "pushEventType": "DEVICE_CHANGED",
                        "device": new_device_payload,
                    }
                }
            }
        },
    }
    coordinator._handle_event_message(event_message)
    await hass.async_block_till_done()

    initial_entities_count = len(coordinator.entities.get(Platform.SWITCH, []))
    switch_state = hass.states.get("switch.duplicate_check_plug")
    assert switch_state is not None

    # Repeat the same event
    coordinator._handle_event_message(event_message)
    await hass.async_block_till_done()

    assert len(coordinator.entities.get(Platform.SWITCH, [])) == initial_entities_count


async def test_disable_unconfigured_channels_assign_group_later(
    hass: HomeAssistant, client: HcuApiClient
) -> None:
    """With disable_unconfigured_channels: channel without room gets no entity; later group assignment creates it."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        options={
            CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: True,
            CONF_DISABLE_UNCONFIGURED_CHANNELS: True,
        },
        unique_id=HCU_ID,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    coordinator._initial_state_loaded = True

    with (
        patch.object(
            hass.config_entries, "async_reload", AsyncMock()
        ) as mock_async_reload,
        patch.object(
            hass.config_entries, "async_schedule_reload", MagicMock()
        ) as mock_schedule_reload,
    ):
        # 1. New device with channel without room assignment
        device_unconfigured = {
            "id": "dev-unassigned-1",
            "type": "PLUGABLE_SWITCH",
            "modelType": "HMIP-PS",
            "label": "Unassigned Plug",
            "oem": "eQ-3",
            "firmwareVersion": "1.0.0",
            "functionalChannels": {
                "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
                "1": {
                    "functionalChannelType": "SWITCH_CHANNEL",
                    "index": 1,
                    "groups": [],  # No room assigned!
                    "on": False,
                },
            },
        }
        event_1 = {
            "type": "HMIP_SYSTEM_EVENT",
            "body": {
                "eventTransaction": {
                    "events": {
                        "0": {
                            "pushEventType": "DEVICE_CHANGED",
                            "device": device_unconfigured,
                        }
                    }
                }
            },
        }
        coordinator._handle_event_message(event_1)
        await hass.async_block_till_done()

        # Entity should not exist yet
        assert hass.states.get("switch.unassigned_plug") is None

        # 2. Later DEVICE_CHANGED assigns groups
        device_assigned = {
            "id": "dev-unassigned-1",
            "functionalChannels": {
                "1": {
                    "groups": ["room-kitchen"],
                }
            },
        }
        event_2 = {
            "type": "HMIP_SYSTEM_EVENT",
            "body": {
                "eventTransaction": {
                    "events": {
                        "0": {
                            "pushEventType": "DEVICE_CHANGED",
                            "device": device_assigned,
                        }
                    }
                }
            },
        }
        coordinator._handle_event_message(event_2)
        await hass.async_block_till_done()

        # Reload should not be triggered
        mock_async_reload.assert_not_called()
        mock_schedule_reload.assert_not_called()

        # Entity should now be discovered!
        switch_state = hass.states.get("switch.unassigned_plug")
        assert switch_state is not None


async def test_button_event_entity_of_new_device_registered_and_fires(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: HcuApiClient
) -> None:
    """Button/event entities of a new device are registered so a DEVICE_CHANNEL_EVENT fires it."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True

    # Add a brand new device with button event channel (BRAND_SWITCH_NOTIFICATION_LIGHT)
    new_button_device = {
        "id": "new-btn-dev-1",
        "type": "BRAND_SWITCH_NOTIFICATION_LIGHT",
        "modelType": "HmIP-BSL",
        "label": "Wall Button",
        "oem": "eQ-3",
        "firmwareVersion": "1.0.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
            "2": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "index": 2,
                "groups": ["room-1"],
            },
        },
    }
    event_message = {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {
                    "0": {
                        "pushEventType": "DEVICE_CHANGED",
                        "device": new_button_device,
                    }
                }
            }
        },
    }
    coordinator._handle_event_message(event_message)
    await hass.async_block_till_done()

    event_state = (
        hass.states.get("event.wall_button_button_1")
        or hass.states.get("event.wall_button_button")
        or hass.states.get("event.wall_button")
    )
    assert event_state is not None

    # Now fire a DEVICE_CHANNEL_EVENT for that button
    press_event_message = {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {
                    "0": {
                        "pushEventType": "DEVICE_CHANNEL_EVENT",
                        "deviceId": "new-btn-dev-1",
                        "channelIndex": 2,
                        "channelEventType": "KEY_PRESS_SHORT",
                    }
                }
            }
        },
    }
    coordinator._handle_event_message(press_event_message)
    await hass.async_block_till_done()

    # Verify event entity recorded short press
    event_entity = coordinator._event_entities.get(("new-btn-dev-1", "2"))
    assert event_entity is not None
    updated_state = hass.states.get(event_entity.entity_id)
    assert updated_state is not None
    assert updated_state.attributes.get("event_type") == "press_short"


async def test_dynamic_inclusions_guards_and_missing_group(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: HcuApiClient
) -> None:
    """Test guards in _handle_dynamic_inclusions and async_discover_entities_for_group when item missing."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True

    # 1. Test empty included_ids or empty callbacks
    saved_cbs = coordinator._platform_callbacks
    coordinator._platform_callbacks = {}
    coordinator._handle_dynamic_inclusions({"dummy"})
    coordinator._platform_callbacks = saved_cbs
    coordinator._handle_dynamic_inclusions(set())

    # 2. Test missing group in state via async_discover_entities_for_group
    from custom_components.hcu_integration.discovery import (
        async_discover_entities_for_group,
    )

    res = async_discover_entities_for_group(
        client, config_entry, coordinator, "non-existent-grp"
    )
    assert all(len(ents) == 0 for ents in res.values())


async def test_repeated_event_hits_existing_unique_ids(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: HcuApiClient
) -> None:
    """Test that duplicate entities during dynamic addition are skipped via existing_unique_ids check."""
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True

    device_payload = {
        "id": "dev-repeat-uid",
        "type": "PLUGABLE_SWITCH",
        "modelType": "HMIP-PS",
        "label": "Repeat Plug",
        "oem": "eQ-3",
        "firmwareVersion": "1.0.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "index": 1,
                "groups": ["room-1"],
                "on": False,
            },
        },
    }
    event_msg = {
        "type": "HMIP_SYSTEM_EVENT",
        "body": {
            "eventTransaction": {
                "events": {
                    "0": {
                        "pushEventType": "DEVICE_CHANGED",
                        "device": device_payload,
                    }
                }
            }
        },
    }
    # First time adds entity
    coordinator._handle_event_message(event_msg)
    await hass.async_block_till_done()

    # Call _handle_dynamic_inclusions directly with the same device ID to hit the existing_unique_ids branch (line 168)
    coordinator._handle_dynamic_inclusions({"dev-repeat-uid"})
