# custom_components/hcu_integration/siren.py
"""Siren platform for the Homematic IP HCU integration."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from .api import HcuApiClient, HcuApiError
from .entity import HcuAlarmSwitchingGroupEntity
from .util import command_failed

if TYPE_CHECKING:
    from .coordinator import HcuConfigEntry, HcuCoordinator

_LOGGER = logging.getLogger(__name__)


# State is pushed by the HCU, so there is no polling to limit, and actions may
# run in parallel.
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HcuConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the siren platform from a config entry."""
    coordinator = config_entry.runtime_data
    coordinator.async_register_platform(Platform.SIREN, async_add_entities)
    if entities := coordinator.entities.get(Platform.SIREN):
        async_add_entities(entities)


class HcuAlarmSiren(HcuAlarmSwitchingGroupEntity, SirenEntity):
    """Siren of an ALARM_SWITCHING group with at least one alarm siren.

    Switching the group on sounds its alarm sirens (such as the HmIP-ASIR).
    Smoke detectors in the group do not react to it: the HCU only sounds them
    during a real intrusion alarm. Tone, optical signal and the maximum
    duration are set on the group in the Homematic IP app (Connect API
    6.8.5.10). The HCU ignores onTime for alarm groups, so a duration is
    enforced by turning the group off again from Home Assistant.
    """

    PLATFORM = Platform.SIREN
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.DURATION
    )

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the siren of an ALARM_SWITCHING group."""
        super().__init__(coordinator, client, group_data)
        self._attr_unique_id = f"{self._group_id}_siren"
        # Optimistic state while a command waits for the HCU's confirmation.
        self._optimistic_on: bool | None = None
        # Counts group updates, so a failed command can tell whether the HCU
        # reported a newer state while it was running.
        self._group_updates = 0
        # Serializes commands on this siren while allowing other sirens to run
        # in parallel (PARALLEL_UPDATES = 0).
        self._switch_lock = asyncio.Lock()
        # Turns the siren off again after a requested duration.
        self._auto_off_unsub: CALLBACK_TYPE | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Count updates of this group before applying them."""
        if self._group_id in self.coordinator.data:
            self._group_updates += 1
            self._optimistic_on = None
            if self._group.get("on") is not True:
                # Already off (turned off elsewhere or by the HCU's own limit).
                self._cancel_auto_off()
        super()._handle_coordinator_update()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending automatic turn off."""
        self._cancel_auto_off()
        await super().async_will_remove_from_hass()

    def _cancel_auto_off(self) -> None:
        if self._auto_off_unsub is not None:
            self._auto_off_unsub()
            self._auto_off_unsub = None

    @callback
    def _async_auto_off(self, _now: Any) -> None:
        """Turn the siren off once the requested duration has passed."""
        self._auto_off_unsub = None
        self.hass.async_create_task(
            self._async_auto_off_switch(), f"{self.entity_id} automatic turn off"
        )

    async def _async_auto_off_switch(self) -> None:
        try:
            await self._async_switch(False, None)
        except HomeAssistantError:
            # _async_switch has already logged the HCU error.
            _LOGGER.warning(
                "Could not turn off siren %s after its duration; it stops at "
                "the duration set on the group in the Homematic IP app",
                self.entity_id,
            )

    @property
    def is_on(self) -> bool:
        """Return True while the group's alarm signal is on."""
        if self._attr_assumed_state and self._optimistic_on is not None:
            return self._optimistic_on
        return self._group.get("on") is True

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on, for the given duration if there is one."""
        await self._async_switch(True, kwargs.get(ATTR_DURATION))

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        await self._async_switch(False, None)

    async def _async_switch(self, on: bool, duration: float | None) -> None:
        async with self._switch_lock:
            # Restored on failure, unless the HCU reported the group meanwhile:
            # an earlier accepted command may still await its confirmation (for
            # example a turn on before a failed stop).
            previous = (self._optimistic_on, self._attr_assumed_state)
            updates_before = self._group_updates
            self._optimistic_on = on
            self._attr_assumed_state = True
            self._cancel_auto_off()
            self.async_write_ha_state()
            try:
                await self._client.async_set_alarm_switching_group_state(
                    group_id=self._group_id, on=on
                )
            except (HcuApiError, ConnectionError) as err:
                _LOGGER.error(
                    "Failed to switch siren %s %s: %s",
                    self._group_id,
                    "on" if on else "off",
                    err,
                )
                if self._group_updates == updates_before:
                    self._optimistic_on, self._attr_assumed_state = previous
                else:
                    # The HCU reported the group meanwhile; its state is newer.
                    self._optimistic_on, self._attr_assumed_state = None, False
                self.async_write_ha_state()
                raise command_failed(self.entity_id, err) from err
            if on and duration is not None:
                self._auto_off_unsub = async_call_later(
                    self.hass, float(duration), self._async_auto_off
                )
