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
    sensor,
    siren,
    switch,
    text,
    update,
)
from .api import HcuApiClient
from .const import (
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
    MANDATORY_RF_FEATURES,
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

async def async_discover_entities(
    hass: HomeAssistant,
    client: HcuApiClient,
    config_entry: ConfigEntry,
    coordinator: HcuCoordinator,
) -> dict[Platform, list[Any]]:
    """
    Discover and instantiate all entities for the integration.
    
    This function processes the HCU state data and creates appropriate
    Home Assistant entities based on device types, channel types, and features.
    """
    entities: dict[Platform, list[Any]] = {platform: [] for platform in PLATFORMS}
    state = client.state
    valid_entity_unique_ids: set[str] = set()
    
    class_module_map = {
        "HcuLight": light,
        "HcuSwitchLight": light,
        "HcuNotificationLight": light,
        "HcuSiren": siren,
        "HcuSwitch": switch,
        "HcuWateringSwitch": switch,
        "HcuConfigUseInternalOnTime": switch,
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
        "HcuSmokeBinarySensor": binary_sensor,
        "HcuUnreachBinarySensor": binary_sensor,
        "HcuVacationModeBinarySensor": binary_sensor,
    }

    for device_data in state.get("devices", {}).values():
        # Check if manufacturer is disabled via options
        manufacturer = get_device_manufacturer(device_data)
        if manufacturer != MANUFACTURER_EQ3:
            # Check for new disabled_oems list (v1.19.0+)
            disabled_oems = config_entry.options.get("disabled_oems")
            
            is_disabled = False
            if disabled_oems is not None:
                 if manufacturer in disabled_oems:
                     is_disabled = True
            else:
                # Fallback to legacy keys (pre-v1.19.0)
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
                continue

        if device_data.get("updateState") is not None and device_data.get("availableFirmwareVersion") not in (None, "", "UNKNOWN"):
            entity = update.HcuFirmwareUpdate(coordinator, client, device_data, "0")
            entities[Platform.UPDATE].append(entity)
            uid = getattr(entity, "unique_id", None)
            if uid:
                valid_entity_unique_ids.add(uid)

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
            
            #First check if a channel role is found.
            if channel_role in HMIP_CHANNEL_ROLE_TO_ENTITY:
                base_channel_type = channel_role
                channel_mapping = HMIP_CHANNEL_ROLE_TO_ENTITY[base_channel_type]
            elif channel_type:
                # Fallback: Match channel type, including indexed variants (e.g., SWITCH_CHANNEL_1)
                if channel_type in HMIP_CHANNEL_TYPE_TO_ENTITY:
                    base_channel_type = channel_type
                    channel_mapping = HMIP_CHANNEL_TYPE_TO_ENTITY[base_channel_type]
                else:
                    for base_type in HMIP_CHANNEL_TYPE_TO_ENTITY:
                        if channel_type.startswith(base_type):
                            base_channel_type = base_type
                            channel_mapping = HMIP_CHANNEL_TYPE_TO_ENTITY[base_channel_type]
                            break

            # Create channel-based entities (lights, switches, covers, locks, event)
            if channel_mapping:
                class_name = channel_mapping["class"]
                if is_unused_channel:
                    continue

                # Note: Some channels serve multiple functions (e.g., HmIP-BSL NOTIFICATION_LIGHT_CHANNEL)
                # - These channels create light entities for backlight control
                # - They ALSO respond to button presses via DEVICE_CHANNEL_EVENT
                # - Button events are handled in __init__.py via _handle_device_channel_events
                # - See MULTI_FUNCTION_CHANNEL_DEVICES in const.py for device-specific mappings
                if module := class_module_map.get(class_name):
                    try:
                        if not is_unused_device_channel:
                            entity_class = getattr(module, class_name)
                            platform = getattr(entity_class, "PLATFORM")
                            
                            # Determine the correct entity class based on switchVisualization
                            if class_name == "HcuSwitch":
                                switch_visualization = channel_data.get("switchVisualization")
                                if switch_visualization == "LIGHT":
                                    # Register as LightEntity instead of SwitchEntity
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
                                valid_entity_unique_ids.add(uid)
                        else:
                            _LOGGER.debug(
                                "Skipping unconfigured channel %s (%s) on device %s (%s)",
                                channel_index,
                                channel_type,
                                device_data.get("id"),
                                device_data.get("label"),
                            )
                            
                        # Add additional entities defined in the registry for this channel
                        # Some channels create multiple entities (e.g., Lock + Unlatch Button)
                        for extra_cfg in channel_mapping.get("extra_entities", []):
                            # Backward compatible: old style with just "HcuSomeEntity"
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
                                        valid_entity_unique_ids.add(extra_uid)
                        
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

            # Handle multi-function channels (e.g., HmIP-BSL NOTIFICATION_LIGHT_CHANNEL)
            # These channels serve multiple purposes and need additional event entities
            device_type = device_data.get("type")
            if device_type in MULTI_FUNCTION_CHANNEL_DEVICES:
                multi_func_config = MULTI_FUNCTION_CHANNEL_DEVICES[device_type].get(base_channel_type or channel_type)
                if multi_func_config and "button" in multi_func_config.get("functions", []):
                    # Create additional button event entity for multi-function channel
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
                            valid_entity_unique_ids.add(uid)
                    except (AttributeError, TypeError) as e:
                        _LOGGER.error(
                            "Failed to create button event entity for device %s, channel %s (type: %s): %s",
                            device_data.get("id"), channel_index, channel_type, e
                        )

            # Create temperature sensor (prioritize actualTemperature over valveActualTemperature)
            temp_features = {"actualTemperature", "valveActualTemperature"}
            found_temp_feature = next((f for f in temp_features if f in channel_data), None)
            if found_temp_feature:
                try:
                    mapping = HMIP_FEATURE_TO_ENTITY[found_temp_feature]
                    entity = sensor.HcuTemperatureSensor(coordinator, client, device_data, channel_index, found_temp_feature, mapping)
                    entities[Platform.SENSOR].append(entity)
                    uid = getattr(entity, "unique_id", None)
                    if uid:
                        valid_entity_unique_ids.add(uid)

                    processed_features.update(temp_features)
                except (AttributeError, TypeError) as e:
                    _LOGGER.error("Failed to create temperature sensor for %s: %s", device_data.get("id"), e)

            # Create generic feature-based entities (sensors, binary sensors, buttons)
            for feature, mapping in HMIP_FEATURE_TO_ENTITY.items():
                if feature in processed_features or feature not in channel_data:
                    continue

                # Skip HcuHomeSensor entities as they are home-level sensors handled separately
                if mapping.get("class") == "HcuHomeSensor":
                    continue

                # Skip dutyCycleLevel sensor for the main HCU device to avoid redundancy
                # with the home-level dutyCycle sensor (HcuHomeSensor)
                if feature == "dutyCycleLevel" and device_data.get("id") == client.hcu_device_id:
                    continue

                # Hardware Support Guard:
                # If a feature is null, we only create the entity if:
                # It belongs to our mandatory whitelist (features known to be transiently null on RF devices)
                if channel_data[feature] is None:
                    if _should_skip_null_feature(feature, channel_data):
                        _LOGGER.debug(
                            "Skipping unsupported feature '%s' on %s: value is null and not in mandatory whitelist or supported optional features",
                            feature, device_data.get("id")
                        )
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
                            valid_entity_unique_ids.add(uid)

                        # Add reset button for energy counters
                        if feature == "energyCounter":
                            entity = button.HcuResetEnergyButton(coordinator, client, device_data, channel_index)
                            entities[Platform.BUTTON].append(entity)
                            uid = getattr(entity, "unique_id", None)
                            if uid:
                                valid_entity_unique_ids.add(uid)

                        # Add reset button for water volume
                        if feature == "waterVolume":
                            entity = button.HcuResetWaterVolume(coordinator, client, device_data, channel_index)
                            entities[Platform.BUTTON].append(entity)
                            uid = getattr(entity, "unique_id", None)
                            if uid:
                                valid_entity_unique_ids.add(uid)

                        # Create companion config entity if defined (e.g. HcuConfigUseInternalOnTime for onTime).
                        # unique_id includes channel_index, so multiple channels per device are handled correctly.
                        if companion_class_name := mapping.get("config_companion"):
                            if companion_module := class_module_map.get(companion_class_name):
                                try:
                                    companion_class = getattr(companion_module, companion_class_name)
                                    companion = companion_class(coordinator, client, device_data, channel_index)
                                    entities[companion.PLATFORM].append(companion)
                                    c_uid = getattr(companion, "unique_id", None)
                                    if c_uid:
                                        valid_entity_unique_ids.add(c_uid)
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

            # Optional features via supportedOptionalFeatures (channel-level dict: feature -> bool)
            supported_map = channel_data.get("supportedOptionalFeatures") or {}
            
            for feature, mapping in HMIP_OPTIONAL_FEATURE_TO_ENTITY.items():
                # Directly check whether the optional feature is supported (must be True)
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
            
                # Avoid creating duplicates if the value key is already handled by HMIP_FEATURE_TO_ENTITY
                if requires_data_key and data_key in HMIP_FEATURE_TO_ENTITY:
                    continue
            
                # For value-based optional features, only create an entity if the data key exists and is not None
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
            
                    # Select the constructor explicitly based on the mapping flag
                    if mapping.get("simple_init", False):
                        # Use a simpler __init__ signature for action-style entities (e.g., identify button)
                        entity = entity_class(coordinator, client, device_data, channel_index)
                    else:
                        # Use the full __init__ signature for feature/value-based entities
                        entity = entity_class(
                            coordinator, client, device_data, channel_index, feature_arg, entity_mapping
                        )
            
                    entities[platform].append(entity)
                    uid = getattr(entity, "unique_id", None)
                    if uid:
                        valid_entity_unique_ids.add(uid)

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


            # Special handling for dutyCycle binary sensor (device-level warning flag)
            # Note: dutyCycle exists in both home object (percentage) and device channels (boolean)
            # This is handled separately to avoid key collision in HMIP_FEATURE_TO_ENTITY
            if "dutyCycle" in channel_data and isinstance(channel_data["dutyCycle"], bool):
                try:
                    entity_mapping = DUTY_CYCLE_BINARY_SENSOR_MAPPING.copy()
                    if is_deactivated_by_default:
                        entity_mapping["entity_registry_enabled_default"] = not is_unused_channel
                    entity = binary_sensor.HcuBinarySensor(coordinator, client, device_data, channel_index, "dutyCycle", entity_mapping)
                    entities[Platform.BINARY_SENSOR].append(entity)
                    uid = getattr(entity, "unique_id", None)
                    if uid:
                        valid_entity_unique_ids.add(uid)

                except (AttributeError, TypeError) as e:
                    _LOGGER.error("Failed to create dutyCycle binary sensor for device %s: %s", device_data.get("id"), e)

    # Create group entities using type mapping
    # Maps group type to (platform, entity_class, extra_kwargs)
    group_type_mapping = {
        "HEATING": (Platform.CLIMATE, climate.HcuClimate, {"config_entry": config_entry}),
        "SHUTTER": (Platform.COVER, cover.HcuCoverGroup, {}),
        "SWITCHING": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "SWITCHING_PROFILE": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "LINKED_SWITCHING": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "LIGHT": (Platform.LIGHT, light.HcuLightGroup, {}),
        "EXTENDED_LINKED_SWITCHING": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "EXTENDED_LINKED_SHUTTER": (Platform.COVER, cover.HcuCoverGroup, {}),
        "EXTENDED_LINKED_NOTIFICATION": (Platform.LIGHT, light.HcuLightGroup, {}),
        "EXTENDED_LINKED_WATERING": (Platform.SWITCH, switch.HcuWateringGroup, {}),
        "EXTENDED_LINKED_GARAGE_DOOR": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
        "HEATING_COOLING_DEMAND_BOILER": (Platform.BINARY_SENSOR, binary_sensor.HcuHeatDemandBinarySensorGroup, {}),
        "HEATING_COOLING_DEMAND_PUMP": (Platform.BINARY_SENSOR, binary_sensor.HcuHeatDemandBinarySensorGroup, {}),
        "HOT_WATER": (Platform.SWITCH, switch.HcuSwitchGroup, {}),
    }

    # Track group discovery statistics for diagnostics
    groups_discovered = 0
    groups_unknown_type = 0
    
    # Initialize valid device IDs with physical devices (and HCU itself if present in devices)
    # We will also add valid group IDs to this set during the group discovery loop to avoid
    # a second iteration over groups later.
    valid_device_ids = set(state.get("devices", {}).keys())

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

        if mapping := group_type_mapping.get(group_type):

            # Only mark as valid AFTER passing all skip checks above,
            # so the device registry cleanup can remove orphaned groups.
            valid_device_ids.add(group_id)

            platform, entity_class, extra_kwargs = mapping
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
            if feature in state["home"] and mapping.get("class") == "HcuHomeSensor":
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

    return entities

def _should_skip_null_feature(feature: str, channel_data: dict) -> bool:
    """
    Determine whether to skip creating an entity for a feature that has a null value.
    """
    # Manual whitelist for primary features that aren't listed as optional
    # but are core to the device's function and may be null at startup.
    is_mandatory_rf = feature in MANDATORY_RF_FEATURES
    
    # Also check if the feature is explicitly supported, even if its value is null.
    supported_map = channel_data.get("supportedOptionalFeatures", {})
    # For features in HMIP_FEATURE_TO_ENTITY, we check if they are supported by name
    # or by their IFeature/IOptionalFeature variant.
    feature_variants = (
        feature,
        f"IFeature{feature[0].upper()}{feature[1:]}",
        f"IOptionalFeature{feature[0].upper()}{feature[1:]}",
    )
    is_optional_supported = any(
        supported_map.get(v, False) for v in feature_variants
    )
    
    return not (is_mandatory_rf or is_optional_supported)
