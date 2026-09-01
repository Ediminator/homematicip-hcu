# custom_components/hcu_integration/const.py
"""Constants for the Homematic IP Local (HCU) integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchDeviceClass
from homeassistant.const import (
    CONCENTRATION_PARTS_PER_MILLION,
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    Platform,
    UnitOfEnergy,
    UnitOfLength,
    UnitOfPower,
    UnitOfPrecipitationDepth,
    UnitOfSpeed,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfElectricPotential,
    UnitOfFrequency,
    EntityCategory,
)
from typing import Final, Any

# Domain of the integration
DOMAIN = "hcu_integration"

# Platforms to be set up by this integration
PLATFORMS: list[Platform] = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
    Platform.VALVE,
    Platform.TEXT,
    Platform.UPDATE,
]

# --- API and Plugin Constants ---
PLUGIN_ID = "de.homeassistant.hcu.integration"
PLUGIN_FRIENDLY_NAME = {
    "de": "Home Assistant Integration",
    "en": "Home Assistant Integration",
}
PLUGIN_VERSION = "2.2.5"
PLUGIN_DOCUMENTATION_URL = "https://github.com/Ediminator/homematicip-hcu"
PLUGIN_ISSUE_TRACKER_URL = "https://github.com/Ediminator/homematicip-hcu/issues"

# --- Auth Type Constants ---
CONF_AUTH_TYPE = "auth_type"
AUTH_TYPE_PLUGIN = "plugin"
AUTH_TYPE_APP = "app"
AUTH_TYPE_DUAL = "app+plugin"   # DualBridge: App User primary + Plugin User secondary
CONF_APP_TOKEN = "app_token"
CONF_APP_CLIENT_ID = "app_client_id"

# --- Fixed HCU Ports (DualBridge — not user-configurable) ---
HCU_REST_PORT: Final = 6969       # App User REST + Auth
HCU_PLUGIN_WS_PORT: Final = 9001  # Plugin User WebSocket
HCU_APP_WS_PORT: Final = 8888     # App User WebSocket (Events)

# --- Configuration Constants ---
CONF_PIN = "pin"
CONF_DEVICE_PINS = "device_pins"
CONF_AUTH_PORT = "auth_port"
CONF_WEBSOCKET_PORT = "websocket_port"
CONF_PLUGIN_TOKEN = "plugin_token"
CONF_PLUGIN_CLIENT_ID = "plugin_client_id"
CONF_HCU_SGTIN = "hcu_sgtin"
# mDNS service name/type recorded from zeroconf discovery. Used to re-query
# zeroconf for all of the HCU's currently known addresses (e.g. WLAN and
# Ethernet), so a MAC address connection can be registered for each.
CONF_ZEROCONF_NAME = "zeroconf_name"
CONF_ZEROCONF_TYPE = "zeroconf_type"
CONF_ENTITY_PREFIX = "entity_prefix"
# Opt-in, developer-mode-only (see CONF_DEV): while re-pairing (reconfigure/
# reauth) with dev mode enabled, the entry gets its own unique plugin ID
# (PLUGIN_ID + a random 6-char suffix, decided once since it must match what
# was sent in the auth token request) so multiple HA instances can pair with
# the same HCU without colliding on a single shared plugin identity. Everyone
# else — including every brand-new pairing, where dev mode can't yet be set —
# stays on the plain PLUGIN_ID. Purely additive: entries without dev mode
# enabled simply don't have this key, and every read site falls back to the
# plain PLUGIN_ID via `... or PLUGIN_ID` — no config entry version bump or
# migration needed, so downgrading the integration afterwards is unaffected.
CONF_UNIQUE_PLUGIN_ID = "unique_plugin_id"
# Legacy field names — kept only for use in migration code
CONF_CLIENT_ID = "client_id"
CONF_ACCESS_POINT_ID = "access_point_id"
CONF_PLATFORM_OVERRIDES = "platform_overrides"  # Dict mapping entity unique_id to platform override
DEFAULT_HCU_AUTH_PORT = 6969
DEFAULT_HCU_WEBSOCKET_PORT = 9001
CONF_ADVANCED_DEBUGGING = "advanced_debugging"
CONF_ADVANCED_ATTRIBUTES = "advanced_attributes"
CONF_DISABLE_UNCONFIGURED_CHANNELS = "disable_unconfigured_channels"
CONF_COMFORT_TEMPERATURE = "comfort_temperature"
CONF_DISABLED_OEMS = "disabled_oems"
CONF_DISABLED_GROUPS = "disabled_groups"
CONF_AUTO_RELOAD_ON_DEVICE_CHANGE = "auto_reload_on_device_change"
CONF_HA_ENTITIES = "ha_entities"  # legacy — superseded by CONF_HA_DEVICES
CONF_HA_DEVICES = "ha_devices"

# HCU device ID prefix for devices contributed by the HA Entity Bridge itself
# (see ha_entity_bridge.py). Once included, the HCU reports these back in its
# regular device list just like any other plugin-contributed device, so
# discovery.py must recognize and skip them to avoid re-importing an HA
# entity we ourselves bridged out as a brand-new HA device/entity.
HA_DEVICE_ID_PREFIX = "ha."

# Feature type keys used in ha_devices[].features
HA_FEATURE_ON_OFF = "on_off"
HA_FEATURE_BRIGHTNESS = "brightness"
HA_FEATURE_COLOR_TEMP = "color_temp"
HA_FEATURE_RGB_COLOR = "rgb_color"
HA_FEATURE_ON_TIME = "on_time"
HA_FEATURE_TEMPERATURE = "temperature"
HA_FEATURE_HUMIDITY = "humidity"
HA_FEATURE_ILLUMINANCE = "illuminance"
HA_FEATURE_CO2 = "co2"
HA_FEATURE_WIND_SPEED = "wind_speed"
HA_FEATURE_PRECIPITATION = "precipitation"
HA_FEATURE_STORM = "storm"
HA_FEATURE_SUNSHINE = "sunshine"
HA_FEATURE_RAINING = "raining"
HA_FEATURE_WIND_DIRECTION = "wind_direction"
HA_FEATURE_SUNSHINE_DURATION = "sunshine_duration"
HA_FEATURE_POWER = "power"
HA_FEATURE_ENERGY = "energy"
HA_FEATURE_PM1 = "pm1"
HA_FEATURE_PM25 = "pm25"
HA_FEATURE_PM10 = "pm10"
HA_FEATURE_MOTION = "motion"
HA_FEATURE_OCCUPANCY = "occupancy"
# Superseded by HA_FEATURE_CONTACT_SENSOR below — both mapped onto the same
# Connect API feature (contactSensorState) and are kept only so devices
# saved before that consolidation keep working. Not offered in the UI.
HA_FEATURE_DOOR = "door"
HA_FEATURE_WINDOW = "window"
HA_FEATURE_CONTACT_SENSOR = "contact_sensor"
HA_FEATURE_SMOKE = "smoke"
HA_FEATURE_MOISTURE = "moisture"
HA_FEATURE_MOISTURE_DETECTED = "moisture_detected"
HA_FEATURE_BATTERY = "battery"
HA_FEATURE_VEHICLE_RANGE = "vehicle_range"
HA_FEATURE_CLIMATE_OPERATION_MODE = "climate_operation_mode"
HA_FEATURE_COOLING_TEMP_OFFSET = "cooling_temp_offset"
HA_FEATURE_HEATING_TEMP_OFFSET = "heating_temp_offset"
HA_FEATURE_PRESENCE_MODE = "presence_mode"
HA_FEATURE_HOT_WATER_BOOST = "hot_water_boost"
HA_FEATURE_SUPPLY_TEMPERATURE = "supply_temperature"
HA_FEATURE_SET_POINT_TEMP = "set_point_temp"
HA_FEATURE_SHUTTER_LEVEL = "shutter_level"
HA_FEATURE_SLATS_LEVEL = "slats_level"
HA_FEATURE_SHUTTER_DIRECTION = "shutter_direction"

# Maintenance is a composite feature: up to 3 independent HA entities combine
# into a single HCU "maintenance" feature object. Available for every device type.
HA_FEATURE_LOW_BAT = "low_bat"
HA_FEATURE_SABOTAGE = "sabotage"
HA_FEATURE_UNREACH = "unreach"
HA_MAINTENANCE_FEATURE_KEYS = (HA_FEATURE_LOW_BAT, HA_FEATURE_SABOTAGE, HA_FEATURE_UNREACH)

# Which HA domains each feature accepts
HA_FEATURE_DOMAINS: dict[str, list[str]] = {
    HA_FEATURE_ON_OFF:        ["switch", "light"],
    HA_FEATURE_BRIGHTNESS:    ["light"],
    HA_FEATURE_COLOR_TEMP:    ["light"],
    HA_FEATURE_RGB_COLOR:     ["light"],
    HA_FEATURE_ON_TIME:       ["number", "input_number"],
    HA_FEATURE_TEMPERATURE:   ["sensor"],
    HA_FEATURE_HUMIDITY:      ["sensor"],
    HA_FEATURE_ILLUMINANCE:   ["sensor"],
    HA_FEATURE_CO2:           ["sensor"],
    HA_FEATURE_WIND_SPEED:    ["sensor"],
    HA_FEATURE_PRECIPITATION: ["sensor"],
    HA_FEATURE_STORM:         ["binary_sensor"],
    HA_FEATURE_SUNSHINE:      ["binary_sensor"],
    HA_FEATURE_RAINING:       ["binary_sensor"],
    HA_FEATURE_WIND_DIRECTION: ["sensor"],
    HA_FEATURE_SUNSHINE_DURATION: ["sensor"],
    HA_FEATURE_POWER:         ["sensor"],
    HA_FEATURE_ENERGY:        ["sensor"],
    HA_FEATURE_PM1:           ["sensor"],
    HA_FEATURE_PM25:          ["sensor"],
    HA_FEATURE_PM10:          ["sensor"],
    HA_FEATURE_MOTION:        ["binary_sensor"],
    HA_FEATURE_OCCUPANCY:     ["binary_sensor"],
    HA_FEATURE_DOOR:          ["binary_sensor"],
    HA_FEATURE_WINDOW:        ["binary_sensor"],
    HA_FEATURE_CONTACT_SENSOR: ["binary_sensor"],
    HA_FEATURE_SMOKE:         ["binary_sensor"],
    HA_FEATURE_MOISTURE:      ["binary_sensor"],
    HA_FEATURE_MOISTURE_DETECTED: ["binary_sensor"],
    HA_FEATURE_BATTERY:       ["sensor"],
    HA_FEATURE_VEHICLE_RANGE: ["sensor"],
    HA_FEATURE_CLIMATE_OPERATION_MODE: ["select"],
    HA_FEATURE_COOLING_TEMP_OFFSET: ["number", "input_number"],
    HA_FEATURE_HEATING_TEMP_OFFSET: ["number", "input_number"],
    HA_FEATURE_PRESENCE_MODE: ["select"],
    HA_FEATURE_HOT_WATER_BOOST: ["switch", "input_boolean"],
    HA_FEATURE_SUPPLY_TEMPERATURE: ["sensor"],
    HA_FEATURE_SET_POINT_TEMP: ["number", "input_number"],
    HA_FEATURE_SHUTTER_LEVEL: ["number", "input_number"],
    HA_FEATURE_SLATS_LEVEL:   ["number", "input_number"],
    HA_FEATURE_SHUTTER_DIRECTION: ["sensor", "select"],
    HA_FEATURE_LOW_BAT:       ["binary_sensor"],
    HA_FEATURE_SABOTAGE:      ["binary_sensor"],
    HA_FEATURE_UNREACH:       ["binary_sensor"],
}

# HCU device types selectable in the "Add device" step, each mapped to the
# subset of HA_FEATURE_* fields relevant for that type. "Maintenance"
# (HA_MAINTENANCE_FEATURE_KEYS) is available as an optional add-on for every
# type and is therefore not repeated below.
HA_DEVICE_TYPE_LIGHT = "LIGHT"
HA_DEVICE_TYPE_SWITCH = "SWITCH"
HA_DEVICE_TYPE_ENERGY_METER = "ENERGY_METER"
HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR = "PARTICULATE_MATTER_SENSOR"
HA_DEVICE_TYPE_CLIMATE_SENSOR = "CLIMATE_SENSOR"
HA_DEVICE_TYPE_OCCUPANCY_SENSOR = "OCCUPANCY_SENSOR"
HA_DEVICE_TYPE_CONTACT_SENSOR = "CONTACT_SENSOR"
HA_DEVICE_TYPE_SMOKE_ALARM = "SMOKE_ALARM"
HA_DEVICE_TYPE_WATER_SENSOR = "WATER_SENSOR"
HA_DEVICE_TYPE_BATTERY = "BATTERY"
HA_DEVICE_TYPE_EV_CHARGER = "EV_CHARGER"
HA_DEVICE_TYPE_GRID_CONNECTION_POINT = "GRID_CONNECTION_POINT"
HA_DEVICE_TYPE_HEAT_PUMP = "HEAT_PUMP"
HA_DEVICE_TYPE_HVAC = "HVAC"
HA_DEVICE_TYPE_INVERTER = "INVERTER"
HA_DEVICE_TYPE_SWITCH_INPUT = "SWITCH_INPUT"
HA_DEVICE_TYPE_THERMOSTAT = "THERMOSTAT"
HA_DEVICE_TYPE_VEHICLE = "VEHICLE"
HA_DEVICE_TYPE_WINDOW_COVERING = "WINDOW_COVERING"

HA_DEVICE_TYPE_FEATURES: dict[str, dict[str, list[str]]] = {
    HA_DEVICE_TYPE_LIGHT: {
        "required": [HA_FEATURE_ON_OFF],
        "optional": [HA_FEATURE_BRIGHTNESS, HA_FEATURE_COLOR_TEMP, HA_FEATURE_RGB_COLOR, HA_FEATURE_ON_TIME],
    },
    HA_DEVICE_TYPE_SWITCH: {
        "required": [HA_FEATURE_ON_OFF],
        "optional": [HA_FEATURE_ON_TIME],
    },
    HA_DEVICE_TYPE_ENERGY_METER: {
        "required": [],
        "optional": [HA_FEATURE_POWER, HA_FEATURE_ENERGY],
    },
    HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR: {
        "required": [],
        "optional": [HA_FEATURE_PM1, HA_FEATURE_PM25, HA_FEATURE_PM10],
    },
    HA_DEVICE_TYPE_CLIMATE_SENSOR: {
        "required": [],
        "optional": [HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY, HA_FEATURE_ILLUMINANCE,
                     HA_FEATURE_CO2, HA_FEATURE_WIND_SPEED, HA_FEATURE_PRECIPITATION,
                     HA_FEATURE_STORM, HA_FEATURE_SUNSHINE, HA_FEATURE_RAINING,
                     HA_FEATURE_WIND_DIRECTION, HA_FEATURE_SUNSHINE_DURATION],
    },
    HA_DEVICE_TYPE_OCCUPANCY_SENSOR: {
        # The Connect API only has a single PresenceDetected feature — HA's
        # separate "motion" concept has no feature of its own to map to, so
        # it isn't offered here (it would just collide with "occupancy" on
        # the wire). Kept in HA_FEATURE_DOMAINS/HA_FEATURE_MOTION only so
        # devices saved before this change keep working at runtime.
        "required": [HA_FEATURE_OCCUPANCY],
        "optional": [],
    },
    HA_DEVICE_TYPE_CONTACT_SENSOR: {
        # "Door" and "window" both mapped to the same ContactSensorState
        # feature and have been consolidated into this one generic key —
        # only one entity selector is offered so a device can't accidentally
        # be configured with two entities for the same feature. HA_FEATURE_
        # DOOR/WINDOW are kept in HA_FEATURE_DOMAINS only for devices saved
        # before this change (see LEGACY_FEATURE_FALLBACK below).
        "required": [HA_FEATURE_CONTACT_SENSOR],
        "optional": [],
    },
    HA_DEVICE_TYPE_SMOKE_ALARM: {
        "required": [HA_FEATURE_SMOKE],
        "optional": [],
    },
    HA_DEVICE_TYPE_WATER_SENSOR: {
        "required": [HA_FEATURE_MOISTURE],
        "optional": [HA_FEATURE_MOISTURE_DETECTED],
    },
    HA_DEVICE_TYPE_BATTERY: {
        "required": [HA_FEATURE_BATTERY],
        "optional": [HA_FEATURE_POWER, HA_FEATURE_ENERGY],
    },
    HA_DEVICE_TYPE_EV_CHARGER: {
        "required": [HA_FEATURE_POWER],
        "optional": [HA_FEATURE_ENERGY],
    },
    HA_DEVICE_TYPE_GRID_CONNECTION_POINT: {
        "required": [HA_FEATURE_POWER],
        "optional": [HA_FEATURE_ENERGY],
    },
    HA_DEVICE_TYPE_HEAT_PUMP: {
        "required": [HA_FEATURE_CLIMATE_OPERATION_MODE],
        "optional": [HA_FEATURE_COOLING_TEMP_OFFSET, HA_FEATURE_HEATING_TEMP_OFFSET,
                     HA_FEATURE_PRESENCE_MODE, HA_FEATURE_HOT_WATER_BOOST, HA_FEATURE_SUPPLY_TEMPERATURE],
    },
    HA_DEVICE_TYPE_HVAC: {
        "required": [HA_FEATURE_POWER],
        "optional": [HA_FEATURE_ENERGY],
    },
    HA_DEVICE_TYPE_INVERTER: {
        "required": [HA_FEATURE_POWER],
        "optional": [HA_FEATURE_ENERGY],
    },
    HA_DEVICE_TYPE_SWITCH_INPUT: {
        "required": [],
        "optional": [],
    },
    HA_DEVICE_TYPE_THERMOSTAT: {
        "required": [HA_FEATURE_SET_POINT_TEMP],
        "optional": [HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY, HA_FEATURE_CO2],
    },
    HA_DEVICE_TYPE_VEHICLE: {
        "required": [HA_FEATURE_BATTERY],
        "optional": [HA_FEATURE_VEHICLE_RANGE],
    },
    HA_DEVICE_TYPE_WINDOW_COVERING: {
        "required": [HA_FEATURE_SHUTTER_LEVEL],
        "optional": [HA_FEATURE_SLATS_LEVEL, HA_FEATURE_SHUTTER_DIRECTION],
    },
}

# Feature keys that replaced one or more older keys offered in the options
# flow before all of them were found to map onto the same Connect API
# feature (see the comments on OCCUPANCY_SENSOR/CONTACT_SENSOR above). The
# options flow form uses this so a device saved under an old key still
# shows/keeps its configured entity when edited under the new one, instead
# of the field silently going empty. Checked in order, first match wins.
LEGACY_FEATURE_FALLBACK: dict[str, tuple[str, ...]] = {
    HA_FEATURE_OCCUPANCY: (HA_FEATURE_MOTION,),
    HA_FEATURE_CONTACT_SENSOR: (HA_FEATURE_DOOR, HA_FEATURE_WINDOW),
}


def determine_ha_device_type(features: dict[str, str]) -> str:
    """Best-effort inference of the HCU device type from a ha_devices[].features
    mapping. Used as a fallback for devices saved before the explicit "type"
    field was introduced; new devices persist the type chosen in the UI instead,
    since several types (e.g. EV_CHARGER vs. ENERGY_METER) share the same
    feature keys and cannot be told apart from the features alone.
    """
    keys = set(features)
    if keys & {HA_FEATURE_BRIGHTNESS, HA_FEATURE_COLOR_TEMP, HA_FEATURE_RGB_COLOR}:
        return HA_DEVICE_TYPE_LIGHT
    if HA_FEATURE_ON_OFF in keys:
        return HA_DEVICE_TYPE_LIGHT if features[HA_FEATURE_ON_OFF].startswith("light.") else HA_DEVICE_TYPE_SWITCH
    if HA_FEATURE_CLIMATE_OPERATION_MODE in keys:
        return HA_DEVICE_TYPE_HEAT_PUMP
    if HA_FEATURE_SET_POINT_TEMP in keys:
        return HA_DEVICE_TYPE_THERMOSTAT
    if HA_FEATURE_SHUTTER_LEVEL in keys:
        return HA_DEVICE_TYPE_WINDOW_COVERING
    if keys & {HA_FEATURE_POWER, HA_FEATURE_ENERGY}:
        return HA_DEVICE_TYPE_ENERGY_METER
    if keys & {HA_FEATURE_PM1, HA_FEATURE_PM25, HA_FEATURE_PM10}:
        return HA_DEVICE_TYPE_PARTICULATE_MATTER_SENSOR
    if keys & {HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY, HA_FEATURE_ILLUMINANCE,
               HA_FEATURE_CO2, HA_FEATURE_WIND_SPEED, HA_FEATURE_PRECIPITATION,
               HA_FEATURE_STORM, HA_FEATURE_SUNSHINE, HA_FEATURE_RAINING,
               HA_FEATURE_WIND_DIRECTION, HA_FEATURE_SUNSHINE_DURATION}:
        return HA_DEVICE_TYPE_CLIMATE_SENSOR
    if keys & {HA_FEATURE_MOTION, HA_FEATURE_OCCUPANCY}:
        return HA_DEVICE_TYPE_OCCUPANCY_SENSOR
    if keys & {HA_FEATURE_DOOR, HA_FEATURE_WINDOW, HA_FEATURE_CONTACT_SENSOR}:
        return HA_DEVICE_TYPE_CONTACT_SENSOR
    if HA_FEATURE_SMOKE in keys:
        return HA_DEVICE_TYPE_SMOKE_ALARM
    if keys & {HA_FEATURE_MOISTURE, HA_FEATURE_MOISTURE_DETECTED}:
        return HA_DEVICE_TYPE_WATER_SENSOR
    if HA_FEATURE_VEHICLE_RANGE in keys:
        return HA_DEVICE_TYPE_VEHICLE
    if HA_FEATURE_BATTERY in keys:
        return HA_DEVICE_TYPE_BATTERY
    return HA_DEVICE_TYPE_SWITCH


DEFAULT_ADVANCED_DEBUGGING = False
CONF_DEV = "dev"
DEFAULT_DEV = False
DEFAULT_ADVANCED_ATTRIBUTES = False
DEFAULT_DISABLE_UNCONFIGURED_CHANNELS = True
DEFAULT_AUTO_RELOAD_ON_DEVICE_CHANGE = True
DEFAULT_COMFORT_TEMPERATURE = 21.0
DEFAULT_MIN_TEMP = 5.0
DEFAULT_MAX_TEMP = 30.0

# --- Actuator specific Constants ---
HMIP_ON_TIME_INFINITE = 111600

# --- Manufacturer Constants ---
MANUFACTURER_EQ3 = "eQ-3"
MANUFACTURER_HUE = "Philips Hue"
MANUFACTURER_3RD_PARTY = "3rd Party"

# --- Device Identification Constants ---
PLUGIN_ID_HUE = "de.eq3.plugin.hue"
DEVICE_TYPE_PLUGIN_EXTERNAL = "PLUGIN_EXTERNAL"
HUE_MODEL_TOKEN = "Hue"
HOMEMATIC_MODEL_PREFIXES = ("HmIP-", "HmIPW-", "HM-", "ALPHA-", "ELV")

# --- Documentation URLs ---
DOCS_URL_LOCK_PIN_CONFIG = "https://github.com/Ediminator/homematicip-hcu#step-4-configure-door-lock-pin-optional"

# --- Channel Type Constants ---
CHANNEL_TYPE_MULTI_MODE_INPUT_TRANSMITTER = "MULTI_MODE_INPUT_TRANSMITTER"
CHANNEL_TYPE_MULTI_MODE_INPUT = "MULTI_MODE_INPUT_CHANNEL"
CHANNEL_TYPE_ALARM_SIREN = "ALARM_SIREN_CHANNEL"

# --- Timing Constants ---
WEBSOCKET_CONNECT_TIMEOUT = 10
PLUGIN_HANDSHAKE_TIMEOUT = 30
WEBSOCKET_RECONNECT_INITIAL_DELAY = 5
WEBSOCKET_RECONNECT_MAX_DELAY = 60
WEBSOCKET_RECONNECT_JITTER_MAX = 5
WEBSOCKET_HEARTBEAT_INTERVAL = 25
WEBSOCKET_RECEIVE_TIMEOUT = 30
API_REQUEST_TIMEOUT = 10
API_MAX_RETRIES = 3
API_RETRY_BASE_DELAY = 1.0

# --- Service Constants ---
SERVICE_PLAY_SOUND = "play_sound"
SERVICE_SET_RULE_STATE = "set_rule_state"
SERVICE_SET_DISPLAY_CONTENT = "set_display_content"
SERVICE_ACTIVATE_PARTY_MODE = "activate_party_mode"
SERVICE_ACTIVATE_VACATION_MODE = "activate_vacation_mode"
SERVICE_ACTIVATE_ECO_MODE = "activate_eco_mode"
SERVICE_DEACTIVATE_ABSENCE_MODE = "deactivate_absence_mode"
SERVICE_SWITCH_ON_WITH_TIME = "switch_on_with_time"
SERVICE_SEND_API_COMMAND = "send_api_command"
SERVICE_SET_COOLING_MODE = "set_cooling_mode"
SERVICE_USER_MESSAGE = "create_user_message_request"
SERVICE_USER_MESSAGE_DELETE = "delete_user_message_request"

# --- Preset Constants ---
PRESET_ECO = "eco"
PRESET_PARTY = "party"

# --- Service Attribute Constants ---
ATTR_SOUND_FILE = "sound_file"
ATTR_DURATION = "duration"
ATTR_VOLUME = "volume"
ATTR_RULE_ID = "rule_id"
ATTR_ENABLED = "enabled"
ATTR_END_TIME = "end_time"
ATTR_ON_TIME = "on_time"
ATTR_PATH = "path"
ATTR_BODY = "body"
ATTR_COOLING = "cooling"
ATTR_USER_MESSAGE_ID = "user_message_id"
ATTR_USER_MESSAGE_MESSAGE = "message"
ATTR_USER_MESSAGE_TITLE = "title"
ATTR_USER_MESSAGE_BEHAVIOR_TYPE = "behavior_type"
ATTR_USER_MESSAGE_CATEGORY = "message_category"

# --- User Message Acknowledgement Constants ---
EVENT_USER_MESSAGE_ACKNOWLEDGEMENT = f"{DOMAIN}_user_message_ack"
MSG_TYPE_USER_MESSAGE_ACK = "USER_MESSAGE_ACK_EVENT"
ATTR_USER_MESSAGE_ACKNOWLEDGEMENT_TYPE = "ack_type"

# --- API Path Constants ---
API_PATHS = {
    "ACTIVATE_ABSENCE_PERMANENT": "/hmip/home/heating/activateAbsencePermanent",
    "SET_COOLING": "/hmip/home/heating/setCooling",
    "ACTIVATE_PARTY_MODE": "/hmip/group/heating/activatePartyMode",
    "ACTIVATE_VACATION": "/hmip/home/heating/activateVacation",
    "DEACTIVATE_ABSENCE": "/hmip/home/heating/deactivateAbsence",
    "DEACTIVATE_VACATION": "/hmip/home/heating/deactivateVacation",
    "ENABLE_SIMPLE_RULE": "/hmip/rule/enableSimpleRule",
    "GET_SYSTEM_STATE": "/hmip/home/getSystemState",
    "RESET_ENERGY_COUNTER": "/hmip/device/control/resetEnergyCounter",
    "RESET_WATER_VOLUME": "/hmip/device/control/resetWaterVolume",
    "SEND_DOOR_COMMAND": "/hmip/device/control/sendDoorCommand",
    "SEND_DOOR_IMPULSE": "/hmip/device/control/startImpulse",
    "SEND_PULL_LATCH": "/hmip/device/control/pullLatch",
    "DEVICE_IDENTIFY": "/hmip/device/control/setIdentify",
    "SET_COLOR_TEMP": "/hmip/device/control/setColorTemperatureDimLevel",
    "SET_COLOR_TEMP_WITH_TIME": "/hmip/device/control/setColorTemperatureDimLevelWithTime",
    "SET_DIM_LEVEL": "/hmip/device/control/setDimLevel",
    "SET_DIM_LEVEL_WITH_TIME": "/hmip/device/control/setDimLevelWithTime",
    "SET_EPAPER_DISPLAY": "/hmip/device/control/setEpaperDisplay",
    "SET_GROUP_ACTIVE_PROFILE": "/hmip/group/heating/setActiveProfile",
    "SET_GROUP_BOOST": "/hmip/group/heating/setBoost",
    "SET_GROUP_CONTROL_MODE": "/hmip/group/heating/setControlMode",
    "SET_GROUP_SET_POINT_TEMP": "/hmip/group/heating/setSetPointTemperature",
    "SET_GROUP_SHUTTER_LEVEL": "/hmip/group/switching/setPrimaryShadingLevel",
    "SET_GROUP_SECONDARY_SHADING_LEVEL": "/hmip/group/switching/setSecondaryShadingLevel",
    "SET_HUE": "/hmip/device/control/setHueSaturationDimLevel",
    "SET_HUE_WITH_TIME": "/hmip/device/control/setHueSaturationDimLevelWithTime",
    "SET_LOCK_STATE": "/hmip/device/control/setLockState",
    "SET_OPTICAL_SIGNAL_BEHAVIOUR": "/hmip/device/control/setOpticalSignal",
    "SET_OPTICAL_SIGNAL_BEHAVIOUR_WITH_TIME": "/hmip/device/control/setOpticalSignalWithTime",
    "SET_PRIMARY_SHADING_LEVEL": "/hmip/device/control/setPrimaryShadingLevel",  # For SHADING_CHANNEL devices (e.g., HmIP-HDM1)
    "SET_SHUTTER_LEVEL": "/hmip/device/control/setShutterLevel",
    "SET_SIMPLE_RGB_COLOR_STATE": "/hmip/device/control/setSimpleRGBColorDimLevel",
    "SET_SIMPLE_RGB_COLOR_STATE_WITH_TIME": "/hmip/device/control/setSimpleRGBColorDimLevelWithTime",
    "SET_SLATS_LEVEL": "/hmip/device/control/setSlatsLevel",
    "SET_SOUND_FILE": "/hmip/device/control/setSoundFileVolumeLevelWithTime",
    "SET_SWITCH_STATE": "/hmip/device/control/setSwitchState",
    "SET_SWITCH_STATE_WITH_TIME": "/hmip/device/control/setSwitchStateWithTime",
    "SET_SWITCHING_GROUP_STATE": "/hmip/group/switching/setState",
    "TEST_ALARM_SIGNAL_ACOUSTIC": "/hmip/group/switching/alarm/testSignalAcoustic",
    "TEST_ALARM_SIGNAL_OPTICAL": "/hmip/group/switching/alarm/testSignalOptical",
    "SET_WATERING_SWITCH_STATE": "/hmip/device/control/setWateringSwitchState",
    "SET_WATERING_SWITCH_STATE_WITH_TIME": "/hmip/device/control/setWateringSwitchStateWithTime",
    "SET_GROUP_WATERING_SWITCH_STATE": "/hmip/group/linked/control/setWateringSwitchState",
    "SET_GROUP_WATERING_SWITCH_STATE_WITH_TIME": "/hmip/group/linked/control/setWateringSwitchStateWithTime",
    "SET_ZONES_ACTIVATION": "/hmip/home/security/setExtendedZonesActivation",
    "STOP_COVER": "/hmip/device/control/stop",
    "STOP_GROUP_COVER": "/hmip/group/switching/stop",
    "TOGGLE_GARAGE_DOOR_STATE": "/hmip/device/control/toggleGarageDoorState",
}

# --- Device Identification Constants ---
HCU_DEVICE_TYPES = {
    "HOME_CONTROL_ACCESS_POINT",
    "WIRED_ACCESS_POINT",
    "ACCESS_POINT",
    "WIRED_DIN_RAIL_ACCESS_POINT",
}
HCU_MODEL_TYPES = {"HmIP-HCU-1", "HmIP-HCU1-A", "HmIPW-DRAP"}

DEACTIVATED_BY_DEFAULT_DEVICES = {
    "FLOOR_TERMINAL_BLOCK_12",
    "FLOOR_TERMINAL_BLOCK_6",
    "DIN_RAIL_SWITCH_4",
    "DIN_RAIL_BLIND_4",
    "DIN_RAIL_DIMMER_3",
    "WIRED_DIN_RAIL_SWITCH_8",
    "WIRED_DIN_RAIL_BLIND_4",
    "WIRED_DIN_RAIL_DIMMER_3",
    "OPEN_COLLECTOR_MODULE_8",
    "DIGITAL_RADIO_INPUT_32",  # HmIP-DRI32 - Input-only device
}

MANDATORY_RF_FEATURES = ("windowState", "unreach")

# Devices with multi-function channels that serve dual purposes
# Maps device type to a dict of channel types that have multiple functions
# For HmIP-BSL: NOTIFICATION_LIGHT_CHANNEL serves as BOTH button input AND backlight control
MULTI_FUNCTION_CHANNEL_DEVICES = {
    "BRAND_SWITCH_NOTIFICATION_LIGHT": {
        "NOTIFICATION_LIGHT_CHANNEL": {
            "functions": ["button", "light"],
            "description": "Button input with backlight LED (channels 2-3 on HmIP-BSL)",
        }
    }
}

# --- Entity Mapping Dictionaries ---
# This mapping is used by discovery.py to create Event entities
HMIP_DEVICE_HAS_EVENT = {
    "HmIP-WRC2": {"channels": [1, 2]},
    "HmIP-BRC2": {"channels": [1, 2, 3, 4]},
    "HmIP-WRC6-A": {"channels": [1, 2, 3, 4, 5, 6]},
    "HmIP-FCI6": {"channels": [1, 2, 3, 4, 5, 6]},
    "HmIPW-DRI16": {
        "channels": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    },
}

# Devices that require a generic button event entity
GENERIC_BUTTON_DEVICES = {
    "HmIP-WRC2": {"channels": [1, 2]},
    "HmIP-BRC2": {"channels": [1, 2, 3, 4]},
    "HmIP-WRC6-A": {"channels": [1, 2, 3, 4, 5, 6]},
    "HmIP-FCI6": {"channels": [1, 2, 3, 4, 5, 6]},
    "HmIPW-DRI16": {
        "channels": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]
    },
}


HMIP_OPTIONAL_FEATURE_TO_ENTITY = {
    "IFeatureDeviceIdentify": {
        "class": "HcuDeviceIdentifyButton",
        "requires_data_key": False,
        "simple_init": True,
    }
}


HMIP_DEVICE_TYPE_TO_DEVICE_CLASS = {
    "BLIND_ACTUATOR": CoverDeviceClass.BLIND,
    "BLIND_MODULE": CoverDeviceClass.BLIND,  # HmIP-HDM1 HunterDouglas
    "BRAND_BLIND": CoverDeviceClass.BLIND,
    "HUNTER_DOUGLAS_BLIND": CoverDeviceClass.BLIND,
    "GARAGE_DOOR_CONTROLLER": CoverDeviceClass.GARAGE,
    "GARAGE_DOOR_MODULE": CoverDeviceClass.GARAGE,
    "HOERMANN_DRIVES_MODULE": CoverDeviceClass.GARAGE,
    "SHUTTER_ACTUATOR": CoverDeviceClass.SHUTTER,
    "WATERING_ACTUATOR": SwitchDeviceClass.SWITCH,
    "PLUGABLE_SWITCH": SwitchDeviceClass.OUTLET,
    "PLUGABLE_SWITCH_MEASURING": SwitchDeviceClass.OUTLET,
    "BRAND_SWITCH_MEASURING": SwitchDeviceClass.SWITCH,
    "BRAND_SWITCH_MEASURING_INTERNATIONAL": SwitchDeviceClass.SWITCH,
    "FULL_FLUSH_SWITCH_16": SwitchDeviceClass.SWITCH,
    "BRAND_SWITCH_16": SwitchDeviceClass.SWITCH,
    "BRAND_SWITCH_2": SwitchDeviceClass.SWITCH,
    "WALL_MOUNTED_GLASS_SWITCH": SwitchDeviceClass.SWITCH,
    "WIRED_DIN_RAIL_SWITCH_8": SwitchDeviceClass.SWITCH,
    "WIRED_DIN_RAIL_BLIND_4": CoverDeviceClass.BLIND,
    "WIRED_DIN_RAIL_DIMMER_3": None,
    "BRAND_DIMMER": None,
    "OPEN_COLLECTOR_MODULE_8": SwitchDeviceClass.SWITCH,
    "DIGITAL_RADIO_INPUT_32": None,  # HmIP-DRI32 - Input-only device with 32 channels
    "DIN_RAIL_SWITCH_1": SwitchDeviceClass.SWITCH,
    "FLUSH_MOUNT_DIMMER": None,
    "CONTACT_INTERFACE_6": None,
    "ENERGY_SENSING_INTERFACE": None,
    "ENERGY_SENSORS_INTERFACE": None,
    "MAINS_FAILURE_SENSOR": None,
    "BRAND_REMOTE_CONTROL_2": None,
    "PUSH_BUTTON_2": None,
    "DOOR_LOCK_DRIVE": None,
    "DOOR_LOCK_DRIVE_PRO": None,
    "TEMPERATURE_HUMIDITY_SENSOR_OUTDOOR": None,
    "TILT_VIBRATION_SENSOR": None,  # Binary sensors handle this
    "GLASS_WALL_THERMOSTAT_CARBON": None,
    "SOIL_MOUNTURE_SENSOR_INTERFACE": None,
    "FLUSH_MOUNT_CONTACT_INTERFACE_1": None,
    "SHUTTER_CONTACT_MAGNETIC": None,
    "WALL_MOUNTED_GLASS_SWITCH_2": None,
    "RADIATOR_THERMOSTAT": None,
    "SHUTTER_CONTACT": None,
    "BRAND_WALL_THERMOSTAT": None,
    "FLOOR_TERMINAL_BLOCK_MOTOR": None,
    "PRESENCE_DETECTOR_INDOOR": None,
    "ALARM_SIREN_INDOOR": None,
    "LIGHT_SENSOR_OUTDOOR": None,
    "PLUGABLE_DIMMER": None,
    "FLUSH_MOUNT_SWITCH_1": SwitchDeviceClass.SWITCH,
    "COMBINATION_SIGNALLING_DEVICE": None,
    "SHUTTER_CONTACT_INVISIBLE": None,
}

UOM_HPA = "hPa"
UOM_UG_M3 = "µg/m³"
UOM_1_CM3 = "1/cm³"
UOM_UM = "µm"

HMIP_FEATURE_TO_ENTITY = {
    # Sensor Features
    "actualTemperature": {
        "class": "HcuTemperatureSensor",
        "name": "Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "soilTemperature": {
        "class": "HcuTemperatureSensor",
        "name": "Soil Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "soilMoisture": {
        "class": "HcuGenericSensor",
        "name": "Soil Moisture",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.MOISTURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "soilMoistureRawValue": {
        "class": "HcuGenericSensor",
        "name": "Soil Moisture Raw Value",
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:water-percent",
        "entity_registry_enabled_default": False,
    },
    "airPressure": {
        "class": "HcuGenericSensor",
        "name": "Air Pressure",
        "unit": UOM_HPA,
        "device_class": SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:gauge",
    },
    "particulateMassConcentrationOne": {
        "class": "HcuGenericSensor",
        "name": "PM1 Concentration",
        "unit": UOM_UG_M3,
        "device_class": SensorDeviceClass.PM1,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:blur",
    },
    "particulateMassConcentrationOneAverage": {
        "class": "HcuGenericSensor",
        "name": "PM1 Concentration (Average)",
        "unit": UOM_UG_M3,
        "device_class": SensorDeviceClass.PM1,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:blur",
    },
    "particulateNumberConcentrationOne": {
        "class": "HcuGenericSensor",
        "name": "PM1 Number Concentration",
        "unit": UOM_1_CM3,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:counter",
    },
    "particulateMassConcentrationTwoPointFive": {
        "class": "HcuGenericSensor",
        "name": "PM2.5 Concentration",
        "unit": UOM_UG_M3,
        "device_class": SensorDeviceClass.PM25,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:blur",
    },
    "particulateMassConcentrationTwoPointFiveAverage": {
        "class": "HcuGenericSensor",
        "name": "PM2.5 Concentration (Average)",
        "unit": UOM_UG_M3,
        "device_class": SensorDeviceClass.PM25,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:blur",
    },
    "particulateNumberConcentrationTwoPointFive": {
        "class": "HcuGenericSensor",
        "name": "PM2.5 Number Concentration",
        "unit": UOM_1_CM3,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:counter",
    },
    "particulateNumberConcentrationTwoPointFiveAverage": {
        "class": "HcuGenericSensor",
        "name": "PM2.5 Number Concentration (Average)",
        "unit": UOM_1_CM3,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:counter",
    },
    "airQualityIndexTwoPointFive": {
        "class": "HcuGenericSensor",
        "name": "AQI (PM2.5)",
        "device_class": SensorDeviceClass.AQI,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:air-filter",
    },
    "particulateMassConcentrationTen": {
        "class": "HcuGenericSensor",
        "name": "PM10 Concentration",
        "unit": UOM_UG_M3,
        "device_class": SensorDeviceClass.PM10,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:blur",
    },
    "particulateMassConcentrationTenAverage": {
        "class": "HcuGenericSensor",
        "name": "PM10 Concentration (Average)",
        "unit": UOM_UG_M3,
        "device_class": SensorDeviceClass.PM10,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:blur",
    },
    "particulateNumberConcentrationTen": {
        "class": "HcuGenericSensor",
        "name": "PM10 Number Concentration",
        "unit": UOM_1_CM3,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:counter",
    },
    "particulateNumberConcentrationTenAverage": {
        "class": "HcuGenericSensor",
        "name": "PM10 Number Concentration (Average)",
        "unit": UOM_1_CM3,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:counter",
    },
    "airQualityIndexTen": {
        "class": "HcuGenericSensor",
        "name": "AQI (PM10)",
        "device_class": SensorDeviceClass.AQI,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:air-filter",
    },
    "particulateTypicalSize": {
        "class": "HcuGenericSensor",
        "name": "Typical Particle Size",
        "unit": UOM_UM,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
        "icon": "mdi:ruler",
    },
    "valveActualTemperature": {
        "class": "HcuTemperatureSensor",
        "name": "Temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "humidity": {
        "class": "HcuGenericSensor",
        "name": "Humidity",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.HUMIDITY,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "vaporAmount": {
        "class": "HcuGenericSensor",
        "name": "Absolute Humidity",
        "unit": "g/m³",
        "icon": "mdi:water",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "illumination": {
        "class": "HcuGenericSensor",
        "name": "Illumination",
        "unit": LIGHT_LUX,
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "currentIllumination": {
        "class": "HcuGenericSensor",
        "name": "Current Illumination",
        "unit": LIGHT_LUX,
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "skip_if_null": True,
    },
    "averageIllumination": {
        "class": "HcuGenericSensor",
        "name": "Average Illumination",
        "unit": LIGHT_LUX,
        "device_class": SensorDeviceClass.ILLUMINANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "energyCounter": {
        "class": "HcuGenericSensor",
        "name": "Energy Counter",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "energyCounterOne": {
        "class": "HcuGenericSensor",
        "name": "Energy Counter One",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "optional_flag": "IOptionalFeatureEnergyCounterOne",
    },
    "energyCounterTwo": {
        "class": "HcuGenericSensor",
        "name": "Energy Counter Two",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "optional_flag": "IOptionalFeatureEnergyCounterTwo",
        "skip_if_null": True,
    },
    "energyCounterThree": {
        "class": "HcuGenericSensor",
        "name": "Energy Counter Three",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "optional_flag": "IOptionalFeatureEnergyCounterThree",
    },
    "powerProduction": {
        "class": "HcuGenericSensor",
        "name": "Power Production",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "energyProduction": {
        "class": "HcuGenericSensor",
        "name": "Energy Production",
        "unit": UnitOfEnergy.KILO_WATT_HOUR,
        "device_class": SensorDeviceClass.ENERGY,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "currentPowerConsumption": {
        "class": "HcuGenericSensor",
        "name": "Power Consumption",
        "unit": UnitOfPower.WATT,
        "device_class": SensorDeviceClass.POWER,
        "state_class": SensorStateClass.MEASUREMENT,
        "skip_if_null": True,
    },
    "gasVolume": {
        "class": "HcuGenericSensor",
        "name": "Gas Volume",
        "unit": UnitOfVolume.CUBIC_METERS,
        "device_class": SensorDeviceClass.GAS,
        "optional_flag": "IOptionalFeatureGasVolume",
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "currentGasFlow": {
        "class": "HcuGenericSensor",
        "name": "Current Gas Flow",
        "unit": "m³/h",
        "icon": "mdi:meter-gas",
        "optional_flag": "IOptionalFeatureCurrentGasFlow",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "waterVolume": {
        "class": "HcuGenericSensor",
        "name": "Water Volume",
        "unit": UnitOfVolume.LITERS,
        "device_class": SensorDeviceClass.WATER,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "waterVolumeSinceOpen": {
        "class": "HcuGenericSensor",
        "name": "Water Volume Since Open",
        "unit": UnitOfVolume.LITERS,
        "device_class": SensorDeviceClass.WATER,
        "state_class": SensorStateClass.TOTAL_INCREASING,
    },
    "waterFlow": {
        "class": "HcuGenericSensor",
        "name": "Water Flow",
        "unit": "L/min",
        "icon": "mdi:water",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "valvePosition": {
        "class": "HcuGenericSensor",
        "name": "Valve Position",
        "unit": PERCENTAGE,
        "icon": "mdi:pipe-valve",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "windSpeed": {
        "class": "HcuGenericSensor",
        "name": "Wind Speed",
        "unit": UnitOfSpeed.KILOMETERS_PER_HOUR,
        "device_class": SensorDeviceClass.WIND_SPEED,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "windDirection": {
        "class": "HcuGenericSensor",
        "name": "Wind Direction",
        "unit": DEGREE,
        "icon": "mdi:weather-windy",
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "windDirectionVariation": {
        "class": "HcuGenericSensor",
        "name": "Wind Direction Variation",
        "unit": DEGREE,
        "icon": "mdi:weather-windy-variant",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "totalRainCounter": {
        "class": "HcuGenericSensor",
        "name": "Total Rain",
        "unit": UnitOfPrecipitationDepth.MILLIMETERS,
        "device_class": SensorDeviceClass.PRECIPITATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:weather-pouring",
    },
    "todayRainCounter": {
        "class": "HcuGenericSensor",
        "name": "Today's Rain",
        "unit": UnitOfPrecipitationDepth.MILLIMETERS,
        "device_class": SensorDeviceClass.PRECIPITATION,
        "state_class": SensorStateClass.TOTAL,
        "icon": "mdi:weather-rainy",
    },
    "yesterdayRainCounter": {
        "class": "HcuGenericSensor",
        "name": "Yesterday's Rain",
        "unit": UnitOfPrecipitationDepth.MILLIMETERS,
        "device_class": SensorDeviceClass.PRECIPITATION,
        "state_class": SensorStateClass.TOTAL,
        "icon": "mdi:weather-rainy",
    },
    "totalSunshineDuration": {
        "class": "HcuGenericSensor",
        "name": "Total Sunshine Duration",
        "unit": UnitOfTime.MINUTES,
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "icon": "mdi:weather-sunny",
    },
    "todaySunshineDuration": {
        "class": "HcuGenericSensor",
        "name": "Today's Sunshine Duration",
        "unit": UnitOfTime.MINUTES,
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL,
        "icon": "mdi:weather-partly-cloudy",
    },
    "yesterdaySunshineDuration": {
        "class": "HcuGenericSensor",
        "name": "Yesterday's Sunshine Duration",
        "unit": UnitOfTime.MINUTES,
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL,
        "icon": "mdi:weather-sunset",
    },
    "moistureLevel": {
        "class": "HcuGenericSensor",
        "name": "Moisture Level",
        "unit": PERCENTAGE,
        "device_class": SensorDeviceClass.MOISTURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    # Ultrasonic distance sensor interface (ELV-SH-DUSI, DISTANCE_SENSOR_CHANNEL) - Issue #427
    # Raw values from the HCU are in centimeters, e.g. distance=25.2,
    # calculatedHeight=149.8, referenceHeight=175.0 (referenceHeight - distance == calculatedHeight).
    "distance": {
        "class": "HcuGenericSensor",
        "name": "Distance",
        "unit": UnitOfLength.CENTIMETERS,
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 1,
        "icon": "mdi:signal-distance-variant",
    },
    "calculatedHeight": {
        "class": "HcuGenericSensor",
        "name": "Calculated Height",
        "unit": UnitOfLength.CENTIMETERS,
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 1,
        "icon": "mdi:arrow-expand-vertical",
    },
    "referenceHeight": {
        "class": "HcuGenericSensor",
        "name": "Reference Height",
        "unit": UnitOfLength.CENTIMETERS,
        "device_class": SensorDeviceClass.DISTANCE,
        "state_class": SensorStateClass.MEASUREMENT,
        "suggested_display_precision": 1,
        "icon": "mdi:arrow-expand-vertical",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "carrierSense": {
        "class": "HcuHomeSensor",
        "name": "Radio Traffic",
        "unit": PERCENTAGE,
        "icon": "mdi:radio-tower",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "dutyCycle": {
        "class": "HcuHomeSensor",
        "name": "Duty Cycle",
        "unit": PERCENTAGE,
        "icon": "mdi:radio-tower",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "dutyCycleLevel": {
        "class": "HcuGenericSensor",
        "name": "Duty Cycle Level",
        "unit": PERCENTAGE,
        "icon": "mdi:radio-tower",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "dirtLevel": {
        "class": "HcuGenericSensor",
        "name": "Dirt Level",
        "unit": PERCENTAGE,
        "icon": "mdi:dust",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "operationDays": {
        "class": "HcuGenericSensor",
        "name": "Operation Days",
        "unit": "d",
        "device_class": SensorDeviceClass.DURATION,
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "lastSmokeTestTimestamp": {
        "class": "HcuTimestampSensor",
        "name": "Last Smoke Test",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "lastCommunicationTestTimestamp": {
        "class": "HcuTimestampSensor",
        "name": "Last Communication Test",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "smokeTestCounter": {
        "class": "HcuGenericSensor",
        "name": "Smoke Test Counter",
        "icon": "mdi:counter",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "smokeAlarmCounter": {
        "class": "HcuGenericSensor",
        "name": "Smoke Alarm Counter",
        "icon": "mdi:counter",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "rssiDeviceValue": {
        "class": "HcuGenericSensor",
        "name": "RSSI Device",
        "unit": "dBm",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "rssiPeerValue": {
        "class": "HcuGenericSensor",
        "name": "RSSI Peer",
        "unit": "dBm",
        "device_class": SensorDeviceClass.SIGNAL_STRENGTH,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "accelerationSensorValueX": {
        "class": "HcuGenericSensor",
        "name": "Acceleration X",
        "icon": "mdi:axis-x-arrow",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "accelerationSensorValueY": {
        "class": "HcuGenericSensor",
        "name": "Acceleration Y",
        "icon": "mdi:axis-y-arrow",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "accelerationSensorValueZ": {
        "class": "HcuGenericSensor",
        "name": "Acceleration Z",
        "icon": "mdi:axis-z-arrow",
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "accelerationSensorTriggered": {
        "class": "HcuBinarySensor",
        "name": "Acceleration Sensor Triggered",
        "icon": "mdi:accelerometer",
        "device_class": BinarySensorDeviceClass.VIBRATION,
    },
    "accelerationSensorEventCounter": {
        "class": "HcuGenericSensor",
        "name": "Acceleration Events",
        "icon": "mdi:counter",
        "state_class": SensorStateClass.TOTAL_INCREASING,
        "entity_registry_enabled_default": False,
    },
    "tiltState": {
        "class": "HcuGenericSensor",
        "name": "Tilt State",
        "icon": "mdi:axis-z-rotate-clockwise",
    },
    "absoluteAngle": {
        "class": "HcuGenericSensor",
        "name": "Absolute Angle",
        "icon": "mdi:angle-acute",
        "unit": DEGREE,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "mainsVoltage": {
        "class": "HcuGenericSensor",
        "name": "Mains Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "supplyVoltage": {
        "class": "HcuGenericSensor",
        "name": "Supply Voltage",
        "unit": UnitOfElectricPotential.VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "frequency": {
        "class": "HcuGenericSensor",
        "name": "Frequency",
        "unit": UnitOfFrequency.HERTZ,
        "device_class": SensorDeviceClass.FREQUENCY,
        "state_class": SensorStateClass.MEASUREMENT,
        "entity_registry_enabled_default": False,
    },
    "carbonDioxideConcentration": {
        "class": "HcuGenericSensor",
        "name": "CO2 Concentration",
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "device_class": SensorDeviceClass.CO2,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "temperatureExternalOne": {
        "class": "HcuTemperatureSensor",
        "name": "Temperature External 1",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "temperatureExternalTwo": {
        "class": "HcuTemperatureSensor",
        "name": "Temperature External 2",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
    },
    "temperatureExternalDelta": {
        "class": "HcuGenericSensor",
        "name": "Temperature Delta",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "state_class": SensorStateClass.MEASUREMENT,
        "icon": "mdi:thermometer-chevron-up",
    },
    # Binary Sensor Features
    "lowBat": {
        "class": "HcuBinarySensor",
        "name": "Low Battery",
        "device_class": BinarySensorDeviceClass.BATTERY,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "optional_flag": "IOptionalFeatureLowBat",
    },
    "unreach": {
        "class": "HcuUnreachBinarySensor",
        "name": "Connectivity",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
    "motionDetected": {
        "class": "HcuBinarySensor",
        "name": "Motion",
        "device_class": BinarySensorDeviceClass.MOTION,
    },
    "presenceDetected": {
        "class": "HcuBinarySensor",
        "name": "Presence",
        "device_class": BinarySensorDeviceClass.OCCUPANCY,
    },
    "illuminationDetected": {
        "class": "HcuBinarySensor",
        "name": "Illumination Detected",
        "device_class": BinarySensorDeviceClass.LIGHT,
    },
    "chamberDegraded": {
        "class": "HcuBinarySensor",
        "name": "Chamber Degraded",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "deviceOverheated": {
        "class": "HcuBinarySensor",
        "name": "Device Overheated",
        "device_class": BinarySensorDeviceClass.HEAT,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "temperatureOutOfRange": {
        "class": "HcuBinarySensor",
        "name": "Temperature Out Of Range",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "coProFaulty": {
        "class": "HcuBinarySensor",
        "name": "Co-Processor Faulty",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "coProUpdateFailure": {
        "class": "HcuBinarySensor",
        "name": "Co-Processor Update Failure",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
    },
    "mainsFailureActive": {
        "class": "HcuBinarySensor",
        "name": "Mains Failure",
        "device_class": BinarySensorDeviceClass.PROBLEM,
    },
    "sabotage": {
        "class": "HcuBinarySensor",
        "name": "Sabotage",
        "device_class": BinarySensorDeviceClass.TAMPER,
    },
    "waterlevelDetected": {
        "class": "HcuBinarySensor",
        "name": "Water Level",
        "device_class": BinarySensorDeviceClass.MOISTURE,
    },
    "smokeDetectorAlarmType": {
        "class": "HcuSmokeBinarySensor",
        "name": "Smoke",
        "device_class": BinarySensorDeviceClass.SMOKE,
    },
    "moistureDetected": {
        "class": "HcuBinarySensor",
        "name": "Moisture",
        "device_class": BinarySensorDeviceClass.MOISTURE,
    },
    "sunshine": {
        "class": "HcuBinarySensor",
        "name": "Sunshine",
        "device_class": BinarySensorDeviceClass.LIGHT,
    },
    "storm": {
        "class": "HcuBinarySensor",
        "name": "Storm",
        "device_class": BinarySensorDeviceClass.SAFETY,
        "entity_registry_enabled_default": False,
    },
    "raining": {
        "class": "HcuBinarySensor",
        "name": "Raining",
        "device_class": BinarySensorDeviceClass.MOISTURE,
    },
    "processing": {
        "class": "HcuBinarySensor",
        "name": "Activity",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "entity_registry_enabled_default": False,
    },
    "onTime": {
        "class": "HcuGenericSensor",
        "name": "InternalOnTime",
        "translation_key": "hcu_on_time",
        "unit": "s",
        "device_class": SensorDeviceClass.DURATION,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "suggested_display_precision": 0,
        "config_companion": "HcuConfigUseInternalOnTime",
    },
    "wateringOnTime": {
        "class": "HcuGenericSensor",
        "name": "WateringOnTime",
        "translation_key": "hcu_on_time",
        "unit": "s",
        "device_class": SensorDeviceClass.DURATION,
        "entity_category": EntityCategory.DIAGNOSTIC,
        "entity_registry_enabled_default": False,
        "suggested_display_precision": 0,
        "config_companion": "HcuConfigUseInternalOnTime",
    },
    "powerUpSwitchState": {
        "class": "HcuPowerUpSwitchState",
        "name": "Power-up Switch State",
        "entity_registry_enabled_default": False,
        "requires_app_user": True,
    },

}

# Special mapping for dutyCycle binary sensor (device-level warning flag)
# Note: dutyCycle exists in both home object (as percentage) and device channels (as boolean)
# This mapping is used for device channels to avoid key collision in HMIP_FEATURE_TO_ENTITY
DUTY_CYCLE_BINARY_SENSOR_MAPPING = {
    "class": "HcuBinarySensor",
    "name": "Duty Cycle Limit",
    "device_class": BinarySensorDeviceClass.PROBLEM,
    "entity_category": EntityCategory.DIAGNOSTIC,
    "entity_registry_enabled_default": False,
}

# Channel types that send DEVICE_CHANNEL_EVENT messages exclusively
# These should NOT use timestamp-based detection to avoid false positives from configuration changes
DEVICE_CHANNEL_EVENT_ONLY_TYPES = {
    "SINGLE_KEY_CHANNEL",  # HmIP-BRC2, HmIP-WRC2 - sends explicit DEVICE_CHANNEL_EVENT
    "KEY_CHANNEL",  # Modern remote controls - sends explicit DEVICE_CHANNEL_EVENT
    CHANNEL_TYPE_MULTI_MODE_INPUT,  # HmIP-FCI1/6 etc. - sends explicit DEVICE_CHANNEL_EVENT
    CHANNEL_TYPE_MULTI_MODE_INPUT_TRANSMITTER,  # HmIP-FCI1/6 etc. - sends explicit DEVICE_CHANNEL_EVENT
}

EVENT_TYPES = frozenset({
    (
        "button",
        frozenset({
            ("PRESS",                "press"),
            ("PRESS_SHORT",          "press_short"),
            ("PRESS_LONG",           "press_long"),
            ("PRESS_LONG_START",     "press_long_start"),
            ("PRESS_LONG_STOP",      "press_long_stop"),
        }),
    ),
    (
        "doorbell",
        frozenset({
            ("DOOR_BELL_SENSOR_EVENT", "ring"),
        }),
    ),
})

DEVICE_CHANNEL_EVENT_TYPES = frozenset({
    "press",
    "press_short",
    "press_long",
    "press_long_start",
    "press_long_stop",
    "ring",
})

HMIP_CHANNEL_ROLE_TO_ENTITY = { 
    "DOOR_BELL_INPUT": {
        "class": "HcuDoorbellEvent",
        "name": "Doorbell",
    },
    "DOOR_SENSOR": {
        "class": "HcuDoorBinarySensor",
        "name": "Door",
        "feature": "windowState",
        "device_class": BinarySensorDeviceClass.DOOR,
    },
    "WINDOW_SENSOR": {
        "class": "HcuWindowBinarySensor",
        "name": "Window",
        "feature": "windowState",
        "device_class": BinarySensorDeviceClass.WINDOW,
        "extra_entities": [
            {
                "class": "HcuWindowStateSensor",
                "only_channel_types": ["ROTARY_HANDLE_CHANNEL"],
            }
        ],
    },
    "KEY_OR_SWITCH_FOR_GROUP": {
        "class": "HcuButtonEvent"
    },
    "HOT_WATER_PROFILE": {
        "class": "HcuButtonEvent"
    },
    "ECO_MODE_ACTIVATION": {
        "class": "HcuButtonEvent"
    },
    "INPUT_FOR_SILENT_ALARM": {
        "class": "HcuButtonEvent"
    },
    "KEY_OR_SWITCH_FOR_ALARM_ZONE": {
        "class": "HcuButtonEvent"
    }
}
    
HMIP_CHANNEL_TYPE_TO_ENTITY = {
    "DIMMER_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "MULTI_MODE_INPUT_DIMMER_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "RGBW_AUTOMATION_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "UNIVERSAL_LIGHT_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "NOTIFICATION_LIGHT_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "OPTICAL_SIGNAL_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "NOTIFICATION_MP3_SOUND_CHANNEL": {"class": "HcuNotificationLight", "extra_entities": ["HcuConfigRampTime"]},
    "BACKLIGHT_CHANNEL": {"class": "HcuLight", "extra_entities": ["HcuConfigRampTime"]},
    "SWITCH_CHANNEL": {"class": "HcuSwitch"},
    "SWITCH_MEASURING_CHANNEL": {"class": "HcuSwitch"},
    "WIRED_SWITCH_CHANNEL": {"class": "HcuSwitch"},
    "MULTI_MODE_INPUT_SWITCH_CHANNEL": {"class": "HcuSwitch"},
    "WATERING_ACTUATOR_CHANNEL": {"class": "HcuWateringSwitch"},
    "WATERING_CONTROLLER_CHANNEL": {"class": "HcuWateringSwitch"},
    "CONDITIONAL_SWITCH_CHANNEL": {"class": "HcuSwitch"},
    "OPEN_COLLECTOR_CHANNEL_8": {"class": "HcuSwitch"},
    "SHUTTER_CHANNEL": {"class": "HcuCover"},
    "BLIND_CHANNEL": {"class": "HcuCover"},
    "BRAND_BLIND_CHANNEL": {"class": "HcuCover"},  # For HmIP-HDM1 HunterDouglas blinds
    "SHADING_CHANNEL": {"class": "HcuCover"},  # For HmIP-HDM1 HunterDouglas shading actuators
    "GARAGE_DOOR_CHANNEL": {"class": "HcuGarageDoorCover"},
    "DOOR_CHANNEL": {"class": "HcuGarageDoorCover"},
    "DOOR_SWITCH_CHANNEL": {"class": "HcuDoorPullLatchButton", "extra_entities": ["HcuDevicePin"]},
    "IMPULSE_OUTPUT_CHANNEL": {"class": "HcuDoorImpulseButton"},
    "DOOR_LOCK_CHANNEL": {"class": "HcuLock", "extra_entities": ["HcuDoorUnlatchButton", "HcuDevicePin"]},
    "DOOR_LOCK_PRO_CHANNEL": {"class": "HcuLock", "extra_entities": ["HcuDoorUnlatchButton", "HcuDevicePin"]},
    "ROTARY_HANDLE_CHANNEL": {"class": "HcuWindowStateSensor"},
    # Event channel types - create HcuButtonEvent entities for button devices
    "ACCELERATION_SENSOR_CHANNEL": None,
    "CLIMATE_CONTROL_CHANNEL": None,
    "CLIMATE_CONTROL_INPUT_CHANNEL": None,
    "CLIMATE_SENSOR_CHANNEL": None,
    "ENERGY_SENSORS_INTERFACE_CHANNEL": None,
    "GAS_CHANNEL": None,
    "HEATING_CHANNEL": None,
    "LIGHT_SENSOR_CHANNEL": None,
    "MAINS_FAILURE_SENSOR_CHANNEL": None,
    "MOTION_DETECTION_CHANNEL": None,
    "PRESENCE_DETECTION_CHANNEL": None,
    "SHUTTER_CONTACT_CHANNEL": None,
    "SOIL_MOISTURE_SENSOR_CHANNEL": None,
    "TEMPERATURE_SENSOR_2_EXTERNAL_DELTA_CHANNEL": None,
    "WALL_MOUNTED_THERMOSTAT_CARBON_CHANNEL": None,
    "WALL_MOUNTED_THERMOSTAT_CHANNEL": None,
    "EXTERNAL_SWITCH_CHANNEL": {"class": "HcuSwitch"},
}

# --- Simple RGB Color State Constants ---
# Color values for simpleRGBColorState (HmIP-BSL, HmIP-MP3P, etc.)
# Only the 8 colors officially supported by the HCU API are defined here.
# Note: ORANGE is NOT supported by the API despite appearing in some device specs.
HMIP_COLOR_BLACK = "BLACK"
HMIP_COLOR_WHITE = "WHITE"
HMIP_COLOR_RED = "RED"
HMIP_COLOR_BLUE = "BLUE"
HMIP_COLOR_GREEN = "GREEN"
HMIP_COLOR_YELLOW = "YELLOW"
HMIP_COLOR_PURPLE = "PURPLE"
HMIP_COLOR_TURQUOISE = "TURQUOISE"

# RGB Color mappings for devices with simpleRGBColorState (e.g., HmIP-BSL backlight)
# Maps simpleRGBColorState values to HS color tuples (hue, saturation)
# Based on official HCU API documentation - only 8 colors supported:
# BLACK, BLUE, GREEN, TURQUOISE, RED, PURPLE, YELLOW, WHITE
HMIP_RGB_COLOR_MAP = {
    HMIP_COLOR_BLACK: (0, 0),        # Off/Black
    HMIP_COLOR_BLUE: (240, 100),     # Blue
    HMIP_COLOR_GREEN: (120, 100),    # Green
    HMIP_COLOR_TURQUOISE: (180, 100), # Cyan/Turquoise
    HMIP_COLOR_RED: (0, 100),        # Red
    HMIP_COLOR_PURPLE: (300, 100),   # Purple/Magenta
    HMIP_COLOR_YELLOW: (60, 100),    # Yellow
    HMIP_COLOR_WHITE: (0, 0),        # White (will be handled separately with brightness)
    # Note: Hues in the orange range (15-45°) are mapped to RED or YELLOW depending on proximity.
}

# Optical signal behavior values for HmIP-BSL and similar notification lights
# These control visual effects like blinking, flashing, etc.
HMIP_OPTICAL_SIGNAL_BEHAVIOURS = (
    "off",
    "on",
    "blinking_middle",
    "flash_middle",
    "billow_middle",
)

# Siren tone options for HmIP-ASIR2 and compatible devices
# These acoustic signals can be used with the siren.turn_on service
# Based on official HomematicIP API documentation and HmIP-ASIR2 device specification
HMIP_SIREN_TONES = frozenset({
    # Frequency pattern tones (alarm sounds) - alphabetically sorted
    "FREQUENCY_ALTERNATING_LOW_HIGH",
    "FREQUENCY_ALTERNATING_LOW_MID_HIGH",
    "FREQUENCY_FALLING",
    "FREQUENCY_HIGHON_LONGOFF",
    "FREQUENCY_HIGHON_OFF",
    "FREQUENCY_LOWON_LONGOFF_HIGHON_LONGOFF",
    "FREQUENCY_LOWON_OFF_HIGHON_OFF",
    "FREQUENCY_RISING",
    "FREQUENCY_RISING_AND_FALLING",
    # Status and alert tones - alphabetically sorted
    "DELAYED_EXTERNALLY_ARMED",
    "DELAYED_INTERNALLY_ARMED",
    "DISABLE_ACOUSTIC_SIGNAL",
    "DISARMED",
    "ERROR",
    "EVENT",
    "EXTERNALLY_ARMED",
    "INTERNALLY_ARMED",
    "LOW_BATTERY",
})

# Default siren settings
DEFAULT_SIREN_TONE = "FREQUENCY_RISING"
DEFAULT_SIREN_DURATION = 10.0  # seconds
DEFAULT_SIREN_OPTICAL_SIGNAL = "BLINKING_ALTERNATELY_REPEATING"

# Custom attribute for siren optical signal (not a standard Home Assistant attribute)
ATTR_OPTICAL_SIGNAL = "optical_signal"

# Absence Types
ABSENCE_TYPE_NOT_ABSENT = "NOT_ABSENT"
ABSENCE_TYPE_PARTY = "PARTY"
ABSENCE_TYPE_PERIOD = "PERIOD"
ABSENCE_TYPE_PERMANENT = "PERMANENT"
ABSENCE_TYPE_VACATION = "VACATION"

# Window States (used in group windowState evaluation)
WINDOW_STATE_OPEN = "OPEN"
WINDOW_STATE_TILTED = "TILTED"
WINDOW_STATE_CLOSED = "CLOSED"

# Lock States
LOCK_STATE_OPEN: Final = "OPEN"
LOCK_STATE_LOCKED: Final = "LOCKED"
LOCK_STATE_UNLOCKED: Final = "UNLOCKED"
LOCK_STATE_JAMMED: Final = "JAMMED"

# Motor States
MOTOR_STATE_LOCKING: Final = "CLOSING"
MOTOR_STATE_UNLOCKING: Final = "UNLOCKING"
MOTOR_STATE_OPENING: Final = "OPENING"
MOTOR_STATE_JAMMED: Final = "JAMMED"

# Access Authorization
CHANNEL_TYPE_ACCESS_AUTHORIZATION = "ACCESS_AUTHORIZATION_CHANNEL"

# Error Types (lowercase for case-insensitive matching)
INVALID_PIN_ERROR_STRINGS = ("invalid_authorization_pin", "invalid_pin")
ACCESS_DENIED_ERROR_STRINGS = ("access_denied", "invalid_request", "client_invalid_authorization")

# Error Messages
LOCK_AUTH_ERROR_MSG = (
    "Access denied for %s. The 'Home Assistant Integration' user is not authorized to control this lock. "
    "\n\nTo fix this issue:\n"
    "1. CRITICAL: Ensure your HCU Firmware is updated to version 1.6.16 or higher.\n"
    "2. Delete any old 'Home Assistant' profiles if they appear grayed out.\n"
    "3. Open the HomematicIP app on your phone\n"
    "4. Go to Settings → Access Control → Access Profiles\n"
    "5. Create a new access profile for this lock and add the 'Home Assistant Integration' user.\n"
    "\nKNOWN LIMITATION: Even on 1.6.16, the integration user may still appear grayed out or expired in the app. "
    "This is a known UI bug with the HCU firmware. The integration has properly registered with the HCU, "
    "but the HomematicIP app UI often lags.\n"
    "Please check the 'has_access_authorization' attribute on the lock entity to verify authorization status."
)

# Groups that are allowed to be discovered even without channels
ALLOWED_EMPTY_GROUPS = ("SECURITY_ZONE", "META", "INDOOR_CLIMATE", "ENERGY", "SECURITY", "ACCESS_CONTROL", "ENVIRONMENT", "SECURITY_BACKUP_ALARM_SWITCHING")

# Group types that are actually mapped to HA entities (used to filter options flow)
SUPPORTED_GROUP_TYPES = frozenset({
    "HEATING",
    "SHUTTER",
    "SWITCHING",
    "SWITCHING_PROFILE",
    "LINKED_SWITCHING",
    "LIGHT",
    "EXTENDED_LINKED_SWITCHING",
    "EXTENDED_LINKED_SHUTTER",
    "EXTENDED_LINKED_NOTIFICATION",
    "EXTENDED_LINKED_WATERING",
    "EXTENDED_LINKED_GARAGE_DOOR",
    "HEATING_COOLING_DEMAND_BOILER",
    "HEATING_COOLING_DEMAND_PUMP",
    "HOT_WATER",
    "ALARM_SWITCHING",
})
