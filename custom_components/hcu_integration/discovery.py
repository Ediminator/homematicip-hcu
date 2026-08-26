# custom_components/hcu_integration/discovery.py
"""Entity discovery logic for the Homematic IP HCU integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
import asyncio
from urllib.parse import quote

from . import (
    alarm_control_panel,
    binary_sensor,
    button,
    climate,
    cover,
    event,
    light,
    lock,
    number,
    select,
    sensor,
    siren,
    switch,
    text,
    update,
    valve,
)
from .api import HcuApiClient
from .const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    CHANNEL_TYPE_MULTI_MODE_INPUT_TRANSMITTER,
    DEACTIVATED_BY_DEFAULT_DEVICES,
    DOMAIN,
    DUTY_CYCLE_BINARY_SENSOR_MAPPING,
    HMIP_CHANNEL_TYPE_TO_ENTITY,
    HMIP_FEATURE_TO_ENTITY,
    HMIP_OPTIONAL_FEATURE_TO_ENTITY,
    HMIP_CHANNEL_ROLE_TO_ENTITY,
    MULTI_FUNCTION_CHANNEL_DEVICES,
    PLATFORMS,
    MANUFACTURER_EQ3,
    CONF_DISABLED_GROUPS,
    ALLOWED_EMPTY_GROUPS,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    DEFAULT_DISABLE_UNCONFIGURED_CHANNELS,
    HA_DEVICE_ID_PREFIX,
)
from .util import get_device_manufacturer

if TYPE_CHECKING:
    from . import HcuCoordinator

_LOGGER = logging.getLogger(__name__)

# Features newly deactivated by default in Issue #296
# Used for retroactive cleanup in the entity registry
NEWLY_DEACTIVATED_FEATURES = frozenset({
    "dirtLevel", "operationDays", "lastSmokeTestTimestamp",
    "lastCommunicationTestTimestamp", "smokeTestCounter", "smokeAlarmCounter",
    "chamberDegraded", "deviceOverheated", "temperatureOutOfRange",
    "coProFaulty", "coProUpdateFailure"
})

_CLASS_MODULE_MAP: dict[str, Any] = {
    "HcuLight": light,
    "HcuSwitchLight": light,
    "HcuNotificationLight": light,
    "HcuSwitch": switch,
    "HcuWateringSwitch": valve,
    "HcuConfigUseInternalOnTime": switch,
    "HcuConfigRampTime": number,
    "HcuCover": cover,
    "HcuGarageDoorCover": cover,
    "HcuDoorbellEvent": event,
    "HcuButtonEvent": event,
    "HcuLock": lock,
    "HcuResetEnergyButton": button,
    "HcuDoorPullLatchButton": button,
    "HcuDoorImpulseButton": button,
    "HcuDoorUnlatchButton": button,
    "HcuDevicePin": text,
    "HcuDeviceIdentifyButton": button,
    "HcuGenericSensor": sensor,
    "HcuTemperatureSensor": sensor,
    "HcuHomeSensor": sensor,
    "HcuWindowStateSensor": sensor,
    "HcuBinarySensor": binary_sensor,
    "HcuWindowBinarySensor": binary_sensor,
    "HcuDoorBinarySensor": binary_sensor,
    "HcuSmokeBinarySensor": binary_sensor,
    "HcuUnreachBinarySensor": binary_sensor,
    "HcuVacationModeBinarySensor": binary_sensor,
    "HcuPowerUpSwitchState": select,
    "HcuAlarmSignalAcoustic": select,
    "HcuAlarmSignalOptical": select,
}


def _discover_entities_for_device(
    device_data: dict[str, Any],
    config_entry: ConfigEntry,
    coordinator: "HcuCoordinator",
    client: HcuApiClient,
) -> tuple[dict[Platform, list[Any]], set[str]]:
    """
    Process a single device and return its entities and unique IDs.

    Returns a tuple of:
      - dict mapping Platform to list of entity instances
      - set of unique_id strings for all created entities
    """
    entities: dict[Platform, list[Any]] = {platform: [] for platform in PLATFORMS}
    valid_unique_ids: set[str] = set()

    # Devices contributed by our own HA Entity Bridge come back in the HCU's
    # regular device list once included, just like any other plugin-contributed
    # device — but keyed under the HCU's own generated "id", NOT the ha.<uuid>
    # we assigned. That ID only survives in "pluginDeviceId". Re-importing these
    # as new HA entities would bridge them right back into HA, echoing the
    # original entity, so skip them based on that field instead.
    if str(device_data.get("pluginDeviceId") or "").startswith(HA_DEVICE_ID_PREFIX):
        return entities, valid_unique_ids

    class_module_map = _CLASS_MODULE_MAP
    disable_unconfigured = config_entry.options.get(
        CONF_DISABLE_UNCONFIGURED_CHANNELS, DEFAULT_DISABLE_UNCONFIGURED_CHANNELS
    )

    manufacturer = get_device_manufacturer(device_data)
    if manufacturer != MANUFACTURER_EQ3:
        disabled_oems = config_entry.options.get("disabled_oems")
        is_disabled = False
        if disabled_oems is not None:
            if manufacturer in disabled_oems:
                is_disabled = True
        else:
            option_key = f"import_{quote(manufacturer)}"
            if not config_entry.options.get(option_key, True):
                is_disabled = True

        if is_disabled:
            _LOGGER.debug(
                "Skipping device %s (%s) as manufacturer %s is disabled",
                device_data.get("id"),
                device_data.get("label"),
                manufacturer,
            )
            return entities, valid_unique_ids

    if device_data.get("updateState") is not None and device_data.get("availableFirmwareVersion") not in (None, "", "UNKNOWN"):
        entity = update.HcuFirmwareUpdate(coordinator, client, device_data, "0")
        entities[Platform.UPDATE].append(entity)
        uid = getattr(entity, "unique_id", None)
        if uid:
            valid_unique_ids.add(uid)

    for channel_index, channel_data in device_data.get("functionalChannels", {}).items():
        internal_link_config = channel_data.get("internalLinkConfiguration") or {}
        channel_data = {**channel_data, **internal_link_config}
        processed_features = set()
        is_deactivated_by_default = device_data.get("type") in DEACTIVATED_BY_DEFAULT_DEVICES
        is_unused_channel = is_deactivated_by_default and not channel_data.get("groups")
        is_unused_device_channel = not channel_data.get("groups")

        channel_type = channel_data.get("functionalChannelType")
        channel_role = channel_data.get("channelRole")
        base_channel_type = None
        channel_mapping = None

        if channel_role in HMIP_CHANNEL_ROLE_TO_ENTITY:
            base_channel_type = channel_role
            channel_mapping = HMIP_CHANNEL_ROLE_TO_ENTITY[base_channel_type]
        elif channel_type:
            if channel_type in HMIP_CHANNEL_TYPE_TO_ENTITY:
                base_channel_type = channel_type
                channel_mapping = HMIP_CHANNEL_TYPE_TO_ENTITY[base_channel_type]
            else:
                for base_type in HMIP_CHANNEL_TYPE_TO_ENTITY:
                    if channel_type.startswith(base_type):
                        base_channel_type = base_type
                        channel_mapping = HMIP_CHANNEL_TYPE_TO_ENTITY[base_channel_type]
                        break

        if channel_mapping:
            class_name = channel_mapping["class"]
            if is_unused_channel:
                continue

            if module := class_module_map.get(class_name):
                try:
                    if not is_unused_device_channel or not disable_unconfigured:
                        entity_class = getattr(module, class_name)
                        platform = getattr(entity_class, "PLATFORM")

                        if class_name == "HcuSwitch":
                            switch_visualization = channel_data.get("switchVisualization")
                            if switch_visualization == "LIGHT":
                                entity_class = getattr(light, "HcuSwitchLight")
                                platform = Platform.LIGHT
                                _LOGGER.debug(
                                    "Switch channel registered as LightEntity due to switchVisualization=LIGHT: device=%s, channel=%s",
                                    device_data.get("id"),
                                    channel_index,
                                )

                        entity_mapping = channel_mapping.copy()
                        feature = entity_mapping.get("feature")
                        if feature is not None:
                            processed_features.add(feature)
                            entity = entity_class(coordinator, client, device_data, channel_index, feature, entity_mapping)
                        else:
                            entity = entity_class(coordinator, client, device_data, channel_index)
                        entities[platform].append(entity)
                        uid = getattr(entity, "unique_id", None)
                        if uid:
                            valid_unique_ids.add(uid)
                    else:
                        _LOGGER.debug(
                            "Skipping channel %s (%s) on device %s (%s): not assigned to a room in the Homematic IP app",
                            channel_index,
                            channel_type,
                            device_data.get("id"),
                            device_data.get("label"),
                        )

                    for extra_cfg in channel_mapping.get("extra_entities", []):
                        if isinstance(extra_cfg, str):
                            extra_class_name = extra_cfg
                            only_channel_types = None
                        else:
                            extra_class_name = extra_cfg.get("class")
                            only_channel_types = set(extra_cfg.get("only_channel_types", [])) or None

                        if not extra_class_name:
                            continue

                        if only_channel_types and channel_type not in only_channel_types:
                            continue

                        if extra_module := class_module_map.get(extra_class_name):
                            try:
                                extra_entity_class = getattr(extra_module, extra_class_name)
                                extra_platform = getattr(extra_entity_class, "PLATFORM")
                                extra_entity = extra_entity_class(
                                    coordinator, client, device_data, channel_index
                                )
                                entities[extra_platform].append(extra_entity)
                                extra_uid = getattr(extra_entity, "unique_id", None)
                                if extra_uid:
                                    valid_unique_ids.add(extra_uid)
                            except (AttributeError, TypeError) as e:
                                _LOGGER.error(
                                    "Failed to create extra entity '%s' for device %s, channel %s: %s",
                                    extra_class_name,
                                    device_data.get("id"),
                                    channel_index,
                                    e,
                                )

                except (AttributeError, TypeError) as e:
                    _LOGGER.error(
                        "Failed to create entity for device %s, channel %s (type: %s, base: %s, class: %s): %s",
                        device_data.get("id"), channel_index, channel_type, base_channel_type, class_name, e
                    )

        device_type = device_data.get("type")
        if device_type in MULTI_FUNCTION_CHANNEL_DEVICES:
            multi_func_config = MULTI_FUNCTION_CHANNEL_DEVICES[device_type].get(base_channel_type or channel_type)
            if multi_func_config and "button" in multi_func_config.get("functions", []):
                try:
                    _LOGGER.debug(
                        "Creating button event entity for multi-function channel: device=%s (%s), channel=%s (%s)",
                        device_data.get("id"),
                        device_type,
                        channel_index,
                        channel_type,
                    )
                    entity = event.HcuButtonEvent(coordinator, client, device_data, channel_index)
                    entities[Platform.EVENT].append(entity)
                    uid = getattr(entity, "unique_id", None)
                    if uid:
                        valid_unique_ids.add(uid)
                except (AttributeError, TypeError) as e:
                    _LOGGER.error(
                        "Failed to create button event entity for device %s, channel %s (type: %s): %s",
                        device_data.get("id"), channel_index, channel_type, e
                    )

        temp_features = {"actualTemperature", "valveActualTemperature"}
        found_temp_feature = next((f for f in temp_features if f in channel_data), None)
        if found_temp_feature:
            try:
                mapping = HMIP_FEATURE_TO_ENTITY[found_temp_feature]
                entity = sensor.HcuTemperatureSensor(coordinator, client, device_data, channel_index, found_temp_feature, mapping)
                entities[Platform.SENSOR].append(entity)
                uid = getattr(entity, "unique_id", None)
                if uid:
                    valid_unique_ids.add(uid)
                processed_features.update(temp_features)
            except (AttributeError, TypeError) as e:
                _LOGGER.error("Failed to create temperature sensor for %s: %s", device_data.get("id"), e)

        for feature, mapping in HMIP_FEATURE_TO_ENTITY.items():
            if feature in processed_features or feature not in channel_data:
                continue

            if mapping.get("requires_app_user") and client._auth_type not in (AUTH_TYPE_APP, AUTH_TYPE_DUAL):
                continue

            if mapping.get("class") == "HcuHomeSensor":
                continue

            if feature == "dutyCycleLevel" and device_data.get("id") == client.hcu_device_id:
                continue

            optional_flag = mapping.get("optional_flag")
            if optional_flag:
                supported = channel_data.get("supportedOptionalFeatures") or {}
                if not supported.get(optional_flag, False):
                    continue

            if mapping.get("skip_if_null") and channel_data.get(feature) is None:
                continue

            class_name = mapping["class"]
            if module := class_module_map.get(class_name):
                try:
                    entity_class = getattr(module, class_name)
                    platform = getattr(entity_class, "PLATFORM")
                    entity_mapping = mapping.copy()
                    if is_deactivated_by_default:
                        entity_mapping["entity_registry_enabled_default"] = not is_unused_channel
                    entity = entity_class(coordinator, client, device_data, channel_index, feature, entity_mapping)
                    entities[platform].append(entity)
                    uid = getattr(entity, "unique_id", None)
                    if uid:
                        valid_unique_ids.add(uid)

                    if feature == "energyCounter":
                        entity = button.HcuResetEnergyButton(coordinator, client, device_data, channel_index)
                        entities[Platform.BUTTON].append(entity)
                        uid = getattr(entity, "unique_id", None)
                        if uid:
                            valid_unique_ids.add(uid)

                    if feature == "waterVolume":
                        entity = button.HcuResetWaterVolume(coordinator, client, device_data, channel_index)
                        entities[Platform.BUTTON].append(entity)
                        uid = getattr(entity, "unique_id", None)
                        if uid:
                            valid_unique_ids.add(uid)

                    if companion_class_name := mapping.get("config_companion"):
                        if companion_module := class_module_map.get(companion_class_name):
                            try:
                                companion_class = getattr(companion_module, companion_class_name)
                                companion = companion_class(coordinator, client, device_data, channel_index)
                                entities[companion.PLATFORM].append(companion)
                                c_uid = getattr(companion, "unique_id", None)
                                if c_uid:
                                    valid_unique_ids.add(c_uid)
                            except (AttributeError, TypeError) as e:
                                _LOGGER.error(
                                    "Failed to create config companion '%s' for device %s, channel %s: %s",
                                    companion_class_name, device_data.get("id"), channel_index, e,
                                )

                except (AttributeError, TypeError) as e:
                    _LOGGER.error(
                        "Failed to create entity for device %s, channel %s, feature %s (%s): %s",
                        device_data.get("id"), channel_index, feature, class_name, e
                    )

        supported_map = channel_data.get("supportedOptionalFeatures") or {}

        for feature, mapping in HMIP_OPTIONAL_FEATURE_TO_ENTITY.items():
            if not supported_map.get(feature, False):
                continue

            _LOGGER.debug(
                "Optional feature supported: device=%s channel=%s feature=%s",
                device_data.get("id"),
                channel_index,
                feature,
            )

            requires_data_key = mapping.get("requires_data_key", True)
            data_key = mapping.get("data_key", feature)

            if requires_data_key and data_key in HMIP_FEATURE_TO_ENTITY:
                continue

            if requires_data_key:
                if data_key not in channel_data:
                    _LOGGER.debug(
                        "Optional feature supported but not created (missing data key): device=%s channel=%s feature=%s data_key=%s",
                        device_data.get("id"),
                        channel_index,
                        feature,
                        data_key,
                    )
                    continue

            class_name = mapping["class"]
            module = class_module_map.get(class_name)
            if not module:
                _LOGGER.debug(
                    "Optional feature supported but not created (no module mapping): device=%s channel=%s feature=%s class=%s",
                    device_data.get("id"),
                    channel_index,
                    feature,
                    class_name,
                )
                continue

            try:
                entity_class = getattr(module, class_name)
                platform = getattr(entity_class, "PLATFORM")

                entity_mapping = mapping.copy()
                if is_deactivated_by_default:
                    entity_mapping["entity_registry_enabled_default"] = not is_unused_channel

                feature_arg = data_key if requires_data_key else feature

                if mapping.get("simple_init", False):
                    entity = entity_class(coordinator, client, device_data, channel_index)
                else:
                    entity = entity_class(
                        coordinator, client, device_data, channel_index, feature_arg, entity_mapping
                    )

                entities[platform].append(entity)
                uid = getattr(entity, "unique_id", None)
                if uid:
                    valid_unique_ids.add(uid)

                _LOGGER.debug(
                    "Optional feature entity created successfully: device=%s channel=%s feature=%s class=%s platform=%s arg=%s",
                    device_data.get("id"),
                    channel_index,
                    feature,
                    class_name,
                    platform.value,
                    feature_arg,
                )

            except (AttributeError, TypeError) as e:
                _LOGGER.error(
                    "Optional feature entity not created: device=%s channel=%s feature=%s class=%s error=%s",
                    device_data.get("id"),
                    channel_index,
                    feature,
                    class_name,
                    e,
                    exc_info=True,
                )
                continue

        if "dutyCycle" in channel_data and isinstance(channel_data["dutyCycle"], bool):
            try:
                entity_mapping = DUTY_CYCLE_BINARY_SENSOR_MAPPING.copy()
                if is_deactivated_by_default:
                    entity_mapping["entity_registry_enabled_default"] = not is_unused_channel
                entity = binary_sensor.HcuBinarySensor(coordinator, client, device_data, channel_index, "dutyCycle", entity_mapping)
                entities[Platform.BINARY_SENSOR].append(entity)
                uid = getattr(entity, "unique_id", None)
                if uid:
                    valid_unique_ids.add(uid)

            except (AttributeError, TypeError) as e:
                _LOGGER.error("Failed to create dutyCycle binary sensor for device %s: %s", device_data.get("id"), e)

    return entities, valid_unique_ids


async def async_discover_entities(
    hass: HomeAssistant,
    client: HcuApiClient,
    config_entry: ConfigEntry,
    coordinator: "HcuCoordinator",
) -> dict[Platform, list[Any]]:
    """
    Discover and instantiate all entities for the integration.

    Processes HCU state data and creates appropriate Home Assistant entities
    based on device types, channel types, and features.
    """
    entities: dict[Platform, list[Any]] = {platform: [] for platform in PLATFORMS}
    state = client.state
    valid_entity_unique_ids: set[str] = set()

    for device_data in state.get("devices", {}).values():
        dev_entities, dev_uids = _discover_entities_for_device(device_data, config_entry, coordinator, client)
        for platform, platform_entities in dev_entities.items():
            entities[platform].extend(platform_entities)
        valid_entity_unique_ids.update(dev_uids)

    # Create group entities using type mapping
    # Maps group type to (platform, entity_class, extra_kwargs)
    group_type_mapping = {
        "HEATING": (Platform.CLIMATE, climate.HcuClimate, {"config_entry": config_entry}),
        "SHUTTER": (Platform.COVER, cover.HcuCoverGroup, {}),
        "SWITCHING": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "SWITCHING_PROFILE": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "LINKED_SWITCHING": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "LIGHT": (Platform.LIGHT, light.HcuLightGroup, {}),
        "EXTENDED_LINKED_SWITCHING": [
            (Platform.SWITCH, switch.HcuSwitchGroup, {}),
            (Platform.SENSOR, sensor.HcuGroupOnTimeSensor, {}),
        ],
        "EXTENDED_LINKED_SHUTTER": (Platform.COVER, cover.HcuCoverGroup, {}),
        "EXTENDED_LINKED_NOTIFICATION": (Platform.LIGHT, light.HcuLightGroup, {}),
        "EXTENDED_LINKED_WATERING": (Platform.SWITCH, switch.HcuWateringGroup, {}),
        "EXTENDED_LINKED_GARAGE_DOOR": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "HEATING_COOLING_DEMAND_BOILER": (Platform.BINARY_SENSOR, binary_sensor.HcuHeatDemandBinarySensorGroup, {}),
        "HEATING_COOLING_DEMAND_PUMP": (Platform.BINARY_SENSOR, binary_sensor.HcuHeatDemandBinarySensorGroup, {}),
        "HOT_WATER": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "ALARM_SWITCHING": [
            (Platform.SELECT, select.HcuAlarmSignalAcoustic, {}),
            (Platform.SELECT, select.HcuAlarmSignalOptical, {}),
        ],
    }

    # Track group discovery statistics for diagnostics
    groups_discovered = 0
    groups_unknown_type = 0
    
    # Initialize valid device IDs with physical devices (and HCU itself if present in devices)
    # We will also add valid group IDs to this set during the group discovery loop to avoid
    # a second iteration over groups later. HA Entity Bridge devices are excluded here too —
    # we never create entities for them (see the skip above), so leaving their HCU-generated
    # "id" in this set would make the orphaned-device cleanup below think they're still valid
    # and never remove a device/entities that were already imported before that skip existed.
    valid_device_ids = {
        device_id
        for device_id, device_data in state.get("devices", {}).items()
        if not str(device_data.get("pluginDeviceId") or "").startswith(HA_DEVICE_ID_PREFIX)
    }

    # Fetch device registry once before iterating groups
    dev_reg = dr.async_get(hass)
    
    disable_group_types = set(config_entry.options.get(CONF_DISABLED_GROUPS) or [])
    for group_data in state.get("groups", {}).values():
        group_type = group_data.get("type")
        group_id = group_data.get("id")
        group_label = group_data.get("label", group_id)

        # Skip groups without valid ID (defensive null-checking)
        if not group_id:
            _LOGGER.debug(
                "Skipping group without valid ID (type: %s, label: %s)",
                group_type,
                group_label or "unknown"
            )
            continue
            
        # Skip disabled group types
        if group_type in disable_group_types:
            _LOGGER.debug(
                "Skipping group '%s' (id: %s) because group type '%s' is disabled",
                group_label,
                group_id,
                group_type,
            )
            continue

        # Skip groups with no channels (zombie groups)
        # These are groups that exist in the HCU but contain no devices.
        # They should not be exposed as entities.
        channels = group_data.get("channels")
        if channels is not None and not isinstance(channels, list):
            _LOGGER.warning(
                "Group '%s' (id: %s) has malformed 'channels' data (expected list, got %s) - skipping",
                group_label,
                group_id,
                type(channels).__name__
            )
            continue

        if not channels and group_type not in ALLOWED_EMPTY_GROUPS:
            _LOGGER.debug(
                "Skipping group without channels: %s (id: %s)",
                group_label,
                group_id,
            )
            continue

        if group_type == "ALARM_SWITCHING" and group_label.endswith("_SAFETY"):
            _LOGGER.debug(
                "Skipping ALARM_SWITCHING safety group '%s' (id: %s)",
                group_label,
                group_id,
            )
            continue

        if mapping := group_type_mapping.get(group_type):

            # Only mark as valid AFTER passing all skip checks above,
            # so the device registry cleanup can remove orphaned groups.
            valid_device_ids.add(group_id)

            # Support both a single tuple and a list of tuples per group type.
            mappings = mapping if isinstance(mapping, list) else [mapping]
            for platform, entity_class, extra_kwargs in mappings:
                entity = entity_class(coordinator, client, group_data, **extra_kwargs)
                entities[platform].append(entity)
                uid = getattr(entity, "unique_id", None)
                if uid:
                    valid_entity_unique_ids.add(uid)

            groups_discovered += 1
            _LOGGER.debug(
                "Created %s group entity '%s' (id: %s, type: %s)",
                platform.value,
                group_label,
                group_id,
                group_type
            )
        else:
            # Log unknown group types to help diagnose missing entities
            # Ignore META, SECURITY and INDOOR_CLIMATE
            if group_type not in ALLOWED_EMPTY_GROUPS:
                _LOGGER.warning(
                    "Unknown group type '%s' for group '%s' (id: %s) - no entity created. "
                    "If you expected an entity for this group, please report this as an issue.",
                    group_type,
                    group_label,
                    group_id
                )
                groups_unknown_type += 1

    # Create home-level entities (alarm panel, vacation mode sensor, home sensors)
    if "home" in state:
        entity = alarm_control_panel.HcuAlarmControlPanel(coordinator, client)
        entities[Platform.ALARM_CONTROL_PANEL].append(entity)
        uid = getattr(entity, "unique_id", None)
        if uid:
            valid_entity_unique_ids.add(uid)

        entity = binary_sensor.HcuVacationModeBinarySensor(coordinator, client)
        entities[Platform.BINARY_SENSOR].append(entity)
        uid = getattr(entity, "unique_id", None)
        if uid:
            valid_entity_unique_ids.add(uid)

        for feature, mapping in HMIP_FEATURE_TO_ENTITY.items():
            if feature in (state.get("home") or {}) and mapping.get("class") == "HcuHomeSensor":
                entity = sensor.HcuHomeSensor(coordinator, client, feature, mapping)
                entities[Platform.SENSOR].append(entity)
                uid = getattr(entity, "unique_id", None)
                if uid:
                    valid_entity_unique_ids.add(uid)


    _LOGGER.info("Discovered entities: %s", {p.value: len(e) for p, e in entities.items() if e})

    # Log group discovery summary for diagnostics
    if groups_discovered > 0 or groups_unknown_type > 0:
        _LOGGER.info(
            "Group discovery summary: %d created, %d unknown types",
            groups_discovered,
            groups_unknown_type
        )

    # -------------------------------------------------------------------------
    # Device Registry Cleanup (Fix for Issue #185)
    # -------------------------------------------------------------------------
    # Remove devices from the registry that are no longer present in the HCU state
    # or are considered invalid (e.g. empty groups).


    # Find and remove orphaned devices
    # We iterate over all devices in the registry associated with this config entry
    # and check if they correspond to a valid ID in the current state.

    # Get all devices for this config entry
    entry_devices = dr.async_entries_for_config_entry(dev_reg, config_entry.entry_id)

    for device in entry_devices:
        # Check if device has an identifier in our domain
        hcu_identifier = next(
            (id_val for domain, id_val in device.identifiers if domain == DOMAIN),
            None
        )

        # If it's a HCU device/group but not in our valid list, remove it
        if hcu_identifier and hcu_identifier not in valid_device_ids:
            _LOGGER.info(
                "Removing orphaned device from registry: %s (id: %s, HCU ID: %s)",
                device.name,
                device.id,
                hcu_identifier
            )
            try:
                dev_reg.async_remove_device(device.id)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.warning(
                    "Failed to remove orphaned device '%s' (id: %s, HCU ID: %s)",
                    device.name,
                    device.id,
                    hcu_identifier,
                    exc_info=True
                )
    
    # -------------------------------------------------------------------------
    # Entity Registry Cleanup
    # -------------------------------------------------------------------------
    # Remove entity registry entries that no longer exist in the current HCU state.
    
    # Build a lookup map: unique_id -> expected domain (platform)
    # Used to detect entities that moved platforms (e.g. switch → light)
    uid_to_expected_domain: dict[str, str] = {
        uid: platform.value
        for platform, entity_list in entities.items()
        for e in entity_list
        if (uid := getattr(e, "unique_id", None))
    }
    
    ent_reg = er.async_get(hass)
    entry_entities = er.async_entries_for_config_entry(ent_reg, config_entry.entry_id)
    
    for ent in entry_entities:
        # Only touch entities belonging to this integration
        if ent.platform != DOMAIN:
            continue
        
        # Safety: very old entries could theoretically lack unique_id
        if not ent.unique_id or ent.unique_id not in valid_entity_unique_ids:
            _LOGGER.info(
                "Removing orphaned entity from registry: %s (entity_id: %s, unique_id: %s)",
                ent.name,
                ent.entity_id,
                ent.unique_id,
            )
            try:
                ent_reg.async_remove(ent.entity_id)
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.warning(
                    "Failed to remove orphaned entity '%s' (entity_id: %s, unique_id: %s)",
                    ent.name,
                    ent.entity_id,
                    ent.unique_id,
                    exc_info=True,
                )
        else:
            # Check if the entity moved to a different platform (e.g. switch → light)
            # This happens when switchVisualization changes in the Homematic IP app
            expected_domain = uid_to_expected_domain.get(ent.unique_id)
            if expected_domain and ent.domain != expected_domain:
                _LOGGER.info(
                    "Removing entity that moved platforms (%s → %s): %s (unique_id: %s)",
                    ent.domain,
                    expected_domain,
                    ent.entity_id,
                    ent.unique_id,
                )
                try:
                    ent_reg.async_remove(ent.entity_id)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    _LOGGER.warning(
                        "Failed to remove platform-migrated entity '%s' (entity_id: %s, unique_id: %s)",
                        ent.name,
                        ent.entity_id,
                        ent.unique_id,
                        exc_info=True,
                    )
                continue
            
            # Retroactively disable entities that are ONLY newly disabled by default
            # Extract feature name from unique_id
            # We use a generator expression with max() and a default value
            # for better performance and more idiomatic code.
            feature = max(
                (f for f in NEWLY_DEACTIVATED_FEATURES if ent.unique_id.endswith(f"_{f}")),
                key=len,
                default=None,
            )

            if not feature:
                continue

            mapping = HMIP_FEATURE_TO_ENTITY.get(feature)
            if not (mapping and mapping.get("entity_registry_enabled_default") is False):
                continue

            # Only disable if currently active (None) to respect user overrides
            if ent.disabled_by is not None:
                continue

            _LOGGER.info(
                "Retroactively disabling entity to reduce clutter: %s (entity_id: %s, feature: %s)",
                ent.name or ent.entity_id,
                ent.entity_id,
                feature,
            )
            try:
                ent_reg.async_update_entity(
                    ent.entity_id,
                    disabled_by=er.RegistryEntryDisabler.INTEGRATION
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.warning(
                    "Failed to retroactively disable entity '%s' (entity_id: %s, feature: %s)",
                    ent.name or ent.entity_id,
                    ent.entity_id,
                    feature,
                    exc_info=True,
                )

    _resolve_translation_prefixes(entities)

    return entities


def async_discover_entities_for_device(
    client: HcuApiClient,
    config_entry: ConfigEntry,
    coordinator: "HcuCoordinator",
    device_id: str,
) -> dict[Platform, list[Any]]:
    """
    Discover and instantiate entities for a single newly included device.

    Returns a dict mapping Platform to list of entity instances.
    Does not touch the device/entity registries — the caller is responsible
    for registering the new device and calling async_add_entities per platform.
    """
    device_data = client.state.get("devices", {}).get(device_id)
    if not device_data:
        _LOGGER.warning("async_discover_entities_for_device: device %s not found in state", device_id)
        return {platform: [] for platform in PLATFORMS}

    dev_entities, _ = _discover_entities_for_device(device_data, config_entry, coordinator, client)

    _LOGGER.info(
        "Inclusion discovery for device %s: %s",
        device_id,
        {p.value: len(e) for p, e in dev_entities.items() if e},
    )
    return dev_entities


def _resolve_translation_prefixes(entities: dict) -> None:
    """Set CH{n} prefix only on entities where multiple siblings share the same translation key on one device."""
    from collections import defaultdict
    groups: dict[tuple[str, str], list] = defaultdict(list)
    for platform_entities in entities.values():
        for entity in platform_entities:
            base_key = getattr(entity, "_base_translation_key", None)
            device_id = getattr(entity, "_device_id", None)
            if base_key and device_id:
                groups[(device_id, base_key)].append(entity)
    for (_, _), group in groups.items():
        has_siblings = len(group) > 1
        for entity in group:
            entity._resolve_translation_prefix(has_siblings)

