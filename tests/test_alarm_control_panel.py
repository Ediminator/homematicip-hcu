"""Tests for the HCU security system: alarm panel, alarm sensors, sirens."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.hcu_integration.alarm_control_panel import HcuAlarmControlPanel
from custom_components.hcu_integration.api import HcuApiClient, HcuApiError
from custom_components.hcu_integration.binary_sensor import HcuSecurityAlarmBinarySensor
from custom_components.hcu_integration.button import HcuAcknowledgeSafetyAlarmButton
from custom_components.hcu_integration.const import API_PATHS
from custom_components.hcu_integration.siren import HcuSiren

ABSENCE_GROUP = "group-absence"
PRESENCE_GROUP = "group-presence"


@pytest.fixture
def coordinator() -> MagicMock:
    coordinator = MagicMock()
    coordinator.config_entry.data.get.return_value = ""
    return coordinator


def _client(security_home: dict, groups: dict) -> MagicMock:
    client = MagicMock()
    client.hcu_device_id = "hcu-1"
    client.is_connected = True
    client.state = {
        "home": {
            "id": "home-1",
            "functionalHomes": {"SECURITY_AND_ALARM": security_home},
        },
        "groups": groups,
    }
    client.get_group_by_id = MagicMock(side_effect=groups.get)
    return client


def _security_home(**flags: object) -> dict:
    return {
        "solution": "SECURITY_AND_ALARM",
        "securityZones": {"ABSENCE": ABSENCE_GROUP, "PRESENCE": PRESENCE_GROUP},
        "intrusionAlarmActive": False,
        "safetyAlarmActive": False,
        "activationInProgress": False,
        **flags,
    }


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ({"intrusionAlarmActive": True}, AlarmControlPanelState.TRIGGERED),
        ({"safetyAlarmActive": True}, AlarmControlPanelState.TRIGGERED),
        ({"activationInProgress": True}, AlarmControlPanelState.ARMING),
    ],
)
def test_alarm_flags(coordinator: MagicMock, flags: dict, expected: str) -> None:
    """Intrusion and safety alarms both report triggered (unchanged behavior)."""
    groups = {
        ABSENCE_GROUP: {"id": ABSENCE_GROUP, "active": False},
        PRESENCE_GROUP: {"id": PRESENCE_GROUP, "active": False},
    }
    panel = HcuAlarmControlPanel(coordinator, _client(_security_home(**flags), groups))

    assert panel.alarm_state == expected


@pytest.mark.parametrize(
    ("absence", "presence", "expected"),
    [
        (True, False, AlarmControlPanelState.ARMED_AWAY),
        (False, True, AlarmControlPanelState.ARMED_HOME),
        (False, False, AlarmControlPanelState.DISARMED),
    ],
)
def test_zone_states(
    coordinator: MagicMock, absence: bool, presence: bool, expected: str
) -> None:
    groups = {
        ABSENCE_GROUP: {"id": ABSENCE_GROUP, "active": absence},
        PRESENCE_GROUP: {"id": PRESENCE_GROUP, "active": presence},
    }
    panel = HcuAlarmControlPanel(coordinator, _client(_security_home(), groups))

    assert panel.alarm_state == expected


def test_zone_group_missing_from_state(coordinator: MagicMock) -> None:
    """A zone that points to an unknown group counts as inactive instead of failing."""
    groups = {PRESENCE_GROUP: {"id": PRESENCE_GROUP, "active": True}}
    panel = HcuAlarmControlPanel(coordinator, _client(_security_home(), groups))

    assert panel.alarm_state == AlarmControlPanelState.ARMED_HOME


def test_both_zone_groups_missing_from_state(coordinator: MagicMock) -> None:
    panel = HcuAlarmControlPanel(coordinator, _client(_security_home(), {}))

    assert panel.alarm_state == AlarmControlPanelState.DISARMED


def _siren(coordinator: MagicMock, groups: dict) -> tuple[HcuSiren, MagicMock]:
    device = {
        "id": "3014F711A0000000000000AA",
        "label": "Siren",
        "type": "ALARM_SIREN_INDOOR",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "ALARM_SIREN_CHANNEL", "index": 1},
        },
    }
    client = MagicMock()
    client.state = {"groups": groups}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_set_alarm_switching_group_state = AsyncMock()
    siren = HcuSiren(coordinator, client, device, "1")
    siren.async_write_ha_state = MagicMock()
    return siren, client


async def test_siren_turn_on_uses_alarm_switching_group(
    coordinator: MagicMock,
) -> None:
    groups = {
        "alarm-group": {
            "id": "alarm-group",
            "type": "ALARM_SWITCHING",
            "label": "SIREN",
            "acousticFeedbackEnabled": True,
            "on": False,
            "channels": [{"deviceId": "3014F711A0000000000000AA", "channelIndex": 1}],
        }
    }
    siren, client = _siren(coordinator, groups)

    await siren.async_turn_on()

    client.async_set_alarm_switching_group_state.assert_awaited_once_with(
        group_id="alarm-group", on=True
    )


async def test_siren_without_alarm_switching_group_raises(
    coordinator: MagicMock,
) -> None:
    siren, client = _siren(coordinator, {})

    with pytest.raises(HcuApiError):
        await siren.async_turn_on()
    client.async_set_alarm_switching_group_state.assert_not_called()


@pytest.mark.parametrize(
    ("flags", "intrusion", "safety"),
    [
        ({}, False, False),
        ({"intrusionAlarmActive": True}, True, False),
        ({"safetyAlarmActive": True}, False, True),
    ],
)
def test_alarm_binary_sensors_tell_alarms_apart(
    coordinator: MagicMock, flags: dict, intrusion: bool, safety: bool
) -> None:
    client = _client(_security_home(**flags), {})
    intrusion_sensor = HcuSecurityAlarmBinarySensor(
        coordinator, client, "intrusionAlarmActive", "intrusion_alarm"
    )
    safety_sensor = HcuSecurityAlarmBinarySensor(
        coordinator, client, "safetyAlarmActive", "safety_alarm"
    )

    assert intrusion_sensor.is_on is intrusion
    assert safety_sensor.is_on is safety
    assert intrusion_sensor.unique_id == "hcu-1_intrusion_alarm"
    assert safety_sensor.unique_id == "hcu-1_safety_alarm"
    assert intrusion_sensor.translation_key == "hcu_intrusion_alarm"
    assert safety_sensor.translation_key == "hcu_safety_alarm"


def test_alarm_binary_sensor_without_security_home(coordinator: MagicMock) -> None:
    client = _client(_security_home(), {})
    client.state["home"]["functionalHomes"] = {}
    sensor = HcuSecurityAlarmBinarySensor(
        coordinator, client, "safetyAlarmActive", "safety_alarm"
    )

    assert sensor.is_on is None


async def test_acknowledge_safety_alarm_button(coordinator: MagicMock) -> None:
    client = _client(_security_home(safetyAlarmActive=True), {})
    client.async_acknowledge_safety_alarm = AsyncMock()
    button = HcuAcknowledgeSafetyAlarmButton(coordinator, client)

    await button.async_press()

    client.async_acknowledge_safety_alarm.assert_awaited_once_with()
    assert button.unique_id == "hcu-1_acknowledge_safety_alarm"


async def test_acknowledge_safety_alarm_button_reports_errors(
    coordinator: MagicMock,
) -> None:
    client = _client(_security_home(safetyAlarmActive=True), {})
    client.async_acknowledge_safety_alarm = AsyncMock(
        side_effect=HcuApiError("CLIENT_ACCESS_DENIED")
    )
    button = HcuAcknowledgeSafetyAlarmButton(coordinator, client)

    with pytest.raises(HomeAssistantError):
        await button.async_press()


async def test_acknowledge_safety_alarm_request() -> None:
    """The client sends the documented path with an empty body."""
    client = MagicMock()
    client.async_home_control = AsyncMock()

    await HcuApiClient.async_acknowledge_safety_alarm(client)

    client.async_home_control.assert_awaited_once_with(
        "/hmip/home/security/acknowledgeSafetyAlarm", {}
    )
    assert API_PATHS["ACKNOWLEDGE_SAFETY_ALARM"] == (
        "/hmip/home/security/acknowledgeSafetyAlarm"
    )
