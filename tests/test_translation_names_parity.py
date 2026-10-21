"""Self-contained in-repo parity tests for English and German entity translations."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, ProcessEventsResult
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    CONF_ACCESS_POINT_ID,
    CONF_APP_CLIENT_ID,
    CONF_AUTH_TYPE,
    CONF_DEVICE_PINS,
    DOMAIN,
    DUTY_CYCLE_BINARY_SENSOR_MAPPING,
    HMIP_CHANNEL_ROLE_TO_ENTITY,
    HMIP_FEATURE_TO_ENTITY,
)

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

SNAPSHOT_PATH = Path(__file__).parent / "fixtures" / "english_entity_names.json"


def _sample_value_for_feature(feature: str, mapping: dict) -> object:
    cls = mapping.get("class")
    if cls == "HcuBinarySensor":
        return False
    if cls == "HcuTimestampSensor":
        return "2026_01_01 12:00"
    if cls == "HcuPowerUpSwitchState":
        return "PERMANENT"
    if cls == "HcuSmokeBinarySensor":
        return "IDLE_OFF"
    if cls == "HcuUnreachBinarySensor":
        return False
    if feature == "tiltState":
        return "UPRIGHT"
    if feature == "windDirectionVariation":
        return 15.0
    if feature == "windowState":
        return "CLOSED"
    return 10.0


def build_synthetic_fixtures() -> tuple[dict, dict, dict]:
    """Build programmatic fixtures covering HMIP_FEATURE_TO_ENTITY and channel roles."""
    ch1 = {
        "functionalChannelType": "GENERIC_INPUT_TRANSMITTER",
        "supportedOptionalFeatures": {
            "IOptionalFeatureEnergyCounterOne": True,
            "IOptionalFeatureEnergyCounterTwo": True,
            "IOptionalFeatureEnergyCounterThree": True,
            "IOptionalFeatureGasVolume": True,
            "IOptionalFeatureCurrentGasFlow": True,
            "IOptionalFeatureLowBat": True,
        },
    }
    for feat, mapping in HMIP_FEATURE_TO_ENTITY.items():
        if mapping.get("class") != "HcuHomeSensor" and feat not in (
            "valveActualTemperature",
            "wateringOnTime",
        ):
            ch1[feat] = _sample_value_for_feature(feat, mapping)

    dev_features = {
        "id": "dev-all-features",
        "label": "Multi Sensor",
        "modelType": "HMIP-TEST",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "unreach": False,
                "dutyCycle": False,
            },
            "1": ch1,
            "2": {
                "functionalChannelType": "HEATING_THERMOSTAT_CHANNEL",
                "valveActualTemperature": 21.5,
                "wateringOnTime": 45.0,
            },
        },
    }

    dev_roles = {
        "id": "dev-roles",
        "label": "Role Device",
        "modelType": "HMIP-TEST-ROLES",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOOR_BELL_CHANNEL",
                "channelRole": "DOOR_BELL_INPUT",
            },
            "2": {
                "functionalChannelType": "SHUTTER_CONTACT_CHANNEL",
                "channelRole": "DOOR_SENSOR",
                "windowState": "CLOSED",
            },
            "3": {
                "functionalChannelType": "ROTARY_HANDLE_CHANNEL",
                "channelRole": "WINDOW_SENSOR",
                "windowState": "CLOSED",
            },
        },
    }

    dev_multi_unlabeled = {
        "id": "dev-temp-unlabeled",
        "label": "Weather Station",
        "modelType": "HMIP-SWO-PR",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "actualTemperature": 20.0,
            },
            "2": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "actualTemperature": 22.0,
            },
        },
    }

    dev_multi_labeled = {
        "id": "dev-temp-labeled",
        "label": "Weather Station Labeled",
        "modelType": "HMIP-SWO-PR",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "label": "Top",
                "actualTemperature": 20.0,
            },
            "2": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "label": "Bottom",
                "actualTemperature": 22.0,
            },
        },
    }

    dev_siren = {
        "id": "dev-siren",
        "label": "Alarm Siren",
        "modelType": "HMIP-ASIR",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "SIREN_CHANNEL"},
        },
    }

    dev_dimmer = {
        "id": "dev-dimmer",
        "label": "Dimmer",
        "modelType": "HMIP-BDT",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DIMMER_CHANNEL"},
        },
    }

    dev_switch = {
        "id": "dev-switch",
        "label": "Wall Switch",
        "modelType": "HMIP-BSM",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "onTime": 30.0,
            },
        },
    }

    dev_gate = {
        "id": "dev-gate",
        "label": "Garage Gate",
        "modelType": "HMIP-WGC",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOOR_CHANNEL",
                "groupIndex": 10,
                "label": "Gate",
            },
            "2": {
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 10,
                "groups": ["profile-1"],
            },
        },
    }

    dev_lock = {
        "id": "dev-lock",
        "label": "Front Door",
        "modelType": "HMIP-DLD",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOOR_LOCK_CHANNEL",
                "groupIndex": 20,
                "label": "Lock",
            },
            "2": {
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 20,
                "groups": ["profile-1"],
            },
        },
    }

    dev_hcu = {
        "id": "hcu-central",
        "label": "Home Control Unit",
        "modelType": "HMIP-HCU",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
        },
    }

    devices = {
        "dev-all-features": dev_features,
        "dev-roles": dev_roles,
        "dev-temp-unlabeled": dev_multi_unlabeled,
        "dev-temp-labeled": dev_multi_labeled,
        "dev-siren": dev_siren,
        "dev-dimmer": dev_dimmer,
        "dev-switch": dev_switch,
        "dev-gate": dev_gate,
        "dev-lock": dev_lock,
        "hcu-central": dev_hcu,
    }

    groups = {
        "profile-1": {
            "id": "profile-1",
            "type": "ACCESS_AUTHORIZATION_PROFILE",
            "label": "Entry Authorization",
            "clientIds": ["client-ha-1"],
            "authorizationPinAssigned": True,
        },
        "group-heating": {
            "id": "group-heating",
            "type": "HEATING",
            "label": "Living Room Heating",
            "setPointTemperature": 21.0,
            "actualTemperature": 20.5,
            "humidity": 45.0,
            "hvacMode": "AUTOMATIC",
        },
        "group-switching": {
            "id": "group-switching",
            "type": "SWITCHING",
            "label": "All Lights",
            "on": False,
        },
    }

    home = {
        "carrierSense": 12.0,
        "dutyCycle": 24.0,
        "functionalHomes": {
            "SECURITY_AND_ALARM_ID": {
                "solution": "SECURITY_AND_ALARM",
                "safetyAlarmActive": False,
                "alarmActive": False,
            },
            "INDOOR_CLIMATE": {
                "absenceType": "VACATION",
                "absenceStartTime": "2026_01_01 10:00",
                "absenceEndTime": "2026_01_10 18:00",
                "lastVacationTemperature": 18.0,
            },
        },
    }

    return devices, groups, home


async def _setup_synthetic(
    hass: HomeAssistant, language: str = "en"
) -> dict[str, dict[str, str | None]]:
    hass.config.language = language
    devices, groups, home = build_synthetic_fixtures()

    client = MagicMock(spec=HcuApiClient)
    client._auth_type = AUTH_TYPE_APP
    client.plugin_id = "plugin-1"
    client.hcu_device_id = "hcu-central"
    client.state = {
        "devices": devices,
        "groups": groups,
        "home": home,
    }
    client.get_device_by_address = MagicMock(side_effect=devices.get)
    client.get_group_by_id = MagicMock(side_effect=groups.get)
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={
            "host": "192.0.2.10",
            CONF_ACCESS_POINT_ID: "hcu-test",
            CONF_AUTH_TYPE: AUTH_TYPE_APP,
            CONF_APP_CLIENT_ID: "client-ha-1",
        },
        options={
            CONF_DEVICE_PINS: {"dev-lock": "1234"},
        },
        unique_id="hcu-test",
    )
    entry.add_to_hass(hass)

    with (
        patch("custom_components.hcu_integration.HcuApiClient", return_value=client),
        patch(
            "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        ent_reg = er.async_get(hass)
        disabled_entries = [
            e
            for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
            if e.disabled_by is not None
        ]
        if disabled_entries:
            for e in disabled_entries:
                ent_reg.async_update_entity(e.entity_id, disabled_by=None)
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
    entities: dict[str, dict[str, str | None]] = {}
    for entity in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
        state = hass.states.get(entity.entity_id)
        friendly_name = state.attributes.get("friendly_name") if state else None
        entities[entity.unique_id] = {
            "entity_id": entity.entity_id,
            "friendly_name": friendly_name,
        }
    return entities


@pytest.mark.asyncio
async def test_synthetic_english_names_parity(hass: HomeAssistant) -> None:
    """Verify 100% mechanical parity of English friendly_name and entity_id against snapshot."""
    current = await _setup_synthetic(hass, language="en")
    assert SNAPSHOT_PATH.is_file(), "Snapshot file must exist"
    baseline = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))

    assert len(current) == len(baseline)

    differences: list[str] = []
    for uid, base_info in baseline.items():
        if uid not in current:
            differences.append(f"Entity missing from current setup: {uid}")
            continue
        curr_info = current[uid]
        if curr_info["entity_id"] != base_info["entity_id"]:
            differences.append(
                f"entity_id mismatch for {uid}: expected {base_info['entity_id']}, got {curr_info['entity_id']}"
            )
        if curr_info["friendly_name"] != base_info["friendly_name"]:
            differences.append(
                f"friendly_name mismatch for {uid}: expected {base_info['friendly_name']}, got {curr_info['friendly_name']}"
            )

    assert not differences, "\n".join(differences)


@pytest.mark.asyncio
async def test_synthetic_german_representative_names(hass: HomeAssistant) -> None:
    """Verify representative subset of German entity names matches approved translations."""
    current = await _setup_synthetic(hass, language="de")
    names = {uid: info["friendly_name"] for uid, info in current.items()}

    expected_german = {
        # Multi-channel unlabeled: channel 1 has no suffix, channel 2 has index 2
        "dev-temp-unlabeled_1_actualTemperature": "Weather Station Temperatur",
        "dev-temp-unlabeled_2_actualTemperature": "Weather Station Temperatur 2",
        # Multi-channel labeled: each channel uses its channel label
        "dev-temp-labeled_1_actualTemperature": "Weather Station Labeled Top Temperatur",
        "dev-temp-labeled_2_actualTemperature": "Weather Station Labeled Bottom Temperatur",
        # Core device features
        "dev-all-features_1_actualTemperature": "Multi Sensor Temperatur",
        "dev-all-features_1_airPressure": "Multi Sensor Luftdruck",
        "dev-all-features_1_humidity": "Multi Sensor Luftfeuchtigkeit",
        "dev-all-features_1_illumination": "Multi Sensor Helligkeit",
        "dev-all-features_1_lowBat": "Multi Sensor Batterie schwach",
        "dev-all-features_0_unreach": "Multi Sensor Verbindung",
        "dev-all-features_1_energyCounter": "Multi Sensor Energiezähler",
        "dev-all-features_1_reset_energy_counter": "Multi Sensor Energiezähler zurücksetzen",
        "dev-all-features_2_valveActualTemperature": "Multi Sensor Temperatur",
        # Central HCU entities
        "hcu-central_vacation_mode": "Homematic IP HCU Urlaubsmodus",
        "hcu-central_acknowledge_safety_alarm": "Homematic IP HCU Gefahrenalarm quittieren",
        # Platform entities
        "dev-lock_1_unlatch": "Front Door Lock Tür öffnen",
        "dev-lock_device_pin": "Front Door Zutrittsberechtigungs-PIN",
        # Disabled-by-default entities enabled during test
        "dev-all-features_1_dirtLevel": "Multi Sensor Verschmutzungsgrad",
        "dev-dimmer_1_ramp_time": "Dimmer Rampenzeit",
    }

    mismatches = []
    for uid, expected in expected_german.items():
        actual = names.get(uid)
        if actual != expected:
            mismatches.append(f"{uid}: expected '{expected}', got '{actual}'")

    assert not mismatches, "\n".join(mismatches)


def test_synthetic_fixture_mapping_coverage() -> None:
    """Verify synthetic fixtures cover every HMIP feature, duty cycle, and channel roles."""
    devices, _groups, home = build_synthetic_fixtures()

    # Every feature in HMIP_FEATURE_TO_ENTITY is represented below
    ch1 = devices["dev-all-features"]["functionalChannels"]["1"]
    ch2 = devices["dev-all-features"]["functionalChannels"]["2"]
    for feat, mapping in HMIP_FEATURE_TO_ENTITY.items():
        if mapping.get("class") == "HcuHomeSensor":
            assert feat in home or any(
                feat in fh for fh in home.get("functionalHomes", {}).values()
            )
        elif feat in ("valveActualTemperature", "wateringOnTime"):
            assert feat in ch2
        else:
            assert feat in ch1

    # Duty cycle mapping is covered on channel 0
    assert "dutyCycle" in devices["dev-all-features"]["functionalChannels"]["0"]
    assert DUTY_CYCLE_BINARY_SENSOR_MAPPING["translation_key"] == "duty_cycle_limit"

    # Every HMIP_CHANNEL_ROLE_TO_ENTITY with a name is covered on dev-roles
    roles_channels = devices["dev-roles"]["functionalChannels"]
    channel_roles = {
        ch["channelRole"] for ch in roles_channels.values() if "channelRole" in ch
    }
    for role, mapping in HMIP_CHANNEL_ROLE_TO_ENTITY.items():
        if "name" in mapping:
            assert role in channel_roles
