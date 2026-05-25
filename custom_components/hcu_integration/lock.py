# custom_components/hcu_integration/lock.py
"""Lock platform for the Homematic IP HCU integration."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_PIN,
    DOMAIN,
    LOCK_STATE_LOCKED,
    LOCK_STATE_UNLOCKED,
    LOCK_STATE_OPEN,
    LOCK_STATE_JAMMED,
    MOTOR_STATE_LOCKING,
    MOTOR_STATE_UNLOCKING,
    MOTOR_STATE_OPENING,
    MOTOR_STATE_JAMMED,
    CHANNEL_TYPE_ACCESS_AUTHORIZATION,
)
from .entity import HcuBaseEntity, HcuAccessMixin
from .api import HcuApiClient, HcuApiError
from .util import handle_lock_api_error

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the lock platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.LOCK):
        async_add_entities(entities)


class HcuLock(HcuAccessMixin, HcuBaseEntity, LockEntity):
    """Representation of a Homematic IP HCU door lock."""

    PLATFORM = Platform.LOCK
    _attr_supported_features = LockEntityFeature.OPEN
    
    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
        **kwargs: Any,
    ):
        """Initialize the lock."""
        super().__init__(coordinator, client, device_data, channel_index, **kwargs)
        self._config_entry = coordinator.config_entry
        self._set_entity_name(channel_label=self._channel.get("label"))
        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_lock"

        # Track if this specific lock has determined it requires a PIN
        self._pin_required: bool | None = None

        # Optimistic transition flags for immediate UI feedback
        self._optimistic_is_locking: bool = False
        self._optimistic_is_unlocking: bool = False
        self._optimistic_is_opening: bool = False

        # Log available channel data fields for diagnostics
        _LOGGER.debug(
            "Lock '%s' initialized with channel data fields: %s",
            self._attr_unique_id,
            list(self._channel.keys())
        )

    @property
    def is_locked(self) -> bool:
        """Return true if the lock is locked."""
        return self._channel.get("lockState") == LOCK_STATE_LOCKED

    @property
    def is_locking(self) -> bool | None:
        """Return true if the lock is locking."""
        if self._optimistic_is_locking:
            return True
        motor_state = self._channel.get("motorState")
        lock_state = self._channel.get("lockState")

        # Return None only if we truly don't know the state (fields are missing)
        if motor_state is None and lock_state is None:
            return None

        # Return True/False based on actual state comparison
        return motor_state == MOTOR_STATE_LOCKING or lock_state == MOTOR_STATE_LOCKING

    @property
    def is_unlocking(self) -> bool | None:
        """Return true if the lock is unlocking."""
        if self._optimistic_is_unlocking:
            return True
        motor_state = self._channel.get("motorState")
        lock_state = self._channel.get("lockState")

        # Return None only if we truly don't know the state (fields are missing)
        if motor_state is None and lock_state is None:
            return None

        # Return True/False based on actual state comparison
        return motor_state == MOTOR_STATE_UNLOCKING or lock_state == MOTOR_STATE_UNLOCKING

    @property
    def is_jammed(self) -> bool | None:
        """Return true if the lock is jammed (incomplete locking)."""
        device_channel = self._device.get("functionalChannels", {}).get("0", {})
        lock_jammed = device_channel.get("lockJammed")
        motor_state = self._channel.get("motorState")
        lock_state = self._channel.get("lockState")

        # Return None only if we truly don't know the jam state (all fields are missing)
        if lock_jammed is None and motor_state is None and lock_state is None:
            return None

        # Return True/False based on actual state comparison
        return (
            lock_jammed is True
            or motor_state == MOTOR_STATE_JAMMED
            or lock_state == LOCK_STATE_JAMMED
        )

    @property
    def is_opening(self) -> bool | None:
        """Return true if the lock is opening."""
        if self._optimistic_is_opening:
            return True
        motor_state = self._channel.get("motorState")
        lock_state = self._channel.get("lockState")

        # Return None only if we truly don't know the state (fields are missing)
        if motor_state is None and lock_state is None:
            return None

        # Return True/False based on actual state comparison
        return motor_state == MOTOR_STATE_OPENING or lock_state == MOTOR_STATE_OPENING

    @property
    def extra_state_attributes(self) -> dict:
        """Return additional state attributes."""
        pin = self._get_pin()
        attrs = (super().extra_state_attributes or {}) | {
            "pin_configured": bool(pin),
        }
        # Add PIN requirement status if determined
        if self._pin_required is not None:
            attrs["pin_required"] = self._pin_required

        # Expose channel 1 fields for diagnostics (confirmed to exist on HmIP-DLD)
        channel_fields = {
            "motor_state": self._channel.get("motorState"),
            "auto_relock_enabled": self._channel.get("autoRelockEnabled"),
            "auto_relock_delay": self._channel.get("autoRelockDelay"),
        }
        attrs.update({k: v for k, v in channel_fields.items() if v is not None})

        # Expose lockJammed from channel 0 (DEVICE_OPERATIONLOCK)
        device_channel = self._device.get("functionalChannels", {}).get("0", {})
        if (lock_jammed := device_channel.get("lockJammed")) is not None:
            attrs["lock_jammed"] = lock_jammed

        # Check access authorization channels for diagnostic purposes
        # Helps users understand if the plugin has permission to control the lock
        authorized_channels = [
            ch_id
            for ch_id, ch_data in self._device.get("functionalChannels", {}).items()
            if ch_data.get("functionalChannelType") == CHANNEL_TYPE_ACCESS_AUTHORIZATION
            and ch_data.get("authorized") is True
        ]

        attrs["has_access_authorization"] = bool(authorized_channels)
        if authorized_channels:
            attrs["authorized_access_channels"] = authorized_channels

        return attrs

    def _handle_coordinator_update(self) -> None:
        """Clear optimistic transition flags and let actual device state take over."""
        if self._device_id in self.coordinator.data:
            self._optimistic_is_locking = False
            self._optimistic_is_unlocking = False
            self._optimistic_is_opening = False
        super()._handle_coordinator_update()

    async def _set_lock_state(self, state: str, pin: str | None = None) -> None:
        """Send the command to set the lock state."""

        _LOGGER.debug(
            "Setting lock state for '%s' to %s (channel: %s, device: %s)",
            self.name, state, self._channel_index, self._device_id
        )

        # Set optimistic transition flags for immediate UI feedback before the API call.
        # is_locking/is_unlocking/is_opening read these flags first so the slider reacts instantly.
        # The flags are cleared in _handle_coordinator_update() when the device reports back.
        self._optimistic_is_locking = state == LOCK_STATE_LOCKED
        self._optimistic_is_unlocking = state == LOCK_STATE_UNLOCKED
        self._optimistic_is_opening = state == LOCK_STATE_OPEN
        self._attr_assumed_state = True
        self.async_write_ha_state()

        try:
            await self._client.async_set_lock_state(
                self._device_id, self._channel_index, state=state, pin=pin
            )
            _LOGGER.debug("Successfully sent lock state command for '%s'", self.name)

            # If successful and we used no PIN, mark this lock as not requiring one
            if not pin and self._pin_required is None:
                self._pin_required = False

        except HcuApiError as err:
            err_type = handle_lock_api_error(err, self.name, pin)

            if err_type == "invalid_pin":
                self._pin_required = True
                ir.async_create_issue(
                    hass=self.hass,
                    domain=DOMAIN,
                    issue_id=f"pin_failed_{self._device_id}",
                    is_fixable=True,
                    severity=ir.IssueSeverity.ERROR,
                    translation_key="pin_failed",
                    data={
                        "entry_id": self._config_entry.entry_id,
                        "device_name": self.name,
                    },
                    translation_placeholders={"device_name": self.name},
                )
            elif not err_type:
                _LOGGER.error("Failed to set lock state for %s: %s", self.name, err)

            # Revert optimistic state on error
            self._optimistic_is_locking = False
            self._optimistic_is_unlocking = False
            self._optimistic_is_opening = False
            self._attr_assumed_state = False
            self.async_write_ha_state()

        except ConnectionError as err:
            _LOGGER.error(
                "Connection failed while setting lock state for %s: %s", self.name, err
            )

            # Revert optimistic state on error
            self._optimistic_is_locking = False
            self._optimistic_is_unlocking = False
            self._optimistic_is_opening = False
            self._attr_assumed_state = False
            self.async_write_ha_state()

    async def async_lock(self, **kwargs) -> None:
        """Lock the door."""
        await self._set_lock_state(LOCK_STATE_LOCKED, pin=self._get_pin())

    async def async_unlock(self, **kwargs) -> None:
        """Unlock the door."""
        await self._set_lock_state(LOCK_STATE_UNLOCKED, pin=self._get_pin())

    async def async_open(self, **kwargs) -> None:
        """Open the door latch."""
        await self._set_lock_state(LOCK_STATE_OPEN, pin=self._get_pin())
