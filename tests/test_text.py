"""Unit tests for the HCU text platform."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import CONF_DEVICE_PINS, DOMAIN
from custom_components.hcu_integration.text import HcuDevicePin, async_setup_entry


def _make_device_pin(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_id: str = "dev-lock-1",
    pin_options: dict[str, str] | None = None,
) -> HcuDevicePin:
    options = dict(config_entry.options)
    if pin_options is not None:
        options[CONF_DEVICE_PINS] = pin_options
    hass.config_entries.async_update_entry(config_entry, options=options)

    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.data = {}

    client = MagicMock()
    device_data = {
        "id": device_id,
        "label": "Front Door",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "label": "Front Door"},
            "1": {"functionalChannelType": "DOOR_LOCK_CHANNEL", "label": "Lock"},
        },
    }
    entity = HcuDevicePin(coordinator, client, device_data, "1")
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()
    return entity


@pytest.mark.asyncio
async def test_text_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.TEXT: [mock_entity]}
    entry.runtime_data = mock_coordinator

    added = []

    def mock_add_entities(entities: list) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == [mock_entity]

    # Test when no entities
    mock_coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == []


@pytest.mark.asyncio
async def test_device_pin_properties_and_initial_value(hass: HomeAssistant) -> None:
    """Test initial attributes and masked native_value."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    # When no PIN is stored
    entity = _make_device_pin(hass, entry, pin_options={})
    assert entity.unique_id == "dev-lock-1_device_pin"
    assert entity.entity_category == EntityCategory.CONFIG
    assert entity.native_value == ""

    # When PIN is stored
    entity_with_pin = _make_device_pin(hass, entry, pin_options={"dev-lock-1": "1234"})
    assert entity_with_pin.native_value == "****"


@pytest.mark.asyncio
async def test_device_pin_set_new_value(hass: HomeAssistant) -> None:
    """Test updating the PIN with a new value."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    entity = _make_device_pin(hass, entry, pin_options={})
    await entity.async_set_value("5678")

    assert entry.options.get(CONF_DEVICE_PINS, {}).get("dev-lock-1") == "5678"
    assert entity.native_value == "****"
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_device_pin_clear_value(hass: HomeAssistant) -> None:
    """Test clearing the stored PIN by setting empty string."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_DEVICE_PINS: {"dev-lock-1": "1234", "other-dev": "9999"}},
    )
    entry.add_to_hass(hass)

    entity = _make_device_pin(hass, entry)
    await entity.async_set_value("")

    pins = entry.options.get(CONF_DEVICE_PINS, {})
    assert "dev-lock-1" not in pins
    assert pins.get("other-dev") == "9999"
    assert entity.native_value == ""
    entity.async_write_ha_state.assert_called_once()


@pytest.mark.asyncio
async def test_device_pin_unchanged_or_masked_value_skips_update(
    hass: HomeAssistant,
) -> None:
    """Test that submitting the current PIN or masked asterisks does not update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_DEVICE_PINS: {"dev-lock-1": "1234"}},
    )
    entry.add_to_hass(hass)

    entity = _make_device_pin(hass, entry)

    # 1. Exact current pin
    await entity.async_set_value("1234")
    entity.async_write_ha_state.assert_not_called()

    # 2. Asterisks matching current pin length
    await entity.async_set_value("****")
    entity.async_write_ha_state.assert_not_called()

    # Confirm options were unchanged
    assert entry.options[CONF_DEVICE_PINS]["dev-lock-1"] == "1234"
