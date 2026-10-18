"""Tests for Homematic IP HCU options flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.config_flow import HcuOptionsFlowHandler
from custom_components.hcu_integration.const import (
    ATTR_END_TIME,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_ADVANCED_ATTRIBUTES,
    CONF_ADVANCED_DEBUGGING,
    CONF_APP_TOKEN,
    CONF_AUTH_TYPE,
    CONF_AUTO_RELOAD_ON_DEVICE_CHANGE,
    CONF_COMFORT_TEMPERATURE,
    CONF_DEV,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    CONF_DISABLED_GROUPS,
    CONF_DISABLED_OEMS,
    CONF_HA_DEVICES,
    CONF_PLUGIN_TOKEN,
    DOMAIN,
    HUE_MODEL_TOKEN,
    MANUFACTURER_EQ3,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent entry creation from starting real coordinator tasks and sockets."""
    with patch(
        "custom_components.hcu_integration.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


# ---------------------------------------------------------------------------
# Menu (init step)
# ---------------------------------------------------------------------------


async def test_options_flow_init_menu_non_dev(hass: HomeAssistant) -> None:
    """Options flow menu without developer mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={CONF_DEV: False},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == [
        "connection_status",
        "global_settings",
        "vacation",
        "ha_devices",
    ]


async def test_options_flow_init_menu_dev_mode(hass: HomeAssistant) -> None:
    """Options flow menu with developer mode enabled includes developer_settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={CONF_DEV: True},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.MENU
    assert result["step_id"] == "init"
    assert result["menu_options"] == [
        "connection_status",
        "global_settings",
        "developer_settings",
        "vacation",
        "ha_devices",
    ]


# ---------------------------------------------------------------------------
# Connection Status Step
# ---------------------------------------------------------------------------


async def test_options_flow_connection_status_submit(hass: HomeAssistant) -> None:
    """Submitting connection_status creates entry preserving existing options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={CONF_COMFORT_TEMPERATURE: 22.0},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result_form = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"next_step_id": "connection_status"},
    )
    assert result_form["type"] is FlowResultType.FORM
    assert result_form["step_id"] == "connection_status"

    result_saved = await hass.config_entries.options.async_configure(
        result_form["flow_id"],
        user_input={},
    )
    assert result_saved["type"] is FlowResultType.CREATE_ENTRY
    assert result_saved["data"][CONF_COMFORT_TEMPERATURE] == 22.0


async def test_options_flow_connection_status_view_cases(hass: HomeAssistant) -> None:
    """Test connection status view formatting across different auth types and client states."""
    # Case 1: Dual mode with both connected
    entry1 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_APP_TOKEN: "app-tok",
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-1",
    )
    entry1.add_to_hass(hass)
    entry1.mock_state(hass, ConfigEntryState.LOADED)

    mock_client1 = MagicMock()
    mock_client1.is_connected = True
    mock_client1._app_token = "app-tok"
    mock_client1.is_plugin_connected = True
    mock_coord1 = MagicMock()
    mock_coord1.client = mock_client1
    entry1.runtime_data = mock_coord1

    res_init1 = await hass.config_entries.options.async_init(entry1.entry_id)
    res1 = await hass.config_entries.options.async_configure(
        res_init1["flow_id"], user_input={"next_step_id": "connection_status"}
    )
    assert res1["type"] is FlowResultType.FORM
    assert "Connected" in res1["description_placeholders"]["app_status"]
    assert "Connected" in res1["description_placeholders"]["plugin_status"]

    # Case 2: Plugin mode with disconnected client
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-2",
    )
    entry2.add_to_hass(hass)
    entry2.mock_state(hass, ConfigEntryState.LOADED)

    mock_client2 = MagicMock()
    mock_client2.is_connected = False
    mock_coord2 = MagicMock()
    mock_coord2.client = mock_client2
    entry2.runtime_data = mock_coord2

    res_init2 = await hass.config_entries.options.async_init(entry2.entry_id)
    res2 = await hass.config_entries.options.async_configure(
        res_init2["flow_id"], user_input={"next_step_id": "connection_status"}
    )
    assert "not configured" in res2["description_placeholders"]["app_status"].lower()
    assert "Not connected" in res2["description_placeholders"]["plugin_status"]

    # Case 3: App mode without client
    entry3 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            CONF_APP_TOKEN: "app-tok",
        },
        unique_id="hcu-3",
    )
    entry3.add_to_hass(hass)
    entry3.mock_state(hass, ConfigEntryState.LOADED)
    entry3.runtime_data = None

    res_init3 = await hass.config_entries.options.async_init(entry3.entry_id)
    res3 = await hass.config_entries.options.async_configure(
        res_init3["flow_id"], user_input={"next_step_id": "connection_status"}
    )
    assert "Not connected" in res3["description_placeholders"]["app_status"]
    assert "not configured" in res3["description_placeholders"]["plugin_status"].lower()

    # Case 4: Dual mode missing both tokens
    entry4 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
        },
        unique_id="hcu-4",
    )
    entry4.add_to_hass(hass)
    entry4.mock_state(hass, ConfigEntryState.LOADED)
    entry4.runtime_data = None

    res_init4 = await hass.config_entries.options.async_init(entry4.entry_id)
    res4 = await hass.config_entries.options.async_configure(
        res_init4["flow_id"], user_input={"next_step_id": "connection_status"}
    )
    assert "not configured" in res4["description_placeholders"]["app_status"].lower()
    assert "not configured" in res4["description_placeholders"]["plugin_status"].lower()

    # Case 5: Custom/unmapped auth_type
    entry5 = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: "custom_unknown_auth",
        },
        unique_id="hcu-5",
    )
    entry5.add_to_hass(hass)
    entry5.mock_state(hass, ConfigEntryState.LOADED)
    entry5.runtime_data = None

    res_init5 = await hass.config_entries.options.async_init(entry5.entry_id)
    res5 = await hass.config_entries.options.async_configure(
        res_init5["flow_id"], user_input={"next_step_id": "connection_status"}
    )
    assert res5["description_placeholders"]["auth_type_label"] == "custom_unknown_auth"


# ---------------------------------------------------------------------------
# Global Settings Step
# ---------------------------------------------------------------------------


async def test_options_flow_global_settings_view_and_migration(
    hass: HomeAssistant,
) -> None:
    """Global settings view discovers OEMs and groups, and migrates legacy boolean keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={
            "import_Philips_Hue": False,
            "import_somfy": False,
            CONF_COMFORT_TEMPERATURE: 20.5,
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    mock_client = MagicMock()
    mock_client.state = {
        "devices": {
            "d1": {"oem": "Philips Hue"},
            "d2": {"oem": "Somfy"},
        },
        "groups": {
            "g1": {"type": "HEATING"},
        },
    }
    mock_coord = MagicMock()
    mock_coord.client = mock_client
    entry.runtime_data = mock_coord

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    res = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "global_settings"}
    )
    assert res["type"] is FlowResultType.FORM
    assert res["step_id"] == "global_settings"
    assert CONF_DISABLED_OEMS in res["data_schema"].schema
    assert CONF_DISABLED_GROUPS in res["data_schema"].schema
    disabled_oems_marker = next(
        k
        for k in res["data_schema"].schema
        if getattr(k, "schema", None) == CONF_DISABLED_OEMS
    )
    assert set(disabled_oems_marker.default()) == {"Philips Hue", "Somfy"}


async def test_options_flow_global_settings_submit(hass: HomeAssistant) -> None:
    """Submitting global settings saves new options and cleans up legacy keys."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        options={
            "import_old_key": True,
            CONF_COMFORT_TEMPERATURE: 21.0,
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    mock_client = MagicMock()
    mock_client.state = {
        "devices": {"d1": {"oem": "Somfy"}},
        "groups": {"g1": {"type": "HEATING"}},
    }
    mock_client.disconnect = AsyncMock()
    mock_coord = MagicMock()
    mock_coord.client = mock_client
    entry.runtime_data = mock_coord

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "global_settings"}
    )

    user_input = {
        CONF_DISABLE_UNCONFIGURED_CHANNELS: True,
        CONF_AUTO_RELOAD_ON_DEVICE_CHANGE: False,
        CONF_COMFORT_TEMPERATURE: 23.5,
        CONF_DISABLED_OEMS: ["Somfy"],
        CONF_DISABLED_GROUPS: ["HEATING"],
    }

    with patch.object(
        HcuOptionsFlowHandler, "_handle_device_removal", AsyncMock()
    ) as mock_remove:
        res = await hass.config_entries.options.async_configure(
            res_init["flow_id"], user_input=user_input
        )
        mock_remove.assert_called_once_with(["Somfy"])

    assert res["type"] is FlowResultType.CREATE_ENTRY
    saved_opts = res["data"]
    assert saved_opts[CONF_DISABLE_UNCONFIGURED_CHANNELS] is True
    assert saved_opts[CONF_AUTO_RELOAD_ON_DEVICE_CHANGE] is False
    assert saved_opts[CONF_COMFORT_TEMPERATURE] == 23.5
    assert saved_opts[CONF_DISABLED_OEMS] == ["Somfy"]
    assert saved_opts[CONF_DISABLED_GROUPS] == ["HEATING"]
    assert "import_old_key" not in saved_opts


# ---------------------------------------------------------------------------
# Vacation Step
# ---------------------------------------------------------------------------


async def test_options_flow_vacation_client_unavailable(hass: HomeAssistant) -> None:
    """Vacation step aborts if HCU client is unavailable."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10"},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)
    entry.runtime_data = None

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    res = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "vacation"}
    )
    assert res["type"] is FlowResultType.ABORT
    assert res["reason"] == "internal_error"


async def test_options_flow_vacation_view_and_success(hass: HomeAssistant) -> None:
    """Vacation step shows form and activates vacation mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10"},
        options={CONF_COMFORT_TEMPERATURE: 21.0},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    mock_client = MagicMock()
    mock_client.async_activate_vacation = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_coord = MagicMock()
    mock_coord.client = mock_client
    entry.runtime_data = mock_coord

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    res_form = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "vacation"}
    )
    assert res_form["type"] is FlowResultType.FORM
    assert res_form["step_id"] == "vacation"

    await hass.config.async_set_time_zone("Europe/Berlin")
    user_input = {
        ATTR_TEMPERATURE: 18.0,
        ATTR_END_TIME: "2026-12-31T12:00:00+01:00",
    }
    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input=user_input
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    mock_client.async_activate_vacation.assert_awaited_once_with(
        temperature=18.0, end_time="2026_12_31 12:00"
    )
    assert res_saved["data"][CONF_COMFORT_TEMPERATURE] == 21.0


async def test_options_flow_vacation_errors(hass: HomeAssistant) -> None:
    """Vacation step exception handling."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10"},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    mock_client = MagicMock()
    mock_client.disconnect = AsyncMock()
    mock_coord = MagicMock()
    mock_coord.client = mock_client
    entry.runtime_data = mock_coord

    user_input = {
        ATTR_TEMPERATURE: 18.0,
        ATTR_END_TIME: "2026-12-31T12:00:00",
    }

    # 1. HcuApiError -> api_error
    mock_client.async_activate_vacation = AsyncMock(side_effect=HcuApiError("API fail"))
    res_init1 = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init1["flow_id"], user_input={"next_step_id": "vacation"}
    )
    res1 = await hass.config_entries.options.async_configure(
        res_init1["flow_id"], user_input=user_input
    )
    assert res1["errors"] == {"base": "api_error"}

    # 2. ConnectionError -> cannot_connect
    mock_client.async_activate_vacation = AsyncMock(side_effect=ConnectionError())
    res_init2 = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init2["flow_id"], user_input={"next_step_id": "vacation"}
    )
    res2 = await hass.config_entries.options.async_configure(
        res_init2["flow_id"], user_input=user_input
    )
    assert res2["errors"] == {"base": "cannot_connect"}

    # 3. ValueError -> invalid_data
    mock_client.async_activate_vacation = AsyncMock(
        side_effect=ValueError("Invalid date")
    )
    res_init3 = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init3["flow_id"], user_input={"next_step_id": "vacation"}
    )
    res3 = await hass.config_entries.options.async_configure(
        res_init3["flow_id"], user_input=user_input
    )
    assert res3["errors"] == {"base": "invalid_data"}

    # 4. TypeError -> invalid_data
    mock_client.async_activate_vacation = AsyncMock(
        side_effect=TypeError("Invalid type")
    )
    res_init4 = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init4["flow_id"], user_input={"next_step_id": "vacation"}
    )
    res4 = await hass.config_entries.options.async_configure(
        res_init4["flow_id"], user_input=user_input
    )
    assert res4["errors"] == {"base": "invalid_data"}

    # 5. Unexpected Exception -> unknown
    mock_client.async_activate_vacation = AsyncMock(side_effect=RuntimeError("Boom"))
    res_init5 = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init5["flow_id"], user_input={"next_step_id": "vacation"}
    )
    res5 = await hass.config_entries.options.async_configure(
        res_init5["flow_id"], user_input=user_input
    )
    assert res5["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# HA Devices Step (Bridge Management)
# ---------------------------------------------------------------------------


async def test_options_flow_ha_devices_menu(hass: HomeAssistant) -> None:
    """ha_devices menu options when devices list is empty vs populated."""
    # Empty devices
    entry1 = MockConfigEntry(
        domain=DOMAIN, options={CONF_HA_DEVICES: []}, unique_id="hcu-1"
    )
    entry1.add_to_hass(hass)
    res_init1 = await hass.config_entries.options.async_init(entry1.entry_id)
    res1 = await hass.config_entries.options.async_configure(
        res_init1["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    assert res1["menu_options"] == ["ha_devices_add"]

    # Populated devices
    entry2 = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_HA_DEVICES: [{"id": "d1", "name": "Lamp"}]},
        unique_id="hcu-2",
    )
    entry2.add_to_hass(hass)
    res_init2 = await hass.config_entries.options.async_init(entry2.entry_id)
    res2 = await hass.config_entries.options.async_configure(
        res_init2["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    assert res2["menu_options"] == [
        "ha_devices_add",
        "ha_devices_edit",
        "ha_devices_remove",
    ]


async def test_options_flow_ha_devices_add(hass: HomeAssistant) -> None:
    """Adding a new HA device mapping through two phases."""
    entry = MockConfigEntry(
        domain=DOMAIN, options={CONF_HA_DEVICES: []}, unique_id="hcu-1"
    )
    entry.add_to_hass(hass)

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices"}
    )

    # Phase 1: select device_type
    res_phase1 = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices_add"}
    )
    assert res_phase1["type"] is FlowResultType.FORM
    assert "device_type" in res_phase1["data_schema"].schema

    # Submit Phase 1 with device_type='SWITCH' -> shows Phase 2 form
    res_phase2 = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"device_type": "SWITCH"}
    )
    assert res_phase2["type"] is FlowResultType.FORM
    assert "name" in res_phase2["data_schema"].schema
    assert "on_off" in res_phase2["data_schema"].schema

    # Submit Phase 2 -> saves new device
    device_input = {
        "name": "Living Room Socket",
        "on_off": "switch.living_room",
    }
    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input=device_input
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved_devices = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved_devices) == 1
    assert saved_devices[0]["name"] == "Living Room Socket"
    assert saved_devices[0]["type"] == "SWITCH"
    assert saved_devices[0]["features"] == {"on_off": "switch.living_room"}


async def test_options_flow_ha_devices_edit(hass: HomeAssistant) -> None:
    """Editing an existing HA device mapping."""
    # When no devices, direct call redirects
    entry_empty = MockConfigEntry(
        domain=DOMAIN, options={CONF_HA_DEVICES: []}, unique_id="hcu-1"
    )
    entry_empty.add_to_hass(hass)
    flow_empty = HcuOptionsFlowHandler()
    flow_empty.hass = hass
    flow_empty.handler = entry_empty.entry_id
    res_redirect = await flow_empty.async_step_ha_devices_edit()
    assert res_redirect["step_id"] == "ha_devices"

    # Populated devices: Phase 1 selects device
    device1 = {
        "id": "dev-1",
        "name": "Old Switch",
        "type": "SWITCH",
        "features": {"on_off": "switch.old"},
    }
    device_legacy = {
        "id": "dev-2",
        "name": "Door Sensor",
        # type missing, inferred from features (contact_sensor from door)
        "features": {"door": "binary_sensor.front_door"},
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_HA_DEVICES: [device1, device_legacy]},
        unique_id="hcu-2",
    )
    entry.add_to_hass(hass)

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    res_select = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices_edit"}
    )
    assert res_select["type"] is FlowResultType.FORM
    assert "device_id" in res_select["data_schema"].schema

    # Pick device1 -> shows edit form
    res_edit = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"device_id": "dev-1"}
    )
    assert res_edit["type"] is FlowResultType.FORM

    # Submit updated values
    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"],
        user_input={"name": "Updated Switch", "on_off": "switch.new"},
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved_devices = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved_devices) == 2
    assert saved_devices[0]["id"] == "dev-1"
    assert saved_devices[0]["name"] == "Updated Switch"
    assert saved_devices[0]["features"] == {"on_off": "switch.new"}
    assert saved_devices[1] == device_legacy

    # Edit device_legacy with fallback inferred type and legacy feature key
    entry3 = MockConfigEntry(
        domain=DOMAIN,
        options={CONF_HA_DEVICES: [device_legacy]},
        unique_id="hcu-3",
    )
    entry3.add_to_hass(hass)
    res_init3 = await hass.config_entries.options.async_init(entry3.entry_id)
    await hass.config_entries.options.async_configure(
        res_init3["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    await hass.config_entries.options.async_configure(
        res_init3["flow_id"], user_input={"next_step_id": "ha_devices_edit"}
    )
    res_legacy_edit = await hass.config_entries.options.async_configure(
        res_init3["flow_id"], user_input={"device_id": "dev-2"}
    )
    assert res_legacy_edit["type"] is FlowResultType.FORM

    # Test editing_id gone meanwhile (shows selection again)
    flow3 = hass.config_entries.options._progress[res_init3["flow_id"]]
    flow3._editing_device_id = "non-existent-device-id"
    res_reselect = await flow3.async_step_ha_devices_edit()
    assert res_reselect["step_id"] == "ha_devices_edit"
    assert "device_id" in res_reselect["data_schema"].schema


async def test_options_flow_ha_devices_remove(hass: HomeAssistant) -> None:
    """Removing devices from ha_devices."""
    # Direct call redirects when empty
    entry_empty = MockConfigEntry(
        domain=DOMAIN, options={CONF_HA_DEVICES: []}, unique_id="hcu-1"
    )
    entry_empty.add_to_hass(hass)
    flow_empty = HcuOptionsFlowHandler()
    flow_empty.hass = hass
    flow_empty.handler = entry_empty.entry_id
    assert (await flow_empty.async_step_ha_devices_remove())["step_id"] == "ha_devices"

    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_HA_DEVICES: [
                {"id": "dev-1", "name": "Device 1"},
                {"id": "dev-2", "name": "Device 2"},
            ]
        },
        unique_id="hcu-2",
    )
    entry.add_to_hass(hass)

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices"}
    )
    res_form = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "ha_devices_remove"}
    )
    assert res_form["type"] is FlowResultType.FORM
    assert "device_ids" in res_form["data_schema"].schema

    # Submit remove dev-1
    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"device_ids": ["dev-1"]}
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    saved_devices = res_saved["data"][CONF_HA_DEVICES]
    assert len(saved_devices) == 1
    assert saved_devices[0]["id"] == "dev-2"


# ---------------------------------------------------------------------------
# Entity Exclusion in Form Schema
# ---------------------------------------------------------------------------


async def test_options_flow_excluded_entity_ids(hass: HomeAssistant) -> None:
    """Entities belonging to this entry are excluded in device picker."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="hcu-1")
    entry.add_to_hass(hass)

    reg = er.async_get(hass)
    entity_entry1 = reg.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id="switch-1",
        config_entry=entry,
    )
    entity_entry2 = reg.async_get_or_create(
        domain="switch",
        platform="other_domain",
        unique_id="switch-2",
    )

    flow = HcuOptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id

    excluded = flow._excluded_entity_ids()
    assert set(excluded) == {entity_entry1.entity_id}
    assert entity_entry2.entity_id not in excluded


# ---------------------------------------------------------------------------
# Handle Device Removal for Disabled OEMs
# ---------------------------------------------------------------------------


async def test_options_flow_handle_device_removal(hass: HomeAssistant) -> None:
    """Test _handle_device_removal across OEM match, Hue token, and fallback."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="hcu-1")
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    flow = HcuOptionsFlowHandler()
    flow.hass = hass
    flow.handler = entry.entry_id

    # 1. Disabled OEMs empty -> no-op
    await flow._handle_device_removal([])

    # 2. Client is None -> no-op
    entry.runtime_data = None
    await flow._handle_device_removal(["Philips Hue"])

    # 3. Client available -> remove devices matching disabled OEMs
    mock_client = MagicMock()
    mock_coord = MagicMock()
    mock_coord.client = mock_client
    entry.runtime_data = mock_coord

    dev_reg = dr.async_get(hass)
    # Device 1: found in client -> Philips Hue
    d1 = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "addr-1")},
        name="Hue Lamp 1",
    )
    mock_client.get_device_by_address.side_effect = lambda addr: (
        {"oem": "Philips Hue"} if addr == "addr-1" else None
    )

    # Device 2: not in client, model contains HUE_MODEL_TOKEN
    d2 = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "addr-2")},
        name="Hue Lamp 2",
        model=f"Smart bulb {HUE_MODEL_TOKEN}",
    )

    # Device 3: not in client, manufacturer matches
    d3 = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "addr-3")},
        name="Somfy Blind",
        manufacturer="Somfy",
    )

    # Device 4: standard eQ-3 device -> kept
    d4 = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "addr-4")},
        name="Homematic Switch",
        manufacturer=MANUFACTURER_EQ3,
    )

    await flow._handle_device_removal(["Philips Hue", "Somfy"])

    # d1, d2, d3 should be removed, d4 kept
    assert dev_reg.async_get(d1.id) is None
    assert dev_reg.async_get(d2.id) is None
    assert dev_reg.async_get(d3.id) is None
    assert dev_reg.async_get(d4.id) is not None


# ---------------------------------------------------------------------------
# Developer Settings Step
# ---------------------------------------------------------------------------


async def test_options_flow_developer_settings(hass: HomeAssistant) -> None:
    """Developer settings view and update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            CONF_DEV: True,
            CONF_ADVANCED_DEBUGGING: False,
            CONF_ADVANCED_ATTRIBUTES: False,
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    res_init = await hass.config_entries.options.async_init(entry.entry_id)
    # View form
    res_form = await hass.config_entries.options.async_configure(
        res_init["flow_id"], user_input={"next_step_id": "developer_settings"}
    )
    assert res_form["type"] is FlowResultType.FORM
    assert res_form["step_id"] == "developer_settings"
    assert CONF_ADVANCED_DEBUGGING in res_form["data_schema"].schema
    assert CONF_ADVANCED_ATTRIBUTES in res_form["data_schema"].schema

    # Submit form
    res_saved = await hass.config_entries.options.async_configure(
        res_init["flow_id"],
        user_input={
            CONF_ADVANCED_DEBUGGING: True,
            CONF_ADVANCED_ATTRIBUTES: True,
        },
    )
    assert res_saved["type"] is FlowResultType.CREATE_ENTRY
    assert res_saved["data"][CONF_ADVANCED_DEBUGGING] is True
    assert res_saved["data"][CONF_ADVANCED_ATTRIBUTES] is True
