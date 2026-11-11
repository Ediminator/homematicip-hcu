"""Tests for HCU identity verification during config entry reconfiguration."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.config_flow import HcuConfigFlow
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_AUTH_TYPE,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_UNIQUE_PLUGIN_ID,
    DOMAIN,
    PLUGIN_ID,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "hcu_integration"

SGTIN_A = "3014F711A000000000000001"
SGTIN_B = "3014F711A000000000000002"


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent entry creation or reload from starting real coordinator tasks."""
    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ) as mock_setup,
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
    ):
        yield mock_setup


def _make_fake_client(
    reported_hcu_id: str | None = None,
    *,
    get_system_state_error: Exception | None = None,
    connect_error: Exception | None = None,
    is_connected: bool = True,
    hang_listen: bool = False,
) -> tuple[MagicMock, asyncio.Event]:
    """Create a fake HcuApiClient whose get_system_state populates hcu_device_id."""
    client = MagicMock(spec=HcuApiClient)
    client.hcu_device_id = None
    client.is_connected = is_connected
    client.connect = AsyncMock(side_effect=connect_error)
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()

    listen_cancelled = asyncio.Event()
    if hang_listen:

        async def _listen() -> None:
            try:
                await asyncio.sleep(0.2)
            except asyncio.CancelledError:
                listen_cancelled.set()
                raise

        client.listen = AsyncMock(side_effect=_listen)
    else:
        client.listen = AsyncMock()

    async def _get_system_state() -> dict:
        if get_system_state_error is not None:
            raise get_system_state_error
        client.hcu_device_id = reported_hcu_id
        return {"home": {}, "devices": {}}

    client.get_system_state = AsyncMock(side_effect=_get_system_state)
    return client, listen_cancelled


async def _run_reconfigure_e1_keep_tokens(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    new_host: str,
    auth_type: str,
) -> dict:
    """Drive reconfigure flow through E1 (keep tokens, refresh nothing)."""
    result = await entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: new_host},
    )
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reconfigure_auth_type_selection"

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": auth_type, "keep_tokens": True},
    )
    assert result3["type"] is FlowResultType.FORM
    assert result3["step_id"] == "reconfigure_token_options"

    token_input: dict[str, bool] = {}
    if auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
        token_input["refresh_app_token"] = False
    if auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL):
        token_input["refresh_plugin_token"] = False

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=token_input,
    )


async def _run_reconfigure_e2_new_plugin_token(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    new_host: str,
) -> dict:
    """Drive reconfigure flow through E2 (new plugin activation key)."""
    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: new_host},
    )
    res_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_PLUGIN, "keep_tokens": False},
    )
    assert res_auth["step_id"] == "reconfigure_auth"

    with (
        patch.object(
            HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-tok"
        ),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-plugin-cid"
        ),
    ):
        return await hass.config_entries.flow.async_configure(
            res_auth["flow_id"],
            user_input={"activation_key": "valid-key"},
        )


async def _run_reconfigure_e3_new_app_token(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    new_host: str,
    sgtin_input: str = SGTIN_B,
) -> dict:
    """Drive reconfigure flow through E3 (new app token via system button)."""
    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: new_host},
    )
    res_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_APP, "keep_tokens": False},
    )
    assert res_init["step_id"] == "reconfigure_app_auth_init"

    event = asyncio.Event()

    async def _mock_wait_button(self, *args, **kwargs) -> None:
        await event.wait()
        self._app_new_token = "new-app-tok"
        self._app_new_client_id = "new-app-cid"

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", _mock_wait_button),
    ):
        res_confirm = await hass.config_entries.flow.async_configure(
            res_init["flow_id"],
            user_input={"sgtin": sgtin_input},
        )
        assert res_confirm["type"] is FlowResultType.SHOW_PROGRESS
        event.set()
        await hass.async_block_till_done()
        return await hass.config_entries.flow.async_configure(res_confirm["flow_id"])


# ---------------------------------------------------------------------------
# T1 - T11 from SE1 spec
# ---------------------------------------------------------------------------


async def test_keep_tokens_to_different_hcu_aborts(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """T1: E1 (keep tokens) aborts with different_hcu when the new host reports B."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "secret-plugin-tok",
            CONF_PLUGIN_CLIENT_ID: "plug-cid",
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, listen_cancelled = _make_fake_client(SGTIN_B, hang_listen=True)
    caplog.set_level(logging.WARNING)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ) as mock_client_cls:
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    assert dict(entry.data) == original_data
    assert mock_client_cls.call_args.args[1] == "192.0.2.99"
    assert mock_client_cls.call_args.kwargs["plugin_id"] == PLUGIN_ID
    fake_client.connect.assert_awaited_once()
    fake_client.get_system_state.assert_awaited_once()
    fake_client.disconnect.assert_awaited_once()
    assert listen_cancelled.is_set()
    assert any(
        rec.levelno == logging.WARNING and "192.0.2.99" in rec.message
        for rec in caplog.records
    )
    assert "secret-plugin-tok" not in caplog.text


async def test_new_plugin_token_to_different_hcu_aborts(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """T2: E2 (new plugin token) aborts with different_hcu and keeps old data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "old-plugin-tok",
            CONF_PLUGIN_CLIENT_ID: "old-plugin-cid",
            CONF_UNIQUE_PLUGIN_ID: f"{PLUGIN_ID}.abc123",
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, _ = _make_fake_client(SGTIN_B)
    caplog.set_level(logging.WARNING)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ) as mock_client_cls:
        result = await _run_reconfigure_e2_new_plugin_token(hass, entry, "192.0.2.99")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    assert dict(entry.data) == original_data
    assert mock_client_cls.call_args.args[1] == "192.0.2.99"
    assert mock_client_cls.call_args.args[2] == "new-plugin-tok"
    assert mock_client_cls.call_args.kwargs["client_id"] == "new-plugin-cid"
    assert mock_client_cls.call_args.kwargs["plugin_id"] == PLUGIN_ID
    assert "new-plugin-tok" not in caplog.text
    assert "old-plugin-tok" not in caplog.text


async def test_new_app_token_to_different_hcu_aborts(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """T3: E3 (new app token) aborts with different_hcu and keeps old data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            CONF_APP_TOKEN: "old-app-tok",
            CONF_APP_CLIENT_ID: "old-app-cid",
            CONF_HCU_SGTIN: SGTIN_A,
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, _ = _make_fake_client(SGTIN_B)
    caplog.set_level(logging.WARNING)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ) as mock_client_cls:
        result = await _run_reconfigure_e3_new_app_token(
            hass, entry, "192.0.2.99", sgtin_input=SGTIN_B
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    assert dict(entry.data) == original_data
    assert mock_client_cls.call_args.args[1] == "192.0.2.99"
    assert mock_client_cls.call_args.kwargs["app_token"] == "new-app-tok"
    assert mock_client_cls.call_args.kwargs["auth_type"] == AUTH_TYPE_APP
    fake_client.connect.assert_not_called()
    fake_client.get_system_state.assert_awaited_once()
    assert "new-app-tok" not in caplog.text
    assert "old-app-tok" not in caplog.text


@pytest.mark.parametrize(
    ("exit_path", "reported_id"),
    [
        ("e1", SGTIN_A),
        ("e1", SGTIN_A.lower()),
        ("e2", SGTIN_A),
        ("e2", SGTIN_A.lower()),
        ("e3", SGTIN_A),
        ("e3", SGTIN_A.lower()),
    ],
)
async def test_same_hcu_at_new_host_is_saved(
    hass: HomeAssistant,
    exit_path: str,
    reported_id: str,
) -> None:
    """T4: All three exits save when the new host reports the same HCU (any case)."""
    is_app = exit_path == "e3"
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP if is_app else AUTH_TYPE_PLUGIN,
            **(
                {
                    CONF_APP_TOKEN: "old-app-tok",
                    CONF_APP_CLIENT_ID: "old-app-cid",
                    CONF_HCU_SGTIN: SGTIN_A,
                }
                if is_app
                else {
                    CONF_PLUGIN_TOKEN: "old-plugin-tok",
                    CONF_PLUGIN_CLIENT_ID: "old-plugin-cid",
                }
            ),
        },
    )
    entry.add_to_hass(hass)

    fake_client, _ = _make_fake_client(reported_id)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ):
        if exit_path == "e1":
            result = await _run_reconfigure_e1_keep_tokens(
                hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
            )
        elif exit_path == "e2":
            result = await _run_reconfigure_e2_new_plugin_token(
                hass, entry, "192.0.2.99"
            )
        else:
            result = await _run_reconfigure_e3_new_app_token(
                hass, entry, "192.0.2.99", sgtin_input=SGTIN_A
            )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.0.2.99"
    if exit_path == "e2":
        assert entry.data[CONF_PLUGIN_TOKEN] == "new-plugin-tok"
    elif exit_path == "e3":
        assert entry.data[CONF_APP_TOKEN] == "new-app-tok"


async def test_same_hcu_at_new_host_checks_via_expected_transport(
    hass: HomeAssistant,
) -> None:
    """Changed host with known SGTIN verifies via WS for Plugin and REST for App."""
    plugin_entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plugin-tok",
        },
    )
    plugin_entry.add_to_hass(hass)
    plugin_client, _ = _make_fake_client(SGTIN_A)
    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=plugin_client,
    ):
        res = await _run_reconfigure_e1_keep_tokens(
            hass, plugin_entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )
    assert res["reason"] == "reconfigure_successful"
    plugin_client.connect.assert_awaited_once()
    plugin_client.get_system_state.assert_awaited_once()
    plugin_client.disconnect.assert_awaited_once()

    app_entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            CONF_APP_TOKEN: "app-tok",
            CONF_HCU_SGTIN: SGTIN_A,
        },
    )
    app_entry.add_to_hass(hass)
    app_client, _ = _make_fake_client(SGTIN_A.lower())
    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=app_client,
    ):
        res_app = await _run_reconfigure_e1_keep_tokens(
            hass, app_entry, "192.0.2.98", AUTH_TYPE_APP
        )
    assert res_app["reason"] == "reconfigure_successful"
    app_client.connect.assert_not_called()
    app_client.get_system_state.assert_awaited_once()


@pytest.mark.parametrize(
    (
        "get_state_err",
        "connect_err",
        "reported_id",
        "is_connected",
        "expect_disconnect",
    ),
    [
        (HcuApiError("failed"), None, None, True, True),
        (None, OSError("refused"), None, False, False),
        (None, None, None, True, True),
        (TimeoutError(), None, None, False, False),
        (aiohttp.ClientError("net"), None, None, True, True),
    ],
)
async def test_unreadable_new_host_aborts(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    get_state_err: Exception | None,
    connect_err: Exception | None,
    reported_id: str | None,
    is_connected: bool,
    expect_disconnect: bool,
) -> None:
    """T5: Unreadable new host or missing HCU id aborts with cannot_verify_hcu."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "secret-tok",
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, listen_cancelled = _make_fake_client(
        reported_id,
        get_system_state_error=get_state_err,
        connect_error=connect_err,
        is_connected=is_connected,
        hang_listen=connect_err is None,
    )
    caplog.set_level(logging.WARNING)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ):
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_verify_hcu"
    assert dict(entry.data) == original_data
    if expect_disconnect:
        fake_client.disconnect.assert_awaited_once()
    else:
        fake_client.disconnect.assert_not_awaited()
    if connect_err is None:
        assert listen_cancelled.is_set()
    assert any(
        rec.levelno == logging.WARNING and "192.0.2.99" in rec.message
        for rec in caplog.records
    )
    assert "secret-tok" not in caplog.text


async def test_app_user_unreadable_new_host_aborts(hass: HomeAssistant) -> None:
    """App User REST failure during reconfigure check aborts with cannot_verify_hcu."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            CONF_APP_TOKEN: "app-tok",
            CONF_HCU_SGTIN: SGTIN_A,
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, _ = _make_fake_client(
        get_system_state_error=HcuApiError("REST failed")
    )

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ):
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_APP
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_verify_hcu"
    assert dict(entry.data) == original_data
    fake_client.connect.assert_not_called()


async def test_unchanged_host_is_not_checked(hass: HomeAssistant) -> None:
    """T6: Reconfigure with the same host skips the HCU identity check."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "old-plugin-tok",
        },
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient"
    ) as mock_client_cls:
        result = await _run_reconfigure_e2_new_plugin_token(hass, entry, "192.0.2.10")

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    mock_client_cls.assert_not_called()
    assert entry.data[CONF_PLUGIN_TOKEN] == "new-plugin-tok"


@pytest.mark.parametrize("stored_sgtin", [None, "", "not-an-sgtin"])
async def test_unknown_hcu_id_is_not_checked(
    hass: HomeAssistant, stored_sgtin: str | None
) -> None:
    """T7: Entry without SGTIN unique_id, coordinator, or valid stored SGTIN skips check."""
    data = {
        CONF_HOST: "192.0.2.10",
        CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
        CONF_PLUGIN_TOKEN: "plugin-tok",
    }
    if stored_sgtin is not None:
        data[CONF_HCU_SGTIN] = stored_sgtin

    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id="192.0.2.10",
        data=data,
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient"
    ) as mock_client_cls:
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    mock_client_cls.assert_not_called()
    assert entry.data[CONF_HOST] == "192.0.2.99"


async def test_known_id_from_running_entry(hass: HomeAssistant) -> None:
    """T8: Loaded entry with IP unique_id gets its known ID from running coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id="192.0.2.10",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plugin-tok",
        },
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.LOADED)

    running_client = MagicMock(spec=HcuApiClient)
    running_client.hcu_device_id = SGTIN_A
    running_coord = MagicMock()
    running_coord.client = running_client
    entry.runtime_data = running_coord
    original_data = dict(entry.data)

    fake_client, _ = _make_fake_client(SGTIN_B)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ):
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    assert dict(entry.data) == original_data


async def test_known_id_from_stored_sgtin(hass: HomeAssistant) -> None:
    """T9: Unloaded App entry with non-SGTIN unique_id uses stored CONF_HCU_SGTIN."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id="192.0.2.10",
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            CONF_APP_TOKEN: "app-tok",
            CONF_HCU_SGTIN: SGTIN_A,
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, _ = _make_fake_client(SGTIN_B)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ):
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_APP
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    assert dict(entry.data) == original_data
    fake_client.connect.assert_not_called()


async def test_no_reload_after_abort(hass: HomeAssistant) -> None:
    """T10: Aborting reconfigure does not trigger a config entry reload."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plugin-tok",
        },
    )
    entry.add_to_hass(hass)

    fake_client, _ = _make_fake_client(SGTIN_B)

    with (
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=fake_client,
        ),
        patch.object(hass.config_entries, "async_reload", AsyncMock()) as mock_reload,
        patch.object(
            hass.config_entries, "async_schedule_reload"
        ) as mock_schedule_reload,
    ):
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    mock_reload.assert_not_called()
    mock_schedule_reload.assert_not_called()


@pytest.mark.parametrize(
    "filename",
    ["strings.json", "translations/en.json", "translations/de.json"],
)
def test_new_abort_reasons_are_translated(filename: str) -> None:
    """T11: New abort reasons exist and are non-empty in strings and translations."""
    data = json.loads((COMPONENT_DIR / filename).read_text(encoding="utf-8"))
    abort_strings = data["config"]["abort"]
    for key in ("different_hcu", "cannot_verify_hcu"):
        assert key in abort_strings
        assert isinstance(abort_strings[key], str)
        assert abort_strings[key].strip()


async def test_dual_bridge_keep_tokens_uses_rest_and_unique_plugin_id(
    hass: HomeAssistant,
) -> None:
    """DualBridge E1 reads state over REST and preserves CONF_UNIQUE_PLUGIN_ID."""
    unique_pid = f"{PLUGIN_ID}.deadbe"
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
            CONF_APP_TOKEN: "app-tok",
            CONF_HCU_SGTIN: SGTIN_A,
            CONF_PLUGIN_TOKEN: "plug-tok",
            CONF_UNIQUE_PLUGIN_ID: unique_pid,
        },
    )
    entry.add_to_hass(hass)
    original_data = dict(entry.data)

    fake_client, _ = _make_fake_client(SGTIN_B)

    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_client,
    ) as mock_client_cls:
        result = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_DUAL
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "different_hcu"
    assert dict(entry.data) == original_data
    assert mock_client_cls.call_args.kwargs["plugin_id"] == unique_pid
    fake_client.connect.assert_not_called()
    fake_client.get_system_state.assert_awaited_once()


async def test_second_reconfigure_after_abort_succeeds(hass: HomeAssistant) -> None:
    """Starting a second reconfigure flow after an abort succeeds for the same HCU."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        unique_id=SGTIN_A,
        data={
            CONF_HOST: "192.0.2.10",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
    )
    entry.add_to_hass(hass)

    fake_other, _ = _make_fake_client(SGTIN_B)
    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_other,
    ):
        aborted = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.99", AUTH_TYPE_PLUGIN
        )
    assert aborted["type"] is FlowResultType.ABORT
    assert aborted["reason"] == "different_hcu"
    assert entry.data[CONF_HOST] == "192.0.2.10"

    fake_same, _ = _make_fake_client(SGTIN_A)
    with patch(
        "custom_components.hcu_integration.config_flow.HcuApiClient",
        return_value=fake_same,
    ):
        saved = await _run_reconfigure_e1_keep_tokens(
            hass, entry, "192.0.2.50", AUTH_TYPE_PLUGIN
        )
    assert saved["type"] is FlowResultType.ABORT
    assert saved["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.0.2.50"
