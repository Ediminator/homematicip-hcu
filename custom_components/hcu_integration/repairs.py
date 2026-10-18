# custom_components/hcu_integration/repairs.py
"""Repairs for the Homematic IP HCU integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class SetupFailedRepairFlow(RepairsFlow):
    """Repair flow for setup failures — lets the user jump straight to reauth."""

    def __init__(self, entry_id: str) -> None:
        self._entry_id = entry_id

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        if user_input is not None:
            self.hass.async_create_task(
                self.hass.config_entries.async_reload(self._entry_id)
            )
            return self.async_create_entry(data={})
        return self.async_show_form(step_id="confirm")


class InvalidPinNotificationFlow(RepairsFlow):
    """Repair flow that only informs about an invalid PIN — no input required."""

    def __init__(self, hass: HomeAssistant, entry_id: str, device_name: str) -> None:
        """Initialize the notification flow."""
        self._hass = hass
        self._entry_id = entry_id
        self._device_name = device_name

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
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

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> RepairsFlowResult:
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
    hass: HomeAssistant, issue_id: str, data: dict[str, Any] | None
) -> RepairsFlow:
    """Create the repair flow for a given issue."""
    safe_data = data or {}
    if issue_id.startswith("setup_failed_"):
        return SetupFailedRepairFlow(entry_id=str(safe_data.get("entry_id") or ""))
    if issue_id.startswith("pin_failed_"):
        return InvalidPinNotificationFlow(
            hass=hass,
            entry_id=str(safe_data.get("entry_id") or ""),
            device_name=str(safe_data.get("device_name") or ""),
        )
    if issue_id.startswith("access_authorization_"):
        return AccessAuthorizationRepairFlow(
            device_name=str(safe_data.get("device_name") or ""),
            channel_index=int(safe_data.get("channel_index") or 0),
        )
    raise ValueError(f"Unknown issue id: {issue_id}")
