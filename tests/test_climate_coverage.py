"""Coverage tests for HCU climate platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.climate import (
    PRESET_BOOST,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.climate import HcuClimate, async_setup_entry
from custom_components.hcu_integration.const import (
    CONF_COMFORT_TEMPERATURE,
    DOMAIN,
    PRESET_ECO,
    PRESET_PARTY,
)


def _create_climate(
    hass: HomeAssistant,
    group_overrides: dict | None = None,
    client_devices: dict | None = None,
    options: dict | None = None,
) -> tuple[HcuClimate, MagicMock, MagicMock]:
    """Create an HcuClimate test entity with mocks."""
    group_data = {
        "id": "grp-climate-1",
        "type": "HEATING",
        "label": "Bed Room",
        "controlMode": "AUTOMATIC",
        "setPointTemperature": 21.0,
        "actualTemperature": 20.0,
        "humidity": 50,
        "minTemperature": 5.0,
        "maxTemperature": 30.0,
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

    devices = client_devices or {}

    client = MagicMock()
    client.is_connected = True
    client.hcu_device_id = "hcu-1"
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.get_device_by_address = MagicMock(side_effect=devices.get)
    client.state = {
        "home": {"functionalHomes": {"INDOOR_CLIMATE": {"absenceType": "NOT_ABSENT"}}},
        "devices": devices,
    }
    client.async_set_group_control_mode = AsyncMock()
    client.async_set_group_setpoint_temperature = AsyncMock()
    client.async_set_group_boost = AsyncMock()
    client.async_set_group_active_profile = AsyncMock()
    client.async_activate_group_party_mode = AsyncMock()

    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.options = options or {CONF_COMFORT_TEMPERATURE: 21.0}

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {group_data["id"]: group_data}
    coordinator.client = client
    coordinator.config_entry = config_entry

    entity = HcuClimate(coordinator, client, group_data, config_entry)
    entity.hass = hass
    entity.async_write_ha_state = MagicMock()
    return entity, coordinator, client


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test platform setup with and without climate entities."""
    entry = MagicMock()
    coordinator = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    # Case 1: No climate entities
    coordinator.entities = {}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

    # Case 2: Climate entities present
    climate_entity = MagicMock()
    coordinator.entities = {Platform.CLIMATE: [climate_entity]}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([climate_entity])


def test_temperature_limits_and_target_temperature(hass: HomeAssistant) -> None:
    """Test min_temp, max_temp, and target_temperature properties."""
    climate, _, _ = _create_climate(
        hass, group_overrides={"minTemperature": 6.0, "maxTemperature": 28.0}
    )
    assert climate.min_temp == 6.0
    assert climate.max_temp == 28.0
    assert climate.target_temperature == 21.0

    # Assumed state
    climate._attr_assumed_state = True
    climate._attr_target_temperature = 22.5
    assert climate.target_temperature == 22.5


def test_fallbacks_from_device_channels(hass: HomeAssistant) -> None:
    """Test humidity, temperature, and valve position fallbacks from group device channels."""
    devices = {
        "dev-trv-1": {
            "functionalChannels": {
                "1": {
                    "humidity": 45,
                    "actualTemperature": 21.3,
                    "valvePosition": 0.42,
                }
            }
        },
        "dev-trv-2": {
            "functionalChannels": {
                "1": {
                    "valveActualTemperature": 21.8,
                    "valvePosition": 0.75,
                }
            }
        },
    }
    # Group with no group-level humidity or actualTemperature
    climate, _, _ = _create_climate(
        hass,
        group_overrides={
            "humidity": None,
            "actualTemperature": None,
            "channels": [
                {"deviceId": "dev-trv-1", "channelIndex": 1},
                {"deviceId": "dev-trv-2", "channelIndex": 1},
            ],
        },
        client_devices=devices,
    )
    assert climate.current_humidity == 45
    assert climate.current_temperature == 21.3
    assert climate.current_valve_position == 75

    # Group with no device channels
    climate_empty, _, _ = _create_climate(
        hass,
        group_overrides={
            "humidity": None,
            "actualTemperature": None,
            "channels": [],
        },
    )
    assert climate_empty.current_humidity is None
    assert climate_empty.current_temperature is None
    assert climate_empty.current_valve_position is None


def test_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test extra_state_attributes dictionary."""
    climate, _, _ = _create_climate(
        hass,
        group_overrides={
            "windowState": "OPEN",
            "cooling": True,
            "coolingIgnored": False,
            "coolingAllowed": True,
        },
    )
    attrs = climate.extra_state_attributes
    assert attrs["window_state"] == "OPEN"
    assert attrs["cooling"] is True
    assert attrs["cooling_ignored"] is False
    assert attrs["cooling_allowed"] is True
    assert attrs["is_cooling_blocked_or_ignored"] is False


def test_hvac_action_states(hass: HomeAssistant) -> None:
    """Test hvac_action in heating, cooling, idle, and off states."""
    devices = {"dev-1": {"functionalChannels": {"1": {"valvePosition": 0.3}}}}
    channels = [{"deviceId": "dev-1", "channelIndex": 1}]

    # 1. HVACMode.OFF -> HVACAction.OFF
    climate_off, _, _ = _create_climate(
        hass,
        group_overrides={"controlMode": "OFF"},
        client_devices=devices,
    )
    assert climate_off.hvac_action == HVACAction.OFF

    # 2. No valve position -> HVACAction.IDLE
    climate_no_valve, _, _ = _create_climate(
        hass,
        group_overrides={"controlMode": "AUTOMATIC", "channels": []},
    )
    assert climate_no_valve.hvac_action == HVACAction.IDLE

    # 3. Heating with valve > 0 -> HVACAction.HEATING
    climate_heat, _, _ = _create_climate(
        hass,
        group_overrides={"controlMode": "AUTOMATIC", "channels": channels},
        client_devices=devices,
    )
    assert climate_heat.hvac_action == HVACAction.HEATING

    # 4. Heating with valve == 0 -> HVACAction.IDLE
    dev_closed = {"dev-1": {"functionalChannels": {"1": {"valvePosition": 0.0}}}}
    climate_idle, _, _ = _create_climate(
        hass,
        group_overrides={"controlMode": "AUTOMATIC", "channels": channels},
        client_devices=dev_closed,
    )
    assert climate_idle.hvac_action == HVACAction.IDLE

    # 5. Cooling: effective cooling with valve > 0 -> HVACAction.COOLING
    climate_cool, _, _ = _create_climate(
        hass,
        group_overrides={
            "controlMode": "AUTOMATIC",
            "cooling": True,
            "coolingAllowed": True,
            "coolingIgnored": False,
            "channels": channels,
        },
        client_devices=devices,
    )
    assert climate_cool.hvac_action == HVACAction.COOLING

    # 6. Cooling: blocked or ignored -> HVACAction.OFF
    climate_cool_blocked, _, _ = _create_climate(
        hass,
        group_overrides={
            "controlMode": "AUTOMATIC",
            "cooling": True,
            "coolingAllowed": False,
            "channels": channels,
        },
        client_devices=devices,
    )
    assert climate_cool_blocked.hvac_action == HVACAction.OFF

    # 7. Cooling: valve == 0 -> HVACAction.IDLE
    climate_cool_idle, _, _ = _create_climate(
        hass,
        group_overrides={
            "controlMode": "AUTOMATIC",
            "cooling": True,
            "coolingAllowed": True,
            "coolingIgnored": False,
            "channels": channels,
        },
        client_devices=dev_closed,
    )
    assert climate_cool_idle.hvac_action == HVACAction.IDLE


def test_hvac_mode_branches(hass: HomeAssistant) -> None:
    """Test hvac_mode computation for all controlMode and cooling branches."""
    # Assumed state
    climate, _, _ = _create_climate(hass)
    climate._attr_assumed_state = True
    climate._attr_hvac_mode = HVACMode.HEAT
    assert climate.hvac_mode == HVACMode.HEAT

    # Cooling blocked
    climate_blocked, _, _ = _create_climate(
        hass, group_overrides={"cooling": True, "coolingAllowed": False}
    )
    assert climate_blocked.hvac_mode == HVACMode.OFF

    # controlMode == OFF
    climate_off, _, _ = _create_climate(hass, group_overrides={"controlMode": "OFF"})
    assert climate_off.hvac_mode == HVACMode.OFF

    # controlMode == MANUAL and effective cooling
    climate_manual_cool, _, _ = _create_climate(
        hass,
        group_overrides={
            "controlMode": "MANUAL",
            "setPointTemperature": 22.0,
            "cooling": True,
            "coolingAllowed": True,
            "coolingIgnored": False,
        },
    )
    assert climate_manual_cool.hvac_mode == HVACMode.COOL

    # Unrecognized controlMode
    climate_unknown, _, _ = _create_climate(
        hass, group_overrides={"controlMode": "UNKNOWN_MODE"}
    )
    assert climate_unknown.hvac_mode == HVACMode.OFF


def test_preset_modes_and_preset_mode_branches(hass: HomeAssistant) -> None:
    """Test preset_mode and preset_modes with boost, party, cooling blocked, etc."""
    # Cooling blocked/ignored -> returns [PRESET_ECO] and PRESET_ECO
    climate_blocked, _, _ = _create_climate(
        hass, group_overrides={"cooling": True, "coolingIgnored": True}
    )
    assert climate_blocked.preset_mode == PRESET_ECO
    assert climate_blocked.preset_modes == [PRESET_ECO]

    # Boost mode
    climate_boost, _, _ = _create_climate(hass, group_overrides={"boostMode": True})
    assert climate_boost.preset_mode == PRESET_BOOST

    # Party mode
    climate_party, _, _ = _create_climate(hass, group_overrides={"partyMode": True})
    assert climate_party.preset_mode == PRESET_PARTY

    # Active profile selection (not default)
    climate_workday, _, _ = _create_climate(
        hass, group_overrides={"activeProfile": "PROFILE_2"}
    )
    assert climate_workday.preset_mode == "Workday"

    # Assumed preset mode
    climate_boost._attr_assumed_state = True
    climate_boost._attr_preset_mode = "Custom"
    assert climate_boost.preset_mode == "Custom"


async def test_async_set_temperature_branches(hass: HomeAssistant) -> None:
    """Test async_set_temperature with None, cooling blocked, min temp, and modes."""
    climate, _, client = _create_climate(hass)

    # 1. Temperature is None -> does nothing
    await climate.async_set_temperature()
    client.async_set_group_setpoint_temperature.assert_not_awaited()

    # 2. Cooling blocked -> does nothing
    climate._group["cooling"] = True
    climate._group["coolingAllowed"] = False
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 22.0})
    client.async_set_group_setpoint_temperature.assert_not_awaited()

    # 3. Valid temp <= min_temp -> sets hvac_mode = OFF
    climate._group["cooling"] = False
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 5.0})
    assert climate._attr_hvac_mode == HVACMode.OFF
    client.async_set_group_control_mode.assert_not_awaited()
    client.async_set_group_setpoint_temperature.assert_awaited_with(
        "grp-climate-1", 5.0
    )

    # 4. Valid temp in HEAT mode with controlMode != MANUAL -> switches to MANUAL
    client.async_set_group_control_mode.reset_mock()
    climate._attr_hvac_mode = HVACMode.HEAT
    climate._group["controlMode"] = "AUTOMATIC"
    await climate.async_set_temperature(**{ATTR_TEMPERATURE: 23.0})
    client.async_set_group_control_mode.assert_awaited_with("grp-climate-1", "MANUAL")
    client.async_set_group_setpoint_temperature.assert_awaited_with(
        "grp-climate-1", 23.0
    )


async def test_async_set_hvac_mode_off_and_auto(hass: HomeAssistant) -> None:
    """Test async_set_hvac_mode to OFF and AUTO."""
    climate, _, client = _create_climate(
        hass, group_overrides={"controlMode": "AUTOMATIC", "setPointTemperature": 20.0}
    )

    # Set HVACMode.OFF
    await climate.async_set_hvac_mode(HVACMode.OFF)
    client.async_set_group_control_mode.assert_awaited_with("grp-climate-1", "MANUAL")
    client.async_set_group_setpoint_temperature.assert_awaited_with(
        "grp-climate-1", 5.0
    )
    assert climate._attr_hvac_mode == HVACMode.OFF
    assert climate._attr_target_temperature == 5.0

    # Set HVACMode.AUTO
    climate._group["controlMode"] = "MANUAL"
    await climate.async_set_hvac_mode(HVACMode.AUTO)
    client.async_set_group_control_mode.assert_awaited_with(
        "grp-climate-1", "AUTOMATIC"
    )
    assert climate._attr_hvac_mode == HVACMode.AUTO


async def test_async_set_hvac_mode_cool(hass: HomeAssistant) -> None:
    """Test async_set_hvac_mode to COOL with reset to comfort temperature."""
    climate, _, client = _create_climate(
        hass,
        group_overrides={
            "controlMode": "AUTOMATIC",
            "setPointTemperature": 5.0,  # <= min_temp
        },
        options={CONF_COMFORT_TEMPERATURE: 22.0},
    )
    await climate.async_set_hvac_mode(HVACMode.COOL)
    client.async_set_group_control_mode.assert_awaited_with("grp-climate-1", "MANUAL")
    client.async_set_group_setpoint_temperature.assert_awaited_with(
        "grp-climate-1", 22.0
    )
    assert climate._attr_target_temperature == 22.0


async def test_async_set_preset_mode_boost_and_error(hass: HomeAssistant) -> None:
    """Test setting PRESET_BOOST and error recovery."""
    climate, _, client = _create_climate(hass)

    # Set Boost
    climate.async_write_ha_state.reset_mock()
    await climate.async_set_preset_mode(PRESET_BOOST)
    assert climate.async_write_ha_state.call_count == 2
    client.async_set_group_boost.assert_awaited_with(
        group_id="grp-climate-1", boost=True
    )

    # Switch from Boost to profile -> disables boost
    climate._group["boostMode"] = True
    await climate.async_set_preset_mode("Workday")
    client.async_set_group_boost.assert_awaited_with(
        group_id="grp-climate-1", boost=False
    )
    client.async_set_group_active_profile.assert_awaited_with(
        group_id="grp-climate-1", profile_index="PROFILE_2"
    )

    # Error recovery
    client.async_set_group_boost.side_effect = HcuApiError("Boost failed")
    with pytest.raises(HomeAssistantError) as exc_info:
        await climate.async_set_preset_mode(PRESET_BOOST)
    assert exc_info.value.translation_key == "command_failed"
    assert climate.assumed_state is False


async def test_async_activate_party_mode_end_time_str_and_validation(
    hass: HomeAssistant,
) -> None:
    """Test async_activate_party_mode with end_time_str and ValueError on missing params."""
    climate, _, client = _create_climate(hass)

    # With end_time_str
    await climate.async_activate_party_mode(
        temperature=22.0, end_time_str="2026_12_31 23:59"
    )
    client.async_activate_group_party_mode.assert_awaited_with(
        group_id="grp-climate-1", temperature=22.0, end_time="2026_12_31 23:59"
    )

    # Without end_time_str and duration -> raises ServiceValidationError
    with pytest.raises(ServiceValidationError) as exc:
        await climate.async_activate_party_mode(temperature=22.0)
    assert exc.value.translation_domain == DOMAIN
    assert exc.value.translation_key == "party_mode_needs_end_time_or_duration"


def test_climate_additional_branches(hass: HomeAssistant) -> None:
    """Test remaining branches: eco target_temp, coordinator update super, attributes, etc."""
    # 1. Line 209 & 227: group has direct humidity and actualTemperature
    climate, _, _ = _create_climate(
        hass,
        group_overrides={
            "humidity": 65,
            "actualTemperature": 22.1,
            "channels": [{"deviceId": "dev-1", "channelIndex": 1}],
        },
        client_devices={"dev-1": {"functionalChannels": {"1": {"valvePosition": 0.5}}}},
    )
    assert climate.current_humidity == 65
    assert climate.current_temperature == 22.1
    assert "valve_position" in climate.extra_state_attributes

    # 2. Line 100: eco mode target temperature
    climate_eco, _, _ = _create_climate(
        hass,
        group_overrides={"ecoAllowed": True},
        options={CONF_COMFORT_TEMPERATURE: 21.0},
    )
    climate_eco._client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"] = {
        "absenceType": "PERIOD",
        "ecoTemperature": 16.5,
    }
    assert climate_eco.target_temperature == 16.5

    # 3. Line 152: coordinator update when group_id IS in coordinator.data
    climate_eco._client.state["home"]["functionalHomes"]["INDOOR_CLIMATE"][
        "absenceType"
    ] = "NOT_ABSENT"
    climate_eco._attr_assumed_state = True
    climate_eco.async_write_ha_state.reset_mock()
    updated_group = dict(climate_eco._group)
    updated_group["setPointTemperature"] = 19.5
    climate_eco.coordinator.data = {climate_eco._group_id: updated_group}
    climate_eco._client.get_group_by_id = MagicMock(return_value=updated_group)
    climate_eco._handle_coordinator_update()
    assert climate_eco.target_temperature == 19.5
    assert climate_eco.assumed_state is False
    climate_eco.async_write_ha_state.assert_called_once()

    # 4. Line 179: optimistic update state flapping prevention
    climate_flapping, _, _ = _create_climate(hass)
    climate_flapping._attr_assumed_state = True
    climate_flapping._attr_hvac_mode = HVACMode.OFF
    climate_flapping._group["controlMode"] = "MANUAL"
    climate_flapping._group["setPointTemperature"] = 20.0
    climate_flapping._update_attributes_from_group_data()
    assert climate_flapping._attr_hvac_mode == HVACMode.OFF

    # 5. Line 183: group not controllable
    climate_uncontrollable, _, _ = _create_climate(
        hass, group_overrides={"controllable": False}
    )
    assert climate_uncontrollable._attr_hvac_mode == HVACMode.OFF

    # 6. Line 362: preset_mode fallback to default profile name when unknown profile
    climate_unknown_prof, _, _ = _create_climate(
        hass, group_overrides={"activeProfile": "PROFILE_99"}
    )
    assert climate_unknown_prof.preset_mode == "Standard"

    # 7. Line 393: async_set_temperature when hvac_mode not in (AUTO, HEAT)
    # e.g. when hvac_mode is OFF, set temp > min_temp turns it to HEAT
    climate_heat_mode, _, _client_heat = _create_climate(
        hass, group_overrides={"controlMode": "MANUAL", "setPointTemperature": 5.0}
    )
    climate_heat_mode._attr_hvac_mode = HVACMode.OFF
    import asyncio

    asyncio.run(climate_heat_mode.async_set_temperature(temperature=22.0))
    assert climate_heat_mode._attr_hvac_mode == HVACMode.HEAT


def test_hvac_action_cooling_blocked_in_assumed_state(hass: HomeAssistant) -> None:
    """Test line 296: cooling blocked or ignored while assumed state is non-off."""
    devices = {"dev-1": {"functionalChannels": {"1": {"valvePosition": 0.5}}}}
    climate, _, _ = _create_climate(
        hass,
        group_overrides={
            "cooling": True,
            "coolingAllowed": False,
            "channels": [{"deviceId": "dev-1", "channelIndex": 1}],
        },
        client_devices=devices,
    )
    climate._attr_assumed_state = True
    climate._attr_hvac_mode = HVACMode.COOL
    assert climate.hvac_action == HVACAction.OFF
