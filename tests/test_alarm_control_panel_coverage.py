"""Coverage tests for HCU alarm control panel platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.alarm_control_panel import AlarmControlPanelState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from custom_components.hcu_integration.alarm_control_panel import (
    HcuAlarmControlPanel,
    async_setup_entry,
)
from custom_components.hcu_integration.api import HcuApiError


def _create_panel(
    hass: HomeAssistant,
    security_home: dict | None = None,
    groups: dict | None = None,
) -> tuple[HcuAlarmControlPanel, MagicMock, MagicMock]:
    """Create an HcuAlarmControlPanel test entity with mocks."""
    sec_home = {
        "solution": "SECURITY_AND_ALARM",
        "securityZones": {"ABSENCE": "grp-abs", "PRESENCE": "grp-pres"},
        "intrusionAlarmActive": False,
        "safetyAlarmActive": False,
        "activationInProgress": False,
    }
    if security_home is not None:
        sec_home = security_home

    grp_dict = groups or {
        "grp-abs": {"id": "grp-abs", "active": False},
        "grp-pres": {"id": "grp-pres", "active": False},
    }

    client = MagicMock()
    client.hcu_device_id = "hcu-1"
    client.is_connected = True
    client.state = {
        "home": {
            "id": "home-uuid-1",
            "functionalHomes": {"SECURITY_AND_ALARM": sec_home} if sec_home else {},
        },
        "groups": grp_dict,
    }
    client.get_group_by_id = MagicMock(side_effect=grp_dict.get)
    client.async_set_zones_activation = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"home-uuid-1": client.state["home"]}
    coordinator.client = client
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.data = {}
    coordinator.config_entry.options = {}

    panel = HcuAlarmControlPanel(coordinator, client)
    panel._attr_name = "Alarm"
    panel.hass = hass
    return panel, coordinator, client


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test platform setup with and without alarm entities."""
    entry = MagicMock()
    coordinator = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    # Case 1: No alarm entities
    coordinator.entities = {}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

    # Case 2: Alarm entities present
    alarm_entity = MagicMock()
    coordinator.entities = {Platform.ALARM_CONTROL_PANEL: [alarm_entity]}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([alarm_entity])


def test_legacy_zone_naming_and_states(hass: HomeAssistant) -> None:
    """Test legacy pre-1.79 INTERNAL/EXTERNAL zone naming states and payloads."""
    legacy_sec_home = {
        "solution": "SECURITY_AND_ALARM",
        "securityZones": {"INTERNAL": "grp-int", "EXTERNAL": "grp-ext"},
        "intrusionAlarmActive": False,
        "safetyAlarmActive": False,
        "activationInProgress": False,
    }
    groups = {
        "grp-int": {"id": "grp-int", "active": False},
        "grp-ext": {"id": "grp-ext", "active": False},
    }
    panel, _, _ = _create_panel(hass, security_home=legacy_sec_home, groups=groups)

    # Disarmed
    assert panel.alarm_state == AlarmControlPanelState.DISARMED

    # External only -> Armed home
    groups["grp-ext"]["active"] = True
    assert panel.alarm_state == AlarmControlPanelState.ARMED_HOME

    # Both -> Armed away
    groups["grp-int"]["active"] = True
    assert panel.alarm_state == AlarmControlPanelState.ARMED_AWAY

    # Verify payload generation for legacy zones
    zones = legacy_sec_home["securityZones"]
    payload_home = panel._zones_activation_payload(
        zones, armed_home=True, armed_away=False
    )
    assert payload_home == {"INTERNAL": False, "EXTERNAL": True}

    payload_away = panel._zones_activation_payload(
        zones, armed_home=False, armed_away=True
    )
    assert payload_away == {"INTERNAL": True, "EXTERNAL": True}

    payload_disarm = panel._zones_activation_payload(
        zones, armed_home=False, armed_away=False
    )
    assert payload_disarm == {"INTERNAL": False, "EXTERNAL": False}


def test_invalid_zones_format_and_missing_home(hass: HomeAssistant) -> None:
    """Test non-dict securityZones data and missing security home handling."""
    # Non-dict zones
    invalid_sec_home = {
        "solution": "SECURITY_AND_ALARM",
        "securityZones": "not_a_dictionary",
    }
    panel, _, _ = _create_panel(hass, security_home=invalid_sec_home)
    assert panel.alarm_state == AlarmControlPanelState.DISARMED

    # Missing security home
    panel_empty, _, _ = _create_panel(hass, security_home={})
    assert panel_empty.alarm_state is None


def test_optimistic_state_and_coordinator_update(hass: HomeAssistant) -> None:
    """Test assumed state returning optimistic alarm state and coordinator update clearing it."""
    panel, _, _ = _create_panel(hass)
    panel.async_write_ha_state = MagicMock()

    panel._attr_assumed_state = True
    panel._attr_alarm_state = AlarmControlPanelState.ARMING
    assert panel.alarm_state == AlarmControlPanelState.ARMING

    # Coordinator update clears optimistic state
    panel._handle_coordinator_update()
    assert panel._attr_alarm_state is None


async def test_alarm_control_actions_success(hass: HomeAssistant) -> None:
    """Test async_alarm_arm_home, async_alarm_arm_away, and async_alarm_disarm."""
    panel, _, client = _create_panel(hass)
    panel.async_write_ha_state = MagicMock()

    # Arm Home
    await panel.async_alarm_arm_home()
    client.async_set_zones_activation.assert_awaited_with(
        payload={"zonesActivation": {"ABSENCE": False, "PRESENCE": True}}
    )
    assert panel.alarm_state == AlarmControlPanelState.ARMING

    # Arm Away
    await panel.async_alarm_arm_away()
    client.async_set_zones_activation.assert_awaited_with(
        payload={"zonesActivation": {"ABSENCE": True, "PRESENCE": False}}
    )
    assert panel.alarm_state == AlarmControlPanelState.ARMING

    # Disarm
    await panel.async_alarm_disarm()
    client.async_set_zones_activation.assert_awaited_with(
        payload={"zonesActivation": {"ABSENCE": False, "PRESENCE": False}}
    )
    assert panel.alarm_state == AlarmControlPanelState.DISARMED


async def test_alarm_control_actions_error_handling(hass: HomeAssistant) -> None:
    """Test error recovery on HcuApiError and ConnectionError during arm/disarm."""
    panel, _, client = _create_panel(hass)
    panel.async_write_ha_state = MagicMock()

    # HcuApiError
    client.async_set_zones_activation.side_effect = HcuApiError(
        "Zone activation rejected"
    )
    await panel.async_alarm_arm_home()
    assert panel._attr_alarm_state is None
    assert panel.assumed_state is False

    # ConnectionError
    client.async_set_zones_activation.side_effect = ConnectionError("Disconnected")
    await panel.async_alarm_disarm()
    assert panel._attr_alarm_state is None
    assert panel.assumed_state is False
