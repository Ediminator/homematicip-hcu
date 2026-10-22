"""Tests for the siren entity of ALARM_SWITCHING groups."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.siren import ATTR_DURATION, SirenEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.discovery import _discover_entities_for_group
from custom_components.hcu_integration.select import HcuAlarmSignalAcoustic
from custom_components.hcu_integration.siren import HcuAlarmSiren, async_setup_entry


def _siren_group(**overrides) -> dict:
    group = {
        "id": "grp-siren",
        "type": "ALARM_SWITCHING",
        "label": "SIREN",
        "on": None,
        "onTime": 180.0,
        "signalAcoustic": "FREQUENCY_RISING",
        "signalOptical": "DOUBLE_FLASHING_REPEATING",
        "channels": [
            {"deviceId": "smoke-1", "channelIndex": 1},
            {"deviceId": "smoke-2", "channelIndex": 1},
        ],
    }
    group.update(overrides)
    return group


def _make_siren(group: dict) -> tuple[HcuAlarmSiren, MagicMock]:
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {group["id"]: group}
    client = MagicMock()
    client.hcu_device_id = "hcu-1"
    client.is_connected = True
    client.get_group_by_id = MagicMock(return_value=group)
    client.async_set_alarm_switching_group_state = AsyncMock()
    client.async_set_switching_group_state_with_time = AsyncMock()
    siren = HcuAlarmSiren(coordinator, client, group)
    siren.entity_id = "siren.indoor_sirene"
    siren.async_write_ha_state = MagicMock()
    return siren, client


# --- Discovery ---


def test_alarm_switching_group_with_members_gets_a_siren() -> None:
    group = _siren_group()
    client = MagicMock()
    client.state = {"devices": {}, "groups": {group["id"]: group}}
    client.get_group_by_id = MagicMock(return_value=group)
    entry = MagicMock()
    entry.options = {}

    entities, unique_ids, status = _discover_entities_for_group(
        group, entry, MagicMock(), client
    )

    assert status == "discovered"
    sirens = entities[Platform.SIREN]
    assert len(sirens) == 1
    assert isinstance(sirens[0], HcuAlarmSiren)
    assert "grp-siren_siren" in unique_ids
    # The signal test selects stay on the same group device.
    assert any(isinstance(e, HcuAlarmSignalAcoustic) for e in entities[Platform.SELECT])


@pytest.mark.parametrize(
    "group",
    [
        _siren_group(channels=[]),  # no member devices
        _siren_group(label="SIREN_SAFETY"),  # safety alarm group
        _siren_group(type="SECURITY_BACKUP_ALARM_SWITCHING"),  # backup alarm
    ],
)
def test_no_siren_for_empty_safety_or_backup_groups(group: dict) -> None:
    client = MagicMock()
    client.state = {"devices": {}, "groups": {group["id"]: group}}
    client.get_group_by_id = MagicMock(return_value=group)
    entry = MagicMock()
    entry.options = {}

    entities, _, _ = _discover_entities_for_group(group, entry, MagicMock(), client)

    assert entities[Platform.SIREN] == []


# --- Entity ---


def test_siren_is_the_group_devices_main_entity() -> None:
    siren, _ = _make_siren(_siren_group())

    assert siren.unique_id == "grp-siren_siren"
    assert siren.has_entity_name is True
    assert siren.name is None  # shown with the device name
    assert siren.device_info["name"] == "Indoor Sirene"
    assert siren.supported_features == (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
    )


@pytest.mark.parametrize(
    ("on", "expected"), [(True, True), (False, False), (None, False)]
)
def test_siren_state_follows_group(on: bool | None, expected: bool) -> None:
    siren, _ = _make_siren(_siren_group(on=on))

    assert siren.is_on is expected


async def test_siren_turn_on_uses_group_switching_request() -> None:
    siren, client = _make_siren(_siren_group(on=False))

    await siren.async_turn_on()

    client.async_set_alarm_switching_group_state.assert_awaited_once_with(
        group_id="grp-siren", on=True
    )
    client.async_set_switching_group_state_with_time.assert_not_awaited()
    assert siren.is_on is True
    assert siren.assumed_state is True


async def test_siren_turn_on_with_duration() -> None:
    siren, client = _make_siren(_siren_group(on=False))

    await siren.async_turn_on(**{ATTR_DURATION: 10})

    client.async_set_switching_group_state_with_time.assert_awaited_once_with(
        group_id="grp-siren", on=True, on_time=10.0
    )
    client.async_set_alarm_switching_group_state.assert_not_awaited()


async def test_siren_turn_off() -> None:
    siren, client = _make_siren(_siren_group(on=True))

    await siren.async_turn_off()

    client.async_set_alarm_switching_group_state.assert_awaited_once_with(
        group_id="grp-siren", on=False
    )
    assert siren.is_on is False


async def test_siren_confirmed_state_replaces_optimistic_state() -> None:
    group = _siren_group(on=False)
    siren, _ = _make_siren(group)
    await siren.async_turn_on()

    # The HCU reports the group as still off (e.g. the alarm ended at once).
    siren._handle_coordinator_update()

    assert siren.assumed_state is False
    assert siren.is_on is False


@pytest.mark.parametrize("error", [HcuApiError("rejected"), ConnectionError("down")])
@pytest.mark.parametrize(
    ("action", "kwargs"),
    [
        ("async_turn_on", {}),
        ("async_turn_on", {ATTR_DURATION: 5}),
        ("async_turn_off", {}),
    ],
)
async def test_siren_failure_reverts_and_raises(
    error: Exception, action: str, kwargs: dict, caplog: pytest.LogCaptureFixture
) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    client.async_set_alarm_switching_group_state.side_effect = error
    client.async_set_switching_group_state_with_time.side_effect = error

    with caplog.at_level(logging.ERROR), pytest.raises(HomeAssistantError) as exc_info:
        await getattr(siren, action)(**kwargs)

    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders["entity"] == "siren.indoor_sirene"
    assert siren.assumed_state is False
    assert siren.is_on is False
    assert "Failed to switch siren" in caplog.text


async def test_siren_platform_setup_adds_discovered_sirens(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    siren_entity = MagicMock()
    coordinator = MagicMock()
    coordinator.entities = {Platform.SIREN: [siren_entity]}
    entry.runtime_data = coordinator
    added: list = []

    await async_setup_entry(hass, entry, added.extend)

    assert added == [siren_entity]
    coordinator.async_register_platform.assert_called_once_with(
        Platform.SIREN, added.extend
    )

    coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, added.extend)
    assert added == []


async def test_failed_turn_off_keeps_the_siren_shown_as_on() -> None:
    """A failed stop must not show the siren as off while it still sounds."""
    siren, client = _make_siren(_siren_group(on=False))
    await siren.async_turn_on()  # accepted, HCU confirmation not yet received
    client.async_set_alarm_switching_group_state.side_effect = HcuApiError("busy")

    with pytest.raises(HomeAssistantError):
        await siren.async_turn_off()

    assert siren.is_on is True
    assert siren.assumed_state is True

    # The next group update from the HCU decides again.
    siren._handle_coordinator_update()
    assert siren.assumed_state is False
    assert siren.is_on is False
