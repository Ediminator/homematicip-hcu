# custom_components/hcu_integration/repairs.py
"""Repairs for the Homematic IP HCU integration."""
import logging
import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_PIN

_LOGGER = logging.getLogger(__name__)

class InvalidPinNotificationFlow(RepairsFlow):
    """Repair flow that only informs about an invalid PIN — no input required."""

    def __init__(self, hass: HomeAssistant, entry_id: str, device_name: str) -> None:
        """Initialize the notification flow."""
        self._hass = hass
        self._entry_id = entry_id
        self._device_name = device_name

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Handle the first step."""
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> FlowResult:
        """Show the PIN failure notice and confirm."""
        if user_input is not None:
            await self._hass.config_entries.async_reload(self._entry_id)
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"device_name": self._device_name},
        )

class AccessAuthorizationRepairFlow(RepairsFlow):
    """Repair flow for CLIENT_ACCESS_DENIED on a device channel."""

    def __init__(self, device_name: str, channel_index: int) -> None:
        """Initialize the repair flow."""
        self._device_name = device_name
        self._channel_index = channel_index

    async def async_step_init(self, user_input=None) -> FlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(data={})
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                "device_name": self._device_name,
                "channel_index": str(self._channel_index),
            },
        )

async def async_create_fix_flow(
    hass: HomeAssistant, issue_id: str, data: dict | None
) -> RepairsFlow:
    """Create the repair flow for a given issue."""
    if issue_id.startswith("pin_failed_"):
        return InvalidPinNotificationFlow(
            hass=hass,
            entry_id=data["entry_id"],
            device_name=data["device_name"],
        )
    if issue_id.startswith("access_authorization_"):
        return AccessAuthorizationRepairFlow(
            device_name=data["device_name"],
            channel_index=data["channel_index"],
        )
    raise ValueError(f"Unknown issue id: {issue_id}")