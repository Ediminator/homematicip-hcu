"""Tests for the device type that is inferred from the features of a bridged device."""

from __future__ import annotations

import pytest

from custom_components.hcu_integration.const import (
    HA_DEVICE_TYPE_BATTERY,
    HA_DEVICE_TYPE_CLIMATE_SENSOR,
    HA_DEVICE_TYPE_CONTACT_SENSOR,
    HA_DEVICE_TYPE_ENERGY_METER,
    HA_DEVICE_TYPE_HEAT_PUMP,
    HA_DEVICE_TYPE_LIGHT,
    HA_DEVICE_TYPE_OCCUPANCY_SENSOR,
    HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR,
    HA_DEVICE_TYPE_SMOKE_ALARM,
    HA_DEVICE_TYPE_SWITCH,
    HA_DEVICE_TYPE_THERMOSTAT,
    HA_DEVICE_TYPE_VEHICLE,
    HA_DEVICE_TYPE_WATER_SENSOR,
    HA_DEVICE_TYPE_WINDOW_COVERING,
    determine_ha_device_type,
)

# One row per feature key that decides a device type on its own. The keys are
# written as literals on purpose: they are stored in the options of existing
# users, so renaming a constant must not silently change the inferred type.
SINGLE_FEATURE_CASES = [
    ({"brightness": "light.a"}, HA_DEVICE_TYPE_LIGHT),
    ({"color_temp": "light.a"}, HA_DEVICE_TYPE_LIGHT),
    ({"rgb_color": "light.a"}, HA_DEVICE_TYPE_LIGHT),
    ({"on_off": "light.a"}, HA_DEVICE_TYPE_LIGHT),
    ({"on_off": "switch.a"}, HA_DEVICE_TYPE_SWITCH),
    ({"on_off": "input_boolean.a"}, HA_DEVICE_TYPE_SWITCH),
    ({"climate_operation_mode": "climate.a"}, HA_DEVICE_TYPE_HEAT_PUMP),
    ({"set_point_temp": "climate.a"}, HA_DEVICE_TYPE_THERMOSTAT),
    ({"shutter_level": "cover.a"}, HA_DEVICE_TYPE_WINDOW_COVERING),
    ({"power": "sensor.a"}, HA_DEVICE_TYPE_ENERGY_METER),
    ({"energy": "sensor.a"}, HA_DEVICE_TYPE_ENERGY_METER),
    ({"pm1": "sensor.a"}, HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR),
    ({"pm25": "sensor.a"}, HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR),
    ({"pm10": "sensor.a"}, HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR),
    ({"temperature": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"humidity": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"illuminance": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"co2": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"wind_speed": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"precipitation": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"storm": "binary_sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"sunshine": "binary_sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"raining": "binary_sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"wind_direction": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"sunshine_duration": "sensor.a"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
    ({"motion": "binary_sensor.a"}, HA_DEVICE_TYPE_OCCUPANCY_SENSOR),
    ({"occupancy": "binary_sensor.a"}, HA_DEVICE_TYPE_OCCUPANCY_SENSOR),
    ({"door": "binary_sensor.a"}, HA_DEVICE_TYPE_CONTACT_SENSOR),
    ({"window": "binary_sensor.a"}, HA_DEVICE_TYPE_CONTACT_SENSOR),
    ({"contact_sensor": "binary_sensor.a"}, HA_DEVICE_TYPE_CONTACT_SENSOR),
    ({"smoke": "binary_sensor.a"}, HA_DEVICE_TYPE_SMOKE_ALARM),
    ({"moisture": "sensor.a"}, HA_DEVICE_TYPE_WATER_SENSOR),
    ({"moisture_detected": "binary_sensor.a"}, HA_DEVICE_TYPE_WATER_SENSOR),
    ({"vehicle_range": "sensor.a"}, HA_DEVICE_TYPE_VEHICLE),
    ({"battery": "sensor.a"}, HA_DEVICE_TYPE_BATTERY),
]

# Keys that never decide the type: the result is the documented fallback.
FALLBACK_CASES = [
    ({}, HA_DEVICE_TYPE_SWITCH),
    ({"on_time": "number.a"}, HA_DEVICE_TYPE_SWITCH),
    ({"slats_level": "cover.a"}, HA_DEVICE_TYPE_SWITCH),
    (
        {"low_bat": "binary_sensor.a", "unreach": "binary_sensor.b"},
        HA_DEVICE_TYPE_SWITCH,
    ),
]

# Each row holds the deciding key of two neighbouring checks. The earlier
# check has to win, so swapping two checks fails at least one row.
PRECEDENCE_CASES = [
    ({"brightness": "light.a", "on_off": "switch.a"}, HA_DEVICE_TYPE_LIGHT),
    (
        {"on_off": "switch.a", "climate_operation_mode": "climate.a"},
        HA_DEVICE_TYPE_SWITCH,
    ),
    (
        {"climate_operation_mode": "climate.a", "set_point_temp": "climate.a"},
        HA_DEVICE_TYPE_HEAT_PUMP,
    ),
    (
        {"set_point_temp": "climate.a", "shutter_level": "cover.a"},
        HA_DEVICE_TYPE_THERMOSTAT,
    ),
    ({"shutter_level": "cover.a", "power": "sensor.a"}, HA_DEVICE_TYPE_WINDOW_COVERING),
    ({"energy": "sensor.a", "pm25": "sensor.b"}, HA_DEVICE_TYPE_ENERGY_METER),
    (
        {"pm10": "sensor.a", "temperature": "sensor.b"},
        HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR,
    ),
    (
        {"humidity": "sensor.a", "motion": "binary_sensor.a"},
        HA_DEVICE_TYPE_CLIMATE_SENSOR,
    ),
    (
        {"occupancy": "binary_sensor.a", "door": "binary_sensor.b"},
        HA_DEVICE_TYPE_OCCUPANCY_SENSOR,
    ),
    (
        {"window": "binary_sensor.a", "smoke": "binary_sensor.b"},
        HA_DEVICE_TYPE_CONTACT_SENSOR,
    ),
    ({"smoke": "binary_sensor.a", "moisture": "sensor.a"}, HA_DEVICE_TYPE_SMOKE_ALARM),
    (
        {"moisture_detected": "binary_sensor.a", "vehicle_range": "sensor.a"},
        HA_DEVICE_TYPE_WATER_SENSOR,
    ),
    ({"vehicle_range": "sensor.a", "battery": "sensor.b"}, HA_DEVICE_TYPE_VEHICLE),
    # A set point next to climate sensor keys stays a thermostat.
    (
        {
            "set_point_temp": "climate.a",
            "temperature": "sensor.a",
            "humidity": "sensor.b",
        },
        HA_DEVICE_TYPE_THERMOSTAT,
    ),
    # A battery level next to any deciding key never makes it a battery.
    ({"battery": "sensor.a", "temperature": "sensor.b"}, HA_DEVICE_TYPE_CLIMATE_SENSOR),
]


@pytest.mark.parametrize(
    ("features", "expected"),
    SINGLE_FEATURE_CASES + FALLBACK_CASES + PRECEDENCE_CASES,
)
def test_determine_ha_device_type(features: dict[str, str], expected: str):
    """The inferred type follows the fixed order of the feature checks."""
    assert determine_ha_device_type(features) == expected


def test_every_return_path_is_in_the_table():
    """The table reaches all 14 device types the function can return."""
    reached = {
        expected
        for _, expected in SINGLE_FEATURE_CASES + FALLBACK_CASES + PRECEDENCE_CASES
    }
    assert reached == {
        "LIGHT",
        "SWITCH",
        "HEAT_PUMP",
        "THERMOSTAT",
        "WINDOW_COVERING",
        "ENERGY_METER",
        "PARTICULATE_MATTER_SENSOR",
        "CLIMATE_SENSOR",
        "OCCUPANCY_SENSOR",
        "CONTACT_SENSOR",
        "SMOKE_ALARM",
        "WATER_SENSOR",
        "VEHICLE",
        "BATTERY",
    }
