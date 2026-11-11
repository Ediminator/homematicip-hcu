"""Tests for the siren entity of ALARM_SWITCHING groups."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from freezegun.api import FrozenDateTimeFactory
from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    SirenEntityFeature,
)
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
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A failed stop must not show the siren as off, and the timed stop retries."""
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 10})
    client.async_test_alarm_signal_acoustic.side_effect = [
        HcuApiError("busy", error_code="DEVICE_BUSY"),
        None,
    ]

    with pytest.raises(HomeAssistantError):
        await siren.async_turn_off()
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


async def test_failed_automatic_stop_is_logged(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    siren, client = _make_siren(_siren_group(on=False))
    siren.hass = hass
    await siren.async_turn_on(**{ATTR_DURATION: 5})
    client.async_test_alarm_signal_acoustic.side_effect = HcuApiError("busy")

    freezer.tick(6)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert "Could not stop siren siren.indoor_sirene after its duration" in caplog.text
    assert siren.is_on is True


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
