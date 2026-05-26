# custom_components/hcu_integration/alarm_control_panel.py
"""Alarm control panel platform for the Homematic IP HCU integration."""
import logging
from typing import TYPE_CHECKING

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .api import HcuApiClient, HcuApiError
from .entity import HcuHomeBaseEntity

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the alarm control panel platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.ALARM_CONTROL_PANEL):
        async_add_entities(entities)


class HcuAlarmControlPanel(HcuHomeBaseEntity, AlarmControlPanelEntity):
    """Representation of the HCU Security System."""

    PLATFORM = Platform.ALARM_CONTROL_PANEL
    _attr_supported_features = (
        AlarmControlPanelEntityFeature.ARM_HOME | AlarmControlPanelEntityFeature.ARM_AWAY
    )
    _attr_code_arm_required = False
    _enable_turn_on_off_backwards_compatibility = False
    _attr_has_entity_name = False

    def __init__(self, coordinator: "HcuCoordinator", client: HcuApiClient):
        super().__init__(coordinator, client)
        self._attr_name = self._apply_prefix("Homematic IP Alarm")
        self._attr_unique_id = f"{self._hcu_device_id}_security"
        self._attr_alarm_state: AlarmControlPanelState | None = None

    @property
    def _security_home(self) -> dict:
        for home in self._home.get("functionalHomes", {}).values():
            if home.get("solution") == "SECURITY_AND_ALARM":
                return home
        return {}

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self._home_uuid in self.coordinator.data:
            # Clear any optimistically set alarm state
            self._attr_alarm_state = None
            self.async_write_ha_state()
        
        # Call super *after* clearing optimistic state
        super()._handle_coordinator_update()

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        if self._attr_assumed_state:
            return self._attr_alarm_state

        sec_home = self._security_home
        if not sec_home:
            return None

        if sec_home.get("intrusionAlarmActive") or sec_home.get("safetyAlarmActive"):
            return AlarmControlPanelState.TRIGGERED

        if sec_home.get("activationInProgress"):
            return AlarmControlPanelState.ARMING

        zones = sec_home.get("securityZones", {})

        if not isinstance(zones, dict):
            _LOGGER.warning(
                "Security zones data is not in the expected format: %s", zones
            )
            return AlarmControlPanelState.DISARMED

        internal_group_id = zones.get("INTERNAL")
        external_group_id = zones.get("EXTERNAL")

        internal_group = (
            self._client.get_group_by_id(internal_group_id) if internal_group_id else {}
        )
        external_group = (
            self._client.get_group_by_id(external_group_id) if external_group_id else {}
        )

        internal_active = internal_group.get("active", False)
        external_active = external_group.get("active", False)

        if internal_active and external_active:
            return AlarmControlPanelState.ARMED_AWAY
        if external_active:
            return AlarmControlPanelState.ARMED_HOME
        return AlarmControlPanelState.DISARMED

    async def _async_set_alarm_state(
        self, new_state: AlarmControlPanelState, payload: dict
    ) -> None:
        if new_state in (AlarmControlPanelState.ARMED_HOME, AlarmControlPanelState.ARMED_AWAY):
            self._attr_alarm_state = AlarmControlPanelState.ARMING
        else:
            self._attr_alarm_state = new_state

        self._attr_assumed_state = True
        self.async_write_ha_state()

        try:
            await self._client.async_set_zones_activation(payload=payload)
        except (HcuApiError, ConnectionError) as err:
            _LOGGER.error("Failed to set alarm state for %s: %s", self.name, err)
            self._attr_alarm_state = None
            self._attr_assumed_state = False
            self.async_write_ha_state()

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Send disarm command."""
        await self._async_set_alarm_state(
            AlarmControlPanelState.DISARMED,
            {"zonesActivation": {"INTERNAL": False, "EXTERNAL": False}},
        )

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Send arm home command."""
        await self._async_set_alarm_state(
            AlarmControlPanelState.ARMED_HOME,
            {"zonesActivation": {"INTERNAL": False, "EXTERNAL": True}},
        )

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Send arm away command."""
        await self._async_set_alarm_state(
            AlarmControlPanelState.ARMED_AWAY,
            {"zonesActivation": {"INTERNAL": True, "EXTERNAL": True}},
        )
