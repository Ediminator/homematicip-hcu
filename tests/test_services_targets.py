"""Tests for action defaults and device/area targets of the HCU actions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import (
    DOMAIN,
    SERVICE_ACTIVATE_PARTY_MODE,
    SERVICE_PLAY_SOUND,
    SERVICE_SWITCH_ON_WITH_TIME,
)
from custom_components.hcu_integration.light import HcuNotificationLight
from custom_components.hcu_integration.services import async_register_services


def _register(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    domain: str,
    unique_id: str,
    device_id: str | None = None,
    platform: str = DOMAIN,
) -> str:
    """Create an entity registry entry and return its entity_id."""
    return (
        er.async_get(hass)
        .async_get_or_create(
            domain,
            platform,
            unique_id,
            config_entry=entry if platform == DOMAIN else None,
            device_id=device_id,
        )
        .entity_id
    )


@pytest.fixture
def setup(hass: HomeAssistant) -> SimpleNamespace:
    """Set up a loaded entry with two devices, one of them in an area.

    The device "chime" (in the area "Hall") has a sound channel (a
    notification light) and a switch. Like every HCU switch, the switch
    accepts play_sound and timed on. The device "radiator" has a climate
    entity. An entity of another integration is also in the area.
    """
    entry = MockConfigEntry(domain=DOMAIN, data={})
    entry.add_to_hass(hass)

    dev_reg = dr.async_get(hass)
    area = ar.async_get(hass).async_create("Hall")
    chime = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "chime")}
    )
    dev_reg.async_update_device(chime.id, area_id=area.id)
    radiator = dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id, identifiers={(DOMAIN, "radiator")}
    )

    sound = MagicMock(spec=HcuNotificationLight)
    sound.entity_id = _register(hass, entry, "light", "sound", chime.id)
    sound.async_play_sound = AsyncMock()
    switch = SimpleNamespace(
        entity_id=_register(hass, entry, "switch", "switch", chime.id),
        async_play_sound=AsyncMock(),
        async_turn_on_with_time=AsyncMock(),
    )
    climate = SimpleNamespace(
        entity_id=_register(hass, entry, "climate", "climate", radiator.id),
        async_activate_party_mode=AsyncMock(),
    )
    other_id = _register(hass, entry, "light", "other", platform="other_platform")
    er.async_get(hass).async_update_entity(other_id, area_id=area.id)

    entry.runtime_data = SimpleNamespace(
        entities={
            Platform.LIGHT: [sound],
            Platform.SWITCH: [switch],
            Platform.CLIMATE: [climate],
        },
        # Used when the test harness unloads the entry.
        client=SimpleNamespace(disconnect=AsyncMock()),
        _ha_bridge=None,
    )
    entry.mock_state(hass, ConfigEntryState.LOADED)
    async_register_services(hass)

    return SimpleNamespace(
        area=area,
        chime=chime,
        radiator=radiator,
        sound=sound,
        switch=switch,
        climate=climate,
    )


async def test_play_sound_applies_documented_defaults(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """Volume and duration are optional and default to 1.0 and 5.0."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_SOUND,
        {"sound_file": "INTERNAL_SOUNDFILE"},
        target={"entity_id": setup.sound.entity_id},
        blocking=True,
    )

    setup.sound.async_play_sound.assert_awaited_once_with(
        sound_file="INTERNAL_SOUNDFILE", volume=1.0, duration=5.0
    )


async def test_play_sound_keeps_given_volume_and_duration(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """Values passed by the user are used instead of the defaults."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_SOUND,
        {"sound_file": "SOUNDFILE_001", "volume": 0.3, "duration": 2.5},
        target={"entity_id": setup.sound.entity_id},
        blocking=True,
    )

    setup.sound.async_play_sound.assert_awaited_once_with(
        sound_file="SOUNDFILE_001", volume=0.3, duration=2.5
    )


async def test_play_sound_device_target(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """A device target plays on the device's sound channel only.

    The device's switch is skipped, as Home Assistant does for entities
    that do not support an action they are targeted with through a device.
    """
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_SOUND,
        {"sound_file": "SOUNDFILE_002", "volume": 0.5, "duration": 1.0},
        target={"device_id": setup.chime.id},
        blocking=True,
    )

    setup.sound.async_play_sound.assert_awaited_once_with(
        sound_file="SOUNDFILE_002", volume=0.5, duration=1.0
    )
    setup.switch.async_play_sound.assert_not_awaited()


async def test_switch_on_with_time_area_target(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """An area target reaches the HCU switches in that area."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SWITCH_ON_WITH_TIME,
        {"on_time": 30},
        target={"area_id": setup.area.id},
        blocking=True,
    )

    setup.switch.async_turn_on_with_time.assert_awaited_once_with(on_time=30)


async def test_party_mode_device_target(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """A device target works for the climate action as well."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_ACTIVATE_PARTY_MODE,
        {"temperature": 21.5, "duration": 3600},
        target={"device_id": setup.radiator.id},
        blocking=True,
    )

    setup.climate.async_activate_party_mode.assert_awaited_once_with(
        temperature=21.5, end_time_str=None, duration=3600
    )


async def test_explicit_entity_and_device_target_combined(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """An entity listed explicitly is not called twice through its device."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SWITCH_ON_WITH_TIME,
        {"on_time": 10},
        target={"entity_id": setup.switch.entity_id, "device_id": setup.chime.id},
        blocking=True,
    )

    setup.switch.async_turn_on_with_time.assert_awaited_once_with(on_time=10)


async def test_explicit_switch_still_accepts_play_sound(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """A switch targeted directly still gets play_sound, as before."""
    await hass.services.async_call(
        DOMAIN,
        SERVICE_PLAY_SOUND,
        {"sound_file": "SOUNDFILE_003"},
        target={"entity_id": setup.switch.entity_id},
        blocking=True,
    )

    setup.switch.async_play_sound.assert_awaited_once_with(
        sound_file="SOUNDFILE_003", volume=1.0, duration=5.0
    )


async def test_target_without_matching_entities_raises(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """A target that resolves to no usable entity keeps the translated error."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_SOUND,
            {"sound_file": "SOUNDFILE_001"},
            target={"device_id": setup.radiator.id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "no_entity_specified"
    assert exc_info.value.translation_placeholders == {"service": SERVICE_PLAY_SOUND}
    setup.sound.async_play_sound.assert_not_awaited()


async def test_explicit_incompatible_entity_still_reported(
    hass: HomeAssistant, setup: SimpleNamespace
) -> None:
    """An explicitly targeted entity without sound support is still an error."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_PLAY_SOUND,
            {"sound_file": "SOUNDFILE_001"},
            target={"entity_id": setup.climate.entity_id},
            blocking=True,
        )

    assert exc_info.value.translation_key == "entities_no_sound"
