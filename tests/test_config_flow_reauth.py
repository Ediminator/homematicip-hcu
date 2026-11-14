"""Tests for the dedicated HCU reauthentication config flow."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    CONF_ZEROCONF_NAME,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "hcu_integration"
SGTIN_1 = "3014F711A000000000000001"


def _make_entry(
    hass: HomeAssistant,
    auth_type: str,
    *,
    unique_id: str = SGTIN_1,
    entry_id: str = "reauth_entry",
) -> MockConfigEntry:
    """Create a MockConfigEntry for reauth testing."""
    data: dict = {
        CONF_HOST: "192.0.2.10",
        CONF_AUTH_TYPE: auth_type,
        CONF_ZEROCONF_NAME: "hcu-mdns._hmip._tcp.local.",
    }
    if auth_type in (AUTH_TYPE_PLUGIN, AUTH_TYPE_DUAL):
        data[CONF_PLUGIN_TOKEN] = "old-plugin-token"
        data[CONF_PLUGIN_CLIENT_ID] = "old-plugin-cid"
    if auth_type in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
        data[CONF_APP_TOKEN] = "old-app-token"
        data[CONF_APP_CLIENT_ID] = "old-app-cid"
        data[CONF_HCU_SGTIN] = SGTIN_1

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Living Room HCU",
        version=7,
        data=data,
        options={"comfort_temperature": 21.5},
        unique_id=unique_id,
        entry_id=entry_id,
    )
    entry.add_to_hass(hass)
    return entry


async def _drive_app_auth(
    hass: HomeAssistant,
    flow_id: str,
    button_event: asyncio.Event,
    *,
    sgtin: str = SGTIN_1,
) -> dict:
    """Drive the App User SGTIN + button confirmation steps."""
    res_init = await hass.config_entries.flow.async_configure(
        flow_id, user_input={"sgtin": sgtin}
    )
    assert res_init["type"] is FlowResultType.SHOW_PROGRESS
    assert res_init["step_id"] == "reconfigure_app_auth_confirm"
    button_event.set()
    await hass.async_block_till_done()
    return await hass.config_entries.flow.async_configure(flow_id)


# ---------------------------------------------------------------------------
# Reauth flow behavior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("auth_type", "expected_label", "expect_switches"),
    [
        (AUTH_TYPE_PLUGIN, "Plugin User", False),
        (AUTH_TYPE_APP, "App User", False),
        (AUTH_TYPE_DUAL, "DualBridge (App + Plugin)", True),
    ],
)
async def test_reauth_starts_at_confirm_step(
    hass: HomeAssistant,
    auth_type: str,
    expected_label: str,
    expect_switches: bool,
) -> None:
    """Reauth opens reauth_confirm with host/auth_mode placeholders and mode-specific fields."""
    entry = _make_entry(hass, auth_type, entry_id=f"f1_{auth_type}")

    result = await entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["description_placeholders"]["host"] == "192.0.2.10"
    assert result["description_placeholders"]["auth_mode"] == expected_label
    schema_keys = {str(k) for k in result["data_schema"].schema}
    if expect_switches:
        assert schema_keys == {"refresh_app_token", "refresh_plugin_token"}
        defaults = {str(key): key.default() for key in result["data_schema"].schema}
        assert defaults == {"refresh_app_token": True, "refresh_plugin_token": True}
    else:
        assert schema_keys == set()


async def test_reauth_plugin_user(hass: HomeAssistant) -> None:
    """Plugin User reauth renews plugin token/client_id and preserves all other fields."""
    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id="f2_plugin")
    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
    ):
        result = await entry.start_reauth_flow(hass)
        res_auth = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert res_auth["type"] is FlowResultType.FORM
        assert res_auth["step_id"] == "reconfigure_auth"

        with (
            patch.object(
                HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-token"
            ),
            patch.object(
                HcuConfigFlow,
                "_async_confirm_auth_token",
                return_value="new-plugin-cid",
            ),
        ):
            res_done = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={"activation_key": "NEW-KEY"}
            )
        await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reauth_successful"
    assert entry.data[CONF_PLUGIN_TOKEN] == "new-plugin-token"
    assert entry.data[CONF_PLUGIN_CLIENT_ID] == "new-plugin-cid"
    assert entry.data[CONF_HOST] == "192.0.2.10"
    assert entry.data[CONF_AUTH_TYPE] == AUTH_TYPE_PLUGIN
    assert entry.data[CONF_ZEROCONF_NAME] == "hcu-mdns._hmip._tcp.local."
    assert entry.options == {"comfort_temperature": 21.5}
    assert entry.title == "Living Room HCU"
    assert entry.unique_id == SGTIN_1


async def test_reauth_app_user(hass: HomeAssistant) -> None:
    """App User reauth renews app token/client_id/SGTIN and ends in reauth_successful."""
    entry = _make_entry(hass, AUTH_TYPE_APP, entry_id="f3_app")
    button_event = asyncio.Event()

    async def fake_wait_for_button(self, *args, **kwargs):
        await button_event.wait()
        self._app_new_token = "new-app-token"
        self._app_new_client_id = "new-app-cid"

    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(
            HcuConfigFlow,
            "_wait_for_button",
            autospec=True,
            side_effect=fake_wait_for_button,
        ),
    ):
        result = await entry.start_reauth_flow(hass)
        res_sgtin = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert res_sgtin["type"] is FlowResultType.FORM
        assert res_sgtin["step_id"] == "reconfigure_app_auth_init"

        res_done = await _drive_app_auth(hass, result["flow_id"], button_event)
        await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reauth_successful"
    assert entry.data[CONF_APP_TOKEN] == "new-app-token"
    assert entry.data[CONF_APP_CLIENT_ID] == "new-app-cid"
    assert entry.data[CONF_HCU_SGTIN] == SGTIN_1
    assert entry.data[CONF_AUTH_TYPE] == AUTH_TYPE_APP
    assert entry.data[CONF_HOST] == "192.0.2.10"
    assert entry.data[CONF_ZEROCONF_NAME] == "hcu-mdns._hmip._tcp.local."
    assert entry.options == {"comfort_temperature": 21.5}


@pytest.mark.parametrize(
    ("refresh_app", "refresh_plugin"),
    [
        (True, True),
        (True, False),
        (False, True),
    ],
)
async def test_reauth_dual(
    hass: HomeAssistant, refresh_app: bool, refresh_plugin: bool
) -> None:
    """DualBridge reauth updates only selected tokens and keeps unselected ones unchanged."""
    entry = _make_entry(
        hass, AUTH_TYPE_DUAL, entry_id=f"f4_{refresh_app}_{refresh_plugin}"
    )
    button_event = asyncio.Event()

    async def fake_wait_for_button(self, *args, **kwargs):
        await button_event.wait()
        self._app_new_token = "new-app-token"
        self._app_new_client_id = "new-app-cid"

    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(
            HcuConfigFlow,
            "_wait_for_button",
            autospec=True,
            side_effect=fake_wait_for_button,
        ),
        patch.object(
            HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-token"
        ),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-plugin-cid"
        ),
    ):
        result = await entry.start_reauth_flow(hass)
        res_next = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                "refresh_app_token": refresh_app,
                "refresh_plugin_token": refresh_plugin,
            },
        )
        if refresh_app:
            assert res_next["step_id"] == "reconfigure_app_auth_init"
            res_next = await _drive_app_auth(hass, result["flow_id"], button_event)
        if refresh_plugin:
            assert res_next["step_id"] == "reconfigure_auth"
            res_next = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input={"activation_key": "NEW-KEY"}
            )
        await hass.async_block_till_done()

    assert res_next["type"] is FlowResultType.ABORT
    assert res_next["reason"] == "reauth_successful"
    assert entry.data[CONF_AUTH_TYPE] == AUTH_TYPE_DUAL
    if refresh_app:
        assert entry.data[CONF_APP_TOKEN] == "new-app-token"
        assert entry.data[CONF_APP_CLIENT_ID] == "new-app-cid"
    else:
        assert entry.data[CONF_APP_TOKEN] == "old-app-token"
        assert entry.data[CONF_APP_CLIENT_ID] == "old-app-cid"
        assert entry.data[CONF_HCU_SGTIN] == SGTIN_1
    if refresh_plugin:
        assert entry.data[CONF_PLUGIN_TOKEN] == "new-plugin-token"
        assert entry.data[CONF_PLUGIN_CLIENT_ID] == "new-plugin-cid"
    else:
        assert entry.data[CONF_PLUGIN_TOKEN] == "old-plugin-token"
        assert entry.data[CONF_PLUGIN_CLIENT_ID] == "old-plugin-cid"


async def test_reauth_dual_nothing_selected(hass: HomeAssistant) -> None:
    """DualBridge reauth rejects submitting with both toggles off."""
    entry = _make_entry(hass, AUTH_TYPE_DUAL, entry_id="f5_none")
    before_data = dict(entry.data)

    result = await entry.start_reauth_flow(hass)
    res_err = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            "refresh_app_token": False,
            "refresh_plugin_token": False,
        },
    )

    assert res_err["type"] is FlowResultType.FORM
    assert res_err["step_id"] == "reauth_confirm"
    assert res_err["errors"] == {"base": "reauth_nothing_selected"}
    assert dict(entry.data) == before_data


@pytest.mark.parametrize("unique_id", [SGTIN_1, "192.0.2.10"])
async def test_reauth_keeps_unique_id_and_devices(
    hass: HomeAssistant, unique_id: str
) -> None:
    """Reauth preserves entry unique_id as well as existing devices and entities."""
    entry = _make_entry(
        hass, AUTH_TYPE_PLUGIN, unique_id=unique_id, entry_id=f"f6_{unique_id}"
    )
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "dev-1")},
        name="Test Switch",
    )
    ent_reg = er.async_get(hass)
    entity = ent_reg.async_get_or_create(
        "switch", DOMAIN, "dev-1_1_on", config_entry=entry, device_id=device.id
    )

    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
        patch.object(
            HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-token"
        ),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-plugin-cid"
        ),
    ):
        result = await entry.start_reauth_flow(hass)
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
        res_done = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"activation_key": "NEW-KEY"}
        )
        await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reauth_successful"
    assert entry.unique_id == unique_id
    assert dev_reg.async_get(device.id) is not None
    kept_entity = ent_reg.async_get(entity.entity_id)
    assert kept_entity is not None
    assert kept_entity.config_entry_id == entry.entry_id


@pytest.mark.parametrize("is_loaded", [True, False])
async def test_reauth_reloads_once(
    hass: HomeAssistant, is_loaded: bool, caplog: pytest.LogCaptureFixture
) -> None:
    """Reauth reloads the entry exactly once and logs no update-listener deprecation."""
    from custom_components.hcu_integration import async_reload_entry

    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id=f"f7_{is_loaded}")
    if is_loaded:
        entry.mock_state(hass, ConfigEntryState.LOADED)
        entry.add_update_listener(async_reload_entry)
    else:
        entry.mock_state(hass, ConfigEntryState.SETUP_ERROR)

    with (
        patch.object(
            hass.config_entries, "async_reload", AsyncMock(return_value=True)
        ) as mock_reload,
        patch.object(
            HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-token"
        ),
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-plugin-cid"
        ),
        caplog.at_level(logging.WARNING),
    ):
        result = await entry.start_reauth_flow(hass)
        await hass.config_entries.flow.async_configure(result["flow_id"], user_input={})
        res_done = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"activation_key": "NEW-KEY"}
        )
        await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reauth_successful"
    assert entry.data[CONF_PLUGIN_TOKEN] == "new-plugin-token"
    assert entry.data[CONF_PLUGIN_CLIENT_ID] == "new-plugin-cid"
    assert entry.title == "Living Room HCU"
    assert entry.unique_id == SGTIN_1
    assert entry.options == {"comfort_temperature": 21.5}
    mock_reload.assert_awaited_once_with(entry.entry_id)
    assert not any("has an update listener" in r.getMessage() for r in caplog.records)


async def test_reauth_token_step_errors_keep_entry(hass: HomeAssistant) -> None:
    """Errors and aborts in the token steps leave the entry data untouched."""
    # 1. Plugin auth errors (invalid_key, cannot_connect)
    entry_plugin = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id="f8_plugin")
    before_plugin = dict(entry_plugin.data)

    res1 = await entry_plugin.start_reauth_flow(hass)
    assert res1["step_id"] == "reauth_confirm"
    step1 = await hass.config_entries.flow.async_configure(
        res1["flow_id"], user_input={}
    )
    assert step1["step_id"] == "reconfigure_auth"

    with patch.object(
        HcuConfigFlow, "_async_get_auth_token", side_effect=ValueError("bad key")
    ):
        bad_key = await hass.config_entries.flow.async_configure(
            res1["flow_id"], user_input={"activation_key": "bad"}
        )
        assert bad_key["type"] is FlowResultType.FORM
        assert bad_key["errors"] == {"base": "invalid_key"}

    with patch.object(
        HcuConfigFlow,
        "_async_get_auth_token",
        side_effect=aiohttp.ClientError("offline"),
    ):
        conn_err = await hass.config_entries.flow.async_configure(
            res1["flow_id"], user_input={"activation_key": "bad"}
        )
        assert conn_err["type"] is FlowResultType.FORM
        assert conn_err["errors"] == {"base": "cannot_connect"}

    assert dict(entry_plugin.data) == before_plugin

    # 2. App auth button timeout aborts without modifying entry
    entry_app = _make_entry(hass, AUTH_TYPE_APP, entry_id="f8_app")
    before_app = dict(entry_app.data)
    timeout_event = asyncio.Event()

    async def timeout_wait_for_button(*args, **kwargs):
        await timeout_event.wait()
        raise TimeoutError("button timeout")

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(
            HcuConfigFlow,
            "_wait_for_button",
            side_effect=timeout_wait_for_button,
        ),
    ):
        res2 = await entry_app.start_reauth_flow(hass)
        assert res2["step_id"] == "reauth_confirm"
        step2 = await hass.config_entries.flow.async_configure(
            res2["flow_id"], user_input={}
        )
        assert step2["step_id"] == "reconfigure_app_auth_init"
        res_prog = await hass.config_entries.flow.async_configure(
            res2["flow_id"], user_input={"sgtin": SGTIN_1}
        )
        assert res_prog["type"] is FlowResultType.SHOW_PROGRESS
        timeout_event.set()
        await hass.async_block_till_done()
        res_timeout = await hass.config_entries.flow.async_configure(res2["flow_id"])

    assert res_timeout["type"] is FlowResultType.ABORT
    assert res_timeout["reason"] == "button_timeout"
    assert dict(entry_app.data) == before_app


async def test_reconfigure_still_ends_with_reconfigure_successful(
    hass: HomeAssistant,
) -> None:
    """Reconfigure flow for the same entry still ends with reconfigure_successful."""
    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id="f9_reconfigure")

    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
    ):
        res = await entry.start_reconfigure_flow(hass)
        await hass.config_entries.flow.async_configure(
            res["flow_id"], user_input={CONF_HOST: "192.0.2.10"}
        )
        await hass.config_entries.flow.async_configure(
            res["flow_id"],
            user_input={"auth_type": AUTH_TYPE_PLUGIN, "keep_tokens": True},
        )
        res_done = await hass.config_entries.flow.async_configure(
            res["flow_id"], user_input={"refresh_plugin_token": False}
        )
        await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reconfigure_successful"


async def test_reauth_uses_updated_host_on_confirm_submit(
    hass: HomeAssistant,
) -> None:
    """If the entry host changes while reauth sits open, submit uses the latest host."""
    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id="reauth_host_refresh")
    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    # Simulate discovery updating the entry's host before the user submits confirm.
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_HOST: "192.0.2.99"}
    )

    with (
        patch(
            "custom_components.hcu_integration.async_setup_entry",
            return_value=True,
        ),
        patch(
            "custom_components.hcu_integration.async_unload_entry",
            return_value=True,
        ),
        patch.object(
            HcuConfigFlow, "_async_get_auth_token", return_value="new-plugin-token"
        ) as mock_get_token,
        patch.object(
            HcuConfigFlow, "_async_confirm_auth_token", return_value="new-plugin-cid"
        ) as mock_confirm_token,
    ):
        res_auth = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )
        assert res_auth["step_id"] == "reconfigure_auth"
        assert res_auth["description_placeholders"]["hcu_ip"] == "192.0.2.99"

        res_done = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={"activation_key": "NEW-KEY"}
        )
        await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reauth_successful"
    assert mock_get_token.call_args.args[1] == "192.0.2.99"
    assert mock_confirm_token.call_args.args[1] == "192.0.2.99"
    assert entry.data[CONF_HOST] == "192.0.2.99"


async def test_rejected_setup_then_reauth_loads_entry(hass: HomeAssistant) -> None:
    """End-to-end: rejected setup opens reauth; completing reauth with valid token loads entry."""
    entry = _make_entry(hass, AUTH_TYPE_PLUGIN, entry_id="f10_e2e")
    session = MagicMock(spec=aiohttp.ClientSession)

    queue: asyncio.Queue[aiohttp.WSMessage | None] = asyncio.Queue()

    class _FakePluginWs:
        closed = False

        async def close(self) -> None:
            self.closed = True
            await queue.put(None)

        async def send_json(self, msg: dict) -> None:
            if msg.get("type") == "HMIP_SYSTEM_REQUEST":
                payload = json.dumps(
                    {
                        "type": "HMIP_SYSTEM_RESPONSE",
                        "id": msg["id"],
                        "body": {"code": 200, "body": state_payload},
                    }
                )
                await queue.put(
                    aiohttp.WSMessage(
                        type=aiohttp.WSMsgType.TEXT, data=payload, extra=None
                    )
                )

        def __aiter__(self):
            return self

        async def __anext__(self):
            item = await queue.get()
            if item is None:
                raise StopAsyncIteration
            return item

    accepted = False
    state_payload = {
        "home": {"id": "home-1", "accessPointId": SGTIN_1},
        "devices": {
            SGTIN_1: {
                "id": SGTIN_1,
                "type": "HOME_CONTROL_ACCESS_POINT",
                "modelType": "HmIP-HCU1",
                "label": "HCU",
                "functionalChannels": {
                    "0": {"functionalChannelType": "DEVICE_BASE"},
                },
            }
        },
        "groups": {},
    }

    async def fake_ws_connect(url: str, headers: dict, **kwargs):
        if not accepted or headers.get("authtoken") != "fresh-plugin-token":
            raise aiohttp.WSServerHandshakeError(
                MagicMock(), (), status=401, message="Invalid response status"
            )
        return _FakePluginWs()

    session.ws_connect = AsyncMock(side_effect=fake_ws_connect)

    with (
        patch(
            "custom_components.hcu_integration.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.hcu_integration.coordinator.getmac.get_mac_address",
            return_value="aa:bb:cc:dd:ee:ff",
        ),
        patch(
            "custom_components.hcu_integration.coordinator.WEBSOCKET_CONNECT_TIMEOUT",
            30,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is False
        await hass.async_block_till_done()

        assert entry.state is ConfigEntryState.SETUP_ERROR
        flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
        assert len(flows) == 1
        flow_id = flows[0]["flow_id"]
        assert flows[0]["context"]["source"] == SOURCE_REAUTH
        assert flows[0]["step_id"] == "reauth_confirm"

        accepted = True
        with (
            patch.object(
                HcuConfigFlow,
                "_async_get_auth_token",
                return_value="fresh-plugin-token",
            ),
            patch.object(
                HcuConfigFlow, "_async_confirm_auth_token", return_value="fresh-cid"
            ),
        ):
            res_auth = await hass.config_entries.flow.async_configure(
                flow_id, user_input={}
            )
            assert res_auth["step_id"] == "reconfigure_auth"
            res_done = await hass.config_entries.flow.async_configure(
                flow_id, user_input={"activation_key": "VALID-KEY"}
            )
            await hass.async_block_till_done()

    assert res_done["type"] is FlowResultType.ABORT
    assert res_done["reason"] == "reauth_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []

    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def test_reauth_texts_exist() -> None:
    """Verify reauth_confirm and reauth_nothing_selected strings exist in all translation files."""
    for rel_path in (
        "strings.json",
        "translations/en.json",
        "translations/de.json",
    ):
        data = json.loads((COMPONENT_DIR / rel_path).read_text(encoding="utf-8"))
        step = data["config"]["step"]["reauth_confirm"]
        assert "{host}" in step["description"]
        assert "{auth_mode}" in step["description"]
        assert "refresh_app_token" in step["data"]
        assert "refresh_plugin_token" in step["data"]
        assert "refresh_app_token" in step["data_description"]
        assert "refresh_plugin_token" in step["data_description"]
        assert "reauth_nothing_selected" in data["config"]["error"]
