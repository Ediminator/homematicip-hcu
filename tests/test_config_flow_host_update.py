"""Tests for host updates of an already configured HCU from the config flow."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.config_flow import HcuConfigFlow
from custom_components.hcu_integration.const import (
    AUTH_TYPE_PLUGIN,
    CONF_AUTH_TYPE,
    CONF_PLUGIN_TOKEN,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

HCU_ID = "3014F711A0001234567890AB"


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent entry creation from starting real coordinator tasks and sockets."""
    with patch(
        "custom_components.hcu_integration.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


def _existing_entry(hass: HomeAssistant, state: ConfigEntryState) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=HCU_ID,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "old-token",
        },
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, state)
    return entry


async def _set_up_same_hcu_at(hass: HomeAssistant, host: str) -> dict:
    """Run a Plugin User setup that reaches the HCU with the existing SGTIN."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: host}
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"use_app_user": False, "use_plugin_user": True}
    )
    client = MagicMock()
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.listen = AsyncMock()
    client.get_system_state = AsyncMock()
    client.hcu_device_id = HCU_ID
    client.state = {"devices": {}}
    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token"),
        patch.object(HcuConfigFlow, "_async_confirm_auth_token", return_value="cid"),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=client,
        ),
    ):
        return await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "key"}
        )


async def test_loaded_entry_reloads_once_through_its_update_listener(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A loaded entry is reloaded by its update listener only, without a warning."""
    entry = _existing_entry(hass, ConfigEntryState.LOADED)
    listener = AsyncMock()
    entry.async_on_unload(entry.add_update_listener(listener))
    caplog.set_level(logging.WARNING)

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        result = await _set_up_same_hcu_at(hass, "192.0.2.20")
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.20"
    listener.assert_awaited_once_with(hass, entry)
    mock_schedule_reload.assert_not_called()
    assert "has an update listener" not in caplog.text


async def test_retrying_entry_is_reloaded_by_the_flow(hass: HomeAssistant) -> None:
    """An entry whose setup is retried has no listener, so the flow reloads it."""
    entry = _existing_entry(hass, ConfigEntryState.SETUP_RETRY)
    assert not entry.update_listeners

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        result = await _set_up_same_hcu_at(hass, "192.0.2.21")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.21"
    mock_schedule_reload.assert_called_once_with(entry.entry_id)


async def test_same_host_does_not_reload(hass: HomeAssistant) -> None:
    """Nothing is reloaded when the stored host is already correct."""
    entry = _existing_entry(hass, ConfigEntryState.LOADED)
    listener = AsyncMock()
    entry.async_on_unload(entry.add_update_listener(listener))

    with patch.object(
        hass.config_entries, "async_schedule_reload"
    ) as mock_schedule_reload:
        result = await _set_up_same_hcu_at(hass, "192.0.2.10")
        await hass.async_block_till_done()

    assert result["reason"] == "already_configured"
    listener.assert_not_awaited()
    mock_schedule_reload.assert_not_called()
