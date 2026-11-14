"""Tests for translated entity command errors and optimistic state rollback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.climate import HVACMode
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.button import (
    HcuDoorPullLatchButton,
    HcuDoorUnlatchButton,
)
from custom_components.hcu_integration.climate import HcuClimate
from custom_components.hcu_integration.const import (
    API_PATHS,
    AUTH_TYPE_APP,
    AUTH_TYPE_PLUGIN,
    CONF_APP_CLIENT_ID,
    CONF_AUTH_TYPE,
    CONF_COMFORT_TEMPERATURE,
    CONF_PLUGIN_CLIENT_ID,
    DOMAIN,
)
from custom_components.hcu_integration.cover import (
    HcuCover,
    HcuCoverGroup,
    HcuGarageDoorCover,
)
from custom_components.hcu_integration.light import HcuLight, HcuNotificationLight
from custom_components.hcu_integration.switch import HcuSwitch, HcuWateringGroup


@dataclass(frozen=True)
class CommandCase:
    """Description of one entity command branch for error/rollback/success tests."""

    case_id: str
    entity_id: str
    build: Callable[[HomeAssistant], tuple[Any, MagicMock, str]]
    invoke: Callable[[Any], Any]
    expected_call_args: tuple[Any, ...]
    expected_call_kwargs: dict[str, Any]
    expected_assumed_on_success: bool
    is_climate: bool = False


def _make_climate(
    hass: HomeAssistant,
    *,
    control_mode: str = "AUTOMATIC",
    setpoint: float = 21.0,
    cooling: bool = False,
    cooling_allowed: bool = False,
    cooling_ignored: bool = False,
) -> tuple[HcuClimate, MagicMock]:
    group_data = {
        "id": "grp-climate-1",
        "type": "HEATING",
        "label": "Living Room",
        "controlMode": control_mode,
        "setPointTemperature": setpoint,
        "actualTemperature": 20.0,
        "humidity": 50,
        "minTemperature": 5.0,
        "maxTemperature": 30.0,
        "controllable": True,
        "ecoAllowed": True,
        "cooling": cooling,
        "coolingAllowed": cooling_allowed,
        "coolingIgnored": cooling_ignored,
        "activeProfile": "PROFILE_1",
        "profiles": {
            "PROFILE_1": {
                "index": "PROFILE_1",
                "name": "Standard",
                "enabled": True,
                "visible": True,
            }
        },
        "channels": [],
    }
    client = MagicMock()
    client.is_connected = True
    client.hcu_device_id = "hcu-1"
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.get_device_by_address = MagicMock(return_value=None)
    client.state = {
        "home": {"functionalHomes": {"INDOOR_CLIMATE": {"absenceType": "NOT_ABSENT"}}},
        "devices": {},
    }
    client.async_set_group_control_mode = AsyncMock()
    client.async_set_group_setpoint_temperature = AsyncMock()

    config_entry = MagicMock()
    config_entry.entry_id = "entry-1"
    config_entry.options = {CONF_COMFORT_TEMPERATURE: 21.0}

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {group_data["id"]: group_data}
    coordinator.config_entry = config_entry

    entity = HcuClimate(coordinator, client, group_data, config_entry)
    entity.hass = hass
    entity.entity_id = "climate.living_room"
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_cover(
    hass: HomeAssistant,
    *,
    level_prop: str = "shutterLevel",
    slats_level: float | None = None,
) -> tuple[HcuCover, MagicMock]:
    ch_data: dict[str, Any] = {
        "functionalChannelType": "SHUTTER_CHANNEL",
        "label": "Shutter",
        level_prop: 0.5,
        "processing": False,
    }
    if slats_level is not None:
        ch_data["slatsLevel"] = slats_level
        ch_data["blindModeActive"] = True

    device = {
        "id": "dev-cover-1",
        "label": "Cover",
        "type": "BRAND_BLIND" if slats_level is not None else "BRAND_SHUTTER",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": ch_data,
        },
    }
    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {"dev-cover-1": device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_set_shutter_level = AsyncMock()
    client.async_set_primary_shading_level = AsyncMock()
    client.async_set_slats_level = AsyncMock()
    client.async_stop_cover = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"dev-cover-1": device}
    coordinator.config_entry = MagicMock(data={}, options={})

    entity = HcuCover(coordinator, client, device, "1")
    entity.hass = hass
    entity.entity_id = "cover.shutter"
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_garage_cover(
    hass: HomeAssistant, *, stateful: bool = True
) -> tuple[HcuGarageDoorCover, MagicMock]:
    ch_data: dict[str, Any] = {
        "functionalChannelType": "DOOR_CHANNEL",
        "label": "Garage",
        "ventilationPositionSupported": True,
    }
    if stateful:
        ch_data["doorState"] = "CLOSED"
        ch_data["doorMotion"] = "NONE"
    device = {
        "id": "dev-garage-1",
        "label": "Garage",
        "type": "GARAGE_DOOR_CONTROLLER",
        "functionalChannels": {"1": ch_data},
    }
    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {"dev-garage-1": device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_send_door_command = AsyncMock()
    client.async_toggle_garage_door_state = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"dev-garage-1": device}
    coordinator.config_entry = MagicMock(data={}, options={})

    entity = HcuGarageDoorCover(coordinator, client, device, "1")
    entity.hass = hass
    entity.entity_id = "cover.garage"
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_cover_group(
    hass: HomeAssistant, *, with_tilt: bool = False
) -> tuple[HcuCoverGroup, MagicMock]:
    group_data = {
        "id": "grp-cover-1",
        "type": "SHUTTER",
        "label": "All Shutters",
        "primaryShadingLevel": 0.5,
        "secondaryShadingLevel": 0.5 if with_tilt else None,
        "channels": [],
    }
    client = MagicMock()
    client.is_connected = True
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.async_group_control = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"grp-cover-1": group_data}
    coordinator.config_entry = MagicMock(data={}, options={})

    entity = HcuCoverGroup(coordinator, client, group_data)
    entity.hass = hass
    entity.entity_id = "cover.all_shutters"
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_light(
    hass: HomeAssistant, *, mode: str = "dimmer"
) -> tuple[HcuLight, MagicMock]:
    ch: dict[str, Any] = {
        "functionalChannelType": "DIMMER_CHANNEL",
        "dimLevel": 0.5,
    }
    if mode == "simple_rgb":
        ch["simpleRGBColorState"] = "BLUE"
        ch["opticalSignalBehaviour"] = "OFF"
        ch["supportedOptionalFeatures"] = {"IFeatureOpticalSignalBehaviourState": True}
    elif mode == "hs":
        ch["hue"] = 120
        ch["saturationLevel"] = 0.5
    elif mode == "color_temp":
        ch["colorTemperature"] = 3000
        ch["minimalColorTemperature"] = 2000
        ch["maximumColorTemperature"] = 6500

    device = {
        "id": "dev-light-1",
        "label": "Light",
        "functionalChannels": {"1": ch},
    }
    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {"dev-light-1": device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_device_control = AsyncMock()
    client.async_set_hue_saturation = AsyncMock()
    client.async_set_color_temperature = AsyncMock()
    client.async_set_dim_level = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"dev-light-1": device}
    coordinator.config_entry = MagicMock(data={}, options={})

    entity = HcuLight(coordinator, client, device, "1")
    entity.hass = hass
    entity.entity_id = "light.lamp"
    entity._get_ramp_time = MagicMock(return_value=None)
    entity._get_internal_on_time = MagicMock(return_value=None)
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_notification_light(
    hass: HomeAssistant,
) -> tuple[HcuNotificationLight, MagicMock]:
    device = {
        "id": "dev-notif-1",
        "label": "Notif Light",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "dimLevel": 0.6,
                "simpleRGBColorState": "PURPLE",
                "on": True,
            }
        },
    }
    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {"dev-notif-1": device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_device_control = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"dev-notif-1": device}
    coordinator.config_entry = MagicMock(data={}, options={})

    entity = HcuNotificationLight(coordinator, client, device, "1")
    entity.hass = hass
    entity.entity_id = "light.notif"
    entity._get_ramp_time = MagicMock(return_value=None)
    entity.async_write_ha_state = MagicMock()
    return entity, client


def _make_watering_group(hass: HomeAssistant) -> tuple[HcuWateringGroup, MagicMock]:
    group_data = {
        "id": "grp-water-1",
        "type": "EXTENDED_LINKED_WATERING",
        "label": "Garden Watering",
        "wateringActive": False,
        "channels": [],
    }
    client = MagicMock()
    client.is_connected = True
    client.get_group_by_id = MagicMock(return_value=group_data)
    client.async_group_control = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"grp-water-1": group_data}
    coordinator.config_entry = MagicMock(data={}, options={})

    entity = HcuWateringGroup(coordinator, client, group_data)
    entity.hass = hass
    entity.entity_id = "switch.garden_watering"
    entity.async_write_ha_state = MagicMock()
    return entity, client


COMMAND_CASES: list[CommandCase] = [
    # --- climate.py: HcuClimate ---
    CommandCase(
        case_id="climate_set_temp_manual",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="MANUAL"),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_temperature(temperature=23.0),
        expected_call_args=("grp-climate-1", 23.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_temp_auto",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="AUTOMATIC"),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_temperature(temperature=23.0),
        expected_call_args=("grp-climate-1", 23.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_temp_switch_to_manual_mode_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="OFF"),
            "async_set_group_control_mode",
        ),
        invoke=lambda e: e.async_set_temperature(temperature=23.0),
        expected_call_args=("grp-climate-1", "MANUAL"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_temp_switch_to_manual_setpoint_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="OFF"),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_temperature(temperature=23.0),
        expected_call_args=("grp-climate-1", 23.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_off_mode_call_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="AUTOMATIC", setpoint=20.0),
            "async_set_group_control_mode",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.OFF),
        expected_call_args=("grp-climate-1", "MANUAL"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_off_setpoint_call_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="AUTOMATIC", setpoint=20.0),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.OFF),
        expected_call_args=("grp-climate-1", 5.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_off_manual_setpoint_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="MANUAL"),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.OFF),
        expected_call_args=("grp-climate-1", 5.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_auto_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="MANUAL"),
            "async_set_group_control_mode",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.AUTO),
        expected_call_args=("grp-climate-1", "AUTOMATIC"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_heat_mode_call_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="AUTOMATIC", setpoint=5.0),
            "async_set_group_control_mode",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.HEAT),
        expected_call_args=("grp-climate-1", "MANUAL"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_heat_setpoint_call_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(hass, control_mode="AUTOMATIC", setpoint=5.0),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.HEAT),
        expected_call_args=("grp-climate-1", 21.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_cool_mode_call_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(
                hass,
                control_mode="AUTOMATIC",
                setpoint=5.0,
                cooling=True,
                cooling_allowed=True,
            ),
            "async_set_group_control_mode",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.COOL),
        expected_call_args=("grp-climate-1", "MANUAL"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    CommandCase(
        case_id="climate_set_mode_cool_setpoint_call_fails",
        entity_id="climate.living_room",
        build=lambda hass: (
            *_make_climate(
                hass,
                control_mode="AUTOMATIC",
                setpoint=5.0,
                cooling=True,
                cooling_allowed=True,
            ),
            "async_set_group_setpoint_temperature",
        ),
        invoke=lambda e: e.async_set_hvac_mode(HVACMode.COOL),
        expected_call_args=("grp-climate-1", 21.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
        is_climate=True,
    ),
    # --- cover.py: HcuCover ---
    CommandCase(
        case_id="cover_open_shutter_level",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, level_prop="shutterLevel"),
            "async_set_shutter_level",
        ),
        invoke=lambda e: e.async_open_cover(),
        expected_call_args=("dev-cover-1", 1, 0.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_open_primary_shading",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, level_prop="primaryShadingLevel"),
            "async_set_primary_shading_level",
        ),
        invoke=lambda e: e.async_open_cover(),
        expected_call_args=("dev-cover-1", 1, 0.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_close_shutter_level",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, level_prop="shutterLevel"),
            "async_set_shutter_level",
        ),
        invoke=lambda e: e.async_close_cover(),
        expected_call_args=("dev-cover-1", 1, 1.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_close_primary_shading",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, level_prop="primaryShadingLevel"),
            "async_set_primary_shading_level",
        ),
        invoke=lambda e: e.async_close_cover(),
        expected_call_args=("dev-cover-1", 1, 1.0),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_stop",
        entity_id="cover.shutter",
        build=lambda hass: (*_make_cover(hass), "async_stop_cover"),
        invoke=lambda e: e.async_stop_cover(),
        expected_call_args=("dev-cover-1", 1),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_set_position_shutter_level",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, level_prop="shutterLevel"),
            "async_set_shutter_level",
        ),
        invoke=lambda e: e.async_set_cover_position(position=60),
        expected_call_args=("dev-cover-1", 1, 0.4),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_set_position_primary_shading",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, level_prop="primaryShadingLevel"),
            "async_set_primary_shading_level",
        ),
        invoke=lambda e: e.async_set_cover_position(position=60),
        expected_call_args=("dev-cover-1", 1, 0.4),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_set_tilt_position",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, slats_level=0.5),
            "async_set_slats_level",
        ),
        invoke=lambda e: e.async_set_cover_tilt_position(tilt_position=30),
        expected_call_args=("dev-cover-1", 1, 0.7),
        expected_call_kwargs={"shutter_level": 0.5},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_open_tilt",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, slats_level=0.5),
            "async_set_slats_level",
        ),
        invoke=lambda e: e.async_open_cover_tilt(),
        expected_call_args=("dev-cover-1", 1, 0.0),
        expected_call_kwargs={"shutter_level": 0.5},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_close_tilt",
        entity_id="cover.shutter",
        build=lambda hass: (
            *_make_cover(hass, slats_level=0.5),
            "async_set_slats_level",
        ),
        invoke=lambda e: e.async_close_cover_tilt(),
        expected_call_args=("dev-cover-1", 1, 1.0),
        expected_call_kwargs={"shutter_level": 0.5},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_stop_tilt",
        entity_id="cover.shutter",
        build=lambda hass: (*_make_cover(hass, slats_level=0.5), "async_stop_cover"),
        invoke=lambda e: e.async_stop_cover_tilt(),
        expected_call_args=("dev-cover-1", 1),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    # --- cover.py: HcuGarageDoorCover ---
    CommandCase(
        case_id="garage_open_stateful",
        entity_id="cover.garage",
        build=lambda hass: (
            *_make_garage_cover(hass, stateful=True),
            "async_send_door_command",
        ),
        invoke=lambda e: e.async_open_cover(),
        expected_call_args=("dev-garage-1", 1, "OPEN"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="garage_open_stateless",
        entity_id="cover.garage",
        build=lambda hass: (
            *_make_garage_cover(hass, stateful=False),
            "async_toggle_garage_door_state",
        ),
        invoke=lambda e: e.async_open_cover(),
        expected_call_args=("dev-garage-1", 1),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="garage_close_stateful",
        entity_id="cover.garage",
        build=lambda hass: (
            *_make_garage_cover(hass, stateful=True),
            "async_send_door_command",
        ),
        invoke=lambda e: e.async_close_cover(),
        expected_call_args=("dev-garage-1", 1, "CLOSE"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="garage_close_stateless",
        entity_id="cover.garage",
        build=lambda hass: (
            *_make_garage_cover(hass, stateful=False),
            "async_toggle_garage_door_state",
        ),
        invoke=lambda e: e.async_close_cover(),
        expected_call_args=("dev-garage-1", 1),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="garage_stop_stateful",
        entity_id="cover.garage",
        build=lambda hass: (
            *_make_garage_cover(hass, stateful=True),
            "async_send_door_command",
        ),
        invoke=lambda e: e.async_stop_cover(),
        expected_call_args=("dev-garage-1", 1, "STOP"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="garage_open_tilt_stateful",
        entity_id="cover.garage",
        build=lambda hass: (
            *_make_garage_cover(hass, stateful=True),
            "async_send_door_command",
        ),
        invoke=lambda e: e.async_open_cover_tilt(),
        expected_call_args=("dev-garage-1", 1, "PARTIAL_OPEN"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    # --- cover.py: HcuCoverGroup ---
    CommandCase(
        case_id="cover_group_open",
        entity_id="cover.all_shutters",
        build=lambda hass: (*_make_cover_group(hass), "async_group_control"),
        invoke=lambda e: e.async_open_cover(),
        expected_call_args=(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            "grp-cover-1",
            {"primaryShadingLevel": 0.0},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_close",
        entity_id="cover.all_shutters",
        build=lambda hass: (*_make_cover_group(hass), "async_group_control"),
        invoke=lambda e: e.async_close_cover(),
        expected_call_args=(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            "grp-cover-1",
            {"primaryShadingLevel": 1.0},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_stop",
        entity_id="cover.all_shutters",
        build=lambda hass: (*_make_cover_group(hass), "async_group_control"),
        invoke=lambda e: e.async_stop_cover(),
        expected_call_args=(API_PATHS["STOP_GROUP_COVER"], "grp-cover-1"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_set_position",
        entity_id="cover.all_shutters",
        build=lambda hass: (*_make_cover_group(hass), "async_group_control"),
        invoke=lambda e: e.async_set_cover_position(position=60),
        expected_call_args=(
            API_PATHS["SET_GROUP_SHUTTER_LEVEL"],
            "grp-cover-1",
            {"primaryShadingLevel": 0.4},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_set_tilt_position",
        entity_id="cover.all_shutters",
        build=lambda hass: (
            *_make_cover_group(hass, with_tilt=True),
            "async_group_control",
        ),
        invoke=lambda e: e.async_set_cover_tilt_position(tilt_position=40),
        expected_call_args=(
            API_PATHS["SET_GROUP_SECONDARY_SHADING_LEVEL"],
            "grp-cover-1",
            {
                "primaryShadingLevel": 0.5,
                "secondaryShadingLevel": 0.6,
                "shutterLevel": 0.5,
                "slatsLevel": 0.6,
            },
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_close_tilt",
        entity_id="cover.all_shutters",
        build=lambda hass: (
            *_make_cover_group(hass, with_tilt=True),
            "async_group_control",
        ),
        invoke=lambda e: e.async_close_cover_tilt(),
        expected_call_args=(
            API_PATHS["SET_GROUP_SECONDARY_SHADING_LEVEL"],
            "grp-cover-1",
            {
                "primaryShadingLevel": 0.5,
                "secondaryShadingLevel": 1.0,
                "shutterLevel": 0.5,
                "slatsLevel": 1.0,
            },
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_open_tilt",
        entity_id="cover.all_shutters",
        build=lambda hass: (
            *_make_cover_group(hass, with_tilt=True),
            "async_group_control",
        ),
        invoke=lambda e: e.async_open_cover_tilt(),
        expected_call_args=(
            API_PATHS["SET_GROUP_SECONDARY_SHADING_LEVEL"],
            "grp-cover-1",
            {
                "primaryShadingLevel": 0.5,
                "secondaryShadingLevel": 0.0,
                "shutterLevel": 0.5,
                "slatsLevel": 0.0,
            },
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="cover_group_stop_tilt",
        entity_id="cover.all_shutters",
        build=lambda hass: (
            *_make_cover_group(hass, with_tilt=True),
            "async_group_control",
        ),
        invoke=lambda e: e.async_stop_cover_tilt(),
        expected_call_args=(API_PATHS["STOP_GROUP_COVER"], "grp-cover-1"),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    # --- light.py: HcuLight ---
    CommandCase(
        case_id="light_turn_on_simple_rgb",
        entity_id="light.lamp",
        build=lambda hass: (
            *_make_light(hass, mode="simple_rgb"),
            "async_device_control",
        ),
        invoke=lambda e: e.async_turn_on(**{ATTR_BRIGHTNESS: 255}),
        expected_call_args=(
            API_PATHS["SET_OPTICAL_SIGNAL_BEHAVIOUR"],
            "dev-light-1",
            1,
            {
                "simpleRGBColorState": "BLUE",
                "dimLevel": 1.0,
                "opticalSignalBehaviour": "ON",
            },
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="light_turn_on_hs",
        entity_id="light.lamp",
        build=lambda hass: (*_make_light(hass, mode="hs"), "async_set_hue_saturation"),
        invoke=lambda e: e.async_turn_on(
            **{ATTR_HS_COLOR: (240.0, 80.0), ATTR_BRIGHTNESS: 255}
        ),
        expected_call_args=("dev-light-1", 1, 240, 0.8, 1.0, None),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    CommandCase(
        case_id="light_turn_on_color_temp",
        entity_id="light.lamp",
        build=lambda hass: (
            *_make_light(hass, mode="color_temp"),
            "async_set_color_temperature",
        ),
        invoke=lambda e: e.async_turn_on(
            **{ATTR_COLOR_TEMP_KELVIN: 4000, ATTR_BRIGHTNESS: 255}
        ),
        expected_call_args=("dev-light-1", 1, 4000, 1.0, None),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    CommandCase(
        case_id="light_turn_on_dimmer",
        entity_id="light.lamp",
        build=lambda hass: (*_make_light(hass, mode="dimmer"), "async_set_dim_level"),
        invoke=lambda e: e.async_turn_on(**{ATTR_BRIGHTNESS: 255}),
        expected_call_args=("dev-light-1", 1, 1.0, None),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    CommandCase(
        case_id="light_turn_off_simple_rgb",
        entity_id="light.lamp",
        build=lambda hass: (
            *_make_light(hass, mode="simple_rgb"),
            "async_device_control",
        ),
        invoke=lambda e: e.async_turn_off(),
        expected_call_args=(
            API_PATHS["SET_OPTICAL_SIGNAL_BEHAVIOUR"],
            "dev-light-1",
            1,
            {
                "simpleRGBColorState": "BLUE",
                "dimLevel": 0.0,
                "opticalSignalBehaviour": "OFF",
            },
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=True,
    ),
    CommandCase(
        case_id="light_turn_off_dimmer",
        entity_id="light.lamp",
        build=lambda hass: (*_make_light(hass, mode="dimmer"), "async_set_dim_level"),
        invoke=lambda e: e.async_turn_off(),
        expected_call_args=("dev-light-1", 1, 0.0, None),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    # --- light.py: HcuNotificationLight ---
    CommandCase(
        case_id="notif_light_turn_on",
        entity_id="light.notif",
        build=lambda hass: (*_make_notification_light(hass), "async_device_control"),
        invoke=lambda e: e.async_turn_on(**{ATTR_BRIGHTNESS: 255}),
        expected_call_args=(
            API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
            "dev-notif-1",
            1,
            {"simpleRGBColorState": "PURPLE", "dimLevel": 1.0},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    CommandCase(
        case_id="notif_light_turn_off",
        entity_id="light.notif",
        build=lambda hass: (*_make_notification_light(hass), "async_device_control"),
        invoke=lambda e: e.async_turn_off(),
        expected_call_args=(
            API_PATHS["SET_SIMPLE_RGB_COLOR_STATE"],
            "dev-notif-1",
            1,
            {"simpleRGBColorState": "BLACK", "dimLevel": 0.0},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    # --- switch.py: HcuWateringGroup ---
    CommandCase(
        case_id="watering_group_turn_on",
        entity_id="switch.garden_watering",
        build=lambda hass: (*_make_watering_group(hass), "async_group_control"),
        invoke=lambda e: e.async_turn_on(),
        expected_call_args=(
            API_PATHS["SET_GROUP_WATERING_SWITCH_STATE"],
            "grp-water-1",
            {"wateringActive": True},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
    CommandCase(
        case_id="watering_group_turn_off",
        entity_id="switch.garden_watering",
        build=lambda hass: (*_make_watering_group(hass), "async_group_control"),
        invoke=lambda e: e.async_turn_off(),
        expected_call_args=(
            API_PATHS["SET_GROUP_WATERING_SWITCH_STATE"],
            "grp-water-1",
            {"wateringActive": False},
        ),
        expected_call_kwargs={},
        expected_assumed_on_success=False,
    ),
]

CLIMATE_CASES = [c for c in COMMAND_CASES if c.is_climate]


@pytest.mark.parametrize("case", COMMAND_CASES, ids=lambda c: c.case_id)
async def test_rejected_command_raises_translated_error(
    hass: HomeAssistant, case: CommandCase
) -> None:
    """Rejected HCU commands raise translated HomeAssistantError with cause."""
    entity, client, method_name = case.build(hass)
    err = HcuApiError("rejected", error_code="DEVICE_UNREACHABLE")
    getattr(client, method_name).side_effect = err

    with pytest.raises(HomeAssistantError) as exc_info:
        await case.invoke(entity)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "hcu_error_device_unreachable"
    assert exc_info.value.translation_placeholders == {"entity": case.entity_id}
    assert exc_info.value.__cause__ is err


@pytest.mark.parametrize("case", COMMAND_CASES, ids=lambda c: c.case_id)
async def test_connection_error_raises_command_failed(
    hass: HomeAssistant, case: CommandCase
) -> None:
    """ConnectionError raises translated command_failed HomeAssistantError."""
    entity, client, method_name = case.build(hass)
    err = ConnectionError("down")
    getattr(client, method_name).side_effect = err

    with pytest.raises(HomeAssistantError) as exc_info:
        await case.invoke(entity)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "command_failed"
    assert exc_info.value.translation_placeholders == {
        "entity": case.entity_id,
        "error": "down",
    }
    assert exc_info.value.__cause__ is err


@pytest.mark.parametrize("case", COMMAND_CASES, ids=lambda c: c.case_id)
async def test_non_api_exception_passes_through_unchanged(
    hass: HomeAssistant, case: CommandCase
) -> None:
    """Unexpected non-HCU exceptions are not caught or wrapped."""
    entity, client, method_name = case.build(hass)
    err = ValueError("unexpected bug")
    getattr(client, method_name).side_effect = err

    with pytest.raises(ValueError, match="unexpected bug") as exc_info:
        await case.invoke(entity)

    assert exc_info.value is err


@pytest.mark.parametrize("case", COMMAND_CASES, ids=lambda c: c.case_id)
async def test_failed_command_clears_assumed_state(
    hass: HomeAssistant, case: CommandCase
) -> None:
    """Failing commands reset _attr_assumed_state and roll back before writing state."""
    entity, client, method_name = case.build(hass)
    err = HcuApiError("rejected", error_code="DEVICE_UNREACHABLE")

    if case.is_climate:
        expected_snapshot: tuple[Any, ...] = (
            False,
            entity.hvac_mode,
            entity.native_target_temperature,
        )
    elif isinstance(entity, HcuCover):
        expected_snapshot = (False, entity.is_opening, entity.is_closing)
    else:
        expected_snapshot = (False,)

    written_states: list[tuple[Any, ...]] = []

    def _record_write() -> None:
        if case.is_climate:
            written_states.append(
                (
                    entity._attr_assumed_state,
                    entity.hvac_mode,
                    entity.native_target_temperature,
                )
            )
        elif isinstance(entity, HcuCover):
            written_states.append(
                (entity._attr_assumed_state, entity.is_opening, entity.is_closing)
            )
        else:
            written_states.append((entity._attr_assumed_state,))

    def _fail(*args: Any, **kwargs: Any) -> None:
        entity.async_write_ha_state.reset_mock()
        entity._attr_assumed_state = True
        entity.async_write_ha_state.side_effect = _record_write
        raise err

    getattr(client, method_name).side_effect = _fail

    with pytest.raises(HomeAssistantError):
        await case.invoke(entity)

    assert entity._attr_assumed_state is False
    entity.async_write_ha_state.assert_called_once()
    assert written_states == [expected_snapshot]


@pytest.mark.parametrize("case", CLIMATE_CASES, ids=lambda c: c.case_id)
async def test_climate_failure_restores_target_and_mode(
    hass: HomeAssistant, case: CommandCase
) -> None:
    """Failed climate commands restore _attr_hvac_mode and target temperature."""
    entity, client, method_name = case.build(hass)
    prev_attr_mode = entity._attr_hvac_mode
    prev_attr_temp = entity._attr_native_target_temperature
    prev_mode = entity.hvac_mode
    prev_temp = entity.native_target_temperature

    getattr(client, method_name).side_effect = HcuApiError(
        "rejected", error_code="DEVICE_UNREACHABLE"
    )

    with pytest.raises(HomeAssistantError):
        await case.invoke(entity)

    assert entity._attr_hvac_mode == prev_attr_mode
    assert entity._attr_native_target_temperature == prev_attr_temp
    assert entity.hvac_mode == prev_mode
    assert entity.native_target_temperature == prev_temp


async def test_climate_failed_command_does_not_change_the_next_one(
    hass: HomeAssistant,
) -> None:
    """A failed set_hvac_mode(HEAT) in auto mode does not force MANUAL on next set_temperature."""
    entity, client = _make_climate(hass, control_mode="AUTOMATIC", setpoint=21.0)
    client.async_set_group_control_mode.side_effect = HcuApiError(
        "rejected", error_code="DEVICE_UNREACHABLE"
    )

    with pytest.raises(HomeAssistantError):
        await entity.async_set_hvac_mode(HVACMode.HEAT)

    client.async_set_group_control_mode.side_effect = None
    client.async_set_group_control_mode.reset_mock()

    await entity.async_set_temperature(temperature=22.0)

    client.async_set_group_control_mode.assert_not_awaited()
    client.async_set_group_setpoint_temperature.assert_awaited_once_with(
        "grp-climate-1", 22.0
    )


async def test_climate_rollback_preserves_event_arriving_during_failing_call(
    hass: HomeAssistant,
) -> None:
    """Climate rollback reflects a newer group event received before failure."""
    entity, client = _make_climate(hass, control_mode="MANUAL", setpoint=21.0)

    def _event_then_fail(*args: Any, **kwargs: Any) -> None:
        entity._group["controlMode"] = "AUTOMATIC"
        entity._handle_coordinator_update()
        raise HcuApiError("timeout", error_code="DEVICE_UNREACHABLE")

    client.async_set_group_control_mode.side_effect = _event_then_fail

    with pytest.raises(HomeAssistantError):
        await entity.async_set_hvac_mode(HVACMode.AUTO)

    assert entity._attr_assumed_state is False
    assert entity._attr_hvac_mode == HVACMode.AUTO
    assert entity.hvac_mode == HVACMode.AUTO

    client.async_set_group_control_mode.side_effect = None
    client.async_set_group_control_mode.reset_mock()

    await entity.async_set_temperature(temperature=22.0)

    client.async_set_group_control_mode.assert_not_awaited()
    client.async_set_group_setpoint_temperature.assert_awaited_once_with(
        "grp-climate-1", 22.0
    )


async def test_cover_failure_restores_direction(hass: HomeAssistant) -> None:
    """Failed move or stop restores previous optimistic cover direction."""
    cover, client = _make_cover(hass)
    cover._channel["processing"] = True

    await cover.async_close_cover()
    assert cover.is_closing is True
    assert cover.is_opening is False
    saved_set_at = cover._optimistic_direction_set_at

    # Failed open restores closing direction before writing state
    written: list[tuple[bool, bool]] = []
    cover.async_write_ha_state = MagicMock(
        side_effect=lambda: written.append((cover.is_opening, cover.is_closing))
    )
    client.async_set_shutter_level.side_effect = HcuApiError(
        "rejected", error_code="DEVICE_UNREACHABLE"
    )
    with pytest.raises(HomeAssistantError):
        await cover.async_open_cover()

    assert written == [(False, True)]
    assert cover.is_closing is True
    assert cover.is_opening is False
    assert cover._optimistic_direction == "closing"
    assert cover._optimistic_direction_set_at == saved_set_at
    assert cover._attr_assumed_state is False

    # Failed stop restores closing direction
    client.async_stop_cover.side_effect = HcuApiError(
        "rejected", error_code="DEVICE_UNREACHABLE"
    )
    with pytest.raises(HomeAssistantError):
        await cover.async_stop_cover()

    assert cover.is_closing is True
    assert cover.is_opening is False
    assert cover._optimistic_direction == "closing"
    assert cover._optimistic_direction_set_at == saved_set_at
    assert cover._attr_assumed_state is False

    # Switch to opening, then verify failed close and failed set_cover_position restore opening
    client.async_set_shutter_level.side_effect = None
    await cover.async_open_cover()
    assert cover.is_opening is True
    assert cover.is_closing is False
    open_set_at = cover._optimistic_direction_set_at

    client.async_set_shutter_level.side_effect = HcuApiError(
        "rejected", error_code="DEVICE_UNREACHABLE"
    )
    for coro in (
        cover.async_close_cover(),
        cover.async_set_cover_position(position=30),
    ):
        with pytest.raises(HomeAssistantError):
            await coro

        assert cover.is_opening is True
        assert cover.is_closing is False
        assert cover._optimistic_direction == "opening"
        assert cover._optimistic_direction_set_at == open_set_at
        assert cover._attr_assumed_state is False


@pytest.mark.parametrize("case", COMMAND_CASES, ids=lambda c: c.case_id)
async def test_successful_commands_are_unchanged(
    hass: HomeAssistant, case: CommandCase
) -> None:
    """Successful commands preserve client call arguments and assumed_state."""
    entity, client, method_name = case.build(hass)

    await case.invoke(entity)

    getattr(client, method_name).assert_awaited_with(
        *case.expected_call_args, **case.expected_call_kwargs
    )
    assert entity._attr_assumed_state is case.expected_assumed_on_success
    if case.case_id == "light_turn_on_simple_rgb":
        client.async_set_dim_level.assert_not_awaited()


@pytest.mark.parametrize(
    ("cooling_allowed", "cooling_ignored"),
    [(False, False), (True, True)],
    ids=["cooling_not_allowed", "cooling_ignored"],
)
async def test_set_temperature_while_cooling_is_blocked_raises(
    hass: HomeAssistant, cooling_allowed: bool, cooling_ignored: bool
) -> None:
    """Changing setpoint when cooling is blocked/ignored raises ServiceValidationError."""
    entity, client = _make_climate(
        hass,
        cooling=True,
        cooling_allowed=cooling_allowed,
        cooling_ignored=cooling_ignored,
    )

    with pytest.raises(ServiceValidationError) as exc_info:
        await entity.async_set_temperature(temperature=22.0)

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "climate_cooling_blocked"
    assert exc_info.value.translation_placeholders == {"entity": entity.entity_id}
    client.async_set_group_control_mode.assert_not_awaited()
    client.async_set_group_setpoint_temperature.assert_not_awaited()
    assert entity._attr_assumed_state is False
    entity.async_write_ha_state.assert_not_called()


async def test_set_temperature_while_cooling_is_allowed_is_sent(
    hass: HomeAssistant,
) -> None:
    """Changing setpoint when cooling is active and allowed sends the command."""
    entity, client = _make_climate(
        hass,
        cooling=True,
        cooling_allowed=True,
        cooling_ignored=False,
    )

    await entity.async_set_temperature(temperature=22.0)

    client.async_set_group_setpoint_temperature.assert_awaited_once_with(
        "grp-climate-1", 22.0
    )


def _make_latch_button(
    hass: HomeAssistant,
    button_cls: type[HcuDoorPullLatchButton | HcuDoorUnlatchButton],
    *,
    auth_type: str,
    with_client_id: bool,
) -> tuple[HcuDoorPullLatchButton | HcuDoorUnlatchButton, MagicMock]:
    data: dict[str, Any] = {CONF_AUTH_TYPE: auth_type}
    if with_client_id:
        key = (
            CONF_APP_CLIENT_ID if auth_type == AUTH_TYPE_APP else CONF_PLUGIN_CLIENT_ID
        )
        data[key] = "client-1"

    entry = MockConfigEntry(domain=DOMAIN, data=data)
    entry.add_to_hass(hass)

    device_data = {
        "id": "dev-latch-1",
        "label": "Front Door",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DOOR_CHANNEL", "groupIndex": 1},
        },
    }
    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_pull_latch = AsyncMock()
    client.async_set_lock_state = AsyncMock()

    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = {"dev-latch-1": device_data}

    btn = button_cls(coordinator, client, device_data, "1")
    btn.hass = hass
    btn.entity_id = "button.front_door_latch"
    btn.platform_data = MagicMock(
        platform_name=DOMAIN, domain="button", platform_translations={}
    )
    return btn, client


@pytest.mark.parametrize(
    ("button_cls", "client_method"),
    [
        (HcuDoorPullLatchButton, "async_pull_latch"),
        (HcuDoorUnlatchButton, "async_set_lock_state"),
    ],
    ids=["pull_latch", "unlatch"],
)
@pytest.mark.parametrize("auth_type", [AUTH_TYPE_APP, AUTH_TYPE_PLUGIN])
async def test_latch_press_without_client_id_raises(
    hass: HomeAssistant,
    button_cls: type[HcuDoorPullLatchButton | HcuDoorUnlatchButton],
    client_method: str,
    auth_type: str,
) -> None:
    """Latch press without stored client ID raises translated HomeAssistantError."""
    btn, client = _make_latch_button(
        hass, button_cls, auth_type=auth_type, with_client_id=False
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await btn.async_press()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "latch_client_id_missing"
    assert exc_info.value.translation_placeholders == {"entity": btn.entity_id}
    getattr(client, client_method).assert_not_awaited()


@pytest.mark.parametrize(
    ("button_cls", "client_method"),
    [
        (HcuDoorPullLatchButton, "async_pull_latch"),
        (HcuDoorUnlatchButton, "async_set_lock_state"),
    ],
    ids=["pull_latch", "unlatch"],
)
async def test_latch_press_without_authorization_raises(
    hass: HomeAssistant,
    button_cls: type[HcuDoorPullLatchButton | HcuDoorUnlatchButton],
    client_method: str,
) -> None:
    """Latch press without access authorization raises and creates repair issue."""
    btn, client = _make_latch_button(
        hass, button_cls, auth_type=AUTH_TYPE_APP, with_client_id=True
    )

    with pytest.raises(HomeAssistantError) as exc_info:
        await btn.async_press()

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "latch_not_authorized"
    assert exc_info.value.translation_placeholders == {"entity": btn.entity_id}
    getattr(client, client_method).assert_not_awaited()
    issue_reg = ir.async_get(hass)
    assert (
        issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-latch-1_1")
        is not None
    )


async def test_play_sound_methods_still_pass_the_client_error_on(
    hass: HomeAssistant,
) -> None:
    """async_play_sound on switch and notification light pass HcuApiError through."""
    err = HcuApiError("sound failed", error_code="INVALID_REQUEST")

    sw_device = {
        "id": "dev-sw-1",
        "label": "Siren Switch",
        "functionalChannels": {
            "1": {"functionalChannelType": "SWITCH_CHANNEL", "on": False}
        },
    }
    sw_client = MagicMock()
    sw_client.get_device_by_address = MagicMock(return_value=sw_device)
    sw_client.async_set_sound_file = AsyncMock(side_effect=err)
    sw_coord = MagicMock(
        hass=hass, data={}, config_entry=MagicMock(data={}, options={})
    )
    sw = HcuSwitch(sw_coord, sw_client, sw_device, "1")
    with pytest.raises(HcuApiError) as sw_exc:
        await sw.async_play_sound("INTERNAL_SOUNDFILE", 1.0, 5.0)
    assert sw_exc.value is err

    notif, notif_client = _make_notification_light(hass)
    notif_client.async_set_sound_file = AsyncMock(side_effect=err)
    with pytest.raises(HcuApiError) as notif_exc:
        await notif.async_play_sound("INTERNAL_SOUNDFILE", 1.0, 5.0)
    assert notif_exc.value is err


async def test_light_turn_on_internal_on_time_error_passes_through(
    hass: HomeAssistant,
) -> None:
    """HcuLight.async_turn_on delegates to async_turn_on_with_time without re-wrapping."""
    light, client = _make_light(hass, mode="dimmer")
    light._get_internal_on_time = MagicMock(return_value=30.0)
    err = HcuApiError("rejected", error_code="DEVICE_UNREACHABLE")
    client.async_set_dim_level.side_effect = err

    with pytest.raises(HomeAssistantError) as exc_info:
        await light.async_turn_on()

    assert exc_info.value.translation_key == "hcu_error_device_unreachable"
    assert exc_info.value.__cause__ is err
    assert light._attr_assumed_state is False


async def test_garage_tilt_delegation_error_passes_through(
    hass: HomeAssistant,
) -> None:
    """HcuGarageDoorCover close/stop tilt propagate command_failed cleanly."""
    garage, client = _make_garage_cover(hass, stateful=True)
    err = HcuApiError("rejected", error_code="DEVICE_UNREACHABLE")
    client.async_send_door_command.side_effect = err

    for coro in (garage.async_close_cover_tilt(), garage.async_stop_cover_tilt()):
        with patch.object(garage, "async_write_ha_state"):
            with pytest.raises(HomeAssistantError) as exc_info:
                await coro
            assert exc_info.value.translation_key == "hcu_error_device_unreachable"
            assert exc_info.value.__cause__ is err
            assert garage._attr_assumed_state is False
