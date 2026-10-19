"""Tests for device and group discovery."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.binary_sensor import HcuSecurityAlarmBinarySensor
from custom_components.hcu_integration.button import HcuAcknowledgeSafetyAlarmButton
from custom_components.hcu_integration.const import SYSTEM_RULE_GROUPS
from custom_components.hcu_integration.discovery import async_discover_entities
from custom_components.hcu_integration.light import HcuLightGroup
from custom_components.hcu_integration.sensor import HcuGroupOnTimeSensor
from custom_components.hcu_integration.switch import HcuSwitchGroup


def test_heat_demand_rules_in_system_rule_groups():
    """Test that heat demand rule group types are recognized as system rule groups."""
    assert "HEAT_DEMAND_RULE" in SYSTEM_RULE_GROUPS
    assert "HEAT_DEMAND_RULE_WITH_LEAD_ROOM" in SYSTEM_RULE_GROUPS


@pytest.mark.parametrize(
    "group_type,group_label",
    [
        ("HEAT_DEMAND_RULE", "Heat Demand Rule"),
        ("HEAT_DEMAND_RULE_WITH_LEAD_ROOM", "Heat Demand Lead Room Rule"),
    ],
)
async def test_heat_demand_rule_group_skipped_without_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
    group_type: str,
    group_label: str,
):
    """Test that heat demand rule groups are skipped without logging a warning."""
    mock_hcu_client.state = {
        "devices": {},
        "groups": {
            "heat-demand-rule-id": {
                "id": "heat-demand-rule-id",
                "type": group_type,
                "label": group_label,
                "channels": ["some_channel"],
            }
        },
    }

    with caplog.at_level(logging.DEBUG):
        entities = await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )

    # No entities created for any platform from heat demand rules
    for platform_entities in entities.values():
        assert len(platform_entities) == 0

    # Ensure no warning was logged for unknown group type
    assert not any(
        record.levelno >= logging.WARNING and "Unknown group type" in record.message
        for record in caplog.records
    )

    # Ensure debug message confirms skipping system rule group
    assert any(
        f"Skipping system rule group '{group_label}'" in record.message
        for record in caplog.records
    )


def test_plugin_version_matches_manifest():
    """Test that PLUGIN_VERSION in const.py matches version in manifest.json."""
    import json
    from pathlib import Path

    from custom_components.hcu_integration.const import PLUGIN_VERSION

    manifest_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "hcu_integration"
        / "manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["version"] == PLUGIN_VERSION


async def test_extended_linked_switching_group_with_switch_visualization_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that EXTENDED_LINKED_SWITCHING group with switchVisualization=LIGHT becomes HcuLightGroup."""
    mock_hcu_client.state = {
        "devices": {
            "dev-switch-1": {
                "id": "dev-switch-1",
                "label": "Light Switch",
                "type": "BRAND_SWITCH_MEASURING",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                    "1": {
                        "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["group-light-1"],
                    },
                },
            }
        },
        "groups": {
            "group-light-1": {
                "id": "group-light-1",
                "type": "EXTENDED_LINKED_SWITCHING",
                "label": "Garden Lights Group",
                "on": False,
                "onTime": 120.0,
                "channels": [
                    {"deviceId": "dev-switch-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    # Main group entity should be in Platform.LIGHT
    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 1
    assert light_groups[0].unique_id == "group-light-1"

    # No switch group entity should be in Platform.SWITCH
    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 0

    # Diagnostic on-time sensor should still be in Platform.SENSOR
    on_time_sensors = [
        e for e in entities[Platform.SENSOR] if isinstance(e, HcuGroupOnTimeSensor)
    ]
    assert len(on_time_sensors) == 1
    assert on_time_sensors[0].unique_id == "group-light-1_on_time"


async def test_extended_linked_switching_group_with_dimmer(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that switching group containing a DIMMER_CHANNEL becomes HcuLightGroup."""
    mock_hcu_client.state = {
        "devices": {
            "dev-dimmer-1": {
                "id": "dev-dimmer-1",
                "label": "Living Room Dimmer",
                "type": "DIMMER",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                    "1": {
                        "functionalChannelType": "DIMMER_CHANNEL",
                        "groups": ["group-dimmer-1"],
                    },
                },
            }
        },
        "groups": {
            "group-dimmer-1": {
                "id": "group-dimmer-1",
                "type": "EXTENDED_LINKED_SWITCHING",
                "label": "Living Room Group",
                "on": True,
                "channels": [
                    {"deviceId": "dev-dimmer-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 1
    assert light_groups[0].unique_id == "group-dimmer-1"

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 0


async def test_switching_group_with_button_and_light(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that a direct connection linking a button (input) and a light switch becomes HcuLightGroup."""
    mock_hcu_client.state = {
        "devices": {
            "dev-button-1": {
                "id": "dev-button-1",
                "label": "Wall Switch Button",
                "type": "PUSH_BUTTON",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                    "1": {
                        "functionalChannelType": "SINGLE_KEY_CHANNEL",
                        "groups": ["group-direct-link-1"],
                    },
                },
            },
            "dev-light-1": {
                "id": "dev-light-1",
                "label": "Ceiling Light",
                "type": "BRAND_SWITCH_NOTIFICATION_LIGHT",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["group-direct-link-1"],
                    },
                },
            },
        },
        "groups": {
            "group-direct-link-1": {
                "id": "group-direct-link-1",
                "type": "LINKED_SWITCHING",
                "label": "Direct Link Ceiling Light",
                "on": False,
                "channels": [
                    {"deviceId": "dev-button-1", "channelIndex": 1},
                    {"deviceId": "dev-light-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    # Input channel is ignored; actuator is a light -> group is a LightGroup
    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 1
    assert light_groups[0].unique_id == "group-direct-link-1"

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 0


async def test_switching_group_with_outlet_stays_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that a switching group with switchVisualization=OUTLET remains HcuSwitchGroup."""
    mock_hcu_client.state = {
        "devices": {
            "dev-socket-1": {
                "id": "dev-socket-1",
                "label": "Coffee Socket",
                "type": "PLUGABLE_SWITCH_MEASURING",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                    "1": {
                        "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                        "switchVisualization": "OUTLET",
                        "groups": ["group-socket-1"],
                    },
                },
            }
        },
        "groups": {
            "group-socket-1": {
                "id": "group-socket-1",
                "type": "EXTENDED_LINKED_SWITCHING",
                "label": "Coffee Machine Group",
                "on": False,
                "channels": [
                    {"deviceId": "dev-socket-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    # Group must remain HcuSwitchGroup
    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 1
    assert switch_groups[0].unique_id == "group-socket-1"

    # No light group
    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 0


async def test_switching_group_with_mixed_light_and_outlet_stays_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that a mixed switching group (light + outlet) remains HcuSwitchGroup."""
    mock_hcu_client.state = {
        "devices": {
            "dev-light-1": {
                "id": "dev-light-1",
                "label": "Desk Light",
                "type": "BRAND_SWITCH",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["group-mixed-1"],
                    },
                },
            },
            "dev-socket-1": {
                "id": "dev-socket-1",
                "label": "Desk Socket",
                "type": "PLUGABLE_SWITCH",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "OUTLET",
                        "groups": ["group-mixed-1"],
                    },
                },
            },
        },
        "groups": {
            "group-mixed-1": {
                "id": "group-mixed-1",
                "type": "SWITCHING",
                "label": "Mixed Desk Group",
                "on": True,
                "channels": [
                    {"deviceId": "dev-light-1", "channelIndex": 1},
                    {"deviceId": "dev-socket-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 1
    assert switch_groups[0].unique_id == "group-mixed-1"

    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 0


async def test_switching_group_with_switch_having_key_role_stays_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that an outlet actuator whose channel has channelRole=KEY_OR_SWITCH_FOR_GROUP keeps the group as switch."""
    mock_hcu_client.state = {
        "devices": {
            "dev-light-1": {
                "id": "dev-light-1",
                "label": "Ceiling Light",
                "type": "BRAND_SWITCH",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["group-role-test"],
                    },
                },
            },
            "dev-socket-1": {
                "id": "dev-socket-1",
                "label": "Wall Plug Outlet",
                "type": "PLUGABLE_SWITCH",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
                        "switchVisualization": "OUTLET",
                        "groups": ["group-role-test"],
                    },
                },
            },
        },
        "groups": {
            "group-role-test": {
                "id": "group-role-test",
                "type": "SWITCHING",
                "label": "Role Test Group",
                "on": True,
                "channels": [
                    {"deviceId": "dev-light-1", "channelIndex": 1},
                    {"deviceId": "dev-socket-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 1
    assert switch_groups[0].unique_id == "group-role-test"

    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 0


def test_is_channel_light_actuator_precedence():
    """Test that switch actuator types take precedence over channelRole in _is_channel_light."""
    from custom_components.hcu_integration.discovery import _is_channel_light

    # Switch channel with channelRole=KEY_OR_SWITCH_FOR_GROUP and OUTLET -> False (non-light actuator)
    outlet_channel = {
        "functionalChannelType": "SWITCH_CHANNEL",
        "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
        "switchVisualization": "OUTLET",
    }
    assert _is_channel_light(outlet_channel, 1) is False

    # Switch channel with channelRole=KEY_OR_SWITCH_FOR_GROUP and LIGHT -> True (light actuator)
    light_switch_channel = {
        "functionalChannelType": "SWITCH_CHANNEL",
        "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
        "switchVisualization": "LIGHT",
    }
    assert _is_channel_light(light_switch_channel, 1) is True

    # Pure button channel with channelRole=KEY_OR_SWITCH_FOR_GROUP -> None (ignored non-actuator)
    button_channel = {
        "functionalChannelType": "SINGLE_KEY_CHANNEL",
        "channelRole": "KEY_OR_SWITCH_FOR_GROUP",
    }
    assert _is_channel_light(button_channel, 1) is None


@pytest.mark.parametrize(
    "group_type",
    [
        "EXTENDED_LINKED_SWITCHING",
        "LINKED_SWITCHING",
        "SWITCHING",
        "SWITCHING_PROFILE",
    ],
)
async def test_all_switching_group_types_support_light_conversion(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    group_type: str,
):
    """Test that all supported switching group types become HcuLightGroup when containing lights."""
    mock_hcu_client.state = {
        "devices": {
            "dev-light-1": {
                "id": "dev-light-1",
                "label": "Test Light",
                "type": "BRAND_SWITCH",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["test-group-id"],
                    },
                },
            }
        },
        "groups": {
            "test-group-id": {
                "id": "test-group-id",
                "type": group_type,
                "label": f"Test {group_type}",
                "on": False,
                "channels": [
                    {"deviceId": "dev-light-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 1
    assert light_groups[0].unique_id == "test-group-id"

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 0


async def test_switching_group_fallback_on_missing_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that a switching group with unresolvable device safely falls back to HcuSwitchGroup."""
    mock_hcu_client.state = {
        "devices": {},  # device not in state
        "groups": {
            "group-missing-dev": {
                "id": "group-missing-dev",
                "type": "EXTENDED_LINKED_SWITCHING",
                "label": "Missing Device Group",
                "channels": [
                    {"deviceId": "unknown-device-id", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 1
    assert switch_groups[0].unique_id == "group-missing-dev"


async def test_switching_group_only_buttons_stays_switch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that a group with only button/sensor channels (no actuators) remains a switch group."""
    mock_hcu_client.state = {
        "devices": {
            "dev-btn-1": {
                "id": "dev-btn-1",
                "label": "Wall Button",
                "type": "PUSH_BUTTON",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SINGLE_KEY_CHANNEL",
                        "groups": ["group-buttons-only"],
                    },
                },
            }
        },
        "groups": {
            "group-buttons-only": {
                "id": "group-buttons-only",
                "type": "LINKED_SWITCHING",
                "label": "Buttons Only Group",
                "channels": [
                    {"deviceId": "dev-btn-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert len(switch_groups) == 1
    assert switch_groups[0].unique_id == "group-buttons-only"


async def test_switching_group_platform_migration_removes_old_registry_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
):
    """Test that when a switching group changes to light, the old switch entity is removed from registry."""
    from homeassistant.helpers import entity_registry as er

    from custom_components.hcu_integration.const import DOMAIN

    # Mock an existing switch entity in the registry for this group
    old_switch_entry = MagicMock()
    old_switch_entry.platform = DOMAIN
    old_switch_entry.domain = "switch"
    old_switch_entry.unique_id = "migrating-group-id"
    old_switch_entry.entity_id = "switch.living_room_lights"
    old_switch_entry.name = "Living Room Lights"

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_remove = MagicMock()

    monkeypatch.setattr(er, "async_get", lambda _hass: mock_ent_reg)
    monkeypatch.setattr(
        er,
        "async_entries_for_config_entry",
        lambda _reg, _entry_id: [old_switch_entry],
    )

    mock_hcu_client.state = {
        "devices": {
            "dev-light-1": {
                "id": "dev-light-1",
                "label": "Living Room Light",
                "type": "BRAND_SWITCH",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["migrating-group-id"],
                    },
                },
            }
        },
        "groups": {
            "migrating-group-id": {
                "id": "migrating-group-id",
                "type": "EXTENDED_LINKED_SWITCHING",
                "label": "Living Room Lights",
                "on": False,
                "channels": [
                    {"deviceId": "dev-light-1", "channelIndex": 1},
                ],
            }
        },
    }
    mock_hcu_client.get_group_by_id.side_effect = lambda gid: mock_hcu_client.state[
        "groups"
    ].get(gid)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    # Verifies old switch entity was removed from registry
    mock_ent_reg.async_remove.assert_called_once_with("switch.living_room_lights")

    # Verifies new light group entity was created
    light_groups = [e for e in entities[Platform.LIGHT] if isinstance(e, HcuLightGroup)]
    assert len(light_groups) == 1
    assert light_groups[0].unique_id == "migrating-group-id"


async def test_firmware_update_supported_features_is_intflag(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
):
    """Test that HcuFirmwareUpdate uses UpdateEntityFeature(0) IntFlag instead of set()."""
    from homeassistant.components.update import UpdateEntityFeature

    from custom_components.hcu_integration.update import HcuFirmwareUpdate

    device_data = {
        "id": "dev-update-1",
        "label": "Thermostat",
        "type": "HEATING_THERMOSTAT",
        "firmwareVersion": "1.0.0",
        "availableFirmwareVersion": "1.2.0",
        "updateState": "UPDATE_AVAILABLE",
        "functionalChannels": {"0": {"functionalChannelType": "DEVICE_BASE"}},
    }
    mock_hcu_client.get_device_by_address.return_value = device_data

    entity = HcuFirmwareUpdate(mock_coordinator, mock_hcu_client, device_data, "0")
    assert isinstance(entity.supported_features, UpdateEntityFeature)
    assert entity.supported_features == UpdateEntityFeature(0)
    # Home Assistant core performs bitwise & checks on supported_features
    assert (entity.supported_features & UpdateEntityFeature.INSTALL) == 0


async def test_device_pin_update_skips_full_integration_reload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
):
    """Test that updating a device PIN via HcuDevicePin updates options without reloading the entry."""
    from unittest.mock import AsyncMock

    from homeassistant.config_entries import ConfigEntryState

    from custom_components.hcu_integration import HcuCoordinator, async_reload_entry
    from custom_components.hcu_integration.const import (
        CONF_COMFORT_TEMPERATURE,
        CONF_DEVICE_PINS,
    )
    from custom_components.hcu_integration.text import HcuDevicePin

    # Use the real config entry registry so options go through async_update_entry.
    mock_config_entry.add_to_hass(hass)
    coordinator = HcuCoordinator(hass, mock_hcu_client, mock_config_entry)
    mock_config_entry.mock_state(hass, ConfigEntryState.LOADED)
    mock_config_entry.runtime_data = coordinator
    hass.config_entries.async_reload = AsyncMock()

    device_data = {
        "id": "dev-lock-1",
        "label": "Front Door Lock",
        "type": "DOOR_LOCK_DRIVE",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DOOR_LOCK_CHANNEL", "groups": ["g1"]},
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device_data

    pin_entity = HcuDevicePin(coordinator, mock_hcu_client, device_data, "1")
    pin_entity.hass = hass
    pin_entity.async_write_ha_state = MagicMock()

    await pin_entity.async_set_value("4321")
    assert mock_config_entry.options[CONF_DEVICE_PINS]["dev-lock-1"] == "4321"
    assert pin_entity.native_value == "****"

    # Simulate Home Assistant firing the update listener after async_update_entry
    await async_reload_entry(hass, mock_config_entry)
    hass.config_entries.async_reload.assert_not_awaited()

    # Updating a non-PIN option must still trigger a full integration reload
    hass.config_entries.async_update_entry(
        mock_config_entry,
        options={**mock_config_entry.options, CONF_COMFORT_TEMPERATURE: 22.5},
    )
    await async_reload_entry(hass, mock_config_entry)
    hass.config_entries.async_reload.assert_awaited_once_with(
        mock_config_entry.entry_id
    )


@pytest.mark.parametrize("has_security", [True, False])
async def test_security_alarm_entities_created_with_security_system(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    has_security: bool,
) -> None:
    """Alarm sensors and the acknowledge button exist only with a security system."""
    functional_homes = (
        {"SECURITY_AND_ALARM": {"solution": "SECURITY_AND_ALARM"}}
        if has_security
        else {}
    )
    mock_hcu_client.state = {
        "home": {"id": "home-1", "functionalHomes": functional_homes},
        "devices": {},
        "groups": {},
    }

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    alarm_sensors = [
        e
        for e in entities[Platform.BINARY_SENSOR]
        if isinstance(e, HcuSecurityAlarmBinarySensor)
    ]
    ack_buttons = [
        e
        for e in entities[Platform.BUTTON]
        if isinstance(e, HcuAcknowledgeSafetyAlarmButton)
    ]
    assert len(alarm_sensors) == (2 if has_security else 0)
    assert len(ack_buttons) == (1 if has_security else 0)


async def test_group_with_null_label_does_not_break_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """A group whose label is null does not stop discovery of the other groups."""
    channels = [{"deviceId": "dev-1", "channelIndex": 1}]
    groups = {
        "alarm-group": {
            "id": "alarm-group",
            "type": "ALARM_SWITCHING",
            "label": None,
            "channels": channels,
        },
        "garden-group": {
            "id": "garden-group",
            "type": "SWITCHING",
            "label": "Garden",
            "channels": channels,
        },
    }
    mock_hcu_client.state = {"devices": {}, "groups": groups}
    mock_hcu_client.get_group_by_id = MagicMock(side_effect=groups.get)

    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    switch_groups = [
        e for e in entities[Platform.SWITCH] if isinstance(e, HcuSwitchGroup)
    ]
    assert [e._group_id for e in switch_groups] == ["garden-group"]
