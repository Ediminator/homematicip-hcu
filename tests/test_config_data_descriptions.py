"""Tests for setup and options form field help texts and removed port strings."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
from pathlib import Path
import re
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_TEMPERATURE, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.hcu_integration.config_flow import HcuConfigFlow
from custom_components.hcu_integration.const import (
    ATTR_END_TIME,
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    CONF_APP_TOKEN,
    CONF_AUTH_TYPE,
    CONF_COMFORT_TEMPERATURE,
    CONF_PLUGIN_TOKEN,
    DOMAIN,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

INTEGRATION_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "hcu_integration"
)

TRANSLATION_FILES = (
    INTEGRATION_DIR / "strings.json",
    INTEGRATION_DIR / "translations" / "en.json",
    INTEGRATION_DIR / "translations" / "de.json",
)

BRIDGE_STEPS = frozenset(
    {
        "ha_devices",
        "ha_devices_add",
        "ha_devices_edit",
        "ha_devices_remove",
    }
)

# Keys stored under step.data that are read as display snippets by config_flow.py
# for description placeholders rather than rendered as form fields.
LABEL_ONLY: dict[str, set[str]] = {
    "reconfigure_auth_type_selection": {
        "status_connected",
        "status_not_connected",
        "status_not_configured",
    },
    "connection_status": {
        "status_connected",
        "status_not_connected",
        "status_not_configured",
        "mode_app",
        "mode_plugin",
        "mode_dual",
    },
}

NEW_HELP_KEYS: tuple[tuple[str, str, str], ...] = (
    ("config", "user", "host"),
    ("config", "auth_type_selection", "use_app_user"),
    ("config", "auth_type_selection", "use_plugin_user"),
    ("config", "auth", "activation_key"),
    ("config", "select_oems", "disabled_oems"),
    ("config", "reconfigure", "host"),
    ("config", "reconfigure_auth", "activation_key"),
    ("config", "reconfigure_auth_type_selection", "auth_type"),
    ("config", "reconfigure_auth_type_selection", "keep_tokens"),
    ("config", "reconfigure_token_options", "refresh_app_token"),
    ("config", "reconfigure_token_options", "refresh_plugin_token"),
    ("options", "vacation", "temperature"),
    ("options", "vacation", "end_time"),
)

STYLE_FORBIDDEN_RE = re.compile(r"—| - | – |[{}]|\*\*|`")
GERMAN_ADDRESS_RE = re.compile(r"\b(du|dir|dich|dein\w*|Sie|Ihnen|Ihr\w*)\b")


def _load_json(path: Path) -> dict[str, Any]:
    """Load and parse a JSON translation file."""
    return json.loads(path.read_text(encoding="utf-8"))


async def _reach_step(
    hass: HomeAssistant, step_id: str, host: str = "192.0.2.20"
) -> dict[str, Any]:
    """Drive the real config or options flow to the requested form step."""
    if step_id == "user":
        return await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

    if step_id == "auth_type_selection":
        res = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        return await hass.config_entries.flow.async_configure(
            res["flow_id"], user_input={CONF_HOST: host}
        )

    if step_id == "auth":
        res = await _reach_step(hass, "auth_type_selection", host=host)
        return await hass.config_entries.flow.async_configure(
            res["flow_id"],
            user_input={"use_app_user": False, "use_plugin_user": True},
        )

    if step_id == "select_oems":
        res = await _reach_step(hass, "auth", host=host)
        mock_client = MagicMock()
        mock_client.is_connected = False
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.listen = AsyncMock()
        mock_client.get_system_state = AsyncMock()
        mock_client.hcu_device_id = "test-unique-hcu"
        mock_client.state = {"devices": {"d1": {"oem": "Philips Hue"}}}
        with (
            patch.object(
                HcuConfigFlow, "_async_get_auth_token", return_value="token123"
            ),
            patch.object(
                HcuConfigFlow, "_async_confirm_auth_token", return_value="client123"
            ),
            patch(
                "custom_components.hcu_integration.config_flow.HcuApiClient",
                return_value=mock_client,
            ),
        ):
            return await hass.config_entries.flow.async_configure(
                res["flow_id"], user_input={"activation_key": "valid-key"}
            )

    if step_id in (
        "reconfigure",
        "reconfigure_auth_type_selection",
        "reconfigure_token_options",
        "reconfigure_auth",
    ):
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
        res = await entry.start_reconfigure_flow(hass)
        if step_id == "reconfigure":
            return res
        res = await hass.config_entries.flow.async_configure(
            res["flow_id"], user_input={CONF_HOST: "192.0.2.10"}
        )
        if step_id == "reconfigure_auth_type_selection":
            return res
        if step_id == "reconfigure_token_options":
            return await hass.config_entries.flow.async_configure(
                res["flow_id"],
                user_input={"auth_type": AUTH_TYPE_DUAL, "keep_tokens": True},
            )
        return await hass.config_entries.flow.async_configure(
            res["flow_id"],
            user_input={"auth_type": AUTH_TYPE_PLUGIN, "keep_tokens": False},
        )

    if step_id in ("vacation", "connection_status"):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_PLUGIN},
            options={CONF_COMFORT_TEMPERATURE: 19.5},
            unique_id="hcu-1",
        )
        entry.add_to_hass(hass)
        entry.mock_state(hass, ConfigEntryState.LOADED)
        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        mock_coord = MagicMock()
        mock_coord.client = mock_client
        entry.runtime_data = mock_coord
        res = await hass.config_entries.options.async_init(entry.entry_id)
        return await hass.config_entries.options.async_configure(
            res["flow_id"], user_input={"next_step_id": step_id}
        )

    raise ValueError(f"Unsupported step_id: {step_id}")


@pytest.mark.parametrize("path", TRANSLATION_FILES, ids=lambda p: p.name)
def test_every_form_field_has_help_text(path: Path) -> None:
    """Every non-bridge setup and options form field has a non-empty help text."""
    data = _load_json(path)
    mismatches: list[str] = []
    for section in ("config", "options"):
        for step_id, step_data in data[section]["step"].items():
            if step_id in BRIDGE_STEPS:
                continue
            data_keys = set(step_data.get("data", {}))
            expected_fields = data_keys - LABEL_ONLY.get(step_id, set())
            descriptions = step_data.get("data_description", {})
            if set(descriptions) != expected_fields:
                mismatches.append(
                    f"{section}.step.{step_id}: "
                    f"missing={sorted(expected_fields - set(descriptions))}, "
                    f"extra={sorted(set(descriptions) - expected_fields)}"
                )
            for key, text in descriptions.items():
                if not isinstance(text, str) or not text.strip():
                    mismatches.append(
                        f"{section}.step.{step_id}.data_description.{key}: empty"
                    )
    assert not mismatches, f"{path.name} mismatches:\n" + "\n".join(mismatches)


@pytest.mark.parametrize("path", TRANSLATION_FILES, ids=lambda p: p.name)
def test_removed_port_fields_have_no_strings(path: Path) -> None:
    """Unused auth_port and websocket_port keys are absent from user and reconfigure."""
    data = _load_json(path)
    for step_id in ("user", "reconfigure"):
        step_data = data["config"]["step"][step_id]
        for subkey in ("data", "data_description"):
            section = step_data.get(subkey, {})
            assert "auth_port" not in section, f"{path.name} {step_id}.{subkey}"
            assert "websocket_port" not in section, f"{path.name} {step_id}.{subkey}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("section", "step_id"),
    [
        ("config", "user"),
        ("config", "auth_type_selection"),
        ("config", "auth"),
        ("config", "select_oems"),
        ("config", "reconfigure"),
        ("config", "reconfigure_auth_type_selection"),
        ("config", "reconfigure_token_options"),
        ("config", "reconfigure_auth"),
        ("options", "vacation"),
        ("options", "connection_status"),
    ],
)
async def test_shown_fields_have_label_and_help_text(
    hass: HomeAssistant, section: str, step_id: str
) -> None:
    """Every field rendered by a real flow step has both data and data_description."""
    result = await _reach_step(hass, step_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id

    fields = {str(key) for key in result["data_schema"].schema}
    step_data = _load_json(INTEGRATION_DIR / "strings.json")[section]["step"][step_id]

    assert fields <= set(step_data.get("data", {}))
    if step_id == "connection_status":
        assert fields == set()
        assert "data_description" not in step_data
    else:
        assert fields == set(step_data.get("data_description", {}))


@pytest.mark.parametrize(
    ("lang", "path"),
    [
        ("en", INTEGRATION_DIR / "translations" / "en.json"),
        ("de", INTEGRATION_DIR / "translations" / "de.json"),
    ],
)
@pytest.mark.parametrize(("section", "step_id", "field"), NEW_HELP_KEYS)
def test_new_help_texts_follow_style(
    lang: str, path: Path, section: str, step_id: str, field: str
) -> None:
    """New help texts follow plain text, punctuation, and German address rules."""
    step_data = _load_json(path)[section]["step"][step_id]
    descriptions = step_data.get("data_description", {})
    assert field in descriptions, f"Missing {section}.step.{step_id}.{field} in {lang}"

    text = descriptions[field]
    assert isinstance(text, str) and text == text.strip() and text.endswith(".")
    assert not STYLE_FORBIDDEN_RE.search(text), (
        f"Forbidden style token in {lang} {section}.{step_id}.{field}: {text!r}"
    )
    if lang == "de":
        assert not GERMAN_ADDRESS_RE.search(text), (
            f"German form of address found in {section}.{step_id}.{field}: {text!r}"
        )


@pytest.mark.asyncio
async def test_help_texts_match_form_defaults(hass: HomeAssistant) -> None:
    """Help texts accurately reflect schema defaults, ranges, and presets."""
    en_data = _load_json(INTEGRATION_DIR / "translations" / "en.json")
    de_data = _load_json(INTEGRATION_DIR / "translations" / "de.json")

    # 1. Vacation: comfort temperature preset, 5..30 range, 7 days ahead preset
    vacation_res = await _reach_step(hass, "vacation")
    vacation_schema = vacation_res["data_schema"].schema
    temp_key = next(k for k in vacation_schema if str(k) == ATTR_TEMPERATURE)
    end_key = next(k for k in vacation_schema if str(k) == ATTR_END_TIME)

    assert temp_key.default() == 19.5
    range_validators = [
        v
        for v in getattr(vacation_schema[temp_key], "validators", ())
        if isinstance(v, vol.Range)
    ]
    assert len(range_validators) == 1
    assert range_validators[0].min == 5.0
    assert range_validators[0].max == 30.0

    parsed_end = datetime.strptime(end_key.default(), "%Y-%m-%d %H:%M")
    expected_end = datetime.now() + timedelta(days=7)
    assert abs(parsed_end - expected_end) <= timedelta(minutes=2)

    for data, seven_word in ((en_data, "seven"), (de_data, "sieben")):
        vac_desc = data["options"]["step"]["vacation"].get("data_description", {})
        assert ATTR_TEMPERATURE in vac_desc
        assert ATTR_END_TIME in vac_desc
        assert re.search(r"\b5\b", vac_desc[ATTR_TEMPERATURE])
        assert re.search(r"\b30\b", vac_desc[ATTR_TEMPERATURE])
        assert seven_word in vac_desc[ATTR_END_TIME].lower()

    # 2. Auth type selection: both defaults are True
    auth_sel_res = await _reach_step(hass, "auth_type_selection")
    auth_sel_schema = auth_sel_res["data_schema"].schema
    for field in ("use_app_user", "use_plugin_user"):
        key = next(k for k in auth_sel_schema if str(k) == field)
        assert key.default() is True

    # 3. Reconfigure auth type selection: keep_tokens default False, auth_type preselected
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.0.2.10", CONF_AUTH_TYPE: AUTH_TYPE_APP},
        unique_id="hcu-app-1",
    )
    entry.add_to_hass(hass)
    reconf_res = await entry.start_reconfigure_flow(hass)
    reconf_sel_res = await hass.config_entries.flow.async_configure(
        reconf_res["flow_id"], user_input={CONF_HOST: "192.0.2.10"}
    )
    reconf_sel_schema = reconf_sel_res["data_schema"].schema
    keep_key = next(k for k in reconf_sel_schema if str(k) == "keep_tokens")
    mode_key = next(k for k in reconf_sel_schema if str(k) == "auth_type")
    assert keep_key.default() is False
    assert mode_key.default() == AUTH_TYPE_APP

    # 4. Select OEMs: default is []
    oems_res = await _reach_step(hass, "select_oems", host="192.0.2.21")
    oems_schema = oems_res["data_schema"].schema
    oems_key = next(k for k in oems_schema if str(k) == "disabled_oems")
    assert oems_key.default() == []


def test_english_translation_equals_strings() -> None:
    """Config and options sections in en.json match strings.json."""
    strings_data = _load_json(INTEGRATION_DIR / "strings.json")
    en_data = _load_json(INTEGRATION_DIR / "translations" / "en.json")
    assert en_data["config"] == strings_data["config"]
    assert en_data["options"] == strings_data["options"]
