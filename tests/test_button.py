"""Unit tests for the HCU button platform."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.button import (
    HcuAcknowledgeSafetyAlarmButton,
    HcuDeviceIdentifyButton,
    HcuDoorImpulseButton,
    HcuDoorPullLatchButton,
    HcuDoorUnlatchButton,
    HcuResetEnergyButton,
    HcuResetWaterVolume,
    async_setup_entry,
)
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    CONF_APP_CLIENT_ID,
    CONF_AUTH_TYPE,
    CONF_DEVICE_PINS,
    CONF_PLUGIN_CLIENT_ID,
    DOMAIN,
    LOCK_STATE_OPEN,
)


@pytest.mark.asyncio
async def test_button_async_setup_entry(hass: HomeAssistant) -> None:
    """Test async_setup_entry forwards entities when present."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)

    mock_entity = MagicMock()
    mock_coordinator = MagicMock()
    mock_coordinator.entities = {Platform.BUTTON: [mock_entity]}
    entry.runtime_data = mock_coordinator

    added = []

    def mock_add_entities(entities: list) -> None:
        added.extend(entities)

    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == [mock_entity]

    # Empty list
    mock_coordinator.entities = {}
    added.clear()
    await async_setup_entry(hass, entry, mock_add_entities)
    assert added == []


@pytest.mark.asyncio
async def test_reset_energy_button(caplog: pytest.LogCaptureFixture) -> None:
    """Test HcuResetEnergyButton press and error handling."""
    device_data = {
        "id": "dev-psm-1",
        "label": "Coffee Plug",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "SWITCH_MEASURING",
                "label": "Coffee Channel",
            },
        },
    }
    dev_id = "dev-psm-1"
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_reset_energy_counter = AsyncMock()

    entity = HcuResetEnergyButton(coordinator, client, device_data, "1")
    assert entity.unique_id == "dev-psm-1_1_reset_energy_counter"
    assert entity.icon == "mdi:reload"
    assert entity.has_entity_name is True
    assert entity.name == "Coffee Channel Reset Energy Counter"

    # Press success
    await entity.async_press()
    client.async_reset_energy_counter.assert_awaited_once_with("dev-psm-1", 1)

    # Press HcuApiError
    client.async_reset_energy_counter.side_effect = HcuApiError("Reset failed")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error resetting energy counter for" in caplog.text

    # Press ConnectionError
    caplog.clear()
    client.async_reset_energy_counter.side_effect = ConnectionError("Net error")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error resetting energy counter for" in caplog.text


@pytest.mark.asyncio
async def test_reset_water_volume_button(caplog: pytest.LogCaptureFixture) -> None:
    """Test HcuResetWaterVolume press and error handling."""
    device_data = {
        "id": "dev-water-1",
        "label": "Water Meter",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "WATER_SENSOR",
                "label": "Water Channel",
            },
        },
    }
    dev_id = "dev-water-1"
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_reset_water_volume = AsyncMock()

    entity = HcuResetWaterVolume(coordinator, client, device_data, "1")
    assert entity.unique_id == "dev-water-1_1_reset_water_volume"
    assert entity.icon == "mdi:reload"
    assert entity.has_entity_name is True
    assert entity.name == "Water Channel Reset Water Volume"

    # Press success
    await entity.async_press()
    client.async_reset_water_volume.assert_awaited_once_with("dev-water-1", 1)

    # Press HcuApiError
    client.async_reset_water_volume.side_effect = HcuApiError("Reset failed")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error resetting water volume for" in caplog.text

    # Press ConnectionError
    caplog.clear()
    client.async_reset_water_volume.side_effect = ConnectionError("Net down")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error resetting water volume for" in caplog.text


@pytest.mark.asyncio
async def test_door_impulse_button(caplog: pytest.LogCaptureFixture) -> None:
    """Test HcuDoorImpulseButton press and error handling."""
    device_data = {
        "id": "dev-wgc-1",
        "label": "Garage Door",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOOR_CHANNEL",
                "label": "Garage",
            },
        },
    }
    dev_id = "dev-wgc-1"
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_send_door_impulse = AsyncMock()

    entity = HcuDoorImpulseButton(coordinator, client, device_data, "1")
    assert entity.unique_id == "dev-wgc-1_1_impulse"
    assert entity.icon == "mdi:garage"
    assert entity.has_entity_name is True
    assert entity.name == "Garage Impulse"

    # Press success
    await entity.async_press()
    client.async_send_door_impulse.assert_awaited_once_with("dev-wgc-1", 1)

    # Press HcuApiError
    client.async_send_door_impulse.side_effect = HcuApiError("Impulse failed")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error triggering door impulse for" in caplog.text

    # Press ConnectionError
    caplog.clear()
    client.async_send_door_impulse.side_effect = ConnectionError("Net failure")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Connection failed while triggering door impulse for" in caplog.text


@pytest.mark.asyncio
async def test_device_identify_button(caplog: pytest.LogCaptureFixture) -> None:
    """Test HcuDeviceIdentifyButton press and error handling."""
    device_data = {
        "id": "dev-identify-1",
        "label": "Siren Device",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "SIREN_CHANNEL"},
        },
    }
    dev_id = "dev-identify-1"
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.async_send_identify = AsyncMock()

    entity = HcuDeviceIdentifyButton(coordinator, client, device_data, "1")
    assert entity.unique_id == "dev-identify-1_1_identify"
    assert entity.translation_key == "hcu_device_identify"
    assert entity.icon == "mdi:crosshairs-gps"
    assert entity.device_class is None

    # Press success
    await entity.async_press()
    client.async_send_identify.assert_awaited_once_with("dev-identify-1", 1)

    # Press HcuApiError
    client.async_send_identify.side_effect = HcuApiError("Blink failed")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error triggering identify for" in caplog.text

    # Press ConnectionError
    caplog.clear()
    client.async_send_identify.side_effect = ConnectionError("Net failure")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Connection failed while triggering identify for" in caplog.text


@pytest.mark.asyncio
async def test_acknowledge_safety_alarm_button() -> None:
    """Test HcuAcknowledgeSafetyAlarmButton press and HomeAssistantError handling."""
    coordinator = MagicMock()
    coordinator.config_entry = MagicMock()
    coordinator.data = {}

    client = MagicMock()
    client.hcu_device_id = "hcu-central"
    client.async_acknowledge_safety_alarm = AsyncMock()

    entity = HcuAcknowledgeSafetyAlarmButton(coordinator, client)
    assert entity.unique_id == "hcu-central_acknowledge_safety_alarm"
    assert entity.translation_key == "hcu_acknowledge_safety_alarm"

    # Press success
    await entity.async_press()
    client.async_acknowledge_safety_alarm.assert_awaited_once()

    # Press HcuApiError -> raises HomeAssistantError
    client.async_acknowledge_safety_alarm.side_effect = HcuApiError("Safety ack failed")
    with pytest.raises(
        HomeAssistantError, match="Could not acknowledge the safety alarm"
    ):
        await entity.async_press()

    # Press ConnectionError -> raises HomeAssistantError
    client.async_acknowledge_safety_alarm.side_effect = ConnectionError("Offline")
    with pytest.raises(
        HomeAssistantError, match="Could not acknowledge the safety alarm"
    ):
        await entity.async_press()


@pytest.mark.asyncio
async def test_door_pull_latch_button(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test HcuDoorPullLatchButton full lifecycle, authorization lookup, and error paths."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTH_TYPE: AUTH_TYPE_APP, CONF_APP_CLIENT_ID: "client-ha-1"},
        options={CONF_DEVICE_PINS: {"dev-fdc-1": "1234"}},
    )
    entry.add_to_hass(hass)

    device_data = {
        "id": "dev-fdc-1",
        "label": "Front Gate Opener",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOOR_CHANNEL",
                "label": "Gate",
                "groupIndex": 10,
            },
            "2": {
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 10,
                "groups": ["group-auth-1"],
            },
        },
    }
    dev_id = "dev-fdc-1"
    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.get_group_by_id = MagicMock(
        return_value={
            "type": "ACCESS_AUTHORIZATION_PROFILE",
            "authorizationPinAssigned": True,
            "clientIds": ["client-ha-1"],
            "label": "Gate Access",
        }
    )
    client.async_pull_latch = AsyncMock()

    entity = HcuDoorPullLatchButton(coordinator, client, device_data, "1")
    entity.hass = hass
    entity.platform_data = MagicMock(
        platform_name="hcu_integration", domain="button", platform_translations={}
    )

    assert entity.unique_id == "dev-fdc-1_1_pull_latch"
    assert entity.translation_key == "hcu_pull_latch"
    assert entity.has_entity_name is True
    assert entity.name == "Gate Pull Latch"

    # Add to hass resolves authorization channel and hooks coordinator listener
    await entity.async_added_to_hass()
    coordinator.async_add_listener.assert_called()
    assert entity._authorization_channel_index == 2
    assert entity._authorization_profile_label == "Gate Access"

    # Verify existing access_authorization issue is deleted on successful press
    issue_reg = ir.async_get(hass)
    issue_reg.async_get_or_create(
        DOMAIN,
        "access_authorization_dev-fdc-1_1",
        issue_domain=DOMAIN,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="access_authorization",
    )
    assert (
        issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-fdc-1_1")
        is not None
    )

    # Press success
    await entity.async_press()
    client.async_pull_latch.assert_awaited_once_with("dev-fdc-1", 2, pin="1234")
    assert issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-fdc-1_1") is None

    # Error 1: HcuApiError with invalid PIN creates issue
    client.async_pull_latch.side_effect = HcuApiError("INVALID_AUTHORIZATION_PIN")
    issue_reg = ir.async_get(hass)
    await entity.async_press()
    issue = issue_reg.async_get_issue(DOMAIN, "pin_failed_dev-fdc-1")
    assert issue is not None

    # Error 2: HcuApiError unhandled/generic logs error
    caplog.clear()
    client.async_pull_latch.side_effect = HcuApiError("SOME_HARDWARE_FAILURE_XYZ")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error triggering pull latch for" in caplog.text

    # Error 3: ConnectionError logs error
    caplog.clear()
    client.async_pull_latch.side_effect = ConnectionError("Disconnected")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Connection failed while triggering pull latch for" in caplog.text

    # Error 4: No client_id in config_entry
    caplog.clear()
    hass.config_entries.async_update_entry(entry, data={CONF_AUTH_TYPE: AUTH_TYPE_APP})
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "No clientId found for this integration" in caplog.text

    # Error 5: No authorization channel index found
    hass.config_entries.async_update_entry(
        entry, data={CONF_AUTH_TYPE: AUTH_TYPE_APP, CONF_APP_CLIENT_ID: "client-ha-1"}
    )
    entity._authorization_channel_index = None
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "not authorized to control device" in caplog.text
    auth_issue = issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-fdc-1_1")
    assert auth_issue is not None


@pytest.mark.asyncio
async def test_door_unlatch_button(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test HcuDoorUnlatchButton lifecycle, authorization, and lock state setting."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_AUTH_TYPE: "plugin", CONF_PLUGIN_CLIENT_ID: "plugin-ha-1"},
        options={CONF_DEVICE_PINS: {"dev-dld-1": "4321"}},
    )
    entry.add_to_hass(hass)

    device_data = {
        "id": "dev-dld-1",
        "label": "Front Door Lock",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {
                "functionalChannelType": "DOOR_LOCK_CHANNEL",
                "label": "Lock Channel",
                "groupIndex": 5,
            },
            "2": {
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 5,
                "groups": ["group-auth-2"],
            },
        },
    }
    dev_id = "dev-dld-1"
    coordinator = MagicMock()
    coordinator.config_entry = entry
    coordinator.data = {dev_id: device_data}

    client = MagicMock()
    client.get_device_by_address = MagicMock(return_value=device_data)
    client.get_group_by_id = MagicMock(
        return_value={
            "type": "ACCESS_AUTHORIZATION_PROFILE",
            "authorizationPinAssigned": True,
            "clientIds": ["plugin-ha-1"],
            "label": "Front Door Access",
        }
    )
    client.async_set_lock_state = AsyncMock()

    entity = HcuDoorUnlatchButton(coordinator, client, device_data, "1")
    entity.hass = hass
    entity.platform_data = MagicMock(
        platform_name="hcu_integration", domain="button", platform_translations={}
    )

    assert entity.unique_id == "dev-dld-1_1_unlatch"
    assert entity.icon == "mdi:door-open"
    assert entity.has_entity_name is True
    assert entity.name == "Lock Channel Unlatch"

    # Add to hass hooks coordinator listener
    await entity.async_added_to_hass()
    coordinator.async_add_listener.assert_called()
    assert entity._authorization_channel_index == 2

    # Verify existing access_authorization issue is deleted on successful press
    issue_reg = ir.async_get(hass)
    issue_reg.async_get_or_create(
        DOMAIN,
        "access_authorization_dev-dld-1_1",
        issue_domain=DOMAIN,
        is_fixable=False,
        is_persistent=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="access_authorization",
    )
    assert (
        issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-dld-1_1")
        is not None
    )

    # Press success
    await entity.async_press()
    client.async_set_lock_state.assert_awaited_once_with(
        "dev-dld-1", 1, state=LOCK_STATE_OPEN, pin="4321"
    )
    assert issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-dld-1_1") is None

    # Error 1: HcuApiError with invalid pin
    client.async_set_lock_state.side_effect = HcuApiError("INVALID_PIN")
    issue_reg = ir.async_get(hass)
    await entity.async_press()
    assert issue_reg.async_get_issue(DOMAIN, "pin_failed_dev-dld-1") is not None

    # Error 2: HcuApiError generic
    caplog.clear()
    client.async_set_lock_state.side_effect = HcuApiError("SOME_HARDWARE_FAILURE_XYZ")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Error triggering unlatch for" in caplog.text

    # Error 3: ConnectionError
    caplog.clear()
    client.async_set_lock_state.side_effect = ConnectionError("Net failure")
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "Connection failed while triggering unlatch for" in caplog.text

    # Error 4: No client_id
    caplog.clear()
    hass.config_entries.async_update_entry(entry, data={CONF_AUTH_TYPE: "plugin"})
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "No clientId found for this integration" in caplog.text

    # Error 5: No authorization channel
    hass.config_entries.async_update_entry(
        entry, data={CONF_AUTH_TYPE: "plugin", CONF_PLUGIN_CLIENT_ID: "plugin-ha-1"}
    )
    entity._authorization_channel_index = None
    with caplog.at_level(logging.ERROR):
        await entity.async_press()
    assert "not authorized to control device" in caplog.text
    assert (
        issue_reg.async_get_issue(DOMAIN, "access_authorization_dev-dld-1_1")
        is not None
    )
