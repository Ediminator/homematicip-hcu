"""Unit tests for the HCU update platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.components.update import UpdateDeviceClass, UpdateEntityFeature
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.update import (
    HcuFirmwareUpdate,
    async_setup_entry,
)


def _make_firmware_update_entity(
    device_data: dict,
    channel_index: str = "0",
) -> HcuFirmwareUpdate:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuFirmwareUpdate(coordinator, client, device_data, channel_index)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_update_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.UPDATE: [mock_entity]}
    entry.runtime_data = mock_coordinator

    added = []

    def mock_add_entities(entities: list) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == [mock_entity]

    # Empty list
    mock_coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == []


def test_firmware_update_properties() -> None:
    """Test firmware update attributes and version reporting."""
    device_data = {
        "id": "dev-thermostat-1",
        "label": "Radiator Valve",
        "firmwareVersion": "1.2.4",
        "availableFirmwareVersion": "1.3.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "label": "Device Base"}
        },
    }
    entity = _make_firmware_update_entity(device_data)

    assert entity.unique_id == "dev-thermostat-1_firmware_update"
    assert entity.device_class == UpdateDeviceClass.FIRMWARE
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert entity.supported_features == UpdateEntityFeature(0)
    assert entity.installed_version == "1.2.4"
    assert entity.latest_version == "1.3.0"


def test_firmware_update_none_versions() -> None:
    """Test firmware update when versions are missing or None."""
    device_data = {
        "id": "dev-sensor-1",
        "label": "Sensor",
        "firmwareVersion": None,
        "availableFirmwareVersion": None,
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "label": "Device Base"}
        },
    }
    entity = _make_firmware_update_entity(device_data)
    assert entity.installed_version is None
    assert entity.latest_version is None


def test_firmware_update_coordinator_update() -> None:
    """Test coordinator update callback triggers super handler."""
    device_data = {
        "id": "dev-switch-1",
        "label": "Switch",
        "firmwareVersion": "2.0.0",
        "availableFirmwareVersion": "2.0.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "label": "Device Base"}
        },
    }
    entity = _make_firmware_update_entity(device_data)
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_called_once()
