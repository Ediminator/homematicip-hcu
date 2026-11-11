"""Tests for the siren entity of ALARM_SWITCHING groups."""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    SirenEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
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
from custom_components.hcu_integration.siren import (
    _STOP_RETRY_DELAYS,
    HcuAlarmSiren,
    HcuSirenStoredData,
    async_setup_entry,
)

from .test_dynamic_devices import _make_client


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
    client.async_test_alarm_signal_acoustic = AsyncMock()
    client.async_test_alarm_signal_optical = AsyncMock()
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


def test_plugin_user_gets_no_siren_and_no_signal_tests() -> None:
    """The HCU rejects the test signal paths for plugins (NOT_ALLOWED, #516).

    Switching the group with setState is accepted but stays silent, so a
    Plugin User entry has nothing that could sound the sirens.
    """
    entities, unique_ids, status = _discover(_siren_group(), AUTH_TYPE_PLUGIN)

    assert status == "discovered"
    assert entities[Platform.SIREN] == []
    assert entities[Platform.SELECT] == []
    assert unique_ids == set()


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
        | SirenEntityFeature.TONES
        | SirenEntityFeature.DURATION
    )
    assert siren.available_tones[:2] == ["frequency_rising", "frequency_falling"]
    assert "disable_acoustic_signal" not in siren.available_tones
    assert siren.assumed_state is True
    assert siren.is_on is False


def test_tones_are_the_acoustic_signals_of_the_test_select() -> None:
    """The tones are sent to the HCU in upper case, so none may get lost or renamed."""
    siren, _ = _make_siren(_siren_group())

    assert siren.available_tones == [
        "frequency_rising",
        "frequency_falling",
        "frequency_rising_and_falling",
        "frequency_alternating_low_high",
        "frequency_alternating_low_mid_high",
        "frequency_highon_off",
        "frequency_highon_longoff",
        "frequency_lowon_off_highon_off",
        "frequency_lowon_longoff_highon_longoff",
        "low_battery",
        "disarmed",
        "internally_armed",
        "externally_armed",
        "delayed_internally_armed",
        "delayed_externally_armed",
        "event",
        "error",
    ]
    # The acoustic test select keeps its options: the stop entry plus the tones.
    entities, _, _ = _discover(_siren_group(), AUTH_TYPE_DUAL)
    acoustic = next(
        e for e in entities[Platform.SELECT] if isinstance(e, HcuAlarmSignalAcoustic)
    )
    assert acoustic.options == ["disable_acoustic_signal", *siren.available_tones]


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
def test_siren_shows_a_real_alarm_from_the_group(
    on: bool | None, expected: bool
) -> None:
    """The group is on during a real intrusion alarm."""
    siren, _ = _make_siren(_siren_group(on=on))

    assert siren.is_on is expected


async def test_turn_on_plays_the_configured_signal_and_stops_after_on_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Without tone or duration the group's signals and alarm duration are used."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass

    await siren.async_turn_on()

    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "FREQUENCY_RISING"
    )
    client.async_test_alarm_signal_optical.assert_awaited_once_with(
        "grp-siren", "DOUBLE_FLASHING_REPEATING"
    )
    # setState is accepted by the HCU but stays silent (#516).
    client.async_set_alarm_switching_group_state.assert_not_awaited()
    client.async_set_switching_group_state_with_time.assert_not_awaited()
    assert siren.is_on is True
    assert siren.assumed_state is True

    freezer.tick(179)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_test_alarm_signal_acoustic.await_count == 1
    assert siren.is_on is True

    freezer.tick(2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_test_alarm_signal_acoustic.await_args_list[-1].args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )
    assert client.async_test_alarm_signal_optical.await_args_list[-1].args == (
        "grp-siren",
        "DISABLE_OPTICAL_SIGNAL",
    )
    assert siren.is_on is False


async def test_turn_on_with_tone_and_duration(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass

    await siren.async_turn_on(**{ATTR_TONE: "frequency_highon_off", ATTR_DURATION: 10})

    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "FREQUENCY_HIGHON_OFF"
    )
    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [
        c.args[1] for c in client.async_test_alarm_signal_acoustic.await_args_list
    ] == [
        "FREQUENCY_HIGHON_OFF",
        "DISABLE_ACOUSTIC_SIGNAL",
    ]
    assert siren.is_on is False


@pytest.mark.parametrize(
    ("overrides", "tone", "optical", "duration"),
    [
        # Unknown or missing values fall back to safe defaults.
        ({"signalAcoustic": "SOMETHING_NEW"}, "FREQUENCY_RISING", True, 180),
        ({"signalAcoustic": None}, "FREQUENCY_RISING", True, 180),
        ({"signalAcoustic": "DISABLE_ACOUSTIC_SIGNAL"}, "FREQUENCY_RISING", True, 180),
        # No optical signal set on the group: no optical requests at all.
        ({"signalOptical": "DISABLE_OPTICAL_SIGNAL"}, "FREQUENCY_RISING", False, 180),
        ({"signalOptical": None}, "FREQUENCY_RISING", False, 180),
        # No usable alarm duration on the group: three minutes.
        ({"onTime": None}, "FREQUENCY_RISING", True, 180),
        ({"onTime": 0}, "FREQUENCY_RISING", True, 180),
        ({"onTime": 30.0, "signalAcoustic": "EVENT"}, "EVENT", True, 30),
    ],
)
async def test_group_settings_and_defaults(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    overrides: dict,
    tone: str,
    optical: bool,
    duration: int,
) -> None:
    siren, client = _make_siren(_siren_group(on=False, **overrides))
    siren.hass = hass

    await siren.async_turn_on()

    client.async_test_alarm_signal_acoustic.assert_awaited_once_with("grp-siren", tone)
    assert client.async_test_alarm_signal_optical.await_count == (1 if optical else 0)

    freezer.tick(duration - 1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert siren.is_on is True
    freezer.tick(2)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert siren.is_on is False
    assert client.async_test_alarm_signal_optical.await_count == (2 if optical else 0)


async def test_turn_off_stops_both_signals_and_the_timer(hass: HomeAssistant) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 10})

    await siren.async_turn_off()

    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )
    assert client.async_test_alarm_signal_optical.await_args.args == (
        "grp-siren",
        "DISABLE_OPTICAL_SIGNAL",
    )
    assert siren._auto_off_unsub is None
    assert siren.is_on is False
    client.async_set_alarm_switching_group_state.assert_not_awaited()


async def test_removing_the_entity_cancels_the_timer(hass: HomeAssistant) -> None:
    siren, _ = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 10})

    await siren.async_will_remove_from_hass()

    assert siren._auto_off_unsub is None


@pytest.mark.parametrize("error", [HcuApiError("rejected"), ConnectionError("down")])
async def test_failed_turn_on_raises_and_stays_off(
    hass: HomeAssistant,
    error: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    client.async_test_alarm_signal_acoustic.side_effect = error

    with caplog.at_level(logging.ERROR), pytest.raises(HomeAssistantError) as exc_info:
        await siren.async_turn_on()

    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders["entity"] == "siren.indoor_sirene"
    assert siren.is_on is False
    assert siren._auto_off_unsub is None
    client.async_test_alarm_signal_optical.assert_not_awaited()
    assert "Failed to turn on siren grp-siren" in caplog.text


async def test_failed_optical_signal_keeps_the_sounding_siren_on(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The acoustic signal already plays, so the siren is on and stops on time."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    client.async_test_alarm_signal_optical.side_effect = [HcuApiError("busy"), None]

    with caplog.at_level(logging.ERROR), pytest.raises(HomeAssistantError) as exc_info:
        await siren.async_turn_on(**{ATTR_DURATION: 10})

    assert exc_info.value.translation_key == "command_failed"
    assert "plays its acoustic signal, but the optical signal failed" in caplog.text
    assert siren.is_on is True
    assert siren._auto_off_unsub is not None

    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert siren.is_on is False
    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )


async def test_duration_zero_stops_right_away(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """An explicit duration of 0 is not replaced by the group's alarm duration."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass

    await siren.async_turn_on(**{ATTR_DURATION: 0})
    freezer.tick(1)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert siren.is_on is False
    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )


async def test_failed_turn_off_keeps_the_siren_on_and_the_timed_stop(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed stop must not show the siren as off, and the timed stop retries."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    client.async_test_alarm_signal_acoustic.side_effect = [
        HcuApiError("busy", error_code="DEVICE_BUSY"),
        None,
    ]

    with caplog.at_level(logging.ERROR), pytest.raises(HomeAssistantError):
        await siren.async_turn_off()
    assert "Failed to turn off siren grp-siren" in caplog.text
    assert siren.is_on is True
    assert siren._auto_off_unsub is not None

    freezer.tick(11)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert siren.is_on is False
    assert [
        c.args[1] for c in client.async_test_alarm_signal_acoustic.await_args_list
    ] == [
        "FREQUENCY_RISING",
        "DISABLE_ACOUSTIC_SIGNAL",
        "DISABLE_ACOUSTIC_SIGNAL",
    ]


async def _pass(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: float
) -> None:
    freezer.tick(seconds)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_failed_automatic_stop_is_retried_until_it_works(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stop that fails, for example while the HCU restarts, is tried again."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    acoustic = client.async_test_alarm_signal_acoustic
    acoustic.side_effect = [HcuApiError("busy"), ConnectionError("down"), None]

    await _pass(hass, freezer, 6)
    assert (
        "Could not stop siren siren.indoor_sirene after its duration; "
        "trying again in 5 seconds"
    ) in caplog.text
    assert siren.is_on is True
    assert siren._auto_off_unsub is not None
    assert acoustic.await_count == 2

    # Not before the first wait is over.
    await _pass(hass, freezer, 4)
    assert acoustic.await_count == 2
    await _pass(hass, freezer, 2)
    assert acoustic.await_count == 3
    assert "trying again in 15 seconds" in caplog.text
    assert siren.is_on is True

    await _pass(hass, freezer, 16)
    assert [c.args[1] for c in acoustic.await_args_list] == [
        "FREQUENCY_RISING",
        "DISABLE_ACOUSTIC_SIGNAL",
        "DISABLE_ACOUSTIC_SIGNAL",
        "DISABLE_ACOUSTIC_SIGNAL",
    ]
    assert siren.is_on is False
    assert siren._auto_off_unsub is None
    assert siren.extra_restore_state_data is None


async def test_failed_automatic_stop_gives_up_after_the_last_retry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    client.async_test_alarm_signal_acoustic.side_effect = HcuApiError("denied")

    await _pass(hass, freezer, 6)
    assert _STOP_RETRY_DELAYS == (5.0, 15.0, 30.0, 60.0, 60.0, 60.0)
    for delay in _STOP_RETRY_DELAYS:
        assert siren._auto_off_unsub is not None
        await _pass(hass, freezer, delay + 1)

    # One turn on, the stop at the duration, and one stop per retry.
    assert client.async_test_alarm_signal_acoustic.await_count == 2 + len(
        _STOP_RETRY_DELAYS
    )
    assert "also not in 6 further attempts" in caplog.text
    assert siren._auto_off_unsub is None
    # The siren may still sound, so it is not shown as off.
    assert siren.is_on is True

    await _pass(hass, freezer, 600)
    assert client.async_test_alarm_signal_acoustic.await_count == 2 + len(
        _STOP_RETRY_DELAYS
    )


@pytest.mark.parametrize("newer", ["turn_on", "turn_off"])
async def test_newer_command_ends_the_stop_retries(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, newer: str
) -> None:
    """A command accepted while a failed stop waits for its retry takes over."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    acoustic = client.async_test_alarm_signal_acoustic
    acoustic.side_effect = [HcuApiError("busy"), None, None]
    await _pass(hass, freezer, 6)
    assert siren._auto_off_unsub is not None

    if newer == "turn_on":
        await siren.async_turn_on(**{ATTR_DURATION: 600})
    else:
        await siren.async_turn_off()
    calls = acoustic.await_count

    # The retry of the old stop (after 5 seconds) must not run any more.
    await _pass(hass, freezer, 30)
    assert acoustic.await_count == calls
    assert siren.is_on is (newer == "turn_on")
    await siren.async_will_remove_from_hass()


async def test_turn_on_queued_behind_a_failing_stop_replaces_its_retry(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A turn on that waits while the timed stop fails must not be stopped by its retry."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    entered = asyncio.Event()
    release = asyncio.Event()
    calls = 0

    async def acoustic(*_args: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            # The timed stop: fails after the turn on below has queued up.
            entered.set()
            await release.wait()
            raise HcuApiError("busy")

    client.async_test_alarm_signal_acoustic.side_effect = acoustic
    freezer.tick(6)
    async_fire_time_changed(hass)
    await entered.wait()
    queued = hass.async_create_task(siren.async_turn_on(**{ATTR_DURATION: 600}))
    await asyncio.sleep(0)
    release.set()
    await queued
    assert siren.is_on is True

    # The retry of the failed stop was due after 5 seconds.
    await _pass(hass, freezer, 60)
    assert [
        c.args[1] for c in client.async_test_alarm_signal_acoustic.await_args_list
    ] == ["FREQUENCY_RISING", "DISABLE_ACOUSTIC_SIGNAL", "FREQUENCY_RISING"]
    assert siren.is_on is True
    await siren.async_will_remove_from_hass()


async def test_stop_failing_while_the_entity_is_removed_is_not_retried(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The reloaded entity takes over the stored stop time instead."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    entered = asyncio.Event()
    release = asyncio.Event()

    async def failing_stop(*_args: object) -> None:
        entered.set()
        await release.wait()
        raise HcuApiError("busy")

    client.async_test_alarm_signal_acoustic.side_effect = failing_stop
    freezer.tick(6)
    async_fire_time_changed(hass)
    await entered.wait()

    stored = siren.extra_restore_state_data
    await siren.async_will_remove_from_hass()
    release.set()
    await hass.async_block_till_done()

    assert siren._auto_off_unsub is None
    assert stored is not None
    assert siren.extra_restore_state_data == stored


async def test_second_turn_on_replaces_the_first_timed_stop(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The stop of an earlier turn on is cancelled, and the new one stays tracked."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    await siren.async_turn_on(**{ATTR_DURATION: 60})

    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert client.async_test_alarm_signal_acoustic.await_count == 2
    assert siren.is_on is True
    assert siren._auto_off_unsub is not None

    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )
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

    async def slow_turn_on(*_args: object) -> None:
        entered.set()
        await release.wait()

    client.async_test_alarm_signal_acoustic.side_effect = slow_turn_on
    second = hass.async_create_task(siren.async_turn_on(**{ATTR_DURATION: 60}))
    await entered.wait()

    # The first deadline passes while the second turn on waits for the HCU.
    freezer.tick(6)
    async_fire_time_changed(hass)
    await asyncio.sleep(0)
    release.set()
    await second
    await hass.async_block_till_done()

    calls = client.async_test_alarm_signal_acoustic.await_args_list
    assert [c.args[1] for c in calls] == ["FREQUENCY_RISING", "FREQUENCY_RISING"]
    assert siren.is_on is True

    client.async_test_alarm_signal_acoustic.side_effect = None
    freezer.tick(60)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert [c.args[1] for c in calls] == [
        "FREQUENCY_RISING",
        "FREQUENCY_RISING",
        "DISABLE_ACOUSTIC_SIGNAL",
    ]
    assert siren.is_on is False


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


# --- A started optical signal is stopped, whatever the group says by then ---


@pytest.mark.parametrize("new_setting", ["DISABLE_OPTICAL_SIGNAL", None])
@pytest.mark.parametrize("stop", ["turn_off", "timed"])
async def test_started_light_is_stopped_after_the_group_setting_changed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    new_setting: str | None,
    stop: str,
) -> None:
    """The light was started, so it is stopped even if the setting is off by then."""
    group = _siren_group(on=False)
    siren, client = _make_siren(group)
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    # The optical signal of the group is turned off in the Homematic IP app.
    group["signalOptical"] = new_setting

    if stop == "turn_off":
        await siren.async_turn_off()
    else:
        await _pass(hass, freezer, 11)

    assert [c.args for c in client.async_test_alarm_signal_optical.await_args_list] == [
        ("grp-siren", "DOUBLE_FLASHING_REPEATING"),
        ("grp-siren", "DISABLE_OPTICAL_SIGNAL"),
    ]
    assert siren.is_on is False


async def test_light_of_an_earlier_turn_on_is_still_stopped(
    hass: HomeAssistant,
) -> None:
    """A second turn on without a light must not forget the light of the first."""
    group = _siren_group(on=False)
    siren, client = _make_siren(group)
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 60})
    group["signalOptical"] = None
    await siren.async_turn_on(**{ATTR_DURATION: 60})
    assert client.async_test_alarm_signal_optical.await_count == 1

    await siren.async_turn_off()

    assert client.async_test_alarm_signal_optical.await_count == 2
    assert client.async_test_alarm_signal_optical.await_args.args == (
        "grp-siren",
        "DISABLE_OPTICAL_SIGNAL",
    )


async def test_stopped_light_is_not_stopped_again(hass: HomeAssistant) -> None:
    """After a stop, only the group's setting decides about the optical stop."""
    group = _siren_group(on=False)
    siren, client = _make_siren(group)
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 60})
    await siren.async_turn_off()
    group["signalOptical"] = None
    optical_calls = client.async_test_alarm_signal_optical.await_count

    await siren.async_turn_off()

    assert client.async_test_alarm_signal_optical.await_count == optical_calls
    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )


@pytest.mark.parametrize(
    ("setting", "optical_stop"), [("DOUBLE_FLASHING_REPEATING", True), (None, False)]
)
async def test_turn_off_without_a_known_signal_follows_the_group_setting(
    setting: str | None, optical_stop: bool
) -> None:
    """A signal started elsewhere, for example with the test selects, can be stopped."""
    siren, client = _make_siren(_siren_group(on=False, signalOptical=setting))

    await siren.async_turn_off()

    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "DISABLE_ACOUSTIC_SIGNAL"
    )
    assert client.async_test_alarm_signal_optical.await_count == (
        1 if optical_stop else 0
    )


@pytest.mark.parametrize(
    ("setting", "optical"), [("DOUBLE_FLASHING_REPEATING", True), (None, False)]
)
async def test_stored_data_says_whether_a_light_was_started(
    hass: HomeAssistant, setting: str | None, optical: bool
) -> None:
    siren, _ = _make_siren(_siren_group(on=False, signalOptical=setting))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 30})

    stored = siren.extra_restore_state_data

    assert stored is not None
    assert stored.optical is optical
    assert stored.as_dict()["optical"] is optical
    await siren.async_will_remove_from_hass()


# --- Stop time kept over restarts and reloads ---


def test_stop_time_is_stored_only_while_a_signal_runs() -> None:
    siren, _ = _make_siren(_siren_group(on=False))

    assert siren.extra_restore_state_data is None
    # A real alarm (group on) was not started here and has no stop time.
    siren_alarm, _ = _make_siren(_siren_group(on=True))
    assert siren_alarm.extra_restore_state_data is None


async def test_turn_on_stores_the_stop_time_and_turn_off_clears_it(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    siren, _ = _make_siren(_siren_group(on=False))
    siren.hass = hass
    started = dt_util.utcnow()

    await siren.async_turn_on(**{ATTR_DURATION: 45})

    stored = siren.extra_restore_state_data
    assert stored == HcuSirenStoredData(started + timedelta(seconds=45))
    assert stored.as_dict() == {
        "stop_at": (started + timedelta(seconds=45)).isoformat(),
        "optical": True,
    }

    await siren.async_turn_off()
    assert siren.extra_restore_state_data is None


async def _restore(
    hass: HomeAssistant, extra: dict | None, group: dict | None = None
) -> tuple[HcuAlarmSiren, MagicMock]:
    siren, client = _make_siren(group or _siren_group(on=False))
    siren.hass = hass
    last = RestoredExtraData(extra) if extra is not None else None
    with patch.object(siren, "async_get_last_extra_data", AsyncMock(return_value=last)):
        await siren.async_added_to_hass()
    return siren, client


async def test_restored_signal_is_stopped_at_its_stop_time(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """After a restart or reload the signal still stops when it was meant to."""
    stop_at = dt_util.utcnow() + timedelta(seconds=40)

    siren, client = await _restore(hass, {"stop_at": stop_at.isoformat()})

    assert siren.is_on is True
    assert siren.extra_restore_state_data == HcuSirenStoredData(stop_at)
    client.async_test_alarm_signal_acoustic.assert_not_awaited()

    await _pass(hass, freezer, 39)
    client.async_test_alarm_signal_acoustic.assert_not_awaited()
    await _pass(hass, freezer, 2)
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "DISABLE_ACOUSTIC_SIGNAL"
    )
    client.async_test_alarm_signal_optical.assert_awaited_once_with(
        "grp-siren", "DISABLE_OPTICAL_SIGNAL"
    )
    assert siren.is_on is False


async def test_restored_signal_past_its_stop_time_is_stopped_at_once(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Home Assistant was down when the stop was due, so it is sent right away."""
    stop_at = dt_util.utcnow() - timedelta(minutes=5)

    siren, client = await _restore(hass, {"stop_at": stop_at.isoformat()})
    assert siren.is_on is True

    await _pass(hass, freezer, 1)
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "DISABLE_ACOUSTIC_SIGNAL"
    )
    assert siren.is_on is False


@pytest.mark.parametrize(
    "extra", [None, {}, {"stop_at": None}, {"stop_at": "not a time"}, {"stop_at": 5}]
)
async def test_nothing_to_restore_leaves_the_siren_off(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, extra: dict | None
) -> None:
    siren, client = await _restore(hass, extra)

    assert siren.is_on is False
    assert siren._auto_off_unsub is None
    await _pass(hass, freezer, 600)
    client.async_test_alarm_signal_acoustic.assert_not_awaited()


@pytest.mark.parametrize(
    ("stored_optical", "optical_stop"),
    [
        (True, True),
        (False, False),
        # Data stored by 2.7.2-beta1 has no entry: the light is stopped as well.
        (None, True),
        ("yes", True),
    ],
)
async def test_restored_signal_stops_the_light_it_started(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    stored_optical: object,
    optical_stop: bool,
) -> None:
    """The group has no optical signal any more; the stored entry decides."""
    extra: dict = {"stop_at": (dt_util.utcnow() + timedelta(seconds=20)).isoformat()}
    if stored_optical is not None:
        extra["optical"] = stored_optical

    siren, client = await _restore(
        hass, extra, _siren_group(on=False, signalOptical=None)
    )
    await _pass(hass, freezer, 21)

    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "DISABLE_ACOUSTIC_SIGNAL"
    )
    if optical_stop:
        client.async_test_alarm_signal_optical.assert_awaited_once_with(
            "grp-siren", "DISABLE_OPTICAL_SIGNAL"
        )
    else:
        client.async_test_alarm_signal_optical.assert_not_awaited()
    assert siren.is_on is False


# --- Through Home Assistant ---

_ENTITY_ID = "siren.indoor_sirene"


@pytest.fixture
def dual_client(mock_async_zeroconf: None) -> Generator[MagicMock]:
    """Patch in a DualBridge client whose alarm group has a real alarm siren."""
    client = _make_client()
    client._auth_type = AUTH_TYPE_DUAL
    client.async_test_alarm_signal_acoustic = AsyncMock()
    client.async_test_alarm_signal_optical = AsyncMock()
    client.async_set_alarm_switching_group_state = AsyncMock()
    client._state["devices"]["dev-asir-1"] = {
        "id": "dev-asir-1",
        "type": "ALARM_SIREN_INDOOR",
        "modelType": "HmIP-ASIR-2",
        "label": "Hallway Siren",
        "oem": "eQ-3",
        "firmwareVersion": "1.0.0",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_SABOTAGE", "index": 0},
            "1": {
                "functionalChannelType": "ALARM_SIREN_CHANNEL",
                "index": 1,
                "groups": ["grp-siren"],
            },
        },
    }
    client._state["groups"]["grp-siren"] = _siren_group(
        on=False, channels=[{"deviceId": "dev-asir-1", "channelIndex": 1}]
    )
    with (
        patch("custom_components.hcu_integration.HcuApiClient", return_value=client),
        patch(
            "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
            AsyncMock(return_value=True),
        ),
    ):
        yield client


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=7,
        data={"host": "192.0.2.10", "app_token": "t", "auth_type": AUTH_TYPE_DUAL},
        unique_id="hcu-test-1",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_siren_actions_through_home_assistant(
    hass: HomeAssistant, dual_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """siren.turn_on and siren.turn_off reach the HCU with tone and duration."""
    client = dual_client
    await _setup_entry(hass)
    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "off"
    assert state.attributes["assumed_state"] is True
    assert state.attributes["available_tones"][0] == "frequency_rising"

    await hass.services.async_call(
        "siren",
        "turn_on",
        {"entity_id": _ENTITY_ID, "tone": "event", "duration": 10},
        blocking=True,
    )
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "EVENT"
    )
    client.async_test_alarm_signal_optical.assert_awaited_once_with(
        "grp-siren", "DOUBLE_FLASHING_REPEATING"
    )
    assert hass.states.get(_ENTITY_ID).state == "on"

    # The timed stop also updates the state Home Assistant shows.
    await _pass(hass, freezer, 11)
    assert hass.states.get(_ENTITY_ID).state == "off"
    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )

    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": _ENTITY_ID}, blocking=True
    )
    assert hass.states.get(_ENTITY_ID).state == "on"
    await hass.services.async_call(
        "siren", "turn_off", {"entity_id": _ENTITY_ID}, blocking=True
    )
    assert hass.states.get(_ENTITY_ID).state == "off"
    client.async_set_alarm_switching_group_state.assert_not_awaited()

    # A tone the siren does not have is rejected before anything is sent.
    calls_before = client.async_test_alarm_signal_acoustic.await_count
    with pytest.raises(ValueError, match="Invalid tone"):
        await hass.services.async_call(
            "siren",
            "turn_on",
            {"entity_id": _ENTITY_ID, "tone": "disable_acoustic_signal"},
            blocking=True,
        )
    assert client.async_test_alarm_signal_acoustic.await_count == calls_before


async def test_reload_keeps_a_playing_signal_and_its_stop(
    hass: HomeAssistant, dual_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A reload while the siren sounds must not leave it without a stop."""
    client = dual_client
    entry = await _setup_entry(hass)
    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": _ENTITY_ID, "duration": 60}, blocking=True
    )
    freezer.tick(20)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Still shown as on, and no stop was sent by the reload itself.
    assert hass.states.get(_ENTITY_ID).state == "on"
    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "FREQUENCY_RISING"
    )

    # 59 seconds after the turn on: not yet. 61 seconds: stopped.
    await _pass(hass, freezer, 39)
    assert client.async_test_alarm_signal_acoustic.await_count == 1
    await _pass(hass, freezer, 2)
    assert client.async_test_alarm_signal_acoustic.await_args.args == (
        "grp-siren",
        "DISABLE_ACOUSTIC_SIGNAL",
    )
    assert hass.states.get(_ENTITY_ID).state == "off"

    # A reload after the stop has nothing to take over.
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(_ENTITY_ID).state == "off"
    await _pass(hass, freezer, 600)
    assert client.async_test_alarm_signal_acoustic.await_count == 2


async def test_restart_stops_a_signal_whose_stop_time_passed(
    hass: HomeAssistant, dual_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Home Assistant restarted while the siren sounded and missed its stop."""
    client = dual_client
    stop_at = dt_util.utcnow() - timedelta(minutes=2)
    mock_restore_cache_with_extra_data(
        hass, ((State(_ENTITY_ID, "on"), {"stop_at": stop_at.isoformat()}),)
    )

    await _setup_entry(hass)
    await _pass(hass, freezer, 1)

    client.async_test_alarm_signal_acoustic.assert_awaited_once_with(
        "grp-siren", "DISABLE_ACOUSTIC_SIGNAL"
    )
    assert hass.states.get(_ENTITY_ID).state == "off"


async def test_real_alarm_reported_by_the_hcu_shows_the_siren_as_on(
    hass: HomeAssistant, dual_client: MagicMock
) -> None:
    """A group update from the HCU reaches the entity, for example a real alarm."""
    entry = await _setup_entry(hass)
    coordinator = entry.runtime_data
    coordinator._initial_state_loaded = True
    assert hass.states.get(_ENTITY_ID).state == "off"

    def _group_changed(on: bool) -> dict:
        group = _siren_group(
            on=on, channels=[{"deviceId": "dev-asir-1", "channelIndex": 1}]
        )
        return {
            "type": "HMIP_SYSTEM_EVENT",
            "body": {
                "eventTransaction": {
                    "events": {"0": {"pushEventType": "GROUP_CHANGED", "group": group}}
                }
            },
        }

    coordinator._handle_event_message(_group_changed(True))
    await hass.async_block_till_done()
    assert hass.states.get(_ENTITY_ID).state == "on"

    coordinator._handle_event_message(_group_changed(False))
    await hass.async_block_till_done()
    assert hass.states.get(_ENTITY_ID).state == "off"
    # Showing the alarm sends nothing to the HCU.
    dual_client.async_test_alarm_signal_acoustic.assert_not_awaited()


async def test_reload_remembers_the_light_to_stop(
    hass: HomeAssistant, dual_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """The optical setting is turned off and the integration reloads meanwhile."""
    client = dual_client
    entry = await _setup_entry(hass)
    await hass.services.async_call(
        "siren", "turn_on", {"entity_id": _ENTITY_ID, "duration": 60}, blocking=True
    )
    client._state["groups"]["grp-siren"]["signalOptical"] = "DISABLE_OPTICAL_SIGNAL"

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    await _pass(hass, freezer, 61)

    assert [c.args for c in client.async_test_alarm_signal_optical.await_args_list] == [
        ("grp-siren", "DOUBLE_FLASHING_REPEATING"),
        ("grp-siren", "DISABLE_OPTICAL_SIGNAL"),
    ]
    assert hass.states.get(_ENTITY_ID).state == "off"
