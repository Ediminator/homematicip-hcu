"""Tests for entity base classes."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.hcu_integration.entity import (
    HcuBaseEntity,
    HcuGroupBaseEntity,
    HcuHomeBaseEntity,
)


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    coordinator.config_entry.data.get.return_value = ""
    return coordinator


def test_hcu_base_entity_initialization(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test HcuBaseEntity initialization."""
    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    assert entity._client == mock_hcu_client
    assert entity._device_id == "test-device-id"
    assert entity._channel_index_str == "1"
    assert entity._channel_index == 1
    assert entity._attr_assumed_state is False


def test_hcu_base_entity_device_info(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test device_info property."""
    # Configure mock to return device data when entity accesses it
    mock_hcu_client.get_device_by_address = MagicMock(return_value=mock_device_data)

    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    device_info = entity.device_info
    assert device_info["identifiers"] == {("hcu_integration", "test-device-id")}
    assert device_info["name"] == "Test Device"
    assert device_info["model"] == "HMIP-PSM"


def test_hcu_base_entity_device_info_for_hcu_part(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test device_info property when device is part of HCU hardware."""
    # Configure mock to return device data when entity accesses it
    mock_hcu_client.get_device_by_address = MagicMock(return_value=mock_device_data)
    mock_hcu_client.hcu_device_id = "hcu-main-device-id"
    mock_hcu_client.hcu_part_device_ids = {"test-device-id"}  # Device is part of HCU

    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    device_info = entity.device_info
    # HCU part devices should link to the main HCU device
    assert device_info["identifiers"] == {("hcu_integration", "hcu-main-device-id")}
    # Should not include separate device info fields
    assert "name" not in device_info
    assert "model" not in device_info


def test_hcu_base_entity_set_entity_name_with_feature(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test _set_entity_name with feature name."""
    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    entity._set_entity_name(channel_label="Test Channel", feature_name="Power Consumption")

    assert entity._attr_name == "Test Channel Power Consumption"
    assert entity._attr_has_entity_name is False
    assert entity._attr_translation_key is None


def test_hcu_base_entity_set_entity_name_without_feature(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test _set_entity_name without feature name."""
    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    entity._set_entity_name(channel_label="Test Channel")

    assert entity._attr_name == "Test Channel"
    assert entity._attr_has_entity_name is False


def test_hcu_base_entity_set_entity_name_with_feature_no_label(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test _set_entity_name with feature name but no channel label."""
    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    entity._set_entity_name(channel_label=None, feature_name="Low Battery")

    assert entity._attr_name == "Low Battery"
    assert entity._attr_has_entity_name is True


def test_hcu_base_entity_set_entity_name_no_feature_no_label(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test _set_entity_name without feature name or channel label."""
    mock_hcu_client.get_device_by_address.return_value = mock_device_data
    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    entity._set_entity_name(channel_label=None, feature_name=None)

    assert entity._attr_name is None
    assert entity._attr_has_entity_name is True


def test_hcu_group_base_entity_initialization(mock_coordinator, mock_hcu_client, mock_group_data):
    """Test HcuGroupBaseEntity initialization."""
    entity = HcuGroupBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        group_data=mock_group_data,
    )

    assert entity._client == mock_hcu_client
    assert entity._group_id == "test-group-id"
    assert entity._attr_assumed_state is False


def test_hcu_group_base_entity_group_property(mock_coordinator, mock_hcu_client, mock_group_data):
    """Test _group property."""
    mock_hcu_client.get_group_by_id = MagicMock(return_value=mock_group_data)

    entity = HcuGroupBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        group_data=mock_group_data,
    )

    group = entity._group
    assert group == mock_group_data
    mock_hcu_client.get_group_by_id.assert_called_once_with("test-group-id")


def test_hcu_group_base_entity_device_info(mock_coordinator, mock_hcu_client, mock_group_data):
    """Test device_info property for group entity."""
    mock_hcu_client.hcu_device_id = "hcu-device-id"

    entity = HcuGroupBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        group_data=mock_group_data,
    )

    device_info = entity.device_info
    assert device_info["identifiers"] == {("hcu_integration", "test-group-id")}


def test_hcu_home_base_entity_initialization(mock_coordinator, mock_hcu_client):
    """Test HcuHomeBaseEntity initialization."""
    mock_hcu_client.hcu_device_id = "hcu-device-id"
    mock_hcu_client.state = {
        "home": {
            "id": "home-uuid",
        },
    }

    entity = HcuHomeBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
    )

    assert entity._client == mock_hcu_client
    assert entity._hcu_device_id == "hcu-device-id"
    assert entity._home_uuid == "home-uuid"
    assert entity._attr_assumed_state is False


def test_hcu_home_base_entity_home_property(mock_coordinator, mock_hcu_client):
    """Test _home property."""
    home_data = {"id": "home-uuid", "currentAPVersion": "1.0.0"}
    mock_hcu_client.state = {"home": home_data}
    mock_hcu_client.hcu_device_id = "hcu-device-id"

    entity = HcuHomeBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
    )

    home = entity._home
    assert home == home_data


def test_hcu_home_base_entity_device_info(mock_coordinator, mock_hcu_client):
    """Test device_info property for home entity."""
    mock_hcu_client.hcu_device_id = "hcu-device-id"
    mock_hcu_client.state = {"home": {"id": "home-uuid"}}

    entity = HcuHomeBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
    )

    device_info = entity.device_info
    assert device_info["identifiers"] == {("hcu_integration", "hcu-device-id")}


@pytest.mark.parametrize(
    "is_connected,device_return,expected_available",
    [
        # Client connected, device reachable (non-permanently-reachable)
        (
            True,
            {
                "id": "test-device-id",
                "permanentlyReachable": False,
                "functionalChannels": {
                    "0": {"unreach": False},
                    "1": {},
                },
            },
            True,
        ),
        # Client disconnected
        (False, None, False),
        # Client connected, device unreachable (non-permanently-reachable)
        (
            True,
            {
                "id": "test-device-id",
                "permanentlyReachable": False,
                "functionalChannels": {
                    "0": {"unreach": True},
                    "1": {},
                },
            },
            False,
        ),
        # Device not found
        (True, None, False),
        # Permanently reachable device, even if marked unreachable
        (
            True,
            {
                "id": "test-device-id",
                "permanentlyReachable": True,
                "functionalChannels": {
                    "0": {"unreach": True},
                    "1": {},
                },
            },
            True,
        ),
        # Permanently reachable device, marked reachable
        (
            True,
            {
                "id": "test-device-id",
                "permanentlyReachable": True,
                "functionalChannels": {
                    "0": {"unreach": False},
                    "1": {},
                },
            },
            True,
        ),
    ],
    ids=[
        "connected_reachable_non_permanent",
        "client_disconnected",
        "connected_unreachable_non_permanent",
        "device_not_found",
        "permanently_reachable_marked_unreachable",
        "permanently_reachable_marked_reachable",
    ],
)
def test_hcu_base_entity_availability(
    mock_coordinator,
    mock_hcu_client,
    mock_device_data,
    is_connected,
    device_return,
    expected_available,
):
    """Test entity availability across various scenarios."""
    mock_hcu_client.is_connected = is_connected
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_return)

    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    assert entity.available is expected_available


def test_resolve_via_device_info_with_device_entry_id(mock_coordinator):
    """Test _resolve_via_device_info returns via_device_id when hcu_device_entry_id is present."""
    from custom_components.hcu_integration.entity import _resolve_via_device_info

    mock_coordinator.hcu_device_entry_id = "test_entry_id_123"
    result = _resolve_via_device_info(mock_coordinator, "hcu_dev_1")
    assert result == {"via_device_id": "test_entry_id_123"}


def test_resolve_via_device_info_fallback(mock_coordinator):
    """Test _resolve_via_device_info falls back to via_device tuple when no device entry id is found."""
    from custom_components.hcu_integration.entity import _resolve_via_device_info
    from custom_components.hcu_integration.const import DOMAIN

    mock_coordinator.hcu_device_entry_id = None
    mock_coordinator.hass = None
    result = _resolve_via_device_info(mock_coordinator, "hcu_dev_1")
    assert result == {"via_device": (DOMAIN, "hcu_dev_1")}


def test_hcu_base_entity_device_info_uses_via_device_id(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test HcuBaseEntity device_info contains via_device_id when available."""
    mock_coordinator.hcu_device_entry_id = "parent_hcu_reg_id"
    mock_hcu_client.hcu_device_id = "hcu_dev_1"

    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    info = entity.device_info
    assert info.get("via_device_id") == "parent_hcu_reg_id"


def test_hcu_base_entity_set_entity_name_multi_channel_feature(mock_coordinator, mock_hcu_client, mock_device_data):
    """Test _set_entity_name appends channel index for channels > 1 when unlabeled."""
    # Channel 0 (maintenance)
    entity_ch0 = HcuBaseEntity(mock_coordinator, mock_hcu_client, mock_device_data, "0")
    entity_ch0._set_entity_name(channel_label=None, feature_name="Low Battery")
    assert entity_ch0._attr_name == "Low Battery"

    # Channel 1 (primary channel)
    entity_ch1 = HcuBaseEntity(mock_coordinator, mock_hcu_client, mock_device_data, "1")
    entity_ch1._set_entity_name(channel_label=None, feature_name="Power Consumption")
    assert entity_ch1._attr_name == "Power Consumption"

    # Channel 2 (secondary channel)
    entity_ch2 = HcuBaseEntity(mock_coordinator, mock_hcu_client, mock_device_data, "2")
    entity_ch2._set_entity_name(channel_label=None, feature_name="Power Consumption")
    assert entity_ch2._attr_name == "Power Consumption 2"


def test_get_functional_channel_count(mock_coordinator, mock_hcu_client):
    """Test _get_functional_channel_count correctly filters maintenance and device base channels."""
    device_data = {
        "id": "dev1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "SWITCH_CHANNEL"},
            "2": {"functionalChannelType": "SWITCH_CHANNEL"},
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device_data
    entity = HcuBaseEntity(mock_coordinator, mock_hcu_client, device_data, "1")
    assert entity._get_functional_channel_count() == 2

    # Single channel device
    device_single = {
        "id": "dev2",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DIMMER_CHANNEL"},
        },
    }
    mock_hcu_client.get_device_by_address.return_value = device_single
    entity_single = HcuBaseEntity(mock_coordinator, mock_hcu_client, device_single, "1")
    assert entity_single._get_functional_channel_count() == 1


def test_multi_channel_platform_entity_naming(mock_coordinator, mock_hcu_client):
    """Test platform entities assign correct names or placeholders for multi-channel devices."""
    from custom_components.hcu_integration.light import HcuLight, HcuNotificationLight, HcuSwitchLight
    from custom_components.hcu_integration.event import HcuButtonEvent
    from custom_components.hcu_integration.switch import HcuSwitch
    from custom_components.hcu_integration.cover import HcuCover
    from custom_components.hcu_integration.lock import HcuLock
    from custom_components.hcu_integration.siren import HcuSiren
    from custom_components.hcu_integration.valve import HcuWateringSwitch

    multi_dev = {
        "id": "multi_dev_id",
        "label": "Multi Device",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "GENERIC"},
            "2": {"functionalChannelType": "GENERIC"},
        },
    }
    single_dev = {
        "id": "single_dev_id",
        "label": "Single Device",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "GENERIC"},
        },
    }

    mock_hcu_client.get_device_by_address.side_effect = lambda addr: multi_dev if addr == "multi_dev_id" else single_dev

    # Light
    light_multi = HcuLight(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert light_multi.translation_placeholders == {"channel_index": " 2"}

    light_single = HcuLight(mock_coordinator, mock_hcu_client, single_dev, "1")
    assert light_single.translation_placeholders == {"channel_index": ""}

    # Notification light
    notif_light = HcuNotificationLight(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert notif_light.translation_key == "hcu_light"
    assert notif_light.translation_placeholders == {"channel_index": " 2"}

    # Switch light
    switch_light = HcuSwitchLight(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert switch_light._attr_name == "Light 2"

    # Button event
    btn_event = HcuButtonEvent(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert btn_event.translation_placeholders == {"channel_index": " 2"}

    # Switch
    switch_ent = HcuSwitch(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert switch_ent._attr_name == "Switch 2"

    # Cover
    cover_ent = HcuCover(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert cover_ent._attr_name == "Cover 2"

    # Lock
    lock_ent = HcuLock(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert lock_ent._attr_name == "Lock 2"

    # Siren
    siren_ent = HcuSiren(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert siren_ent._attr_name == "Siren 2"

    # Valve / Watering
    valve_ent = HcuWateringSwitch(mock_coordinator, mock_hcu_client, multi_dev, "2")
    assert valve_ent._attr_name == "Watering 2"

    # Single-channel entities should have name=None and has_entity_name=True
    switch_single = HcuSwitch(mock_coordinator, mock_hcu_client, single_dev, "1")
    assert switch_single.name is None
    assert switch_single.has_entity_name is True

    cover_single = HcuCover(mock_coordinator, mock_hcu_client, single_dev, "1")
    assert cover_single.name is None
    assert cover_single.has_entity_name is True

    lock_single = HcuLock(mock_coordinator, mock_hcu_client, single_dev, "1")
    assert lock_single.name is None
    assert lock_single.has_entity_name is True

    siren_single = HcuSiren(mock_coordinator, mock_hcu_client, single_dev, "1")
    assert siren_single.name is None
    assert siren_single.has_entity_name is True

    valve_single = HcuWateringSwitch(mock_coordinator, mock_hcu_client, single_dev, "1")
    assert valve_single.name is None
    assert valve_single.has_entity_name is True

    # Labeled channels always take precedence over default naming
    labeled_dev = {
        "id": "labeled_dev_id",
        "label": "Labeled Device",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "GENERIC", "label": "Kitchen Light"},
            "2": {"functionalChannelType": "GENERIC", "label": "Living Room Light"},
        },
    }
    mock_hcu_client.get_device_by_address.side_effect = lambda addr: labeled_dev

    light_labeled = HcuLight(mock_coordinator, mock_hcu_client, labeled_dev, "2")
    assert light_labeled.name == "Living Room Light"
    assert light_labeled.has_entity_name is False
