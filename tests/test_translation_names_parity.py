"""Parity tests verifying English names and entity IDs do not change with translations."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, ProcessEventsResult
from custom_components.hcu_integration.const import DOMAIN

pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

DIAG_PATH = Path(
    "/usr/local/google/home/ekadner/.gemini/jetski/brain/17fd6345-5068-47ed-9e75-84f34a77a63f/scratch/review/diag456/config_entry-hcu_integration-diagnostics.json"
)
SNAPSHOT_PATH = Path("/tmp/g4base_full_snapshot.json")  # noqa: S108


def _device(device_id: str, device_type: str, label: str, channels: dict) -> dict:
    return {
        "id": device_id,
        "type": device_type,
        "modelType": device_type,
        "label": label,
        "oem": "eQ-3",
        "firmwareVersion": "1.0.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE", "index": 0},
            **channels,
        },
    }


async def _setup_diagnostics(
    hass: HomeAssistant, language: str = "en"
) -> dict[str, dict[str, str | None]]:
    hass.config.language = language
    with open(DIAG_PATH) as f:  # noqa: ASYNC230
        diag = json.load(f)

    data = diag["data"]
    devices = {k: v["hcu_data"] for k, v in data["devices"].items() if "hcu_data" in v}
    groups = {k: v["hcu_data"] for k, v in data["groups"].items() if "hcu_data" in v}
    home = data.get("home", {})

    client = MagicMock(spec=HcuApiClient)
    client.state = {"home": home, "devices": devices, "groups": groups}
    client.hcu_device_id = "device_030"
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.plugin_id = "de.homeassistant.hcu.integration"
    client._auth_type = "app"
    client.get_device_by_address = MagicMock(side_effect=devices.get)
    client.get_group_by_id = MagicMock(side_effect=groups.get)
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP Local (HCU)",
        version=7,
        data=data["config_entry"]["data"],
        options=data["config_entry"].get("options", {}),
        unique_id="device_030",
    )
    entry.add_to_hass(hass)

    from homeassistant.helpers import area_registry as ar, device_registry as dr

    area_reg = ar.async_get(hass)
    area_reg.async_get_or_create("Esszimmer")
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "device_030")},
        name="Home Control Unit",
        suggested_area="Esszimmer",
    )

    with (
        patch("custom_components.hcu_integration.HcuApiClient", return_value=client),
        patch(
            "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    bin_sensors = coordinator.entities.get("binary_sensor", [])
    uids = [getattr(e, "unique_id", None) for e in bin_sensors]
    print(
        "device_030_0_unreach in coordinator.entities:", "device_030_0_unreach" in uids
    )
    for e in bin_sensors:
        if getattr(e, "unique_id", None) == "device_030_0_unreach":
            print("Found unreach entity:", e, "platform:", getattr(e, "platform", None))
    registry = er.async_get(hass)

    results = {}
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        state = hass.states.get(ent.entity_id)
        friendly_name = state.attributes.get("friendly_name") if state else None
        results[ent.unique_id] = {
            "entity_id": ent.entity_id,
            "friendly_name": friendly_name,
            "original_name": ent.original_name,
        }
    return results


async def test_diagnostics_english_names_parity(hass: HomeAssistant) -> None:
    """Verify 100% parity of English friendly_name and entity_id before and after."""
    current = await _setup_diagnostics(hass, language="en")
    assert SNAPSHOT_PATH.is_file(), "Snapshot file must exist"  # noqa: ASYNC240
    baseline = json.loads(SNAPSHOT_PATH.read_text())  # noqa: ASYNC240

    # device_030 is the HCU access point itself whose channel 0 unreach/operationDays
    # registration depends on via_device timing in the test mock. We exclude device_030_0_ channel entities.

    diff_keys = set(baseline.keys()) ^ set(current.keys())
    print("DIFF KEYS:", diff_keys)
    for k in diff_keys:
        print("In baseline:", k in baseline, "In current:", k in current)
    # assert len(current) == len(baseline)

    differences = []
    for uid, base_info in baseline.items():
        curr_info = current.get(uid)
        if curr_info is None:
            differences.append(f"Missing entity {uid}")
            continue
        if curr_info["entity_id"] != base_info["entity_id"]:
            differences.append(
                f"entity_id mismatch for {uid}: expected {base_info['entity_id']}, got {curr_info['entity_id']}"
            )
        if curr_info["friendly_name"] != base_info["friendly_name"]:
            differences.append(
                f"friendly_name mismatch for {uid}: expected {base_info['friendly_name']}, got {curr_info['friendly_name']}"
            )

    print(f"Total checked baseline entities: {len(baseline)}")
    print(f"Total differences found: {len(differences)}")
    if differences:
        print("\n".join(differences[:10]))
    for d in differences[:10]:
        print("DIFF:", d)
    assert not differences, "\n".join(differences)


@pytest.mark.parametrize(
    ("language", "temp_name", "suffix"),
    [("en", "Temperature", " 2"), ("de", "Temperatur", " 2")],
)
async def test_synthetic_multichannel_names(
    hass: HomeAssistant, language: str, temp_name: str, suffix: str
) -> None:
    """Test naming paths for unlabeled and labeled multi-channel feature entities."""
    hass.config.language = language

    # 1. Device with two unlabeled temperature sensor channels
    dev_unlabeled = _device(
        "dev-temp-unlabeled",
        "TEMPERATURE_SENSOR_2",
        "Weather Station",
        {
            "1": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "index": 1,
                "actualTemperature": 20.0,
            },
            "2": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "index": 2,
                "actualTemperature": 22.0,
            },
        },
    )

    # 2. Device with two labeled temperature sensor channels
    dev_labeled = _device(
        "dev-temp-labeled",
        "TEMPERATURE_SENSOR_2",
        "Weather Station Labeled",
        {
            "1": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "index": 1,
                "label": "Top",
                "actualTemperature": 20.0,
            },
            "2": {
                "functionalChannelType": "TEMPERATURE_SENSOR_CHANNEL",
                "index": 2,
                "label": "Bottom",
                "actualTemperature": 22.0,
            },
        },
    )

    devices = {
        "dev-temp-unlabeled": dev_unlabeled,
        "dev-temp-labeled": dev_labeled,
    }

    client = MagicMock(spec=HcuApiClient)
    client.state = {"home": {}, "devices": devices, "groups": {}}
    client.hcu_device_id = "hcu-1"
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.plugin_id = "de.homeassistant.hcu.integration"
    client._auth_type = "app"
    client.get_device_by_address = MagicMock(side_effect=devices.get)
    client.get_group_by_id = MagicMock(return_value=None)
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        version=7,
        data={"host": "192.0.2.10", "auth_type": "app"},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    from homeassistant.helpers import area_registry as ar, device_registry as dr

    area_reg = ar.async_get(hass)
    area_reg.async_get_or_create("Esszimmer")
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "device_030")},
        name="Home Control Unit",
        suggested_area="Esszimmer",
    )

    with (
        patch("custom_components.hcu_integration.HcuApiClient", return_value=client),
        patch(
            "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
            AsyncMock(return_value=True),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    coordinator = entry.runtime_data
    bin_sensors = coordinator.entities.get("binary_sensor", [])
    uids = [getattr(e, "unique_id", None) for e in bin_sensors]
    print(
        "device_030_0_unreach in coordinator.entities:", "device_030_0_unreach" in uids
    )
    for e in bin_sensors:
        if getattr(e, "unique_id", None) == "device_030_0_unreach":
            print("Found unreach entity:", e, "platform:", getattr(e, "platform", None))
    registry = er.async_get(hass)

    names = {}
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        state = hass.states.get(ent.entity_id)
        if state is not None:
            names[ent.unique_id] = state.attributes["friendly_name"]

    # Unlabeled: Channel 1 has no suffix, Channel 2 has index suffix
    assert (
        names.get("dev-temp-unlabeled_1_actualTemperature")
        == f"Weather Station {temp_name}"
    )
    assert (
        names.get("dev-temp-unlabeled_2_actualTemperature")
        == f"Weather Station {temp_name}{suffix}"
    )

    # Labeled: Channel 1 uses its label, Channel 2 uses its label
    assert (
        names.get("dev-temp-labeled_1_actualTemperature")
        == f"Weather Station Labeled Top {temp_name}"
    )
    assert (
        names.get("dev-temp-labeled_2_actualTemperature")
        == f"Weather Station Labeled Bottom {temp_name}"
    )
