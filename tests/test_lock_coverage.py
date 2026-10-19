"""Coverage tests for HCU lock platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from homeassistant.components.lock import LockEntityFeature
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    CHANNEL_TYPE_ACCESS_AUTHORIZATION,
    CONF_DEVICE_PINS,
    DOMAIN,
    LOCK_STATE_JAMMED,
    LOCK_STATE_LOCKED,
    LOCK_STATE_OPEN,
    LOCK_STATE_UNLOCKED,
    MOTOR_STATE_JAMMED,
    MOTOR_STATE_LOCKING,
    MOTOR_STATE_OPENING,
    MOTOR_STATE_UNLOCKING,
)
from custom_components.hcu_integration.lock import HcuLock, async_setup_entry


def _create_lock(
    hass: HomeAssistant,
    *,
    device_id: str = "lock-dev-1",
    channel_index: str = "1",
    channel_data: dict | None = None,
    device_channels: dict | None = None,
    pin: str | None = None,
) -> tuple[HcuLock, MagicMock, MagicMock]:
    """Create an HcuLock test entity with mocks."""
    ch_data = {
        "functionalChannelType": "DOOR_LOCK_CHANNEL",
        "label": "Front Door",
        "lockState": LOCK_STATE_UNLOCKED,
        "motorState": "STOPPED",
    }
    if channel_data:
        ch_data.update(channel_data)

    func_channels = {
        "0": {"functionalChannelType": "DEVICE_BASE", "lockJammed": False},
        channel_index: ch_data,
    }
    if device_channels:
        func_channels.update(device_channels)

    device = {
        "id": device_id,
        "label": "Door Lock",
        "type": "DOOR_LOCK_DRIVE",
        "functionalChannels": func_channels,
    }

    client = MagicMock()
    client.is_connected = True
    client.state = {"devices": {device_id: device}}
    client.get_device_by_address = MagicMock(return_value=device)
    client.async_set_lock_state = AsyncMock()

    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {device_id: device}
    coordinator.client = client
    coordinator.config_entry = MagicMock()
    coordinator.config_entry.entry_id = "test-entry-id"
    coordinator.config_entry.data = {}
    options = {}
    if pin:
        options[CONF_DEVICE_PINS] = {device_id: pin}
    coordinator.config_entry.options = options

    lock = HcuLock(coordinator, client, device, channel_index)
    lock.hass = hass
    return lock, coordinator, client


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test platform setup with and without lock entities."""
    entry = MagicMock()
    coordinator = MagicMock()
    entry.runtime_data = coordinator
    async_add_entities = MagicMock()

    # Case 1: No lock entities
    coordinator.entities = {}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_not_called()

    # Case 2: Lock entities present
    lock_entity = MagicMock()
    coordinator.entities = {Platform.LOCK: [lock_entity]}
    await async_setup_entry(hass, entry, async_add_entities)
    async_add_entities.assert_called_once_with([lock_entity])


def test_lock_initialization_and_naming(hass: HomeAssistant) -> None:
    """Test lock naming logic when channel has no label and multiple channels exist."""
    device_channels = {
        "1": {
            "functionalChannelType": "DOOR_LOCK_CHANNEL",
            "label": None,
        },
        "2": {
            "functionalChannelType": "DOOR_LOCK_CHANNEL",
            "label": None,
        },
    }
    lock, _, _ = _create_lock(
        hass,
        channel_index="1",
        channel_data={"label": None},
        device_channels=device_channels,
    )
    assert lock.unique_id == "lock-dev-1_1_lock"
    assert lock.supported_features == LockEntityFeature.OPEN


def test_lock_states(hass: HomeAssistant) -> None:
    """Test is_locked, is_locking, is_unlocking, is_opening, is_jammed."""
    # Test locked
    lock, _, _ = _create_lock(
        hass, channel_data={"lockState": LOCK_STATE_LOCKED, "motorState": "STOPPED"}
    )
    assert lock.is_locked is True
    assert lock.is_locking is False
    assert lock.is_unlocking is False
    assert lock.is_jammed is False
    assert lock.is_opening is False

    # Test unknown states (all fields missing)
    lock_unknown, _, _ = _create_lock(
        hass,
        channel_data={"lockState": None, "motorState": None},
        device_channels={"0": {"lockJammed": None}},
    )
    assert lock_unknown.is_locked is False
    assert lock_unknown.is_locking is None
    assert lock_unknown.is_unlocking is None
    assert lock_unknown.is_jammed is None
    assert lock_unknown.is_opening is None

    # Test motor locking / lockState locking
    lock_locking, _, _ = _create_lock(
        hass, channel_data={"lockState": None, "motorState": MOTOR_STATE_LOCKING}
    )
    assert lock_locking.is_locking is True
    lock_locking2, _, _ = _create_lock(
        hass, channel_data={"lockState": MOTOR_STATE_LOCKING, "motorState": None}
    )
    assert lock_locking2.is_locking is True

    # Test motor unlocking / lockState unlocking
    lock_unlocking, _, _ = _create_lock(
        hass, channel_data={"lockState": None, "motorState": MOTOR_STATE_UNLOCKING}
    )
    assert lock_unlocking.is_unlocking is True
    lock_unlocking2, _, _ = _create_lock(
        hass, channel_data={"lockState": MOTOR_STATE_UNLOCKING, "motorState": None}
    )
    assert lock_unlocking2.is_unlocking is True

    # Test opening
    lock_opening, _, _ = _create_lock(
        hass, channel_data={"lockState": None, "motorState": MOTOR_STATE_OPENING}
    )
    assert lock_opening.is_opening is True
    lock_opening2, _, _ = _create_lock(
        hass, channel_data={"lockState": MOTOR_STATE_OPENING, "motorState": None}
    )
    assert lock_opening2.is_opening is True

    # Test jammed via channel 0, motorState, and lockState
    lock_jammed_ch0, _, _ = _create_lock(
        hass,
        channel_data={"lockState": None, "motorState": None},
        device_channels={"0": {"lockJammed": True}},
    )
    assert lock_jammed_ch0.is_jammed is True

    lock_jammed_motor, _, _ = _create_lock(
        hass,
        channel_data={"lockState": None, "motorState": MOTOR_STATE_JAMMED},
        device_channels={"0": {"lockJammed": False}},
    )
    assert lock_jammed_motor.is_jammed is True

    lock_jammed_state, _, _ = _create_lock(
        hass,
        channel_data={"lockState": LOCK_STATE_JAMMED, "motorState": None},
        device_channels={"0": {"lockJammed": False}},
    )
    assert lock_jammed_state.is_jammed is True


def test_lock_extra_state_attributes(hass: HomeAssistant) -> None:
    """Test extra_state_attributes with PIN, diagnostics, and authorization channels."""
    device_channels = {
        "0": {"functionalChannelType": "DEVICE_BASE", "lockJammed": True},
        "2": {
            "functionalChannelType": CHANNEL_TYPE_ACCESS_AUTHORIZATION,
            "authorized": True,
        },
    }
    lock, _, _ = _create_lock(
        hass,
        pin="1234",
        channel_data={
            "motorState": "STOPPED",
            "autoRelockEnabled": True,
            "autoRelockDelay": 30,
        },
        device_channels=device_channels,
    )
    lock._pin_required = True

    attrs = lock.extra_state_attributes
    assert attrs["pin_configured"] is True
    assert attrs["pin_required"] is True
    assert attrs["motor_state"] == "STOPPED"
    assert attrs["auto_relock_enabled"] is True
    assert attrs["auto_relock_delay"] == 30
    assert attrs["lock_jammed"] is True
    assert attrs["has_access_authorization"] is True
    assert attrs["authorized_access_channels"] == ["2"]


async def test_lock_actions_success_and_coordinator_update(
    hass: HomeAssistant,
) -> None:
    """Test async_lock, async_unlock, async_open and coordinator update clearing optimistic state."""
    lock, _coordinator, client = _create_lock(hass, pin="4321")
    lock.async_write_ha_state = MagicMock()

    # Lock
    await lock.async_lock()
    client.async_set_lock_state.assert_awaited_with(
        "lock-dev-1", 1, state=LOCK_STATE_LOCKED, pin="4321"
    )

    # Unlock
    await lock.async_unlock()
    client.async_set_lock_state.assert_awaited_with(
        "lock-dev-1", 1, state=LOCK_STATE_UNLOCKED, pin="4321"
    )

    # Open
    await lock.async_open()
    client.async_set_lock_state.assert_awaited_with(
        "lock-dev-1", 1, state=LOCK_STATE_OPEN, pin="4321"
    )

    # Test without pin sets _pin_required to False
    lock_no_pin, _, _client_no_pin = _create_lock(hass, pin=None)
    lock_no_pin.async_write_ha_state = MagicMock()
    assert lock_no_pin._pin_required is None

    await lock_no_pin.async_lock()
    assert lock_no_pin._pin_required is False

    # Check optimistic flags during lock
    lock_no_pin._optimistic_is_locking = True
    lock_no_pin._optimistic_is_unlocking = True
    assert lock_no_pin.is_locking is True
    assert lock_no_pin.is_unlocking is True

    # Coordinator update clears optimistic flags
    lock_no_pin._handle_coordinator_update()
    assert lock_no_pin._optimistic_is_locking is False
    assert lock_no_pin._optimistic_is_unlocking is False


async def test_lock_api_error_invalid_pin(hass: HomeAssistant) -> None:
    """Test lock handling invalid PIN error creates repair issue and marks pin_required."""
    lock, _, client = _create_lock(hass, pin=None)
    lock.async_write_ha_state = MagicMock()
    client.async_set_lock_state.side_effect = HcuApiError("invalid_pin: incorrect pin")

    await lock.async_lock()

    assert lock._pin_required is True
    assert lock._optimistic_is_locking is False
    assert lock.assumed_state is False

    # Verify issue registry created an issue
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "pin_failed_lock-dev-1")
    assert issue is not None
    assert issue.translation_key == "pin_failed"


async def test_lock_api_error_generic(hass: HomeAssistant) -> None:
    """Test lock handling generic API error reverts optimistic state."""
    lock, _, client = _create_lock(hass, pin="1234")
    lock.async_write_ha_state = MagicMock()
    client.async_set_lock_state.side_effect = HcuApiError("UNKNOWN_ERROR: server error")

    await lock.async_lock()

    assert lock._optimistic_is_locking is False
    assert lock.assumed_state is False


async def test_lock_connection_error(hass: HomeAssistant) -> None:
    """Test lock handling ConnectionError reverts optimistic state."""
    lock, _, client = _create_lock(hass, pin="1234")
    lock.async_write_ha_state = MagicMock()
    client.async_set_lock_state.side_effect = ConnectionError("Network unreachable")

    await lock.async_lock()

    assert lock._optimistic_is_locking is False
    assert lock.assumed_state is False
