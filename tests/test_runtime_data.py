"""Coordinator lookup through config entry runtime data."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.util import (
    get_entry_coordinator,
    iter_coordinators,
)


@pytest.mark.parametrize(
    ("state", "found"),
    [
        (ConfigEntryState.SETUP_IN_PROGRESS, True),
        (ConfigEntryState.LOADED, True),
        (ConfigEntryState.NOT_LOADED, False),
        (ConfigEntryState.SETUP_RETRY, False),
    ],
)
async def test_actions_find_coordinators_during_platform_setup(
    hass: HomeAssistant, state: ConfigEntryState, found: bool
) -> None:
    """Entities exist before the entry is LOADED, so actions must see them then too."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, unique_id="hcu-1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, state)
    coordinator = MagicMock()
    entry.runtime_data = coordinator

    assert get_entry_coordinator(entry) is (coordinator if found else None)
    assert list(iter_coordinators(hass)) == ([coordinator] if found else [])
