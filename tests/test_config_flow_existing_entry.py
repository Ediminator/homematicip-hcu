"""Config flows that start from an existing entry (reauth and reconfigure)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN

# The integration depends on zeroconf, which would open real sockets.
pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    return entry


async def test_reauth_shows_connection_mode_form(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Reauth looks up its entry and goes straight to the connection mode step."""
    result = await config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_auth_type_selection"


async def test_reconfigure_shows_host_form_with_current_host(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Reconfigure looks up its entry and prefills the current host."""
    result = await config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["description_placeholders"] == {"hcu_ip": "192.0.2.10"}
