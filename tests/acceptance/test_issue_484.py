"""Acceptance tests for Issue 484: HcuTimestampSensor discovery and datetime native_value."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import attr
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import (
    DOMAIN,
    HMIP_CHANNEL_ROLE_TO_ENTITY,
    HMIP_CHANNEL_TYPE_TO_ENTITY,
    HMIP_FEATURE_TO_ENTITY,
    HMIP_OPTIONAL_FEATURE_TO_ENTITY,
)
from custom_components.hcu_integration.discovery import (
    _CLASS_MODULE_MAP,
    _discover_entities_for_device,
    async_discover_entities,
)
from custom_components.hcu_integration.sensor import HcuTimestampSensor


def _make_swsd2_device() -> dict:
    """Return a realistic HmIP-SWSD-2 payload matching live HCU state."""
    return {
        "id": "3014F711A0002E6409A467F3",
        "type": "SMOKE_DETECTOR",
        "modelType": "HmIP-SWSD-2",
        "label": "Rauchmelder Flur",
        "firmwareVersion": "1.0.6",
        "permanentlyReachable": True,
        "functionalChannels": {
            "0": {
                "index": 0,
                "deviceId": "3014F711A0002E6409A467F3",
                "functionalChannelType": "DEVICE_BASE",
                "label": "",
                "unreach": False,
                "lowBat": False,
                "dutyCycle": False,
                "operationDays": 240.0,
                "rssiDeviceValue": -68,
                "supportedOptionalFeatures": {
                    "IOptionalFeatureDutyCycle": True,
                    "IFeatureRssiValue": True,
                    "IOptionalFeatureOperationDays": True,
                    "IOptionalFeatureLowBat": True,
                },
            },
            "1": {
                "index": 1,
                "deviceId": "3014F711A0002E6409A467F3",
                "functionalChannelType": "SMOKE_DETECTOR_CHANNEL",
                "channelRole": "SMOKE_ALARM",
                "label": "",
                "smokeDetectorAlarmType": "IDLE_OFF",
                "chamberDegraded": False,
                "dirtLevel": 0.0,
                "inclusionTimestamp": 1771696846372,
                "lastSmokeTestTimestamp": 1772990422719,
                "lastCommunicationTestTimestamp": None,
                "smokeTestCounter": None,
                "smokeAlarmCounter": None,
                "groups": ["group-1"],
            },
        },
    }


def test_class_module_map_contains_all_mapped_classes() -> None:
    """Every entity class referenced in const.py mappings must be in _CLASS_MODULE_MAP."""
    expected_classes: set[str] = set()

    for mapping in HMIP_FEATURE_TO_ENTITY.values():
        if cls_name := mapping.get("class"):
            expected_classes.add(cls_name)
        if companion := mapping.get("config_companion"):
            expected_classes.add(companion)

    for mapping in HMIP_CHANNEL_TYPE_TO_ENTITY.values():
        if not mapping:
            continue
        if cls_name := mapping.get("class"):
            expected_classes.add(cls_name)
        for extra in mapping.get("extra_entities", []):
            if isinstance(extra, str):
                expected_classes.add(extra)
            elif isinstance(extra, dict) and extra.get("class"):
                expected_classes.add(extra["class"])

    for mapping in HMIP_CHANNEL_ROLE_TO_ENTITY.values():
        if cls_name := mapping.get("class"):
            expected_classes.add(cls_name)
        for extra in mapping.get("extra_entities", []):
            if isinstance(extra, str):
                expected_classes.add(extra)
            elif isinstance(extra, dict) and extra.get("class"):
                expected_classes.add(extra["class"])

    for mapping in HMIP_OPTIONAL_FEATURE_TO_ENTITY.values():
        if cls_name := mapping.get("class"):
            expected_classes.add(cls_name)

    missing = expected_classes - set(_CLASS_MODULE_MAP.keys())
    assert not missing, f"Classes missing from _CLASS_MODULE_MAP: {missing}"


def test_smoke_detector_timestamp_sensors_discovered(hass: HomeAssistant) -> None:
    """Smoke detector timestamp sensors are discovered and configured as disabled diagnostic sensors."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    device_data = _make_swsd2_device()
    dev_id = device_data["id"]

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.hcu_device_id = "hcu-main"
    client.get_device_by_address = MagicMock(return_value=device_data)

    entities, uids = _discover_entities_for_device(
        device_data, entry, coordinator, client
    )

    sensor_entities = {e.unique_id: e for e in entities[Platform.SENSOR]}

    for feature in (
        "lastSmokeTestTimestamp",
        "lastCommunicationTestTimestamp",
        "inclusionTimestamp",
    ):
        uid = f"{dev_id}_1_{feature}"
        assert uid in uids, f"Expected {uid} in valid_unique_ids"
        assert uid in sensor_entities, f"Expected {uid} to be instantiated"
        ent = sensor_entities[uid]
        assert isinstance(ent, HcuTimestampSensor)
        assert ent.device_class == SensorDeviceClass.TIMESTAMP
        assert ent.entity_category == EntityCategory.DIAGNOSTIC
        assert ent.entity_registry_enabled_default is False


def test_timestamp_sensor_native_value_returns_datetime() -> None:
    """HcuTimestampSensor.native_value returns a timezone-aware datetime, as SensorDeviceClass.TIMESTAMP requires."""
    device_data = _make_swsd2_device()
    dev_id = device_data["id"]

    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)

    smoke_test_sensor = HcuTimestampSensor(
        coordinator,
        client,
        device_data,
        "1",
        "lastSmokeTestTimestamp",
        HMIP_FEATURE_TO_ENTITY["lastSmokeTestTimestamp"],
    )

    val = smoke_test_sensor.native_value
    assert isinstance(val, datetime), f"Expected datetime, got {type(val)}"
    assert val.tzinfo is not None
    assert val == datetime(2026, 3, 8, 17, 20, 22, 719000, tzinfo=UTC)

    # Null timestamp (e.g., lastCommunicationTestTimestamp has never occurred)
    comm_test_sensor = HcuTimestampSensor(
        coordinator,
        client,
        device_data,
        "1",
        "lastCommunicationTestTimestamp",
        HMIP_FEATURE_TO_ENTITY["lastCommunicationTestTimestamp"],
    )
    assert comm_test_sensor.native_value is None

    # Inclusion timestamp
    inclusion_sensor = HcuTimestampSensor(
        coordinator,
        client,
        device_data,
        "1",
        "inclusionTimestamp",
        HMIP_FEATURE_TO_ENTITY["inclusionTimestamp"],
    )
    inc_val = inclusion_sensor.native_value
    assert isinstance(inc_val, datetime)
    assert inc_val == datetime(2026, 2, 21, 18, 0, 46, 372000, tzinfo=UTC)

    # Adversarial / invalid values
    for invalid_val in (0, -1000, 300000000000000, "not-a-timestamp", "1e400"):
        device_data["functionalChannels"]["1"]["lastSmokeTestTimestamp"] = invalid_val
        assert smoke_test_sensor.native_value is None


async def test_user_enabled_smoke_detector_entities_stay_enabled_on_reload(
    hass: HomeAssistant,
) -> None:
    """User-enabled smoke detector diagnostic entities are not re-disabled on reload."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    device_data = _make_swsd2_device()
    dev_id = device_data["id"]

    client = MagicMock()
    client.hcu_device_id = "hcu-main"
    client.hcu_part_device_ids = set()
    client.state = {"devices": {dev_id: device_data}, "groups": {}}
    client.get_device_by_address = MagicMock(return_value=device_data)

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = {dev_id: device_data}

    ent_reg = er.async_get(hass)
    # Simulate an entity created earlier with disabled_by=INTEGRATION, then enabled by the user
    reg_entry = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{dev_id}_1_lastSmokeTestTimestamp",
        config_entry=entry,
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )
    earlier = reg_entry.created_at - timedelta(seconds=30)
    ent_reg.entities[reg_entry.entity_id] = attr.evolve(reg_entry, created_at=earlier)

    # User enables the entity in the UI (sets disabled_by=None and updates modified_at)
    ent_reg.async_update_entity(reg_entry.entity_id, disabled_by=None)

    await async_discover_entities(hass, client, entry, coordinator)

    updated = ent_reg.async_get(reg_entry.entity_id)
    assert updated is not None
    assert updated.disabled_by is None


async def test_enabled_diagnostic_entities_are_never_disabled_by_the_integration(
    hass: HomeAssistant,
) -> None:
    """An enabled entity stays enabled, even if its registry entry looks untouched.

    The integration used to guess from the registry timestamps whether the user
    had enabled an entity and disabled it otherwise. Whether a disabled-by-default
    entity is enabled is the user's choice; the integration must not undo it.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    device_data = _make_swsd2_device()
    dev_id = device_data["id"]

    client = MagicMock()
    client.hcu_device_id = "hcu-main"
    client.hcu_part_device_ids = set()
    client.state = {"devices": {dev_id: device_data}, "groups": {}}
    client.get_device_by_address = MagicMock(return_value=device_data)

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = {dev_id: device_data}

    ent_reg = er.async_get(hass)
    enabled = [
        ent_reg.async_get_or_create(
            domain="sensor",
            platform=DOMAIN,
            unique_id=f"{dev_id}_1_{feature}",
            config_entry=entry,
        )
        for feature in ("lastSmokeTestTimestamp", "smokeTestCounter")
    ]
    for reg_entry in enabled:
        assert reg_entry.disabled_by is None
        # Looks untouched: modified within a second of its creation.
        assert (reg_entry.modified_at - reg_entry.created_at).total_seconds() < 1

    await async_discover_entities(hass, client, entry, coordinator)

    for reg_entry in enabled:
        updated = ent_reg.async_get(reg_entry.entity_id)
        assert updated is not None
        assert updated.disabled_by is None
