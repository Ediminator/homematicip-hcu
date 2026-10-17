"""Unit tests for the Homematic IP HCU climate platform."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.climate import HVACMode, PRESET_BOOST

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.climate import HcuClimate
from custom_components.hcu_integration.const import (
    ABSENCE_TYPE_PERMANENT,
    CONF_COMFORT_TEMPERATURE,
    DEFAULT_COMFORT_TEMPERATURE,
    PRESET_ECO,
    PRESET_PARTY,
)


def _make_climate(
    group_overrides: dict | None = None,
    indoor_climate: dict | None = None,
    options: dict | None = None,
) -> tuple[HcuClimate, MagicMock]:
    """Create an HcuClimate entity with mocked coordinator and client."""
    group_data = {
        "id": "group-heating-1",
        "type": "HEATING",
        "label": "Living Room",
        "controlMode": "AUTOMATIC",
        "setPointTemperature": 20.0,
        "actualTemperature": 19.5,
        "minTemperature": 4.5,
        "maxTemperature": 30.5,
        "controllable": True,
        "ecoAllowed": True,
        "cooling": False,
        "coolingAllowed": False,
        "coolingIgnored": False,
        "activeProfile": "PROFILE_1",
        "profiles": {
            "PROFILE_1": {
                "index": "PROFILE_1",
                "name": "Standard",
                "enabled": True,
                "visible": True,
            },
            "PROFILE_2": {
                "index": "PROFILE_2",
                "name": "Workday",
                "enabled": True,
                "visible": True,
            },
        },
        "channels": [],
    }
    if group_overrides:
        group_data.update(group_overrides)

    client = MagicMock()
    client.is_connected = True
    client.hcu_device_id = "hcu-main"
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.state = {
        "home": {
            "functionalHomes": {
                "INDOOR_CLIMATE": indoor_climate or {"absenceType": "NOT_ABSENT"}
            }
        }
    }
    client.async_set_group_control_mode = AsyncMock()
    client.async_set_group_setpoint_temperature = AsyncMock()
    client.async_set_group_boost = AsyncMock()
    client.async_set_group_active_profile = AsyncMock()
    client.async_activate_group_party_mode = AsyncMock()
    client.async_deactivate_vacation = AsyncMock()

    config_entry = SimpleNamespace(
        entry_id="entry-1",
        domain="hcu_integration",
        data={},
        options=options or {CONF_COMFORT_TEMPERATURE: 21.5},
    )
    coordinator = MagicMock()
    coordinator.config_entry = config_entry
    coordinator.data = {group_data["id"]: group_data}

    entity = HcuClimate(coordinator, client, group_data, config_entry)
    entity.async_write_ha_state = MagicMock()
    return entity, client


@pytest.mark.asyncio
async def test_climate_manual_min_temp_reports_hvac_off() -> None:
    """Verify MANUAL mode with setPointTemperature <= min_temp maps to HVACMode.OFF."""
    entity, _ = _make_climate(
        group_overrides={"controlMode": "MANUAL", "setPointTemperature": 4.5}
    )
    assert entity.hvac_mode == HVACMode.OFF
    assert entity._attr_hvac_mode == HVACMode.OFF

    entity_heat, _ = _make_climate(
        group_overrides={"controlMode": "MANUAL", "setPointTemperature": 20.0}
    )
    assert entity_heat.hvac_mode == HVACMode.HEAT
    assert entity_heat._attr_hvac_mode == HVACMode.HEAT


@pytest.mark.asyncio
async def test_climate_preset_modes_dynamic_eco_and_never_none() -> None:
    """Verify preset_modes only includes PRESET_ECO when active and never returns None."""
    entity, _ = _make_climate()
    assert PRESET_ECO not in entity.preset_modes
    assert PRESET_BOOST in entity.preset_modes
    assert PRESET_PARTY in entity.preset_modes
    assert "Standard" in entity.preset_modes

    entity_eco, _ = _make_climate(
        indoor_climate={
            "absenceType": ABSENCE_TYPE_PERMANENT,
            "ecoTemperature": 17.0,
        }
    )
    assert entity_eco.preset_mode == PRESET_ECO
    assert PRESET_ECO in entity_eco.preset_modes

    # Edge case: cooling=True with coolingAllowed=True and coolingIgnored=False
    entity_cooling, _ = _make_climate(
        group_overrides={
            "cooling": True,
            "coolingAllowed": True,
            "coolingIgnored": False,
        }
    )
    assert isinstance(entity_cooling.preset_modes, list)


@pytest.mark.asyncio
async def test_climate_set_hvac_mode_heat_applies_comfort_temp_from_off() -> None:
    """Verify switching from OFF (min_temp) to HEAT restores comfort_temperature."""
    entity, client = _make_climate(
        group_overrides={"controlMode": "MANUAL", "setPointTemperature": 4.5},
        options={CONF_COMFORT_TEMPERATURE: 22.0},
    )
    assert entity.hvac_mode == HVACMode.OFF

    await entity.async_set_hvac_mode(HVACMode.HEAT)

    assert entity._attr_target_temperature == 22.0
    client.async_set_group_setpoint_temperature.assert_awaited_once_with(
        "group-heating-1", 22.0
    )

    # Switching from AUTO at 19.5C (> min_temp) to HEAT should NOT overwrite setpoint
    entity_auto, client_auto = _make_climate(
        group_overrides={"controlMode": "AUTOMATIC", "setPointTemperature": 19.5},
        options={CONF_COMFORT_TEMPERATURE: DEFAULT_COMFORT_TEMPERATURE},
    )
    await entity_auto.async_set_hvac_mode(HVACMode.HEAT)
    client_auto.async_set_group_control_mode.assert_awaited_once_with(
        "group-heating-1", "MANUAL"
    )
    client_auto.async_set_group_setpoint_temperature.assert_not_awaited()


@pytest.mark.asyncio
async def test_climate_set_preset_party_and_exit_to_profile() -> None:
    """Verify PRESET_PARTY activates room party mode and switching to profile exits cleanly."""
    entity, client = _make_climate(options={CONF_COMFORT_TEMPERATURE: 21.5})

    await entity.async_set_preset_mode(PRESET_PARTY)
    client.async_activate_group_party_mode.assert_awaited_once()
    call_kwargs = client.async_activate_group_party_mode.await_args.kwargs
    assert call_kwargs["group_id"] == "group-heating-1"
    assert call_kwargs["temperature"] == 21.5
    assert isinstance(call_kwargs["end_time"], str)

    # Simulate HCU reporting partyMode=True
    entity._group["partyMode"] = True
    entity._group["controlMode"] = "PARTY"
    assert entity.preset_mode == PRESET_PARTY

    # Switch back to profile "Workday"
    await entity.async_set_preset_mode("Workday")
    client.async_set_group_control_mode.assert_awaited_once_with(
        group_id="group-heating-1", mode="AUTOMATIC"
    )
    client.async_set_group_active_profile.assert_awaited_once_with(
        group_id="group-heating-1", profile_index="PROFILE_2"
    )
    client.async_deactivate_vacation.assert_not_awaited()


@pytest.mark.asyncio
async def test_climate_writes_state_on_home_changed_for_eco() -> None:
    """A HOME_CHANGED-only update (eco toggled) must refresh the climate state."""
    entity, client = _make_climate()
    client.state["home"]["id"] = "home-1"
    entity.coordinator.data = {"home-1": {}}  # only the home changed
    entity.async_write_ha_state.reset_mock()

    client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"] = {
        "absenceType": ABSENCE_TYPE_PERMANENT,
        "ecoTemperature": 17.0,
    }
    entity._handle_coordinator_update()

    entity.async_write_ha_state.assert_called_once()
    assert entity.preset_mode == PRESET_ECO
    assert PRESET_ECO in entity.preset_modes


@pytest.mark.asyncio
async def test_climate_party_mode_optimistic_target_temperature() -> None:
    """Activating party mode shows the party temperature right away and reverts on error."""
    entity, client = _make_climate(group_overrides={"setPointTemperature": 19.0})
    await entity.async_activate_party_mode(temperature=23.0, duration=3600)
    assert entity.target_temperature == 23.0

    entity2, client2 = _make_climate(group_overrides={"setPointTemperature": 19.0})
    client2.async_activate_group_party_mode = AsyncMock(
        side_effect=HcuApiError("rejected")
    )
    before = entity2._attr_target_temperature
    with pytest.raises(HcuApiError):
        await entity2.async_activate_party_mode(temperature=23.0, duration=3600)
    assert entity2._attr_target_temperature == before
    assert entity2._attr_assumed_state is False
