"""Tests for Homematic IP HCU config flow."""

from __future__ import annotations

import asyncio
import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState, UnknownEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.config_flow import (
    HcuConfigFlow,
    HcuOptionsFlowHandler,
    async_will_remove_config_entry,
    get_groups,
    get_third_party_oems,
)
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_AUTH_TYPE,
    CONF_DEV,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_UNIQUE_PLUGIN_ID,
    DOMAIN,
    MANUFACTURER_EQ3,
    MANUFACTURER_HUE,
    PLUGIN_ID,
    PLUGIN_ID_HUE,
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
# Module level helper functions & options flow getter
# ---------------------------------------------------------------------------


async def test_async_will_remove_config_entry(hass: HomeAssistant) -> None:
    """Removal hook logs a warning about token revocation."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.0.2.10"})
    with patch(
        "custom_components.hcu_integration.config_flow._LOGGER.warning"
    ) as mock_warn:
        await async_will_remove_config_entry(hass, entry)
        mock_warn.assert_called_once()


def test_async_get_options_flow() -> None:
    """Get options flow handler for config entry."""
    entry = MockConfigEntry(domain=DOMAIN)
    handler = HcuConfigFlow.async_get_options_flow(entry)
    assert isinstance(handler, HcuOptionsFlowHandler)


def test_get_third_party_oems() -> None:
    """Discover third party OEMs filters out eQ-3 using OEM and plugin identifiers."""
    assert get_third_party_oems(None) == set()

    client = MagicMock()
    client.state = None
    assert get_third_party_oems(client) == set()

    client.state = {
        "devices": {
            "d1": {"oem": MANUFACTURER_EQ3},
            "d2": {"pluginId": PLUGIN_ID_HUE},
            "d3": {"oem": "Somfy"},
        }
    }
    assert get_third_party_oems(client) == {MANUFACTURER_HUE, "Somfy"}


def test_get_groups() -> None:
    """Filter group types to only supported ones."""
    assert get_groups(None) == set()

    client = MagicMock()
    client.state = {}
    assert get_groups(client) == set()

    client.state = {
        "groups": {
            "g1": {"type": "HEATING"},
            "g2": {"type": "UNSUPPORTED_TYPE_XYZ"},
            "g3": {},
        }
    }
    assert get_groups(client) == {"HEATING"}


# ---------------------------------------------------------------------------
# Zeroconf Discovery Flow
# ---------------------------------------------------------------------------


async def test_zeroconf_no_ipv4(hass: HomeAssistant) -> None:
    """Abort zeroconf flow if no IPv4 address is present."""
    flow = HcuConfigFlow()
    flow.hass = hass

    discovery_info = MagicMock(spec=ZeroconfServiceInfo)
    discovery_info.addresses = ["not-an-ip", "2001:db8::1"]

    result = await flow.async_step_zeroconf(discovery_info)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_ipv4_address"


async def test_zeroconf_success_and_confirm(hass: HomeAssistant) -> None:
    """Zeroconf flow discovers device and proceeds through confirm."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address("192.0.2.10"),
        ip_addresses=[ipaddress.ip_address("192.0.2.10")],
        port=80,
        hostname="hcu.local.",
        type="_hmip._tcp.local.",
        name="HCU._hmip._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"host": "192.0.2.10"}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth_type_selection"


async def test_zeroconf_already_configured_by_unique_id(hass: HomeAssistant) -> None:
    """Zeroconf aborts if unique_id is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="hcu.local.",
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address("192.0.2.10"),
        ip_addresses=[ipaddress.ip_address("192.0.2.10")],
        port=80,
        hostname="hcu.local.",
        type="_hmip._tcp.local.",
        name="HCU._hmip._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_already_configured_by_host_match(hass: HomeAssistant) -> None:
    """Zeroconf aborts if host matches an existing entry even with different unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="different.local.",
        data={CONF_HOST: "192.0.2.10"},
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ipaddress.ip_address("192.0.2.10"),
        ip_addresses=[ipaddress.ip_address("192.0.2.10")],
        port=80,
        hostname="hcu.local.",
        type="_hmip._tcp.local.",
        name="HCU._hmip._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# User Step & Auth Type Selection Flow
# ---------------------------------------------------------------------------


async def test_user_step_shows_form_and_submits(hass: HomeAssistant) -> None:
    """User flow prompts for host, then moves to auth_type_selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth_type_selection"


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """User step aborts if host matches configured unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="192.0.2.20",
        data={CONF_HOST: "192.0.2.20"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_auth_type_selection_neither_selected(hass: HomeAssistant) -> None:
    """Selecting neither App User nor Plugin User returns validation error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": False},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "auth_type_selection"
    assert result3["errors"] == {"base": "select_at_least_one"}


async def test_auth_type_selection_plugin_only(hass: HomeAssistant) -> None:
    """Selecting only Plugin User navigates directly to auth step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": True},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "auth"


async def test_auth_type_selection_app_only(hass: HomeAssistant) -> None:
    """Selecting only App User navigates to app_auth_init step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": False},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "app_auth_init"


async def test_auth_type_selection_dual(hass: HomeAssistant) -> None:
    """Selecting both App and Plugin User sets dual setup and navigates to app_auth_init."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": True},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "app_auth_init"


# ---------------------------------------------------------------------------
# App Auth Init & Confirm Steps
# ---------------------------------------------------------------------------


async def test_app_auth_init_prefill_and_errors(hass: HomeAssistant) -> None:
    """Test app_auth_init form prefill and network errors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.20", CONF_HCU_SGTIN: "3014F711A000000000000099"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user", "entry_id": entry.entry_id},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": False},
    )
    assert result_auth["type"] is FlowResultType.FORM
    assert result_auth["step_id"] == "app_auth_init"

    # 1. HTTP error
    err = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=500, message="Internal Error"
    )
    with patch.object(HcuConfigFlow, "_async_connection_request", side_effect=err):
        result_err1 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert result_err1["errors"] == {"base": "cannot_connect"}

    # 2. ClientError / Timeout
    with patch.object(
        HcuConfigFlow,
        "_async_connection_request",
        side_effect=aiohttp.ClientError("Network error"),
    ):
        result_err2 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert result_err2["errors"] == {"base": "cannot_connect"}

    # 3. Unexpected exception
    with patch.object(
        HcuConfigFlow,
        "_async_connection_request",
        side_effect=RuntimeError("Boom"),
    ):
        result_err3 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert result_err3["errors"] == {"base": "unknown"}


async def test_app_auth_confirm_progress_and_timeout(hass: HomeAssistant) -> None:
    """App auth confirmation shows progress then handles timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": False},
    )

    event = asyncio.Event()

    async def mock_wait_for_button_hanging(*args, **kwargs):
        await event.wait()
        raise TimeoutError("Button not pressed")

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_for_button_hanging),
    ):
        result_confirm = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        # Progress step is shown while task is running
        assert result_confirm["type"] is FlowResultType.SHOW_PROGRESS
        assert result_confirm["step_id"] == "app_auth_confirm"

        # Release task with timeout
        event.set()
        await hass.async_block_till_done()

        # Task done handler triggers timeout abort
        result_done = await hass.config_entries.flow.async_configure(
            result_confirm["flow_id"]
        )
        assert result_done["type"] is FlowResultType.ABORT
        assert result_done["reason"] == "button_timeout"


async def test_app_auth_confirm_success_app_only(hass: HomeAssistant) -> None:
    """Successful app auth confirmation for app-only setup transitions to select_oems."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": False},
    )

    event = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event.wait()
        self._app_new_token = "app-token-123"
        self._app_new_client_id = "client-id-123"

    mock_client = MagicMock()
    mock_client.get_system_state = AsyncMock()
    mock_client.hcu_device_id = "test-hcu"
    mock_client.state = {"devices": {}}

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ),
    ):
        result_confirm = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert result_confirm["type"] is FlowResultType.SHOW_PROGRESS

        event.set()
        await hass.async_block_till_done()

        result_done = await hass.config_entries.flow.async_configure(
            result_confirm["flow_id"]
        )
        assert result_done["type"] is FlowResultType.CREATE_ENTRY
        assert result_done["data"][CONF_APP_TOKEN] == "app-token-123"


async def test_app_auth_confirm_success_dual(hass: HomeAssistant) -> None:
    """Successful app auth confirmation for dual setup transitions to auth step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": True},
    )

    event = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event.wait()
        self._app_new_token = "app-token-123"
        self._app_new_client_id = "client-id-123"

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
    ):
        result_confirm = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert result_confirm["type"] is FlowResultType.SHOW_PROGRESS

        event.set()
        await hass.async_block_till_done()

        result_done = await hass.config_entries.flow.async_configure(
            result_confirm["flow_id"]
        )
        assert result_done["type"] is FlowResultType.FORM
        assert result_done["step_id"] == "auth"


async def test_button_timeout_step_direct_abort(hass: HomeAssistant) -> None:
    """Direct call to async_step_button_timeout aborts."""
    flow = HcuConfigFlow()
    flow.hass = hass
    result = await flow.async_step_button_timeout()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "button_timeout"


# ---------------------------------------------------------------------------
# Auth Step (Plugin Activation Key)
# ---------------------------------------------------------------------------


async def test_auth_step_errors(hass: HomeAssistant) -> None:
    """Test auth step exception handlers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": True},
    )

    # 1. ClientResponseError -> cannot_connect
    err_http = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=401, message="Unauthorized"
    )
    with patch.object(HcuConfigFlow, "_async_get_auth_token", side_effect=err_http):
        res = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res["errors"] == {"base": "cannot_connect"}

    # 2. TimeoutError -> cannot_connect
    with patch.object(
        HcuConfigFlow, "_async_get_auth_token", side_effect=TimeoutError()
    ):
        res = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res["errors"] == {"base": "cannot_connect"}

    # 3. ValueError -> invalid_key
    with patch.object(
        HcuConfigFlow, "_async_get_auth_token", side_effect=ValueError("invalid")
    ):
        res = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res["errors"] == {"base": "invalid_key"}

    # 4. Unexpected Exception -> unknown
    with patch.object(
        HcuConfigFlow, "_async_get_auth_token", side_effect=RuntimeError("crash")
    ):
        res = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res["errors"] == {"base": "unknown"}


# ---------------------------------------------------------------------------
# Select OEMs Step
# ---------------------------------------------------------------------------


async def test_select_oems_plugin_auth_uses_websocket(hass: HomeAssistant) -> None:
    """Plugin auth mode connects via websocket during OEM selection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": True},
    )

    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.listen = AsyncMock()
    mock_client.get_system_state = AsyncMock()
    mock_client.hcu_device_id = "test-hcu-id"
    mock_client.state = {"devices": {}}

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token123"),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="client123"
        ),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ),
    ):
        result_oems = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"activation_key": "valid-key"},
        )

    mock_client.connect.assert_awaited_once()
    mock_client.disconnect.assert_awaited_once()
    assert result_oems["type"] is FlowResultType.CREATE_ENTRY
    assert result_oems["data"][CONF_PLUGIN_TOKEN] == "token123"
    assert result_oems["data"][CONF_AUTH_TYPE] == AUTH_TYPE_PLUGIN


async def test_select_oems_connection_error_fallback(hass: HomeAssistant) -> None:
    """Connection error during OEM selection logs warning and creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": True},
    )

    mock_client = MagicMock()
    mock_client.connect = AsyncMock(side_effect=HcuApiError("Connection failed"))

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token123"),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="client123"
        ),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ),
    ):
        result_entry = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"activation_key": "valid-key"},
        )

    assert result_entry["type"] is FlowResultType.CREATE_ENTRY


async def test_select_oems_form_and_submission(hass: HomeAssistant) -> None:
    """When third party OEMs are found, select_oems form is shown and saved in options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": True},
    )

    mock_client = MagicMock()
    mock_client.is_connected = False
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.listen = AsyncMock()
    mock_client.get_system_state = AsyncMock()
    mock_client.hcu_device_id = "test-unique-hcu"
    mock_client.state = {
        "devices": {
            "d1": {"oem": "Philips Hue"},
        }
    }

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token123"),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="client123"
        ),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ),
    ):
        result_form = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"activation_key": "valid-key"},
        )

        assert result_form["type"] is FlowResultType.FORM
        assert result_form["step_id"] == "select_oems"

        result_final = await hass.config_entries.flow.async_configure(
            result_form["flow_id"],
            user_input={"disabled_oems": ["Philips Hue"]},
        )
        assert result_final["type"] is FlowResultType.CREATE_ENTRY
        assert result_final["options"] == {"disabled_oems": ["Philips Hue"]}


async def test_select_oems_already_configured_by_hcu_device_id_via_app_auth(
    hass: HomeAssistant,
) -> None:
    """If client.hcu_device_id is already configured, select_oems aborts cleanly."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="existing-hcu-id",
        data={CONF_HOST: "192.0.2.20"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": True, "use_plugin_user": False},
    )

    event = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event.wait()
        self._app_new_token = "app-token"
        self._app_new_client_id = "client-id"

    mock_client = MagicMock()
    mock_client.get_system_state = AsyncMock()
    mock_client.hcu_device_id = "existing-hcu-id"
    mock_client.state = {"devices": {}}

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ),
    ):
        result_confirm = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert result_confirm["type"] is FlowResultType.SHOW_PROGRESS

        event.set()
        await hass.async_block_till_done()

        result_abort = await hass.config_entries.flow.async_configure(
            result_confirm["flow_id"]
        )
        assert result_abort["type"] is FlowResultType.ABORT
        assert result_abort["reason"] == "already_configured"


@pytest.mark.xfail(
    strict=True,
    reason="bug: async_step_auth catches AbortFlow from async_step_select_oems and shows unknown error instead of aborting",
)
async def test_select_oems_already_configured_by_hcu_device_id_via_plugin_auth(
    hass: HomeAssistant,
) -> None:
    """Demonstrates bug: AbortFlow in select_oems is swallowed by async_step_auth's broad except."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="existing-hcu-id",
        data={CONF_HOST: "192.0.2.20"},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.20"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"use_app_user": False, "use_plugin_user": True},
    )

    mock_client = MagicMock()
    mock_client.is_connected = False
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.listen = AsyncMock()
    mock_client.get_system_state = AsyncMock()
    mock_client.hcu_device_id = "existing-hcu-id"
    mock_client.state = {"devices": {}}

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token123"),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="client123"
        ),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ),
    ):
        result_abort = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"],
            user_input={"activation_key": "valid-key"},
        )
        assert result_abort["type"] is FlowResultType.ABORT
        assert result_abort["reason"] == "already_configured"


# ---------------------------------------------------------------------------
# Reauth & Reconfigure Flows
# ---------------------------------------------------------------------------


async def test_reauth_unknown_entry_raises(hass: HomeAssistant) -> None:
    """_get_context_entry raises UnknownEntry if entry_id is not in registry."""
    flow = HcuConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": "non-existent"}
    with pytest.raises(UnknownEntry):
        flow._get_context_entry()


async def test_reauth_flow_starts(hass: HomeAssistant) -> None:
    """Reauth flow loads entry and moves directly to auth type selection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure_auth_type_selection"


async def test_reconfigure_submits_host(hass: HomeAssistant) -> None:
    """Reconfigure submits host and moves to auth type selection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.99"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_auth_type_selection"


async def test_reconfigure_auth_type_selection_status_display(
    hass: HomeAssistant,
) -> None:
    """Check status labels for connection modes in reconfigure_auth_type_selection."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_APP_TOKEN: "app-tok",
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    mock_client = MagicMock()
    mock_client.is_connected = True
    mock_client._app_token = "app-tok"
    mock_client.is_plugin_connected = True
    mock_coord = MagicMock()
    mock_coord.client = mock_client
    entry.runtime_data = mock_coord

    result = await entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_auth_type_selection"
    assert "app_status" in result2["description_placeholders"]
    assert "plugin_status" in result2["description_placeholders"]


async def test_reconfigure_auth_type_selection_status_not_configured(
    hass: HomeAssistant,
) -> None:
    """When APP or PLUGIN token is missing, status displays not_configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            # no APP token
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    result = await entry.start_reconfigure_flow(hass)
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_auth_type_selection"


async def test_reconfigure_auth_type_selection_keep_tokens_false(
    hass: HomeAssistant,
) -> None:
    """When keep_tokens=False, tokens are cleared and flow routes to auth init."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "old-token",
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )

    # 1. Choose APP or DUAL -> routes to reconfigure_app_auth_init
    result_app = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_APP, "keep_tokens": False},
    )
    assert result_app["type"] is FlowResultType.FORM
    assert result_app["step_id"] == "reconfigure_app_auth_init"

    # 2. Choose PLUGIN -> routes to reconfigure_auth
    result_plug_flow = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result_plug_flow["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    result_plug = await hass.config_entries.flow.async_configure(
        result_plug_flow["flow_id"],
        user_input={"auth_type": AUTH_TYPE_PLUGIN, "keep_tokens": False},
    )
    assert result_plug["type"] is FlowResultType.FORM
    assert result_plug["step_id"] == "reconfigure_auth"


async def test_reconfigure_token_options_flow(hass: HomeAssistant) -> None:
    """When keep_tokens=True, token options step lets user refresh specific tokens."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_APP_TOKEN: "app-tok",
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    # Start reconfigure and select keep_tokens=True
    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    result_tokens = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": True},
    )
    assert result_tokens["type"] is FlowResultType.FORM
    assert result_tokens["step_id"] == "reconfigure_token_options"

    # 1. Refresh app token
    result_refresh_app = await hass.config_entries.flow.async_configure(
        result_tokens["flow_id"],
        user_input={"refresh_app_token": True, "refresh_plugin_token": False},
    )
    assert result_refresh_app["type"] is FlowResultType.FORM
    assert result_refresh_app["step_id"] == "reconfigure_app_auth_init"

    # 2. Refresh neither -> aborts reconfigure_successful immediately
    result2 = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"auth_type": AUTH_TYPE_APP, "keep_tokens": True},
    )
    result_saved = await hass.config_entries.flow.async_configure(
        result2["flow_id"],
        user_input={"refresh_app_token": False},
    )
    assert result_saved["type"] is FlowResultType.ABORT
    assert result_saved["reason"] == "reconfigure_successful"
    assert CONF_PLUGIN_TOKEN not in entry.data

    # 3. Refresh plugin token
    result3 = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={"auth_type": AUTH_TYPE_PLUGIN, "keep_tokens": True},
    )
    result_refresh_plug = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        user_input={"refresh_plugin_token": True},
    )
    assert result_refresh_plug["type"] is FlowResultType.FORM
    assert result_refresh_plug["step_id"] == "reconfigure_auth"


async def test_reconfigure_app_auth_flow_complete(hass: HomeAssistant) -> None:
    """Full reconfigure app auth cycle: init, confirm, and finalize."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_HCU_SGTIN: "3014F711A000000000000001",
            CONF_APP_TOKEN: "old-app-tok",
            CONF_PLUGIN_TOKEN: "old-plug-tok",
            CONF_PLUGIN_CLIENT_ID: "old-plug-cid",
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    result_app_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": False},
    )
    assert result_app_init["step_id"] == "reconfigure_app_auth_init"

    # Test error handlers in reconfigure_app_auth_init
    with patch.object(
        HcuConfigFlow,
        "_async_connection_request",
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=400, message="Bad Request"
        ),
    ):
        res_err1 = await hass.config_entries.flow.async_configure(
            result_app_init["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_err1["errors"] == {"base": "cannot_connect"}

    with patch.object(
        HcuConfigFlow,
        "_async_connection_request",
        side_effect=aiohttp.ClientError("Conn error"),
    ):
        res_err2 = await hass.config_entries.flow.async_configure(
            result_app_init["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_err2["errors"] == {"base": "cannot_connect"}

    with patch.object(
        HcuConfigFlow,
        "_async_connection_request",
        side_effect=RuntimeError("Crash"),
    ):
        res_err3 = await hass.config_entries.flow.async_configure(
            result_app_init["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_err3["errors"] == {"base": "unknown"}

    # Now test confirmation timeout
    event_timeout = asyncio.Event()

    async def mock_wait_timeout(self, *args, **kwargs):
        await event_timeout.wait()
        raise TimeoutError("Timeout waiting for button")

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_timeout),
    ):
        res_conf = await hass.config_entries.flow.async_configure(
            result_app_init["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_conf["type"] is FlowResultType.SHOW_PROGRESS
        assert res_conf["step_id"] == "reconfigure_app_auth_confirm"

        event_timeout.set()
        await hass.async_block_till_done()

        res_timeout = await hass.config_entries.flow.async_configure(
            res_conf["flow_id"]
        )
        assert res_timeout["type"] is FlowResultType.ABORT
        assert res_timeout["reason"] == "button_timeout"

    # Test successful reconfigure app auth finalize with reload
    event_success = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event_success.wait()
        self._app_new_token = "new-app-token"
        self._app_new_client_id = "new-app-client-id"

    result_restart = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result_restart["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    result_app_init2 = await hass.config_entries.flow.async_configure(
        result_restart["flow_id"],
        user_input={"auth_type": AUTH_TYPE_APP, "keep_tokens": False},
    )

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload", AsyncMock()
        ) as mock_reload,
    ):
        res_conf2 = await hass.config_entries.flow.async_configure(
            result_app_init2["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_conf2["type"] is FlowResultType.SHOW_PROGRESS

        event_success.set()
        await hass.async_block_till_done()

        res_final = await hass.config_entries.flow.async_configure(res_conf2["flow_id"])
        assert res_final["type"] is FlowResultType.ABORT
        assert res_final["reason"] == "reconfigure_successful"
        assert entry.data[CONF_APP_TOKEN] == "new-app-token"
        await hass.async_block_till_done()
        mock_reload.assert_called_once_with(entry.entry_id)


async def test_reconfigure_app_auth_dual_keep_plugin(hass: HomeAssistant) -> None:
    """Reconfigure app auth in dual mode with keep_plugin_token preserved."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_APP_TOKEN: "old-app-tok",
            CONF_PLUGIN_TOKEN: "kept-plugin-tok",
            CONF_PLUGIN_CLIENT_ID: "kept-plugin-cid",
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": True},
    )
    result_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"refresh_app_token": True, "refresh_plugin_token": False},
    )

    event = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event.wait()
        self._app_new_token = "new-app-tok"
        self._app_new_client_id = "new-app-cid"

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
    ):
        res_conf = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_conf["type"] is FlowResultType.SHOW_PROGRESS

        event.set()
        await hass.async_block_till_done()

        res_fin = await hass.config_entries.flow.async_configure(res_conf["flow_id"])
        assert res_fin["type"] is FlowResultType.ABORT
        assert res_fin["reason"] == "reconfigure_successful"
        assert entry.data[CONF_APP_TOKEN] == "new-app-tok"
        assert entry.data[CONF_PLUGIN_TOKEN] == "kept-plugin-tok"
        assert entry.data[CONF_PLUGIN_CLIENT_ID] == "kept-plugin-cid"


async def test_reconfigure_app_auth_dual_refresh_plugin_advances_to_auth(
    hass: HomeAssistant,
) -> None:
    """Reconfigure app auth in dual mode without keeping plugin advances to reconfigure_auth."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_APP_TOKEN: "old-app-tok",
            CONF_PLUGIN_TOKEN: "old-plug-tok",
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    result_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": False},
    )

    event = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event.wait()
        self._app_new_token = "new-app-tok"
        self._app_new_client_id = "new-app-cid"

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
    ):
        res_conf = await hass.config_entries.flow.async_configure(
            result_init["flow_id"],
            user_input={"sgtin": "3014F711A000000000000001"},
        )
        assert res_conf["type"] is FlowResultType.SHOW_PROGRESS

        event.set()
        await hass.async_block_till_done()

        res_auth = await hass.config_entries.flow.async_configure(res_conf["flow_id"])
        assert res_auth["type"] is FlowResultType.FORM
        assert res_auth["step_id"] == "reconfigure_auth"


async def test_reconfigure_auth_dev_mode_and_errors(hass: HomeAssistant) -> None:
    """Test reconfigure_auth with developer mode, dual setup, and error cases."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "old-token",
        },
        options={CONF_DEV: True},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_PLUGIN, "keep_tokens": False},
    )

    # 1. Error cases
    with patch.object(
        HcuConfigFlow,
        "_async_get_auth_token",
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(), history=(), status=403, message="Forbidden"
        ),
    ):
        res1 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res1["errors"] == {"base": "cannot_connect"}

    with patch.object(
        HcuConfigFlow,
        "_async_get_auth_token",
        side_effect=aiohttp.ClientError("Conn error"),
    ):
        res2 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res2["errors"] == {"base": "cannot_connect"}

    with patch.object(
        HcuConfigFlow,
        "_async_get_auth_token",
        side_effect=ValueError("bad key format"),
    ):
        res3 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res3["errors"] == {"base": "invalid_key"}

    with patch.object(
        HcuConfigFlow,
        "_async_get_auth_token",
        side_effect=RuntimeError("unexpected"),
    ):
        res4 = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "bad-key"}
        )
        assert res4["errors"] == {"base": "unknown"}

    # 2. Success with dev mode: generates CONF_UNIQUE_PLUGIN_ID
    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="new-tok"),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-cid"
        ),
    ):
        res_ok = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "valid-key"}
        )
        assert res_ok["type"] is FlowResultType.ABORT
        assert res_ok["reason"] == "reconfigure_successful"
        assert entry.data[CONF_PLUGIN_TOKEN] == "new-tok"
        assert entry.data[CONF_PLUGIN_CLIENT_ID] == "new-cid"
        assert CONF_UNIQUE_PLUGIN_ID in entry.data
        assert entry.data[CONF_UNIQUE_PLUGIN_ID].startswith(f"{PLUGIN_ID}.")


async def test_reconfigure_auth_non_dev_mode_dual(hass: HomeAssistant) -> None:
    """Reconfigure auth with dev=False in dual setup preserves app tokens and removes unique_plugin_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_UNIQUE_PLUGIN_ID: "old-unique-id",
            CONF_APP_TOKEN: "kept-app-tok",
            CONF_HCU_SGTIN: "kept-sgtin",
            CONF_APP_CLIENT_ID: "kept-app-cid",
        },
        options={CONF_DEV: False},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "192.0.2.10"},
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": True},
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"refresh_app_token": False, "refresh_plugin_token": True},
    )

    with (
        patch.object(
            HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-tok"
        ),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-plugin-cid"
        ),
    ):
        res_ok = await hass.config_entries.flow.async_configure(
            result_auth["flow_id"], user_input={"activation_key": "valid-key"}
        )
        assert res_ok["type"] is FlowResultType.ABORT
        assert res_ok["reason"] == "reconfigure_successful"
        assert entry.data[CONF_PLUGIN_TOKEN] == "new-plugin-tok"
        assert entry.data[CONF_APP_TOKEN] == "kept-app-tok"
        assert entry.data[CONF_HCU_SGTIN] == "kept-sgtin"
        assert CONF_UNIQUE_PLUGIN_ID not in entry.data


# ---------------------------------------------------------------------------
# Private Helper Methods & Device Name
# ---------------------------------------------------------------------------


def test_get_device_name(hass: HomeAssistant) -> None:
    """Test device name resolution across dev and non-dev modes."""
    flow = HcuConfigFlow()
    flow.hass = hass

    # Non-dev mode without entry
    assert flow._get_device_name(with_timestamp=False) == "Home Assistant"
    assert "Home Assistant - " in flow._get_device_name(with_timestamp=True)

    # Dev mode with entry and location_name
    hass.config.location_name = "My Test House"
    entry = MockConfigEntry(domain=DOMAIN, options={CONF_DEV: True})
    flow.reauth_entry = entry
    assert flow._get_device_name(with_timestamp=False) == "My Test House"

    # Dev mode looked up via context entry_id
    entry.add_to_hass(hass)
    flow.reauth_entry = None
    flow.context = {"entry_id": entry.entry_id}
    assert flow._get_device_name(with_timestamp=False) == "My Test House"

    # Dev mode without location_name
    hass.config.location_name = ""
    assert flow._get_device_name(with_timestamp=False) == "Home Assistant"


async def test_wait_for_button_acknowledged_and_timeout(hass: HomeAssistant) -> None:
    """Test _wait_for_button polling loop."""
    flow = HcuConfigFlow()
    flow.hass = hass
    session = MagicMock(spec=aiohttp.ClientSession)

    # 1. Acknowledged on first poll
    with (
        patch.object(
            flow, "_async_is_request_acknowledged", AsyncMock(return_value=True)
        ),
        patch.object(
            flow, "_async_request_app_auth_token", AsyncMock(return_value="tok1")
        ),
        patch.object(
            flow, "_async_confirm_app_auth_token", AsyncMock(return_value="cid1")
        ),
    ):
        await flow._wait_for_button(
            session,
            "192.0.2.10",
            6969,
            "cid",
            "auth",
            "sgtin",
            None,
            timeout=2,
            interval=1,
        )
        assert flow._app_new_token == "tok1"
        assert flow._app_new_client_id == "cid1"

    # 2. Timeout when not acknowledged
    with (
        patch.object(
            flow, "_async_is_request_acknowledged", AsyncMock(return_value=False)
        ),
        patch("asyncio.sleep", AsyncMock()),
        pytest.raises(TimeoutError, match="not pressed within"),
    ):
        await flow._wait_for_button(
            session,
            "192.0.2.10",
            6969,
            "cid",
            "auth",
            "sgtin",
            None,
            timeout=2,
            interval=1,
        )


async def test_async_connection_request(hass: HomeAssistant) -> None:
    """Test _async_connection_request with system PIN and response error."""
    flow = HcuConfigFlow()
    flow.hass = hass

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.raise_for_status = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=mock_ctx)

    # Success with system_pin
    await flow._async_connection_request(
        session, "192.0.2.10", 6969, "cid", "auth", "sgtin", None, system_pin="1234"
    )
    call_kwargs = session.post.call_args[1]
    assert call_kwargs["headers"]["PIN"] == "1234"

    # Response not ok
    mock_resp.ok = False
    mock_resp.text = AsyncMock(return_value="Error details")
    mock_resp.status = 400
    mock_resp.raise_for_status.side_effect = aiohttp.ClientResponseError(
        request_info=MagicMock(), history=(), status=400
    )
    with pytest.raises(aiohttp.ClientResponseError):
        await flow._async_connection_request(
            session, "192.0.2.10", 6969, "cid", "auth", "sgtin", None
        )


async def test_async_is_request_acknowledged(hass: HomeAssistant) -> None:
    """Test _async_is_request_acknowledged status codes."""
    flow = HcuConfigFlow()
    flow.hass = hass

    mock_resp = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=mock_ctx)

    mock_resp.status = 200
    assert (
        await flow._async_is_request_acknowledged(
            session, "192.0.2.10", 6969, "cid", "auth", "sgtin", None
        )
        is True
    )

    mock_resp.status = 404
    assert (
        await flow._async_is_request_acknowledged(
            session, "192.0.2.10", 6969, "cid", "auth", "sgtin", None
        )
        is False
    )


async def test_async_request_and_confirm_app_auth_token(hass: HomeAssistant) -> None:
    """Test _async_request_app_auth_token and _async_confirm_app_auth_token error handling."""
    flow = HcuConfigFlow()
    flow.hass = hass

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.text = AsyncMock(return_value="error")
    mock_resp.status = 400
    mock_resp.raise_for_status = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=mock_ctx)

    # 1. request token - missing authToken raises ValueError
    mock_resp.json = AsyncMock(return_value={})
    with pytest.raises(ValueError, match="No authToken"):
        await flow._async_request_app_auth_token(
            session, "192.0.2.10", 6969, "cid", "auth", "sgtin", None
        )

    # 2. confirm token - missing clientId raises ValueError
    mock_resp.json = AsyncMock(return_value={})
    with pytest.raises(ValueError, match="HCU did not confirm"):
        await flow._async_confirm_app_auth_token(
            session, "192.0.2.10", 6969, "cid", "auth", "tok", "sgtin", None
        )


async def test_async_get_and_confirm_auth_token(hass: HomeAssistant) -> None:
    """Test _async_get_auth_token and _async_confirm_auth_token error handling."""
    flow = HcuConfigFlow()
    flow.hass = hass

    mock_resp = MagicMock()
    mock_resp.ok = False
    mock_resp.text = AsyncMock(return_value="error")
    mock_resp.status = 400
    mock_resp.raise_for_status = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=mock_ctx)

    # 1. get_auth_token - missing authToken raises ValueError
    mock_resp.json = AsyncMock(return_value={})
    with pytest.raises(ValueError, match="No authToken"):
        await flow._async_get_auth_token(session, "192.0.2.10", 6969, "key", None)

    # 2. confirm_auth_token - missing clientId raises ValueError
    mock_resp.json = AsyncMock(return_value={})
    with pytest.raises(ValueError, match="HCU did not confirm"):
        await flow._async_confirm_auth_token(
            session, "192.0.2.10", 6969, "key", "tok", None
        )


async def test_reconfigure_auth_type_selection_context_title_placeholders(
    hass: HomeAssistant,
) -> None:
    """If title_placeholders not in context, it gets initialized."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    flow = HcuConfigFlow()
    flow.hass = hass
    flow.context = {"entry_id": entry.entry_id}
    res = await flow.async_step_reconfigure_auth_type_selection()
    assert res["type"] is FlowResultType.FORM
    assert flow.context["title_placeholders"] == {"host": "192.0.2.10"}


async def test_async_token_methods_success(hass: HomeAssistant) -> None:
    """Test happy path return values of token helpers."""
    flow = HcuConfigFlow()
    flow.hass = hass

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.raise_for_status = MagicMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    session = MagicMock(spec=aiohttp.ClientSession)
    session.post = MagicMock(return_value=mock_ctx)

    # 1. _async_request_app_auth_token
    mock_resp.json = AsyncMock(return_value={"authToken": "app-token"})
    tok = await flow._async_request_app_auth_token(
        session, "192.0.2.10", 6969, "cid", "auth", "sgtin", None
    )
    assert tok == "app-token"

    # 2. _async_confirm_app_auth_token
    mock_resp.json = AsyncMock(return_value={"clientId": "app-client-id"})
    cid = await flow._async_confirm_app_auth_token(
        session, "192.0.2.10", 6969, "cid", "auth", "app-token", "sgtin", None
    )
    assert cid == "app-client-id"

    # 3. _async_get_auth_token
    mock_resp.json = AsyncMock(return_value={"authToken": "plugin-token"})
    ptok = await flow._async_get_auth_token(session, "192.0.2.10", 6969, "key", None)
    assert ptok == "plugin-token"

    # 4. _async_confirm_auth_token
    mock_resp.json = AsyncMock(return_value={"clientId": "plugin-client-id"})
    pcid = await flow._async_confirm_auth_token(
        session, "192.0.2.10", 6969, "key", "plugin-token", None
    )
    assert pcid == "plugin-client-id"
