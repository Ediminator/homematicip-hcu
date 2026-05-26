# custom_components/hcu_integration/siren.py
"""Siren platform for the Homematic IP HCU integration."""
import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.siren import (
    SirenEntity,
    SirenEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import HcuBaseEntity, SwitchStateMixin
from .api import HcuApiClient, HcuApiError
from .const import (
    CHANNEL_TYPE_ALARM_SIREN,
)

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the siren platform from a config entry."""
    coordinator: "HcuCoordinator" = hass.data[config_entry.domain][
        config_entry.entry_id
    ]
    if entities := coordinator.entities.get(Platform.SIREN):
        async_add_entities(entities)


class HcuSiren(SwitchStateMixin, HcuBaseEntity, SirenEntity):
    """Representation of a Homematic IP HCU alarm siren.

    Note: The tone, duration, and optical signal are configured on the
    ALARM_SWITCHING group in the HCU itself and cannot be controlled
    dynamically from Home Assistant. The siren will use whatever settings
    are configured in the HCU when activated.
    """

    PLATFORM = Platform.SIREN

    _attr_supported_features = (
        SirenEntityFeature.TURN_ON
        | SirenEntityFeature.TURN_OFF
    )

    def __init__(
        self,
        coordinator: "HcuCoordinator",
        client: HcuApiClient,
        device_data: dict,
        channel_index: str,
    ):
        super().__init__(coordinator, client, device_data, channel_index)

        # Set entity name using the centralized naming helper
        self._set_entity_name(channel_label=self._channel.get("label"))

        self._attr_unique_id = f"{self._device_id}_{self._channel_index}_siren"

        # Find the ALARM_SWITCHING group for this siren
        self._alarm_group_id = self._find_alarm_switching_group()

        # Initial state sync
        self._sync_state_from_group()

        # Log diagnostic information for troubleshooting
        _LOGGER.debug(
            "HcuSiren initialized: device=%s, channel=%s, channel_type=%s, alarm_group=%s",
            self._device_id,
            self._channel_index,
            self._channel.get("functionalChannelType"),
            self._alarm_group_id,
        )

    def _find_alarm_switching_group(self) -> str | None:
        """Find the ALARM_SWITCHING group that contains this siren channel.

        Prefers groups with acousticFeedbackEnabled=True when multiple groups exist,
        as groups with this flag disabled are typically silent/safety alarms.

        Returns:
            The group ID if found, None otherwise
        """
        # Get all groups from client state (not coordinator.data which is just entity IDs)
        groups = self._client.state.get("groups", {})

        # Find ALARM_SWITCHING group(s) containing this device/channel
        matching_groups = [
            {
                "id": group_id,
                "label": group_data.get("label", group_id),
                "audio_enabled": group_data.get("acousticFeedbackEnabled", False),
            }
            for group_id, group_data in groups.items()
            if group_data.get("type") == "ALARM_SWITCHING"
            and any(
                channel.get("deviceId") == self._device_id
                and str(channel.get("channelIndex")) == str(self._channel_index)
                for channel in group_data.get("channels", [])
            )
        ]

        # Handle results
        if not matching_groups:
            _LOGGER.warning(
                "No ALARM_SWITCHING group found for siren %s channel %s. "
                "Siren control may not work properly.",
                self._device_id,
                self._channel_index,
            )
            return None

        if len(matching_groups) > 1:
            # Sort by ID once for deterministic selection
            matching_groups.sort(key=lambda g: g["id"])

            # Prefer groups with acousticFeedbackEnabled=True (audio-enabled alarms)
            # over silent/safety alarm groups
            audio_enabled_groups = [g for g in matching_groups if g["audio_enabled"]]

            if audio_enabled_groups:
                # Use first audio-enabled group (already sorted)
                selected_group = audio_enabled_groups[0]
                # Format group list for logging
                groups_list = ", ".join(
                    f"'{g['label']}' ({g['id']}, audio={'enabled' if g['audio_enabled'] else 'disabled'})"
                    for g in matching_groups
                )
                silent_count = len(matching_groups) - len(audio_enabled_groups)
                _LOGGER.info(
                    "Multiple ALARM_SWITCHING groups found for siren %s: %s. "
                    "Selected audio-enabled group '%s' (%s) over %d silent/safety alarm group(s).",
                    self._device_id,
                    groups_list,
                    selected_group["label"],
                    selected_group["id"],
                    silent_count,
                )
            else:
                # All groups have audio disabled - use first one (already sorted)
                selected_group = matching_groups[0]
                # Format group list for logging
                groups_list = ", ".join(
                    f"'{g['label']}' ({g['id']})" for g in matching_groups
                )
                _LOGGER.warning(
                    "Multiple ALARM_SWITCHING groups found for siren %s, but all have acousticFeedbackEnabled=False: %s. "
                    "Using first group '%s' (%s). Siren may not produce audio.",
                    self._device_id,
                    groups_list,
                    selected_group["label"],
                    selected_group["id"],
                )
        else:
            # Single group found
            selected_group = matching_groups[0]
            audio_status = "enabled" if selected_group["audio_enabled"] else "disabled"
            _LOGGER.info(
                "Found ALARM_SWITCHING group '%s' (%s) for siren %s (audio %s)",
                selected_group["label"],
                selected_group["id"],
                self._device_id,
                audio_status,
            )

        return selected_group["id"]

    @property
    def available(self) -> bool:
        """Return True if the entity is available.

        Override to add diagnostic logging for troubleshooting siren availability.

        ALARM_SIREN_CHANNEL often has minimal data (only metadata fields like
        functionalChannelType, groups, channelRole) or may be omitted entirely
        from HCU state updates. This is normal behavior - the channel doesn't
        need state fields when the siren is inactive. The base class now properly
        handles this by not checking for channel data presence.
        """
        # Validate channel type if present (diagnostic check only)
        channel_type = self._channel.get("functionalChannelType")
        if channel_type is not None and channel_type != CHANNEL_TYPE_ALARM_SIREN:
            _LOGGER.warning(
                "Siren %s: unexpected channel type '%s', expected '%s'",
                self._device_id,
                channel_type,
                CHANNEL_TYPE_ALARM_SIREN
            )

        # Call base implementation (which handles all availability logic correctly)
        is_available = super().available

        # Add diagnostic logging for unavailable states
        if not is_available:
            if not self._client.is_connected:
                _LOGGER.debug("Siren %s unavailable: client not connected", self._device_id)
            elif not self._device:
                _LOGGER.warning("Siren %s unavailable: device data missing from state", self._device_id)
            else:
                _LOGGER.debug(
                    "Siren %s unavailable: device unreachable (battery-powered device may be sleeping)",
                    self._device_id
                )

        return is_available

    def _validate_alarm_group_configured(self) -> None:
        """Validate that an ALARM_SWITCHING group is configured for this siren.

        Raises:
            HcuApiError: If no ALARM_SWITCHING group is found
        """
        if not self._alarm_group_id:
            _LOGGER.error(
                "Cannot control siren %s: No ALARM_SWITCHING group found. "
                "The siren may not be properly configured in the HCU.",
                self.name,
            )
            raise HcuApiError("No ALARM_SWITCHING group found for siren")

    def _sync_state_from_group(self) -> None:
        """Sync the siren's state from the ALARM_SWITCHING group."""
        is_on = False
        if self._alarm_group_id:
            group_data = self._client.state.get("groups", {}).get(self._alarm_group_id)
            if group_data:
                is_on = group_data.get("on", False)
        self._attr_is_on = is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # Sync state from the group data when an update is received
        if not self._attr_assumed_state:
            self._sync_state_from_group()
        super()._handle_coordinator_update()

    async def _async_execute_with_state_management(
        self, target_state: bool, api_call: Any, action: str
    ) -> None:
        """Execute API call with optimistic state management and error handling.

        Args:
            target_state: The desired state (True for on, False for off)
            api_call: Coroutine to execute for the API call
            action: Action name for logging ("turn on" or "turn off")
        """
        # Store previous state for rollback on error
        previous_state = self.is_on

        # Set optimistic state immediately
        self._attr_is_on = target_state
        self._attr_assumed_state = True
        self.async_write_ha_state()

        try:
            await api_call
            # API call succeeded - clear assumed_state to allow coordinator updates
            self._attr_assumed_state = False
            self.async_write_ha_state()
        except (HcuApiError, ConnectionError) as err:
            # Revert state on error
            _LOGGER.error("Failed to %s siren %s: %s", action, self.name, err)
            self._attr_is_on = previous_state
            self._attr_assumed_state = False
            self.async_write_ha_state()
            raise

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the siren on.

        Note: The tone, duration, and optical signal settings are configured
        on the ALARM_SWITCHING group in the HCU and cannot be controlled from
        Home Assistant. The siren will use whatever settings are configured
        in the HCU when activated.
        """
        # Validate ALARM_SWITCHING group is configured
        self._validate_alarm_group_configured()

        _LOGGER.info("Activating siren %s via ALARM_SWITCHING group", self.name)

        # Activate the siren via ALARM_SWITCHING group
        await self._async_execute_with_state_management(
            target_state=True,
            api_call=self._client.async_set_alarm_switching_group_state(
                group_id=self._alarm_group_id,
                on=True,
            ),
            action="turn on",
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the siren off."""
        # Validate ALARM_SWITCHING group is configured
        self._validate_alarm_group_configured()

        _LOGGER.info("Deactivating siren %s via ALARM_SWITCHING group", self.name)

        # Deactivate the siren via ALARM_SWITCHING group
        await self._async_execute_with_state_management(
            target_state=False,
            api_call=self._client.async_set_alarm_switching_group_state(
                group_id=self._alarm_group_id,
                on=False,
            ),
            action="turn off",
        )
