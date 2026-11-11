# custom_components/hcu_integration/siren.py
"""Siren platform for the Homematic IP HCU integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.siren import (
    ATTR_DURATION,
    ATTR_TONE,
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
from homeassistant.util import dt as dt_util

from .api import HcuApiClient, HcuApiError
from .const import (
    ALARM_ACOUSTIC_SIGNAL_OFF,
    ALARM_ACOUSTIC_SIGNALS,
    ALARM_OPTICAL_SIGNAL_OFF,
    SIREN_DEFAULT_DURATION,
)
from .entity import HcuAlarmSwitchingGroupEntity
from .util import command_failed

if TYPE_CHECKING:
    from .coordinator import HcuConfigEntry, HcuCoordinator

_LOGGER = logging.getLogger(__name__)


# State is pushed by the HCU, so there is no polling to limit, and actions may
# run in parallel.
PARALLEL_UPDATES = 0

# Tone used when neither the action nor the alarm group names a valid one.
_FALLBACK_TONE = "frequency_rising"

# Waits before each further attempt when the automatic stop fails, in seconds.
# They cover a short HCU outage or restart (about four minutes in total).
_STOP_RETRY_DELAYS: tuple[float, ...] = (5.0, 15.0, 30.0, 60.0, 60.0, 60.0)


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


@dataclass
class HcuSirenStoredData(ExtraStoredData):
    """When a running signal has to be stopped, kept over restarts and reloads."""

    stop_at: datetime

    def as_dict(self) -> dict[str, Any]:
        """Return the stop time as an ISO string."""
        return {"stop_at": self.stop_at.isoformat()}


class HcuAlarmSiren(RestoreEntity, HcuAlarmSwitchingGroupEntity, SirenEntity):
    """Siren of an ALARM_SWITCHING group with at least one alarm siren.

    The HCU sounds alarm sirens such as the HmIP-ASIR only through the test
    signal requests (/hmip/group/switching/alarm/testSignalAcoustic and
    testSignalOptical), the same as the test in the Homematic IP app.
    Switching the group with setState is accepted but stays silent (#516).
    The HCU rejects the test signal requests from plugins (NOT_ALLOWED), so
    this entity only exists in App User and DualBridge mode.

    The HCU reports no state for a test signal. The entity therefore shows
    "on" from an accepted turn on until it is turned off or the duration has
    passed; then it sends the stop signal. The stop time is stored, so a
    restart or reload of Home Assistant does not leave the signal playing:
    the new entity stops it at the same time, or at once if that time has
    passed. A failed automatic stop is tried again a few times.

    The entity also shows "on" while the HCU reports the group as on, for
    example during a real intrusion alarm. Smoke detectors in the group do
    not react to test signals; the HCU only sounds them during a real
    intrusion alarm.
    """

    PLATFORM = Platform.SIREN
    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
        | SirenEntityFeature.TONES
        | SirenEntityFeature.DURATION
    )
    _attr_available_tones = list(ALARM_ACOUSTIC_SIGNALS)

    def __init__(
        self,
        coordinator: HcuCoordinator,
        client: HcuApiClient,
        group_data: dict[str, Any],
    ) -> None:
        """Initialize the siren of an ALARM_SWITCHING group."""
        super().__init__(coordinator, client, group_data)
        self._attr_unique_id = f"{self._group_id}_siren"
        # True from an accepted turn on until the signal is stopped.
        self._signal_on = False
        # When the running signal has to be stopped (UTC).
        self._stop_at: datetime | None = None
        # Serializes commands on this siren while allowing other sirens to run
        # in parallel (PARALLEL_UPDATES = 0).
        self._switch_lock = asyncio.Lock()
        # Stops the signal again after the duration.
        self._auto_off_unsub: CALLBACK_TYPE | None = None
        # Counts commands the HCU accepted. A timed stop only runs if no newer
        # command was accepted after it was scheduled.
        self._accepted_commands = 0
        # Set when the entity is removed, so a stop that is failing right then
        # does not schedule another attempt on the removed entity.
        self._removed = False

    async def async_added_to_hass(self) -> None:
        """Take over a signal that was playing before a restart or reload."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_extra_data()) is None:
            return
        raw = last.as_dict().get("stop_at")
        stop_at = dt_util.parse_datetime(raw) if isinstance(raw, str) else None
        if stop_at is None:
            return
        # Home Assistant drops its timers on a restart or reload, and the HCU
        # reports no state for a test signal. The signal may still be playing,
        # so it is shown as on and stopped at its stop time, or at once if
        # that time has passed.
        self._signal_on = True
        self._stop_at = dt_util.as_utc(stop_at)
        self._schedule_stop(
            max(0.0, (self._stop_at - dt_util.utcnow()).total_seconds())
        )

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending automatic stop; the stop time stays stored."""
        self._removed = True
        self._cancel_auto_off()
        await super().async_will_remove_from_hass()

    @property
    def extra_restore_state_data(self) -> HcuSirenStoredData | None:
        """Return when the running signal has to be stopped, if one is running."""
        if not self._signal_on or self._stop_at is None:
            return None
        return HcuSirenStoredData(self._stop_at)

    def _cancel_auto_off(self) -> None:
        if self._auto_off_unsub is not None:
            self._auto_off_unsub()
            self._auto_off_unsub = None

    def _schedule_stop(self, delay: float, attempt: int = 0) -> None:
        """Stop the signal after delay seconds, unless a newer command is accepted."""
        self._cancel_auto_off()
        self._auto_off_unsub = async_call_later(
            self.hass,
            delay,
            partial(self._async_auto_off, self._accepted_commands, attempt),
        )

    @property
    def assumed_state(self) -> bool:
        """Return True: the HCU reports no state for a test signal.

        Home Assistant then offers both turn on and turn off.
        """
        return True

    @property
    def is_on(self) -> bool:
        """Return True while a test signal runs or the HCU reports the group on."""
        return self._signal_on or self._group.get("on") is True

    def _configured_tone(self) -> str:
        """Return the acoustic signal set on the group in the Homematic IP app."""
        configured = str(self._group.get("signalAcoustic") or "").lower()
        return configured if configured in ALARM_ACOUSTIC_SIGNALS else _FALLBACK_TONE

    def _configured_optical_signal(self) -> str | None:
        """Return the optical signal set on the group, or None if there is none."""
        configured = self._group.get("signalOptical")
        if not configured or configured == ALARM_OPTICAL_SIGNAL_OFF:
            return None
        return str(configured)

    def _configured_duration(self) -> float:
        """Return the alarm duration set on the group, in seconds."""
        on_time = self._group.get("onTime")
        if isinstance(on_time, (int, float)) and on_time > 0:
            return float(on_time)
        return SIREN_DEFAULT_DURATION

    @callback
    def _async_auto_off(self, scheduled_after: int, attempt: int, _now: Any) -> None:
        """Stop the signal once the duration has passed."""
        self._auto_off_unsub = None
        self.hass.async_create_task(
            self._async_auto_off_stop(scheduled_after, attempt),
            f"{self.entity_id} automatic stop",
        )

    async def _async_auto_off_stop(self, scheduled_after: int, attempt: int) -> None:
        try:
            await self._async_stop(only_after=scheduled_after)
        except HomeAssistantError:
            # _async_stop has already logged the HCU error. It held the lock
            # until it failed, so no newer command was accepted meanwhile; a
            # command that waited for the lock replaces the retry scheduled
            # here once it is accepted.
            if self._removed:
                # The entity is gone; its successor takes over the stored stop
                # time.
                return
            if attempt >= len(_STOP_RETRY_DELAYS):
                _LOGGER.error(
                    "Could not stop siren %s after its duration, also not in "
                    "%d further attempts. Turn it off again, or stop the "
                    "signal in the Homematic IP app",
                    self.entity_id,
                    len(_STOP_RETRY_DELAYS),
                )
                return
            delay = _STOP_RETRY_DELAYS[attempt]
            _LOGGER.warning(
                "Could not stop siren %s after its duration; trying again in "
                "%d seconds",
                self.entity_id,
                delay,
            )
            self._schedule_stop(delay, attempt + 1)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Play the alarm signal, with the group's tone unless one is given."""
        tone = kwargs.get(ATTR_TONE) or self._configured_tone()
        duration = kwargs.get(ATTR_DURATION)
        async with self._switch_lock:
            optical = self._configured_optical_signal()
            try:
                await self._client.async_test_alarm_signal_acoustic(
                    self._group_id, str(tone).upper()
                )
            except (HcuApiError, ConnectionError) as err:
                _LOGGER.error("Failed to turn on siren %s: %s", self._group_id, err)
                raise command_failed(self.entity_id, err) from err
            # The siren sounds from here on, so it is shown as on and gets its
            # timed stop even if the optical signal fails below.
            delay = (
                float(duration) if duration is not None else self._configured_duration()
            )
            self._accepted_commands += 1
            self._signal_on = True
            self._stop_at = dt_util.utcnow() + timedelta(seconds=delay)
            self._schedule_stop(delay)
            self.async_write_ha_state()
            if optical is None:
                return
            try:
                await self._client.async_test_alarm_signal_optical(
                    self._group_id, optical
                )
            except (HcuApiError, ConnectionError) as err:
                _LOGGER.error(
                    "Siren %s plays its acoustic signal, but the optical signal "
                    "failed: %s",
                    self._group_id,
                    err,
                )
                raise command_failed(self.entity_id, err) from err

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the acoustic and optical signal."""
        await self._async_stop()

    async def _async_stop(self, only_after: int | None = None) -> None:
        async with self._switch_lock:
            if only_after is not None and self._accepted_commands != only_after:
                # A newer command was accepted while this timed stop waited.
                return
            try:
                await self._client.async_test_alarm_signal_acoustic(
                    self._group_id, ALARM_ACOUSTIC_SIGNAL_OFF
                )
                if self._configured_optical_signal() is not None:
                    await self._client.async_test_alarm_signal_optical(
                        self._group_id, ALARM_OPTICAL_SIGNAL_OFF
                    )
            except (HcuApiError, ConnectionError) as err:
                _LOGGER.error("Failed to turn off siren %s: %s", self._group_id, err)
                raise command_failed(self.entity_id, err) from err
            self._accepted_commands += 1
            self._signal_on = False
            self._stop_at = None
            self._cancel_auto_off()
            if not self._removed:
                self.async_write_ha_state()
