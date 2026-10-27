"""Unit tests for the HCU number platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.number import NumberMode
from homeassistant.const import (
    EntityCategory,
    Platform,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import DOMAIN, HMIP_FEATURE_TO_ENTITY
from custom_components.hcu_integration.number import (
    HcuConfigRampTime,
    HcuTemperatureOffset,
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
    assert entity.has_entity_name is True
    assert entity.translation_key == "ramp_time"
    assert entity.translation_placeholders == {
        "channel": "Dimmer Channel ",
        "channel_index": "",
    }
    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.entity_registry_enabled_default is False
    assert entity.native_min_value == 0.0
    assert entity.native_max_value == 16383.0
    assert entity.native_step == 0.1
    assert entity.native_unit_of_measurement == UnitOfTime.SECONDS
    assert entity.mode == NumberMode.BOX
    assert entity.native_value == 0.0

    # Unlabeled channel fallback
    device_unlabeled = {
        "id": "dev-dimmer-2",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DIMMER_CHANNEL"},
        },
    }
    entity_unlabeled = _make_ramp_time_entity(device_unlabeled)
    assert entity_unlabeled.has_entity_name is True
    assert entity_unlabeled.translation_key == "ramp_time"
    assert entity_unlabeled.translation_placeholders == {
        "channel": "",
        "channel_index": "",
    }

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


def _make_temperature_offset_entity() -> tuple[HcuTemperatureOffset, MagicMock, dict]:
    device_data = {
        "id": "dev-etrv-1",
        "label": "Radiator",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "HEATING_THERMOSTAT_CHANNEL",
                "temperatureOffset": 1.5,
            },
        },
    }
    coordinator = MagicMock()
    coordinator.data = {"dev-etrv-1": device_data}
    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_set_temperature_offset = AsyncMock()
    entity = HcuTemperatureOffset(
        coordinator,
        client,
        device_data,
        "1",
        "temperatureOffset",
        HMIP_FEATURE_TO_ENTITY["temperatureOffset"],
    )
    entity.entity_id = "number.radiator_temperature_offset"
    return entity, client, device_data


def test_temperature_offset_properties() -> None:
    """Test HcuTemperatureOffset attributes and value from channel data."""
    entity, _, device_data = _make_temperature_offset_entity()

    assert entity.unique_id == "dev-etrv-1_1_temperatureOffset"
    assert entity.translation_key == "temperature_offset"
    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.native_min_value == -3.5
    assert entity.native_max_value == 3.5
    assert entity.native_step == 0.5
    assert entity.native_unit_of_measurement == UnitOfTemperature.CELSIUS
    assert entity.device_class is None
    assert entity.native_value == 1.5

    device_data["functionalChannels"]["1"]["temperatureOffset"] = -2.0
    assert entity.native_value == -2.0


@pytest.mark.asyncio
async def test_temperature_offset_set_value() -> None:
    """Test setting the offset sends it to the HCU."""
    entity, client, _ = _make_temperature_offset_entity()

    await entity.async_set_native_value(-0.5)
    client.async_set_temperature_offset.assert_awaited_once_with("dev-etrv-1", 1, -0.5)


@pytest.mark.asyncio
async def test_temperature_offset_set_value_error() -> None:
    """Test an HCU error is raised as a Home Assistant error."""
    entity, client, _ = _make_temperature_offset_entity()
    client.async_set_temperature_offset.side_effect = HcuApiError("rejected")

    with pytest.raises(HomeAssistantError):
        await entity.async_set_native_value(1.0)
