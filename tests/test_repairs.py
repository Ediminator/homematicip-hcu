"""Tests for repair flows of the Homematic IP Local (HCU) integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.repairs import (
    AccessAuthorizationRepairFlow,
    InvalidPinNotificationFlow,
    SetupFailedRepairFlow,
    async_create_fix_flow,
)


async def test_setup_failed_repair_flow(hass: HomeAssistant):
    """Test SetupFailedRepairFlow shows confirm form and reloads entry on confirm."""
    flow = SetupFailedRepairFlow(entry_id="entry_test_1")
    flow.hass = hass
    flow.handler = DOMAIN

    # Step init delegates to confirm form
    result_init = await flow.async_step_init()
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "confirm"

    # Confirm without user_input shows form
    result_form = await flow.async_step_confirm(user_input=None)
    assert result_form["type"] is FlowResultType.FORM
    assert result_form["step_id"] == "confirm"

    # Confirm with user_input schedules entry reload
    hass.config_entries.async_reload = AsyncMock()
    result_create = await flow.async_step_confirm(user_input={})
    assert result_create["type"] is FlowResultType.CREATE_ENTRY
    assert result_create["data"] == {}

    await hass.async_block_till_done()
    hass.config_entries.async_reload.assert_called_once_with("entry_test_1")


async def test_invalid_pin_notification_flow(hass: HomeAssistant):
    """Test InvalidPinNotificationFlow shows placeholder and reloads entry on confirm."""
    flow = InvalidPinNotificationFlow(
        hass=hass, entry_id="entry_test_2", device_name="Front Lock"
    )
    flow.hass = hass
    flow.handler = DOMAIN

    # Step init delegates to confirm form
    result_init = await flow.async_step_init()
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "confirm"
    assert result_init["description_placeholders"] == {"device_name": "Front Lock"}

    # Confirm without user_input shows form
    result_form = await flow.async_step_confirm(user_input=None)
    assert result_form["type"] is FlowResultType.FORM
    assert result_form["description_placeholders"] == {"device_name": "Front Lock"}

    # Confirm with user_input reloads entry
    hass.config_entries.async_reload = AsyncMock()
    result_create = await flow.async_step_confirm(user_input={})
    assert result_create["type"] is FlowResultType.CREATE_ENTRY
    assert result_create["data"] == {}

    hass.config_entries.async_reload.assert_awaited_once_with("entry_test_2")


async def test_access_authorization_repair_flow(hass: HomeAssistant):
    """Test AccessAuthorizationRepairFlow displays device details and creates entry."""
    flow = AccessAuthorizationRepairFlow(device_name="Keypad", channel_index=1)
    flow.hass = hass
    flow.handler = DOMAIN

    # Step init delegates to confirm form
    result_init = await flow.async_step_init()
    assert result_init["type"] is FlowResultType.FORM
    assert result_init["step_id"] == "confirm"
    assert result_init["description_placeholders"] == {
        "device_name": "Keypad",
        "channel_index": "1",
    }

    # Confirm without user_input shows form
    result_form = await flow.async_step_confirm(user_input=None)
    assert result_form["type"] is FlowResultType.FORM
    assert result_form["description_placeholders"] == {
        "device_name": "Keypad",
        "channel_index": "1",
    }

    # Confirm with user_input completes flow
    result_create = await flow.async_step_confirm(user_input={})
    assert result_create["type"] is FlowResultType.CREATE_ENTRY
    assert result_create["data"] == {}


async def test_async_create_fix_flow(hass: HomeAssistant):
    """Test async_create_fix_flow creates appropriate flow for issue types."""
    flow_setup = await async_create_fix_flow(
        hass, "setup_failed_123", {"entry_id": "e_setup"}
    )
    assert isinstance(flow_setup, SetupFailedRepairFlow)
    assert flow_setup._entry_id == "e_setup"

    flow_pin = await async_create_fix_flow(
        hass, "pin_failed_456", {"entry_id": "e_pin", "device_name": "Door"}
    )
    assert isinstance(flow_pin, InvalidPinNotificationFlow)
    assert flow_pin._entry_id == "e_pin"
    assert flow_pin._device_name == "Door"

    flow_auth = await async_create_fix_flow(
        hass,
        "access_authorization_789",
        {"device_name": "Pad", "channel_index": 2},
    )
    assert isinstance(flow_auth, AccessAuthorizationRepairFlow)
    assert flow_auth._device_name == "Pad"
    assert flow_auth._channel_index == 2

    flow_auth_default = await async_create_fix_flow(
        hass,
        "access_authorization_789",
        {"device_name": "Pad"},
    )
    assert isinstance(flow_auth_default, AccessAuthorizationRepairFlow)
    assert flow_auth_default._device_name == "Pad"
    assert flow_auth_default._channel_index == 0

    with pytest.raises(ValueError, match="Unknown issue id: unknown_issue_xyz"):
        await async_create_fix_flow(hass, "unknown_issue_xyz", {})
