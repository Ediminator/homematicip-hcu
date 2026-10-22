# custom_components/hcu_integration/siren.py
"""Siren platform for the Homematic IP HCU integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

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
    """Siren of an ALARM_SWITCHING group.

    The group switches all its members together: alarm sirens such as the
    HmIP-ASIR, and smoke detectors that the HCU uses as sirens. Tone, optical
    signal and the default duration are set on the group in the Homematic IP
    app; Home Assistant switches the group on or off, optionally for a
    duration (Connect API 6.8.5.10 and 6.8.5.11).
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
        # Restored on failure: an earlier command may still await its
        # confirmation (for example an accepted turn on before a failed stop).
        previous = (self._optimistic_on, self._attr_assumed_state)
        self._optimistic_on = on
        self._attr_assumed_state = True
        self.async_write_ha_state()
        try:
            if on and duration is not None:
                await self._client.async_set_switching_group_state_with_time(
                    group_id=self._group_id, on=True, on_time=float(duration)
                )
            else:
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
            self._optimistic_on, self._attr_assumed_state = previous
            self.async_write_ha_state()
            raise command_failed(self.entity_id, err) from err
