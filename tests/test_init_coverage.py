"""Coverage tests for __init__.py of the Homematic IP Local (HCU) integration."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration import (
    async_migrate_entry,
    async_reload_entry,
    async_setup,
    async_setup_entry,
    async_unload_entry,
    event,
)
from custom_components.hcu_integration.const import (
    AUTH_TYPE_PLUGIN,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_AUTH_PORT,
    CONF_AUTH_TYPE,
    CONF_DEV,
    CONF_DEVICE_PINS,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    CONF_ENTITY_PREFIX,
    CONF_HA_DEVICES,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_UNIQUE_PLUGIN_ID,
    CONF_WEBSOCKET_PORT,
    DEFAULT_DEV,
    DEFAULT_DISABLE_UNCONFIGURED_CHANNELS,
    DOMAIN,
)
from custom_components.hcu_integration.coordinator import HcuCoordinator


async def test_async_setup(hass: HomeAssistant):
    """Test async_setup registers services."""
    with patch("custom_components.hcu_integration.async_register_services") as mock_reg:
        result = await async_setup(hass, {})
        assert result is True
        mock_reg.assert_called_once_with(hass)


async def test_async_migrate_entry_version_greater_than_7(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Test migrating a config entry with version > 7 downgrades to 7."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=9,
        data={CONF_HOST: "192.168.1.10"},
        options={},
    )
    entry.add_to_hass(hass)

    with caplog.at_level(logging.WARNING):
        res = await async_migrate_entry(hass, entry)

    assert res is True
    assert entry.version == 7
    assert any(
        "Config entry is from a newer version (9) — downgrading to v7" in r.message
        for r in caplog.records
    )


async def test_async_migrate_entry_v1_to_v7(hass: HomeAssistant):
    """Test migrating a v1 config entry all the way to v7."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_AUTH_PORT: 8080,
            CONF_WEBSOCKET_PORT: 8081,
            "system_pin": "1234",
            "token": "my-plugin-token",
            "client_id": "my-client-id",
            "access_point_id": "3014F711A000000000000001",
            "pin": "9999",
            CONF_ENTITY_PREFIX: "OldPrefix_",
        },
        options={},
    )
    entry.add_to_hass(hass)

    res = await async_migrate_entry(hass, entry)
    assert res is True
    assert entry.version == 7

    data = entry.data
    # Removed keys
    assert CONF_AUTH_PORT not in data
    assert CONF_WEBSOCKET_PORT not in data
    assert "system_pin" not in data
    assert "pin" not in data
    assert CONF_ENTITY_PREFIX not in data

    # Renamed keys
    assert data[CONF_PLUGIN_TOKEN] == "my-plugin-token"
    assert data[CONF_PLUGIN_CLIENT_ID] == "my-client-id"
    assert data[CONF_HCU_SGTIN] == "3014F711A000000000000001"

    # Default keys
    assert data[CONF_AUTH_TYPE] == AUTH_TYPE_PLUGIN
    assert data[CONF_APP_TOKEN] == ""
    assert data[CONF_APP_CLIENT_ID] == ""

    # Options defaults
    assert (
        entry.options[CONF_DISABLE_UNCONFIGURED_CHANNELS]
        == DEFAULT_DISABLE_UNCONFIGURED_CHANNELS
    )
    assert entry.options[CONF_DEV] == DEFAULT_DEV

    # Prefix removal issue created
    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(DOMAIN, f"entity_prefix_removed_{entry.entry_id}")
    assert issue is not None
    assert issue.translation_placeholders == {"prefix": "OldPrefix_"}


async def test_async_migrate_entry_v1_without_access_point_id(hass: HomeAssistant):
    """Test migrating a v1 entry without access_point_id populates default empty HCU SGTIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_HOST: "192.168.1.10",
            "token": "my-plugin-token",
        },
    )
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is True
    assert CONF_HCU_SGTIN in entry.data
    assert entry.data[CONF_HCU_SGTIN] == ""


async def test_async_setup_entry_with_unique_plugin_id_and_event_entities(
    hass: HomeAssistant,
):
    """Test setup entry instantiates client with custom plugin_id and registers event entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={
            CONF_HOST: "192.168.1.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_UNIQUE_PLUGIN_ID: "de.eq3.custom_plugin_id",
        },
        options={
            CONF_HA_DEVICES: ["light.living_room"],
        },
    )
    entry.add_to_hass(hass)

    mock_client = MagicMock()
    mock_client.plugin_id = "de.eq3.custom_plugin_id"
    mock_client.state = {"devices": {}}
    mock_client._send_message = AsyncMock()
    mock_client.set_ha_entity_bridge = MagicMock()
    mock_client.disconnect = AsyncMock()

    mock_bridge = MagicMock()
    mock_bridge.start_listening = MagicMock()
    mock_bridge.stop_listening = MagicMock()

    mock_event_entity = MagicMock(spec=event.TriggerableEvent)
    mock_event_entity._device_id = "dev_event_1"
    mock_event_entity._channel_index_str = "1"

    mock_non_triggerable_entity = MagicMock()
    mock_non_triggerable_entity._device_id = "dev_event_2"

    discovered_entities = {
        Platform.EVENT: [mock_event_entity, mock_non_triggerable_entity],
    }

    with (
        patch(
            "custom_components.hcu_integration.HcuApiClient",
            return_value=mock_client,
        ) as mock_client_cls,
        patch(
            "custom_components.hcu_integration.HaEntityBridge",
            return_value=mock_bridge,
        ),
        patch.object(HcuCoordinator, "async_setup", AsyncMock(return_value=True)),
        patch(
            "custom_components.hcu_integration.async_discover_entities",
            AsyncMock(return_value=discovered_entities),
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            AsyncMock(return_value=True),
        ),
    ):
        result = await async_setup_entry(hass, entry)
        assert result is True

    # Verify HcuApiClient received plugin_id
    assert mock_client_cls.call_args.kwargs["plugin_id"] == "de.eq3.custom_plugin_id"

    coordinator = entry.runtime_data
    assert coordinator is not None
    assert coordinator._ha_bridge is mock_bridge
    # Verify event entity was indexed and non-triggerable entity was ignored
    assert ("dev_event_1", "1") in coordinator._event_entities
    assert coordinator._event_entities[("dev_event_1", "1")] is mock_event_entity
    assert len(coordinator._event_entities) == 1

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        assert await async_unload_entry(hass, entry) is True
    mock_bridge.stop_listening.assert_called_once()
    mock_client.disconnect.assert_awaited_once()


async def test_async_unload_entry_stops_bridge_and_disconnects(hass: HomeAssistant):
    """Test async_unload_entry stops bridge and disconnects client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_HOST: "192.168.1.10"},
    )
    entry.add_to_hass(hass)

    mock_bridge = MagicMock()
    mock_client = MagicMock()
    mock_client.disconnect = AsyncMock()

    coordinator = MagicMock()
    coordinator.client = mock_client
    coordinator._ha_bridge = mock_bridge
    entry.runtime_data = coordinator

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        AsyncMock(return_value=True),
    ):
        res = await async_unload_entry(hass, entry)
        assert res is True

    mock_bridge.stop_listening.assert_called_once()
    mock_client.disconnect.assert_awaited_once()


async def test_async_reload_entry_skips_when_only_pins_changed(hass: HomeAssistant):
    """Test async_reload_entry skips reload if only device PINs changed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_HOST: "192.168.1.10"},
        options={CONF_DEVICE_PINS: {"dev1": "1234"}},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    coordinator = MagicMock()
    coordinator.client.disconnect = AsyncMock()
    coordinator._previous_data = {CONF_HOST: "192.168.1.10"}
    coordinator._previous_options = {CONF_DEVICE_PINS: {"dev1": "0000"}}
    entry.runtime_data = coordinator

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await async_reload_entry(hass, entry)
        mock_reload.assert_not_called()
    assert coordinator._previous_data == {CONF_HOST: "192.168.1.10"}
    assert coordinator._previous_options == {CONF_DEVICE_PINS: {"dev1": "1234"}}

    # If other data/options changed as well, reload should be called
    hass.config_entries.async_update_entry(
        entry,
        data={CONF_HOST: "192.168.1.20"},
        options={CONF_DEVICE_PINS: {"dev1": "5678"}, CONF_DEV: True},
    )
    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await async_reload_entry(hass, entry)
        mock_reload.assert_awaited_once_with(entry.entry_id)
    assert coordinator._previous_data == {CONF_HOST: "192.168.1.20"}
    assert coordinator._previous_options == {
        CONF_DEVICE_PINS: {"dev1": "5678"},
        CONF_DEV: True,
    }


async def test_async_reload_entry_when_coordinator_is_none(hass: HomeAssistant):
    """Test async_reload_entry calls async_reload when coordinator is None."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={CONF_HOST: "192.168.1.10"},
    )
    entry.add_to_hass(hass)
    entry.runtime_data = None

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload:
        await async_reload_entry(hass, entry)
        mock_reload.assert_awaited_once_with(entry.entry_id)
