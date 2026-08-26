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
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
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
    """Test _set_entity_name without feature name or channel label.

    When there's no channel label, the entity should use the device label/model as fallback.
    """
    mock_hcu_client.state = {"devices": {mock_device_data["id"]: mock_device_data}}
    entity = HcuBaseEntity(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=mock_device_data,
        channel_index="1",
    )

    entity._set_entity_name(channel_label=None, feature_name=None)

    assert entity._attr_name == "Test Device"
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
