"""Tests for device triggers of the Homematic IP Local (HCU) integration."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.device_trigger import (
    _get_channel_subtype,
    async_attach_trigger,
    async_get_trigger_capabilities,
    async_get_triggers,
)


def test_get_channel_subtype():
    """Test channel subtype extraction from unique_id."""
    assert _get_channel_subtype("3014F711A000000000000001_1_button_event") == "1"
    assert (
        _get_channel_subtype("3014F711A000000000000002_channel2_doorbell_event")
        == "channel2"
    )


async def test_async_get_triggers_button_and_doorbell(hass: HomeAssistant):
    """Test getting triggers for button and doorbell event entities."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "DEV123")},
    )

    entity_reg = er.async_get(hass)
    entity_reg.async_get_or_create(
        domain=EVENT_DOMAIN,
        platform=DOMAIN,
        unique_id="DEV123_1_button_event",
        device_id=device.id,
    )
    entity_reg.async_get_or_create(
        domain=EVENT_DOMAIN,
        platform=DOMAIN,
        unique_id="DEV123_2_doorbell_event",
        device_id=device.id,
    )
    # Ignored: wrong domain
    entity_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="DEV123_3_sensor",
        device_id=device.id,
    )
    # Ignored: wrong platform
    entity_reg.async_get_or_create(
        domain=EVENT_DOMAIN,
        platform="other_integration",
        unique_id="DEV123_4_button_event",
        device_id=device.id,
    )
    # Ignored: event domain and DOMAIN platform but unrecognized suffix
    entity_reg.async_get_or_create(
        domain=EVENT_DOMAIN,
        platform=DOMAIN,
        unique_id="DEV123_5_unknown_event",
        device_id=device.id,
    )

    triggers = await async_get_triggers(hass, device.id)
    assert len(triggers) == 5

    expected_triggers = [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: "press_long",
            "subtype": "1",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: "press_long_start",
            "subtype": "1",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: "press_long_stop",
            "subtype": "1",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: "press_short",
            "subtype": "1",
        },
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device.id,
            CONF_TYPE: "ring",
            "subtype": "2",
        },
    ]

    for expected in expected_triggers:
        assert expected in triggers


async def test_async_attach_trigger_success(hass: HomeAssistant):
    """Test attaching and firing a device trigger successfully."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "SGTIN_DEV_1")},
    )

    action = AsyncMock()
    trigger_info = {
        "domain": DOMAIN,
        "platform_type": DeviceAutomationType.TRIGGER,
        "trigger_data": {},
        "variables": {},
    }
    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "press_short",
        "subtype": "1",
    }

    remove = await async_attach_trigger(hass, config, action, trigger_info)

    # Fire event with matching data
    hass.bus.async_fire(
        f"{DOMAIN}_event",
        {"device_id": "SGTIN_DEV_1", "subtype": "1", "type": "press_short"},
    )
    await hass.async_block_till_done()

    assert action.await_count == 1

    # Fire event with non-matching type
    hass.bus.async_fire(
        f"{DOMAIN}_event",
        {"device_id": "SGTIN_DEV_1", "subtype": "1", "type": "press_long"},
    )
    await hass.async_block_till_done()
    assert action.await_count == 1

    # Fire event with non-matching device_id
    hass.bus.async_fire(
        f"{DOMAIN}_event",
        {"device_id": "OTHER_DEV", "subtype": "1", "type": "press_short"},
    )
    await hass.async_block_till_done()
    assert action.await_count == 1

    # Fire event with non-matching subtype
    hass.bus.async_fire(
        f"{DOMAIN}_event",
        {"device_id": "SGTIN_DEV_1", "subtype": "2", "type": "press_short"},
    )
    await hass.async_block_till_done()
    assert action.await_count == 1

    # Unsubscribe
    remove()

    # Fire matching event again -> action should not be called
    hass.bus.async_fire(
        f"{DOMAIN}_event",
        {"device_id": "SGTIN_DEV_1", "subtype": "1", "type": "press_short"},
    )
    await hass.async_block_till_done()
    assert action.await_count == 1


async def test_async_attach_trigger_device_not_found(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Test attaching a trigger when device is not in device registry."""
    action = AsyncMock()
    trigger_info = {
        "domain": DOMAIN,
        "platform_type": DeviceAutomationType.TRIGGER,
        "trigger_data": {},
        "variables": {},
    }
    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: "nonexistent_dev_id",
        CONF_TYPE: "press_short",
        "subtype": "1",
    }

    with caplog.at_level(logging.ERROR):
        remove = await async_attach_trigger(hass, config, action, trigger_info)

    assert any(
        "Cannot attach trigger: HCU device ID not found for HA device nonexistent_dev_id"
        in r.message
        for r in caplog.records
        if r.levelname == "ERROR"
    )
    assert callable(remove)
    # Calling the returned dummy lambda should not raise
    remove()


async def test_async_attach_trigger_no_hcu_identifier(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Test attaching a trigger when device exists but has no DOMAIN identifier."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("other_domain", "SOME_OTHER_ID")},
    )

    action = AsyncMock()
    trigger_info = {
        "domain": DOMAIN,
        "platform_type": DeviceAutomationType.TRIGGER,
        "trigger_data": {},
        "variables": {},
    }
    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: device.id,
        CONF_TYPE: "press_short",
        "subtype": "1",
    }

    with caplog.at_level(logging.ERROR):
        remove = await async_attach_trigger(hass, config, action, trigger_info)

    assert any(
        f"Cannot attach trigger: HCU device ID not found for HA device {device.id}"
        in r.message
        for r in caplog.records
        if r.levelname == "ERROR"
    )
    assert callable(remove)
    remove()


async def test_async_get_trigger_capabilities(hass: HomeAssistant):
    """Test trigger capabilities returns empty dict."""
    config = {
        CONF_PLATFORM: "device",
        CONF_DOMAIN: DOMAIN,
        CONF_DEVICE_ID: "dev1",
        CONF_TYPE: "press_short",
        "subtype": "1",
    }
    caps = await async_get_trigger_capabilities(hass, config)
    assert caps == {}
