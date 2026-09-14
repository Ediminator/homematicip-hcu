"""Tests for HCU light entity state handling when channel values are null."""
from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.hcu_integration.light import HcuLight, HcuNotificationLight


def test_hcu_notification_light_is_on_when_null(mock_coordinator, mock_hcu_client):
    """Test that HcuNotificationLight.is_on returns False instead of None when on and dimLevel are null."""
    device_data = {
        "id": "test-hcu-id",
        "modelType": "HmIP-HCU1-A",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "dimLevel": None,
                "on": None,
                "userDesiredProfileMode": "AUTOMATIC",
            }
        },
    }
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuNotificationLight(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=device_data,
        channel_index="1",
    )

    assert entity.is_on is False


def test_hcu_light_is_on_when_null(mock_coordinator, mock_hcu_client):
    """Test that HcuLight.is_on returns False instead of None when on and dimLevel are null."""
    device_data = {
        "id": "test-dimmer-id",
        "modelType": "HmIP-BDT",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "dimLevel": None,
                "on": None,
            }
        },
    }
    mock_hcu_client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuLight(
        coordinator=mock_coordinator,
        client=mock_hcu_client,
        device_data=device_data,
        channel_index="1",
    )

    assert entity.is_on is False
