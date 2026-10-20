"""Unit tests for translations, icons, strings.json parity, and diagnostics redaction."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
import pytest
import yaml

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

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

INTEGRATION_DIR = (
    Path(__file__).resolve().parent.parent / "custom_components" / "hcu_integration"
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
    assert "closed" in icons_data["entity"]["sensor"]["hcu_tiltwindow"]["state"]
    services_yaml = INTEGRATION_DIR / "services.yaml"
    described = set(yaml.safe_load(services_yaml.read_text(encoding="utf-8")))
    assert set(icons_data["services"]) == described


@pytest.mark.asyncio
async def test_former_hardcoded_icons_mapping_in_icons_json(
    hass: HomeAssistant,
) -> None:
    """Verify all 58 former hardcoded icons exist in icons.json, derive platform from real entities, and are removed from Python."""
    from homeassistant.helpers import entity_registry as er

    from tests.test_translation_names_parity import _setup_synthetic

    icons_path = INTEGRATION_DIR / "icons.json"
    icons_data = json.loads(icons_path.read_text(encoding="utf-8"))

    former_hardcoded_icons: dict[str, str] = {
        "hcu_vacation_mode": "mdi:palm-tree",
        "hcu_device_identify": "mdi:crosshairs-gps",
        "hcu_pull_latch": "mdi:door",
        "reset_energy_counter": "mdi:reload",
        "reset_water_volume": "mdi:reload",
        "impulse": "mdi:garage",
        "unlatch": "mdi:door-open",
        "ramp_time": "mdi:timer-cog-outline",
        "hcu_power_up_switch_state": "mdi:power-settings",
        "alarm_test_signal_acoustic": "mdi:alarm-bell",
        "alarm_test_signal_optical": "mdi:alarm-light-outline",
        "hcu_use_internal_on_time": "mdi:timer-cog-outline",
        "hcu_device_pin": "mdi:lock-outline",
        "soil_moisture_raw_value": "mdi:water-percent",
        "air_pressure": "mdi:gauge",
        "particulate_mass_concentration_one": "mdi:blur",
        "particulate_mass_concentration_one_average": "mdi:blur",
        "particulate_number_concentration_one": "mdi:counter",
        "particulate_mass_concentration_two_point_five": "mdi:blur",
        "particulate_mass_concentration_two_point_five_average": "mdi:blur",
        "particulate_number_concentration_two_point_five": "mdi:counter",
        "particulate_number_concentration_two_point_five_average": "mdi:counter",
        "air_quality_index_two_point_five": "mdi:air-filter",
        "particulate_mass_concentration_ten": "mdi:blur",
        "particulate_mass_concentration_ten_average": "mdi:blur",
        "particulate_number_concentration_ten": "mdi:counter",
        "particulate_number_concentration_ten_average": "mdi:counter",
        "air_quality_index_ten": "mdi:air-filter",
        "particulate_typical_size": "mdi:ruler",
        "vapor_amount": "mdi:water",
        "current_gas_flow": "mdi:meter-gas",
        "water_flow": "mdi:water",
        "valve_position": "mdi:pipe-valve",
        "wind_direction": "mdi:weather-windy",
        "wind_direction_variation": "mdi:weather-windy-variant",
        "total_rain_counter": "mdi:weather-pouring",
        "today_rain_counter": "mdi:weather-rainy",
        "yesterday_rain_counter": "mdi:weather-rainy",
        "total_sunshine_duration": "mdi:weather-sunny",
        "today_sunshine_duration": "mdi:weather-partly-cloudy",
        "yesterday_sunshine_duration": "mdi:weather-sunset",
        "distance": "mdi:signal-distance-variant",
        "calculated_height": "mdi:arrow-expand-vertical",
        "reference_height": "mdi:arrow-expand-vertical",
        "carrier_sense": "mdi:radio-tower",
        "duty_cycle": "mdi:radio-tower",
        "duty_cycle_level": "mdi:radio-tower",
        "dirt_level": "mdi:dust",
        "smoke_test_counter": "mdi:counter",
        "smoke_alarm_counter": "mdi:counter",
        "acceleration_sensor_value_x": "mdi:axis-x-arrow",
        "acceleration_sensor_value_y": "mdi:axis-y-arrow",
        "acceleration_sensor_value_z": "mdi:axis-z-arrow",
        "acceleration_sensor_triggered": "mdi:accelerometer",
        "acceleration_sensor_event_counter": "mdi:counter",
        "tilt_state": "mdi:axis-z-rotate-clockwise",
        "absolute_angle": "mdi:angle-acute",
        "temperature_external_delta": "mdi:thermometer-chevron-up",
    }

    assert len(former_hardcoded_icons) == 58

    # Set up integration with synthetic fixtures to discover actual entity platforms
    await _setup_synthetic(hass)
    ent_reg = er.async_get(hass)
    entry = next(iter(hass.config_entries.async_entries(DOMAIN)))
    all_entities = er.async_entries_for_config_entry(ent_reg, entry.entry_id)

    key_to_platforms: dict[str, set[str]] = {}
    for entity in all_entities:
        if entity.translation_key:
            key_to_platforms.setdefault(entity.translation_key, set()).add(
                entity.domain
            )

    # For every entity with a translation_key, assert that icons.json has
    # entity.<entity actual platform>.<translation_key> whenever the entity had an icon before
    for entity in all_entities:
        if entity.translation_key and entity.translation_key in former_hardcoded_icons:
            expected_icon = former_hardcoded_icons[entity.translation_key]
            platform_icons = icons_data["entity"].get(entity.domain, {})
            assert entity.translation_key in platform_icons, (
                f"Missing icon in icons.json for {entity.domain}.{entity.translation_key}"
            )
            assert platform_icons[entity.translation_key]["default"] == expected_icon, (
                f"Icon mismatch for {entity.domain}.{entity.translation_key}"
            )

    # Assert that no icons.json entry exists under a platform where no entity uses that key
    for platform, keys in icons_data["entity"].items():
        for key in keys:
            if key in key_to_platforms:
                assert platform in key_to_platforms[key], (
                    f"icons.json entry '{key}' misplaced under '{platform}'; "
                    f"actual entity platform(s): {key_to_platforms[key]}"
                )

    # Verify no python file contains hardcoded _attr_icon
    for py_file in INTEGRATION_DIR.glob("**/*.py"):
        text = py_file.read_text(encoding="utf-8")
        assert "_attr_icon" not in text, f"Hardcoded _attr_icon found in {py_file}"


def test_every_described_action_is_translated() -> None:
    """Each action in services.yaml has strings in strings.json, en and de."""
    services_yaml = INTEGRATION_DIR / "services.yaml"
    described = set(yaml.safe_load(services_yaml.read_text(encoding="utf-8")))
    for path in (
        INTEGRATION_DIR / "strings.json",
        INTEGRATION_DIR / "translations" / "en.json",
        INTEGRATION_DIR / "translations" / "de.json",
    ):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert set(data["services"]) == described, path.name


def test_exception_messages_do_not_contain_quoted_placeholders() -> None:
    """Hassfest rule: placeholders inside quotes like \x27{placeholder}\x27 are invalid."""
    import re

    quote_pattern = re.compile(
        r"[\x27\x22][^\x27\x22]*\{[a-zA-Z0-9_]+\}[^\x27\x22]*[\x27\x22]"
    )
    for file_path in (
        INTEGRATION_DIR / "strings.json",
        INTEGRATION_DIR / "translations" / "en.json",
        INTEGRATION_DIR / "translations" / "de.json",
    ):
        data = json.loads(file_path.read_text(encoding="utf-8"))
        for key, value in data.get("exceptions", {}).items():
            message = value.get("message", "")
            match = quote_pattern.search(message)
            assert not match, (
                f"Message for {key} in {file_path.name} contains quoted placeholder: {message}"
            )


def test_exception_translation_keys_exist_in_all_translations() -> None:
    """Every translation_key and placeholder used in a raise in the code matches all translations."""
    import re

    placeholder_pattern = re.compile(r"\{([a-zA-Z0-9_]+)\}")
    raises: list[tuple[str, str, set[str] | None]] = []

    for py_file in INTEGRATION_DIR.glob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call):
                key: str | None = None
                placeholders: set[str] | None = None
                for kw in node.exc.keywords:
                    if kw.arg == "translation_key":
                        if isinstance(kw.value, ast.Constant):
                            key = str(kw.value.value)
                        elif isinstance(kw.value, ast.Name):
                            # Dynamic translation key (e.g. key determined by entity validation reason)
                            key = f"DYNAMIC:{kw.value.id}"
                    elif kw.arg == "translation_placeholders":
                        if isinstance(kw.value, ast.Dict):
                            placeholders = {
                                str(k.value)
                                for k in kw.value.keys
                                if isinstance(k, ast.Constant)
                            }
                if key:
                    raises.append((py_file.name, key, placeholders))

    assert raises, "Expected translation_key raises in integration code"

    # Also include dynamically resolved reason keys from services.py key_map
    dynamic_possible_keys = {
        "entities_not_found",
        "entities_no_sound",
        "entities_not_hcu_climate",
        "entities_timed_on_unsupported",
        "entities_invalid_param",
        "entities_invalid",
    }

    short_reason_keys = {
        "reason_not_found",
        "reason_no_sound",
        "reason_not_hcu_climate",
        "reason_timed_on_unsupported",
        "reason_invalid_param",
    }

    translation_files = (
        INTEGRATION_DIR / "strings.json",
        INTEGRATION_DIR / "translations" / "en.json",
        INTEGRATION_DIR / "translations" / "de.json",
    )

    for file_path in translation_files:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        exceptions = data.get("exceptions", {})

        for _py_file, key, placeholders in raises:
            if key.startswith("DYNAMIC:"):
                # Assert all dynamically possible keys exist with exact expected placeholders
                for dyn_key in dynamic_possible_keys:
                    assert dyn_key in exceptions, (
                        f"Dynamic key {dyn_key} missing from {file_path.name}"
                    )
                    msg = exceptions[dyn_key].get("message", "")
                    msg_placeholders = set(placeholder_pattern.findall(msg))
                    if placeholders is not None:
                        assert placeholders == msg_placeholders, (
                            f"Placeholder mismatch for {dyn_key} in {file_path.name}: "
                            f"code passed {placeholders}, translation defined {msg_placeholders}"
                        )
                continue

            assert key in exceptions, f"Key {key} missing from {file_path.name}"
            assert "message" in exceptions[key], (
                f"Key {key} missing message in {file_path.name}"
            )

            if placeholders is not None:
                msg = exceptions[key]["message"]
                msg_placeholders = set(placeholder_pattern.findall(msg))
                assert placeholders == msg_placeholders, (
                    f"Placeholder mismatch for {key} in {file_path.name}: "
                    f"code passed {placeholders}, translation defined {msg_placeholders}"
                )

        for r_key in short_reason_keys:
            assert r_key in exceptions, (
                f"Short reason key {r_key} missing from {file_path.name}"
            )
            assert "message" in exceptions[r_key]


@pytest.mark.asyncio
async def test_diagnostics_redacts_sensitive_identifiers_and_device_pins(
    hass: HomeAssistant,
) -> None:
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

    config_entry.runtime_data = coordinator

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


@pytest.mark.asyncio
async def test_diagnostics_pseudonymizes_device_sgtins_everywhere(
    hass: HomeAssistant,
) -> None:
    """Device SGTINs must not appear anywhere in the dump (keys, ids, unique_ids)."""
    sgtin_a = "3014F711A0000000000000AA"
    sgtin_b = "3014F711A0000000000000BB"
    config_entry = SimpleNamespace(
        entry_id="entry-1", title="Homematic IP HCU", data={}, options={}
    )
    client = MagicMock()
    client.state = {
        "devices": {
            sgtin_a: {
                "id": sgtin_a,
                "label": "Thermostat",
                "functionalChannels": {"0": {"deviceId": sgtin_a, "index": 0}},
            },
            sgtin_b: {"id": sgtin_b, "label": "Window"},
        },
        "groups": {
            "group-uuid-1": {
                "id": "group-uuid-1",
                "label": "Living room",
                "channels": [{"deviceId": sgtin_b, "channelIndex": 1}],
            }
        },
    }
    coordinator = MagicMock()
    coordinator.client = client
    config_entry.runtime_data = coordinator

    ha_device = SimpleNamespace(
        id="ha-dev-1",
        identifiers={(DOMAIN, sgtin_a)},
        manufacturer="eQ-3",
        model="HmIP-eTRV",
        name="Thermostat",
        sw_version="1.0",
        via_device_id=None,
        area_id=None,
        name_by_user=None,
        disabled_by=None,
    )
    entity_entry = SimpleNamespace(
        entity_id="sensor.thermostat_battery",
        unique_id=f"{sgtin_a}_0_lowBat",
        disabled_by=None,
    )
    hass.states.async_set("sensor.thermostat_battery", "ok", {"device_id": sgtin_a})

    with (
        patch(
            "custom_components.hcu_integration.diagnostics.dr.async_entries_for_config_entry",
            return_value=[ha_device],
        ) as entries_mock,
        patch(
            "custom_components.hcu_integration.diagnostics.er.async_entries_for_device",
            return_value=[entity_entry],
        ),
    ):
        result = await async_get_config_entry_diagnostics(hass, config_entry)

    # Devices are looked up within this config entry (no deprecated global lookup).
    assert entries_mock.call_args[0][1] == "entry-1"

    dump = json.dumps(result)
    assert sgtin_a not in dump and sgtin_b not in dump
    assert "3014F7" not in dump

    devices = result["devices"]
    assert set(devices) == {"device_001", "device_002"}
    thermostat = devices["device_001"]
    assert thermostat["hcu_data"]["id"] == "device_001"
    assert thermostat["hcu_data"]["functionalChannels"]["0"]["deviceId"] == "device_001"
    assert thermostat["ha_device"]["name"] == "Thermostat"
    assert thermostat["ha_entities"][0]["unique_id"] == "device_001_0_lowBat"
    assert (
        thermostat["ha_entities"][0]["state"]["attributes"]["device_id"] == "device_001"
    )
    # Group references keep pointing at the same placeholder as the device.
    assert (
        result["groups"]["group-uuid-1"]["hcu_data"]["channels"][0]["deviceId"]
        == "device_002"
    )


@pytest.mark.asyncio
async def test_diagnostics_include_functional_homes_only(
    hass: HomeAssistant,
) -> None:
    """Alarm flags from the home object are visible; location data is not."""
    config_entry = SimpleNamespace(
        entry_id="entry-1", title="Homematic IP HCU", data={}, options={}
    )
    client = MagicMock()
    client.state = {
        "home": {
            "id": "home-uuid",
            "location": {"city": "Leer", "latitude": "53.2", "longitude": "7.4"},
            "functionalHomes": {
                "SECURITY_AND_ALARM": {
                    "solution": "SECURITY_AND_ALARM",
                    "intrusionAlarmActive": False,
                    "safetyAlarmActive": True,
                    "securitySwitchingGroups": {"SIREN": "group-siren"},
                    "homeId": "home-uuid",
                    "intrusionAlarmPhoneNumber": "+49 170 0000000",
                    "safetyAlarmPhoneNumber": "112",
                    "securityZoneActivationModeChangeStatus": {
                        "clientId": "client-uuid",
                        "clientLabel": "Pixel of Jane",
                        "timestamp": 1785367461113,
                    },
                }
            },
        },
        "devices": {},
        "groups": {},
    }
    coordinator = MagicMock()
    coordinator.client = client
    config_entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert set(result["home"]) == {"functionalHomes"}
    security = result["home"]["functionalHomes"]["SECURITY_AND_ALARM"]
    assert security["safetyAlarmActive"] is True
    assert security["intrusionAlarmActive"] is False
    assert security["securitySwitchingGroups"] == {"SIREN": "group-siren"}
    assert security["homeId"] == "**REDACTED**"
    assert security["intrusionAlarmPhoneNumber"] == "**REDACTED**"
    assert security["safetyAlarmPhoneNumber"] == "**REDACTED**"
    change_status = security["securityZoneActivationModeChangeStatus"]
    assert change_status["clientId"] == "**REDACTED**"
    assert change_status["clientLabel"] == "**REDACTED**"
    assert change_status["timestamp"] == 1785367461113
    assert "Pixel of Jane" not in json.dumps(result)
    assert "Leer" not in json.dumps(result)


@pytest.mark.asyncio
async def test_diagnostics_without_home_object(hass: HomeAssistant) -> None:
    config_entry = SimpleNamespace(
        entry_id="entry-1", title="Homematic IP HCU", data={}, options={}
    )
    client = MagicMock()
    client.state = {"devices": {}, "groups": {}}
    coordinator = MagicMock()
    coordinator.client = client
    config_entry.runtime_data = coordinator

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert result["home"] == {"functionalHomes": {}}
