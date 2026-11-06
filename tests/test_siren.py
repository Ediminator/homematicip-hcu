"""Tests for the siren entity of ALARM_SWITCHING groups."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.siren import ATTR_DURATION, SirenEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    AUTH_TYPE_PLUGIN,
    DOMAIN,
)
from custom_components.hcu_integration.discovery import _discover_entities_for_group
from custom_components.hcu_integration.entity import HcuGroupBaseEntity
from custom_components.hcu_integration.select import (
    HcuAlarmSignalAcoustic,
    HcuAlarmSignalOptical,
)
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
            {"deviceId": "asir-1", "channelIndex": 1},
            {"deviceId": "smoke-1", "channelIndex": 1},
        ],
    }
    group.update(overrides)
    return group


# A HmIP-ASIR-2 alarm siren and a HmIP-SWSD smoke detector.
_DEVICES = {
    "asir-1": {
        "id": "asir-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_SABOTAGE"},
            "1": {"functionalChannelType": "ALARM_SIREN_CHANNEL"},
        },
    },
    "smoke-1": {
        "id": "smoke-1",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "SMOKE_DETECTOR_CHANNEL"},
        },
    },
}


def _discover(group: dict, auth_type: str = AUTH_TYPE_DUAL) -> tuple:
    client = MagicMock()
    client._auth_type = auth_type
    client.state = {"devices": _DEVICES, "groups": {group["id"]: group}}
    client.get_group_by_id = MagicMock(return_value=group)
    entry = MagicMock()
    entry.options = {}
    return _discover_entities_for_group(group, entry, MagicMock(), client)


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


@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_DUAL])
def test_alarm_group_with_a_siren_gets_siren_and_signal_tests(auth_type: str) -> None:
    entities, unique_ids, status = _discover(_siren_group(), auth_type)

    assert status == "discovered"
    sirens = entities[Platform.SIREN]
    assert len(sirens) == 1
    assert isinstance(sirens[0], HcuAlarmSiren)
    assert unique_ids == {
        "grp-siren_siren",
        "grp-siren_test_signal_acoustic",
        "grp-siren_test_signal_optical",
    }
    # The signal test selects stay on the same group device.
    assert {type(e) for e in entities[Platform.SELECT]} == {
        HcuAlarmSignalAcoustic,
        HcuAlarmSignalOptical,
    }


def test_plugin_user_gets_the_siren_but_no_signal_tests() -> None:
    """The HCU rejects the test signal paths for plugins (NOT_ALLOWED, #516)."""
    entities, unique_ids, _ = _discover(_siren_group(), AUTH_TYPE_PLUGIN)

    assert [type(e) for e in entities[Platform.SIREN]] == [HcuAlarmSiren]
    assert entities[Platform.SELECT] == []
    assert unique_ids == {"grp-siren_siren"}


@pytest.mark.parametrize(
    "channels",
    [
        # Only smoke detectors: they ignore the group switch.
        [{"deviceId": "smoke-1", "channelIndex": 1}],
        # A member of an unknown device, a non-siren channel and a malformed ref.
        [
            {"deviceId": "unknown", "channelIndex": 1},
            {"deviceId": "asir-1", "channelIndex": 0},
            "asir-1",
        ],
    ],
)
@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_PLUGIN])
def test_alarm_group_without_a_siren_gets_no_entities(
    channels: list, auth_type: str
) -> None:
    entities, unique_ids, status = _discover(_siren_group(channels=channels), auth_type)

    assert status == "discovered"
    assert entities[Platform.SIREN] == []
    assert entities[Platform.SELECT] == []
    assert unique_ids == set()


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


def test_siren_device_info_without_dict_copy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HcuAlarmSwitchingGroupEntity renames SIREN without calling DeviceInfo.copy()."""

    class _DeviceInfoWithoutCopy(dict):
        copy = None

    monkeypatch.setattr(
        HcuGroupBaseEntity,
        "device_info",
        property(
            lambda self: _DeviceInfoWithoutCopy(
                identifiers={(DOMAIN, self._group_id)}, name="SIREN"
            )
        ),
    )
    siren, _ = _make_siren(_siren_group())
    assert siren.device_info["name"] == "Indoor Sirene"


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


async def test_siren_turn_on_with_duration_turns_off_after_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The HCU ignores onTime for alarm groups, so Home Assistant turns it off."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass

    await siren.async_turn_on(**{ATTR_DURATION: 10})

    client.async_set_alarm_switching_group_state.assert_awaited_once_with(
        group_id="grp-siren", on=True
    )
    client.async_set_switching_group_state_with_time.assert_not_awaited()

    freezer.tick(9)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    client.async_set_alarm_switching_group_state.assert_awaited_once()

    freezer.tick(2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_set_alarm_switching_group_state.await_args_list[-1].kwargs == {
        "group_id": "grp-siren",
        "on": False,
    }
    assert client.async_set_alarm_switching_group_state.await_count == 2
    assert siren.is_on is False


async def test_siren_duration_timer_cancelled_by_turn_off_and_group_update(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    group = _siren_group(on=False)
    siren, client = _make_siren(group)
    siren.hass = hass

    # A manual turn off cancels the pending automatic turn off.
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    await siren.async_turn_off()
    # The HCU reports the group off (its own limit or the app) and cancels too.
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    group["on"] = True
    siren._handle_coordinator_update()
    assert siren._auto_off_unsub is not None
    group["on"] = False
    siren._handle_coordinator_update()
    assert siren._auto_off_unsub is None
    # Removing the entity cancels a pending timer.
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    await siren.async_will_remove_from_hass()
    assert siren._auto_off_unsub is None

    freezer.tick(30)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [
        c.kwargs["on"]
        for c in client.async_set_alarm_switching_group_state.await_args_list
    ] == [
        True,
        False,
        True,
        True,
    ]


async def test_siren_failed_automatic_turn_off_is_logged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    client.async_set_alarm_switching_group_state.side_effect = HcuApiError("busy")

    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "Could not turn off siren siren.indoor_sirene after its duration" in (
        caplog.text
    )
    assert siren.is_on is True


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


async def test_failed_command_does_not_override_newer_group_update() -> None:
    """A group update that arrives while a command is running wins over the rollback."""
    group = _siren_group(on=False)
    siren, client = _make_siren(group)
    await siren.async_turn_on()  # accepted, waiting for confirmation

    async def stop_fails_after_update(**_kwargs) -> None:
        # The HCU reports the alarm as ended while the stop request is open.
        group["on"] = False
        siren._handle_coordinator_update()
        raise HcuApiError("busy")

    client.async_set_alarm_switching_group_state.side_effect = stop_fails_after_update

    with pytest.raises(HomeAssistantError):
        await siren.async_turn_off()

    assert siren.assumed_state is False
    assert siren.is_on is False


async def test_overlapping_turn_on_keeps_siren_on_when_first_fails() -> None:
    """A failed earlier turn_on must not roll back a second turn_on that succeeds."""
    siren, client = _make_siren(_siren_group(on=False))
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    release_second = asyncio.Event()
    calls = 0

    async def switch_side_effect(**_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_entered.set()
            await release_first.wait()
            raise HcuApiError("transient")
        await release_second.wait()

    client.async_set_alarm_switching_group_state.side_effect = switch_side_effect

    first = asyncio.create_task(siren.async_turn_on())
    await first_entered.wait()
    second = asyncio.create_task(siren.async_turn_on())
    await asyncio.sleep(0)

    release_first.set()
    with pytest.raises(HomeAssistantError):
        await first

    release_second.set()
    await second

    assert siren.is_on is True
    assert siren.assumed_state is True


async def test_overlapping_turn_on_and_turn_off_that_both_fail_stay_off() -> None:
    """A failed turn_off queued behind a failed turn_on must not restore an unconfirmed on state."""
    siren, client = _make_siren(_siren_group(on=False))
    first_entered = asyncio.Event()
    release_first = asyncio.Event()
    release_second = asyncio.Event()
    calls = 0

    async def switch_side_effect(**_kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            first_entered.set()
            await release_first.wait()
            raise HcuApiError("offline")
        await release_second.wait()
        raise HcuApiError("offline")

    client.async_set_alarm_switching_group_state.side_effect = switch_side_effect

    first = asyncio.create_task(siren.async_turn_on())
    await first_entered.wait()
    second = asyncio.create_task(siren.async_turn_off())
    await asyncio.sleep(0)

    release_first.set()
    with pytest.raises(HomeAssistantError):
        await first

    release_second.set()
    with pytest.raises(HomeAssistantError):
        await second

    assert siren.is_on is False
    assert siren.assumed_state is False


async def test_failed_command_keeps_the_timed_stop(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A failed turn off must not drop the stop of an earlier timed turn on."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    client.async_set_alarm_switching_group_state.side_effect = [
        HcuApiError("busy", error_code="DEVICE_BUSY"),
        None,
    ]

    with pytest.raises(HomeAssistantError):
        await siren.async_turn_off()
    assert siren._auto_off_unsub is not None

    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    calls = client.async_set_alarm_switching_group_state.await_args_list
    assert [c.kwargs["on"] for c in calls] == [True, False, False]
    assert siren.is_on is False


async def test_timed_stop_skipped_after_a_newer_accepted_command(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A timed stop that fires while a newer turn on runs must not stop it."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})

    entered = asyncio.Event()
    release = asyncio.Event()

    async def slow_turn_on(**_kwargs: object) -> None:
        entered.set()
        await release.wait()

    client.async_set_alarm_switching_group_state.side_effect = slow_turn_on
    second = hass.async_create_task(siren.async_turn_on(**{ATTR_DURATION: 60}))
    await entered.wait()

    # The first deadline passes while the second turn on waits for the HCU.
    freezer.tick(6)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    release.set()
    await second
    await hass.async_block_till_done()

    calls = client.async_set_alarm_switching_group_state.await_args_list
    assert [c.kwargs["on"] for c in calls] == [True, True]
    assert siren.is_on is True

    client.async_set_alarm_switching_group_state.side_effect = None
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [c.kwargs["on"] for c in calls] == [True, True, False]
