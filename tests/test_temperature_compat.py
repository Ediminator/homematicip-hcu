"""Tests for the native climate temperature members on older releases."""

from __future__ import annotations

from homeassistant.components.climate import ClimateEntity
from homeassistant.const import UnitOfTemperature

from custom_components.hcu_integration.temperature_compat import (
    ClimateTemperatureCompat,
    _LegacyTemperatureNames,
    _NoLegacyTemperatureNames,
    temperature_compat_for,
)


class _OldEntity:
    """An entity base class from before Home Assistant 2026.11."""


class _NewEntity:
    """An entity base class from Home Assistant 2026.11 on."""

    native_temperature_unit = UnitOfTemperature.CELSIUS


class _Climate(ClimateTemperatureCompat, ClimateEntity):
    """A climate entity that only sets the native attributes."""

    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS


def test_old_base_gets_the_legacy_names() -> None:
    """Releases without native members get the mixin with the old names."""
    assert temperature_compat_for(_OldEntity) is _LegacyTemperatureNames


def test_new_base_gets_nothing() -> None:
    """Releases with native members get an empty mixin."""
    assert temperature_compat_for(_NewEntity) is _NoLegacyTemperatureNames
    assert not [
        name for name in vars(_NoLegacyTemperatureNames) if not name.startswith("__")
    ]


def test_legacy_names_follow_the_native_attributes() -> None:
    """The old names read the native attributes."""
    entity = _LegacyTemperatureNames()
    assert entity.current_temperature is None
    assert entity.target_temperature is None

    entity._attr_native_temperature_unit = UnitOfTemperature.FAHRENHEIT
    entity._attr_native_current_temperature = 68.5
    entity._attr_native_target_temperature = 70

    assert entity.temperature_unit == UnitOfTemperature.FAHRENHEIT
    assert entity.current_temperature == 68.5
    assert entity.target_temperature == 70


def test_legacy_names_follow_overridden_native_properties() -> None:
    """The old names read native properties a subclass overrides."""

    class _Entity(_LegacyTemperatureNames):
        @property
        def native_current_temperature(self) -> float | None:
            return 23.5

        @property
        def native_target_temperature(self) -> float | None:
            return 24

    entity = _Entity()
    assert entity.current_temperature == 23.5
    assert entity.target_temperature == 24


def test_climate_reports_the_native_values_on_this_release() -> None:
    """A climate entity reports the native values on the installed release."""
    entity = _Climate()
    entity._attr_native_current_temperature = 21.2
    entity._attr_native_target_temperature = 22

    assert entity.native_temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.native_current_temperature == 21.2
    assert entity.native_target_temperature == 22
    if ClimateTemperatureCompat is _LegacyTemperatureNames:
        # What Home Assistant < 2026.11 reads; deprecated from 2026.11 on.
        assert entity.temperature_unit == UnitOfTemperature.CELSIUS
        assert entity.current_temperature == 21.2
        assert entity.target_temperature == 22
