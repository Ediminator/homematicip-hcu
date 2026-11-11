"""Tests for SGTIN input handling and the Plugin WebSocket check during setup."""

from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.config_flow import HcuConfigFlow
from custom_components.hcu_integration.const import (
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_APP_TOKEN,
    CONF_AUTH_TYPE,
    CONF_HCU_SGTIN,
    CONF_PLUGIN_TOKEN,
    DOMAIN,
)
from custom_components.hcu_integration.util import (
    compute_client_auth,
    is_valid_sgtin,
    normalize_sgtin,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

COMPONENT_DIR = Path(__file__).parent.parent / "custom_components" / "hcu_integration"

PLAIN_SGTIN = "3014F711A0001234567890AB"
# How the SGTIN is printed on the HCU label, typed in lower case.
LABEL_SGTIN = " 3014-f711-a000-1234-5678-90ab "


def _expected_client_auth(sgtin: str) -> str:
    """CLIENTAUTH as homematicip-rest-api derives it from the access point ID."""
    return (
        hashlib.sha512((sgtin + "jiLpVitHvWnIGD1yo7MA").encode("utf-8"))
        .hexdigest()
        .upper()
    )


@pytest.fixture(autouse=True)
def mock_setup_entry():
    """Prevent entry creation from starting real coordinator tasks and sockets."""
    with patch(
        "custom_components.hcu_integration.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


# ---------------------------------------------------------------------------
# util helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (PLAIN_SGTIN, PLAIN_SGTIN),
        (LABEL_SGTIN, PLAIN_SGTIN),
        ("3014 F711 A000 1234 5678 90AB", PLAIN_SGTIN),
        ("3014f711a0001234567890ab", PLAIN_SGTIN),
        ("\t3014-F711-A000\n1234-5678-90AB", PLAIN_SGTIN),
        ("", ""),
    ],
)
def test_normalize_sgtin(raw: str, expected: str) -> None:
    """Spaces and dashes are removed and letters are upper case."""
    assert normalize_sgtin(raw) == expected


@pytest.mark.parametrize(
    ("value", "valid"),
    [
        (PLAIN_SGTIN, True),
        ("3014F711A000000000000001", True),
        (PLAIN_SGTIN[:-1], False),
        (PLAIN_SGTIN + "0", False),
        ("3014F711A0001234567890AG", False),
        ("3014-F711-A000-1234-5678-90AB", False),
        ("3014f711a0001234567890ab", False),
        ("", False),
    ],
)
def test_is_valid_sgtin(value: str, valid: bool) -> None:
    """Only a normalized 24-character hexadecimal SGTIN is valid."""
    assert is_valid_sgtin(value) is valid


def test_compute_client_auth_matches_rest_api_algorithm() -> None:
    """CLIENTAUTH is the upper-case SHA-512 of SGTIN plus the fixed salt."""
    assert compute_client_auth(PLAIN_SGTIN) == _expected_client_auth(PLAIN_SGTIN)
    assert compute_client_auth(PLAIN_SGTIN) != compute_client_auth(
        "3014-F711-A000-1234-5678-90AB"
    )


# ---------------------------------------------------------------------------
# App User setup: SGTIN input
# ---------------------------------------------------------------------------


async def _start_app_user_setup(hass: HomeAssistant) -> str:
    """Start a fresh App User setup and return the flow id at app_auth_init."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.30"}
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"use_app_user": True, "use_plugin_user": False}
    )
    assert result_auth["step_id"] == "app_auth_init"
    return result_auth["flow_id"]


async def test_app_auth_init_normalizes_label_sgtin(hass: HomeAssistant) -> None:
    """An SGTIN typed as printed on the label is sent and stored in plain form."""
    flow_id = await _start_app_user_setup(hass)
    event = asyncio.Event()
    wait_args: list[tuple] = []

    async def mock_wait_button(self, *args, **kwargs):
        wait_args.append(args)
        await event.wait()
        self._app_new_token = "app-token"
        self._app_new_client_id = "app-client"

    mock_client = MagicMock()
    mock_client.get_system_state = AsyncMock()
    mock_client.hcu_device_id = PLAIN_SGTIN
    mock_client.state = {"devices": {}}

    with (
        patch.object(
            HcuConfigFlow, "_async_connection_request", AsyncMock()
        ) as mock_request,
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=mock_client,
        ) as mock_client_cls,
    ):
        result_confirm = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"sgtin": LABEL_SGTIN}
        )
        assert result_confirm["type"] is FlowResultType.SHOW_PROGRESS

        event.set()
        await hass.async_block_till_done()
        result_done = await hass.config_entries.flow.async_configure(flow_id)

    # connectionRequest: (session, host, port, client_id, client_auth, sgtin, ssl)
    request_args = mock_request.await_args.args
    assert request_args[4] == _expected_client_auth(PLAIN_SGTIN)
    assert request_args[5] == PLAIN_SGTIN
    # Polling for the button uses the same normalized values.
    assert wait_args[0][4] == _expected_client_auth(PLAIN_SGTIN)
    assert wait_args[0][5] == PLAIN_SGTIN
    # The API client of the new entry gets the normalized SGTIN as well.
    assert mock_client_cls.call_args.kwargs["access_point_id"] == PLAIN_SGTIN

    assert result_done["type"] is FlowResultType.CREATE_ENTRY
    assert result_done["data"][CONF_HCU_SGTIN] == PLAIN_SGTIN
    assert result_done["data"][CONF_APP_TOKEN] == "app-token"


@pytest.mark.parametrize(
    "bad_sgtin",
    [
        "3014F711A0001234567890A",  # 23 characters
        "3014F711A0001234567890ABC",  # 25 characters
        "3014-F711-A000-1234-5678-90AZ",  # Z is not hexadecimal
        "my-hcu",
    ],
)
async def test_app_auth_init_rejects_malformed_sgtin(
    hass: HomeAssistant, bad_sgtin: str
) -> None:
    """A value that cannot be an SGTIN is rejected before any request is sent."""
    flow_id = await _start_app_user_setup(hass)

    with patch.object(
        HcuConfigFlow, "_async_connection_request", AsyncMock()
    ) as mock_request:
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"sgtin": bad_sgtin}
        )

    mock_request.assert_not_awaited()
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "app_auth_init"
    assert result["errors"] == {"sgtin": "invalid_sgtin_format"}


async def test_app_auth_init_dashes_only_counts_as_empty(hass: HomeAssistant) -> None:
    """Separators without characters are treated like an empty field."""
    flow_id = await _start_app_user_setup(hass)

    with patch.object(
        HcuConfigFlow, "_async_connection_request", AsyncMock()
    ) as mock_request:
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"sgtin": " - - "}
        )

    mock_request.assert_not_awaited()
    assert result["errors"] == {"sgtin": "sgtin_required"}


async def test_reconfigure_app_auth_init_normalizes_label_sgtin(
    hass: HomeAssistant,
) -> None:
    """Reconfigure to DualBridge sends the SGTIN in plain form, too."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.31",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-reconfigure-sgtin",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.31"}
    )
    res_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": False},
    )
    assert res_init["step_id"] == "reconfigure_app_auth_init"

    event = asyncio.Event()
    wait_args: list[tuple] = []

    async def mock_wait_button(self, *args, **kwargs):
        wait_args.append(args)
        await event.wait()

    with (
        patch.object(
            HcuConfigFlow, "_async_connection_request", AsyncMock()
        ) as mock_request,
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
    ):
        res_confirm = await hass.config_entries.flow.async_configure(
            res_init["flow_id"], user_input={"sgtin": LABEL_SGTIN}
        )
        await asyncio.sleep(0)

        assert res_confirm["type"] is FlowResultType.SHOW_PROGRESS
        request_args = mock_request.await_args.args
        assert request_args[4] == _expected_client_auth(PLAIN_SGTIN)
        assert request_args[5] == PLAIN_SGTIN
        assert wait_args[0][4] == _expected_client_auth(PLAIN_SGTIN)
        assert wait_args[0][5] == PLAIN_SGTIN

        hass.config_entries.flow.async_abort(res_init["flow_id"])
        event.set()
        await hass.async_block_till_done()


async def test_reconfigure_app_auth_init_rejects_malformed_sgtin(
    hass: HomeAssistant,
) -> None:
    """Reconfigure rejects a malformed SGTIN before any request is sent."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.0.2.32",
            CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN,
            CONF_PLUGIN_TOKEN: "plug-tok",
        },
        unique_id="hcu-reconfigure-bad-sgtin",
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, ConfigEntryState.NOT_LOADED)

    result = await entry.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.32"}
    )
    res_init = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": False},
    )

    with patch.object(
        HcuConfigFlow, "_async_connection_request", AsyncMock()
    ) as mock_request:
        res = await hass.config_entries.flow.async_configure(
            res_init["flow_id"], user_input={"sgtin": "3014F711A000"}
        )

    mock_request.assert_not_awaited()
    assert res["step_id"] == "reconfigure_app_auth_init"
    assert res["errors"] == {"sgtin": "invalid_sgtin_format"}


# ---------------------------------------------------------------------------
# Plugin WebSocket check
# ---------------------------------------------------------------------------


def _refused() -> aiohttp.ClientConnectorError:
    """The error aiohttp raises when nothing listens on port 9001."""
    return aiohttp.ClientConnectorError(
        MagicMock(host="192.0.2.40", port=9001, ssl=True),
        ConnectionRefusedError(111, "Connect call failed"),
    )


async def _start_plugin_user_setup(hass: HomeAssistant) -> str:
    """Start a fresh Plugin User setup and return the flow id at the auth step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.40"}
    )
    result_auth = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"use_app_user": False, "use_plugin_user": True}
    )
    assert result_auth["step_id"] == "auth"
    return result_auth["flow_id"]


def _plugin_client() -> MagicMock:
    client = MagicMock()
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.listen = AsyncMock()
    client.get_system_state = AsyncMock()
    client.hcu_device_id = "hcu-plugin-ws"
    client.state = {"devices": {}}
    return client


async def test_plugin_user_refused_websocket_shows_help_step(
    hass: HomeAssistant,
) -> None:
    """A refused port 9001 shows the help step instead of creating an entry."""
    flow_id = await _start_plugin_user_setup(hass)
    client = _plugin_client()
    client.connect.side_effect = _refused()

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token"),
        patch.object(HcuConfigFlow, "_async_confirm_auth_token", return_value="cid"),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"activation_key": "key"}
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "plugin_websocket"
        assert result["errors"] == {}
        placeholders = result["description_placeholders"]
        assert placeholders["hcu_ip"] == "192.0.2.40"
        assert placeholders["port"] == "9001"
        assert "ClientConnectorError" in placeholders["debug_info"]
        client.get_system_state.assert_not_awaited()
        assert not hass.config_entries.async_entries(DOMAIN)

        # Still closed: the same step comes back with an error.
        result_retry = await hass.config_entries.flow.async_configure(
            flow_id, user_input={}
        )
        assert result_retry["step_id"] == "plugin_websocket"
        assert result_retry["errors"] == {"base": "websocket_unreachable"}
        assert not hass.config_entries.async_entries(DOMAIN)

        # Port opened in HCUweb: the next check passes and the entry is created.
        client.connect.side_effect = None
        result_done = await hass.config_entries.flow.async_configure(
            flow_id, user_input={}
        )

    assert result_done["type"] is FlowResultType.CREATE_ENTRY
    assert result_done["data"][CONF_PLUGIN_TOKEN] == "token"
    assert result_done["data"][CONF_AUTH_TYPE] == AUTH_TYPE_PLUGIN
    assert client.connect.await_count == 3
    client.get_system_state.assert_awaited_once()
    client.disconnect.assert_awaited_once()


async def test_plugin_user_websocket_timeout_shows_help_step(
    hass: HomeAssistant,
) -> None:
    """A port that never answers (dropped packets) times out into the help step."""
    flow_id = await _start_plugin_user_setup(hass)
    client = _plugin_client()

    async def hang() -> None:
        await asyncio.Event().wait()

    client.connect.side_effect = hang

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token"),
        patch.object(HcuConfigFlow, "_async_confirm_auth_token", return_value="cid"),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=client,
        ),
        patch(
            "custom_components.hcu_integration.config_flow.WEBSOCKET_CONNECT_TIMEOUT",
            0.01,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"activation_key": "key"}
        )

    assert result["step_id"] == "plugin_websocket"
    assert result["description_placeholders"]["debug_info"] == "`TimeoutError`"
    client.get_system_state.assert_not_awaited()


async def test_plugin_user_other_websocket_error_keeps_fallback(
    hass: HomeAssistant,
) -> None:
    """A rejected handshake is not a closed port: setup continues as before."""
    flow_id = await _start_plugin_user_setup(hass)
    client = _plugin_client()
    client.connect.side_effect = aiohttp.WSServerHandshakeError(
        MagicMock(), (), status=403, message="Forbidden"
    )

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token"),
        patch.object(HcuConfigFlow, "_async_confirm_auth_token", return_value="cid"),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"activation_key": "key"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    client.get_system_state.assert_not_awaited()


async def _dual_setup_at_activation_key(hass: HomeAssistant) -> str:
    """Run the App User part of a DualBridge setup; return the flow id at auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "192.0.2.41"}
    )
    result_init = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"use_app_user": True, "use_plugin_user": True}
    )

    event = asyncio.Event()

    async def mock_wait_button(self, *args, **kwargs):
        await event.wait()
        self._app_new_token = "app-token"
        self._app_new_client_id = "app-client"

    with (
        patch.object(HcuConfigFlow, "_async_connection_request", AsyncMock()),
        patch.object(HcuConfigFlow, "_wait_for_button", mock_wait_button),
    ):
        result_progress = await hass.config_entries.flow.async_configure(
            result_init["flow_id"], user_input={"sgtin": PLAIN_SGTIN}
        )
        assert result_progress["type"] is FlowResultType.SHOW_PROGRESS
        event.set()
        await hass.async_block_till_done()
        result_auth = await hass.config_entries.flow.async_configure(
            result_init["flow_id"]
        )
    assert result_auth["step_id"] == "auth"
    return result_auth["flow_id"]


def _dual_client() -> MagicMock:
    client = MagicMock()
    client.connect_plugin = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    client.get_system_state = AsyncMock()
    client.hcu_device_id = PLAIN_SGTIN
    client.state = {"devices": {}}
    return client


async def test_dual_bridge_refused_plugin_websocket_shows_help_step(
    hass: HomeAssistant,
) -> None:
    """DualBridge also checks port 9001 before the entry is created."""
    flow_id = await _dual_setup_at_activation_key(hass)
    client = _dual_client()
    client.connect_plugin.side_effect = _refused()

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token"),
        patch.object(HcuConfigFlow, "_async_confirm_auth_token", return_value="cid"),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"activation_key": "key"}
        )

        assert result["step_id"] == "plugin_websocket"
        client.get_system_state.assert_not_awaited()
        client.disconnect_plugin.assert_not_awaited()
        assert not hass.config_entries.async_entries(DOMAIN)

        client.connect_plugin.side_effect = None
        result_done = await hass.config_entries.flow.async_configure(
            flow_id, user_input={}
        )

    assert result_done["type"] is FlowResultType.CREATE_ENTRY
    assert result_done["data"][CONF_AUTH_TYPE] == AUTH_TYPE_DUAL
    assert result_done["data"][CONF_HCU_SGTIN] == PLAIN_SGTIN
    client.disconnect_plugin.assert_awaited_once()
    client.get_system_state.assert_awaited_once()


async def test_dual_bridge_open_plugin_websocket_closes_probe(
    hass: HomeAssistant,
) -> None:
    """With port 9001 open, DualBridge closes the probe and reads state over REST."""
    flow_id = await _dual_setup_at_activation_key(hass)
    client = _dual_client()

    with (
        patch.object(HcuConfigFlow, "_async_get_auth_token", return_value="token"),
        patch.object(HcuConfigFlow, "_async_confirm_auth_token", return_value="cid"),
        patch(
            "custom_components.hcu_integration.config_flow.HcuApiClient",
            return_value=client,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id, user_input={"activation_key": "key"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    client.connect_plugin.assert_awaited_once()
    client.disconnect_plugin.assert_awaited_once()
    client.get_system_state.assert_awaited_once()
    client.connect.assert_not_called()


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "restart_hint"),
    [
        ("strings.json", "restart the HCU"),
        ("translations/en.json", "restart the HCU"),
        ("translations/de.json", "starte die HCU neu"),
    ],
)
def test_translations_cover_new_step_and_errors(
    filename: str, restart_hint: str
) -> None:
    """The help step and both new errors exist with the placeholders the code passes."""
    data = json.loads((COMPONENT_DIR / filename).read_text(encoding="utf-8"))
    config = data["config"]
    description = config["step"]["plugin_websocket"]["description"]
    for placeholder in ("{hcu_ip}", "{port}", "{debug_info}"):
        assert placeholder in description
    assert config["error"]["invalid_sgtin_format"]
    # A switch that is on but not effective needs off, HCU restart, on (#520).
    assert restart_hint in description
    assert restart_hint in config["error"]["websocket_unreachable"]
    # The first App User dialog must not ask for the button before OK.
    for step in ("app_auth_init", "reconfigure_app_auth_init"):
        text = config["step"][step]["description"]
        assert text.index("{hcu_ip}") > text.index("OK")
