"""Unit tests for translations, icons, strings.json parity, and diagnostics redaction."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from custom_components.hcu_integration.const import (
    CONF_ACCESS_POINT_ID,
    CONF_APP_CLIENT_ID,
    CONF_APP_TOKEN,
    CONF_CLIENT_ID,
    CONF_DEVICE_PINS,
    CONF_HCU_SGTIN,
    CONF_PIN,
    CONF_PLUGIN_CLIENT_ID,
    CONF_PLUGIN_TOKEN,
    CONF_ZEROCONF_NAME,
    DOMAIN,
)
from custom_components.hcu_integration.diagnostics import (
    async_get_config_entry_diagnostics,
)

INTEGRATION_DIR = (
    Path(__file__).resolve().parent.parent
    / "custom_components"
    / "hcu_integration"
)


def _flatten_keys(data: dict, prefix: str = "") -> set[str]:
    """Return a set of dotted key paths for a nested dictionary."""
    keys: set[str] = set()
    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key
        keys.add(path)
        if isinstance(value, dict):
            keys |= _flatten_keys(value, path)
    return keys


def test_translations_and_strings_json_parity() -> None:
    """Verify strings.json exists and shares identical keys with en.json and de.json."""
    strings_path = INTEGRATION_DIR / "strings.json"
    en_path = INTEGRATION_DIR / "translations" / "en.json"
    de_path = INTEGRATION_DIR / "translations" / "de.json"

    assert strings_path.is_file(), "strings.json must exist"
    strings_data = json.loads(strings_path.read_text(encoding="utf-8"))
    en_data = json.loads(en_path.read_text(encoding="utf-8"))
    de_data = json.loads(de_path.read_text(encoding="utf-8"))

    strings_keys = _flatten_keys(strings_data)
    en_keys = _flatten_keys(en_data)
    de_keys = _flatten_keys(de_data)

    assert strings_keys == en_keys
    assert en_keys == de_keys

    # Required entity translation keys
    assert "entity.binary_sensor.hcu_door.state.on" in en_keys
    assert "entity.binary_sensor.hcu_door.state.off" in en_keys
    assert "entity.update.hcu_firmware.name" in en_keys


def test_icons_json_completeness() -> None:
    """Verify icons.json includes button, tiltwindow closed, and service icons."""
    icons_path = INTEGRATION_DIR / "icons.json"
    icons_data = json.loads(icons_path.read_text(encoding="utf-8"))

    assert "hcu_device_identify" in icons_data["entity"].get("button", {})
    assert "hcu_pull_latch" in icons_data["entity"].get("button", {})
    assert (
        "closed"
        in icons_data["entity"]["sensor"]["hcu_tiltwindow"]["state"]
    )
    assert "set_display_content" in icons_data["services"]


@pytest.mark.asyncio
async def test_diagnostics_redacts_sensitive_identifiers_and_device_pins() -> None:
    """Verify diagnostics redacts SGTIN, client IDs, zeroconf_name, and device_pins."""
    config_entry = SimpleNamespace(
        entry_id="entry-1",
        title="Homematic IP HCU",
        data={
            "host": "192.168.1.50",
            CONF_PLUGIN_TOKEN: "secret-plugin-token",
            CONF_APP_TOKEN: "secret-app-token",
            CONF_PIN: "1234",
            CONF_HCU_SGTIN: "3014F711A0001234567890AB",
            CONF_ZEROCONF_NAME: "Homematic-HCU._hmip._tcp.local.",
            CONF_ACCESS_POINT_ID: "3014F711A0001234567890AB",
            CONF_APP_CLIENT_ID: "app-client-uuid",
            CONF_PLUGIN_CLIENT_ID: "plugin-client-uuid",
            CONF_CLIENT_ID: "legacy-client-uuid",
        },
        options={
            CONF_DEVICE_PINS: {
                "3014F711A000999999999999": "9876",
            }
        },
    )

    client = MagicMock()
    client.state = {
        "devices": {
            "dev-1": {
                "id": "dev-1",
                "sgtin": "3014F711A000111111111111",
                "accessPointId": "3014F711A0001234567890AB",
                "homeId": "home-uuid-1234",
                "authorizationPin": "4321",
                "label": "Front Door Lock",
            }
        },
        "groups": {},
    }
    coordinator = MagicMock()
    coordinator.client = client

    hass = MagicMock()
    hass.data = {DOMAIN: {"entry-1": coordinator}}

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    redacted_data = result["config_entry"]["data"]
    assert redacted_data["host"] == "**REDACTED**"
    assert redacted_data[CONF_PLUGIN_TOKEN] == "**REDACTED**"
    assert redacted_data[CONF_APP_TOKEN] == "**REDACTED**"
    assert redacted_data[CONF_PIN] == "**REDACTED**"
    assert redacted_data[CONF_HCU_SGTIN] == "**REDACTED**"
    assert redacted_data[CONF_ZEROCONF_NAME] == "**REDACTED**"
    assert redacted_data[CONF_ACCESS_POINT_ID] == "**REDACTED**"
    assert redacted_data[CONF_APP_CLIENT_ID] == "**REDACTED**"
    assert redacted_data[CONF_PLUGIN_CLIENT_ID] == "**REDACTED**"
    assert redacted_data[CONF_CLIENT_ID] == "**REDACTED**"

    redacted_options = result["config_entry"]["options"]
    assert redacted_options[CONF_DEVICE_PINS] == "**REDACTED**"

    dev_state = result["devices"]["dev-1"]["hcu_data"]
    assert dev_state["sgtin"] == "**REDACTED**"
    assert dev_state["accessPointId"] == "**REDACTED**"
    assert dev_state["homeId"] == "**REDACTED**"
    assert dev_state["authorizationPin"] == "**REDACTED**"
    assert dev_state["label"] == "Front Door Lock"
