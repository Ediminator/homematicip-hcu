"""Unit tests for the HCU number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.number import NumberMode
from homeassistant.const import EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, State
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.number import (
    HcuConfigRampTime,
    async_setup_entry,
)


def _make_ramp_time_entity(
    device_data: dict,
    channel_index: str = "1",
) -> HcuConfigRampTime:
    dev_id = device_data["id"]
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    entity = HcuConfigRampTime(coordinator, client, device_data, channel_index)
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_number_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.NUMBER: [mock_entity]}
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


def test_ramp_time_properties() -> None:
    """Test HcuConfigRampTime static attributes."""
    device_data = {
        "id": "dev-dimmer-1",
        "label": "Dimmer",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "label": "Device Base"},
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "label": "Dimmer Channel",
            },
        },
    }
    entity = _make_ramp_time_entity(device_data)

    assert entity.unique_id == "dev-dimmer-1_1_ramp_time"
    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.entity_registry_enabled_default is False
    assert entity.native_min_value == 0.0
    assert entity.native_max_value == 16383.0
    assert entity.native_step == 0.1
    assert entity.native_unit_of_measurement == UnitOfTime.SECONDS
    assert entity.mode == NumberMode.BOX
    assert entity.native_value == 0.0

    # Coordinator update is a no-op
    entity._handle_coordinator_update()


@pytest.mark.asyncio
async def test_ramp_time_set_value() -> None:
    """Test setting native value updates internal attribute and writes state."""
    device_data = {
        "id": "dev-dimmer-1",
        "label": "Dimmer",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DIMMER_CHANNEL"},
        },
    }
    entity = _make_ramp_time_entity(device_data)

    await entity.async_set_native_value(2.5)
    assert entity.native_value == 2.5
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_ramp_time_restore_state_valid() -> None:
    """Test state restoration when valid float string is retrieved."""
    device_data = {
        "id": "dev-dimmer-1",
        "label": "Dimmer",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DIMMER_CHANNEL"},
        },
    }
    entity = _make_ramp_time_entity(device_data)
    entity.async_get_last_state = AsyncMock(
        return_value=State("number.dimmer_ramp_time", "7.5")
    )

    await entity.async_added_to_hass()
    assert entity.native_value == 7.5


@pytest.mark.asyncio
async def test_ramp_time_restore_state_invalid_fallback() -> None:
    """Test state restoration fallback when last state is non-numeric or None."""
    device_data = {
        "id": "dev-dimmer-1",
        "label": "Dimmer",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DIMMER_CHANNEL"},
        },
    }

    # Case 1: non-numeric string (e.g. unavailable)
    entity1 = _make_ramp_time_entity(device_data)
    entity1.async_get_last_state = AsyncMock(
        return_value=State("number.dimmer_ramp_time", "unavailable")
    )
    await entity1.async_added_to_hass()
    assert entity1.native_value == 0.0

    # Case 2: None returned
    entity2 = _make_ramp_time_entity(device_data)
    entity2.async_get_last_state = AsyncMock(return_value=None)
    await entity2.async_added_to_hass()
    assert entity2.native_value == 0.0
