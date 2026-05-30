"""Constants for the Homematic IP Local (HCU) integration."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import Platform

DOMAIN = "hcu_integration"

PLATFORMS: list[Platform] = [
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
    Platform.SWITCH,
    Platform.TEXT,
]

PLUGIN_ID = "de.homeassistant.hcu.integration"
PLUGIN_FRIENDLY_NAME = "Home Assistant Integration"
PLUGIN_DOCS_URL = "https://github.com/ediminator/hacs-homematicip-hcu"

MANUFACTURER_EQ3 = "eQ-3"
MANUFACTURER_HUE = "Philips"
HUE_MODEL_TOKEN = "Hue"

CONF_AUTH_PORT = "auth_port"
CONF_CLIENT_ID = "client_id"
CONF_WEBSOCKET_PORT = "websocket_port"
CONF_ENTITY_PREFIX = "entity_prefix"
CONF_PLATFORM_OVERRIDES = "platform_overrides"
CONF_PIN = "pin"
CONF_ADVANCED_DEBUGGING = "advanced_debugging"
CONF_ADVANCED_ATTRIBUTES = "advanced_attributes"
CONF_DISABLE_UNCONFIGURED_CHANNELS = "disable_unconfigured_channels"
CONF_COMFORT_TEMPERATURE = "comfort_temperature"
CONF_SELECTED_OEMS = "selected_oems"
CONF_DISABLED_OEMS = "disabled_oems"
CONF_DISABLED_GROUPS = "disabled_groups"
CONF_HA_ENTITIES = "ha_entities"  # legacy — superseded by CONF_HA_DEVICES
CONF_HA_DEVICES = "ha_devices"

# Feature type keys used in ha_devices[].features
HA_FEATURE_ON_OFF = "on_off"
HA_FEATURE_BRIGHTNESS = "brightness"
HA_FEATURE_COLOR_TEMP = "color_temp"
HA_FEATURE_RGB_COLOR = "rgb_color"
HA_FEATURE_TEMPERATURE = "temperature"
HA_FEATURE_HUMIDITY = "humidity"
HA_FEATURE_ILLUMINANCE = "illuminance"
HA_FEATURE_CO2 = "co2"
HA_FEATURE_WIND_SPEED = "wind_speed"
HA_FEATURE_PRECIPITATION = "precipitation"
HA_FEATURE_POWER = "power"
HA_FEATURE_ENERGY = "energy"
HA_FEATURE_PM25 = "pm25"
HA_FEATURE_PM10 = "pm10"
HA_FEATURE_MOTION = "motion"
HA_FEATURE_OCCUPANCY = "occupancy"
HA_FEATURE_DOOR = "door"
HA_FEATURE_WINDOW = "window"
HA_FEATURE_SMOKE = "smoke"
HA_FEATURE_MOISTURE = "moisture"

# Which HA domains each feature accepts
HA_FEATURE_DOMAINS: dict[str, list[str]] = {
    HA_FEATURE_ON_OFF:       ["switch", "light"],
    HA_FEATURE_BRIGHTNESS:   ["light"],
    HA_FEATURE_COLOR_TEMP:   ["light"],
    HA_FEATURE_RGB_COLOR:    ["light"],
    HA_FEATURE_TEMPERATURE:  ["sensor"],
    HA_FEATURE_HUMIDITY:     ["sensor"],
    HA_FEATURE_ILLUMINANCE:  ["sensor"],
    HA_FEATURE_CO2:          ["sensor"],
    HA_FEATURE_WIND_SPEED:   ["sensor"],
    HA_FEATURE_PRECIPITATION:["sensor"],
    HA_FEATURE_POWER:        ["sensor"],
    HA_FEATURE_ENERGY:       ["sensor"],
    HA_FEATURE_PM25:         ["sensor"],
    HA_FEATURE_PM10:         ["sensor"],
    HA_FEATURE_MOTION:       ["binary_sensor"],
    HA_FEATURE_OCCUPANCY:    ["binary_sensor"],
    HA_FEATURE_DOOR:         ["binary_sensor"],
    HA_FEATURE_WINDOW:       ["binary_sensor"],
    HA_FEATURE_SMOKE:        ["binary_sensor"],
    HA_FEATURE_MOISTURE:     ["binary_sensor"],
}

DEFAULT_ADVANCED_DEBUGGING = False
DEFAULT_ADVANCED_ATTRIBUTES = False
DEFAULT_DISABLE_UNCONFIGURED_CHANNELS = False
DEFAULT_COMFORT_TEMPERATURE = 21.0
DEFAULT_MIN_TEMP = 5.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_TEMP_STEP = 0.5

DEFAULT_HCU_AUTH_PORT = 6969
DEFAULT_HCU_WEBSOCKET_PORT = 9001
ATTR_END_TIME = "end_time"

PLUGIN_ID_HUE = "de.eq3.plugin.hue"

WEBSOCKET_RECONNECT_INITIAL_DELAY = 5
WEBSOCKET_RECONNECT_MAX_DELAY = 300
WEBSOCKET_RECONNECT_JITTER_MAX = 10

HCU_DEVICE_TYPES = {
    "HmIP-HCU4",
}

HAP_DRAP_PREFIXES = (
    "HmIP-HAP",
    "HmIP-DRAP",
)

# ---------------------------------------------------------------------------
# Channel type → HA platform mapping
# ---------------------------------------------------------------------------
CHANNEL_TO_PLATFORM: dict[str, str] = {
    # Climate / heating
    "HEATING_GROUP": "climate",
    "HEATING_DEHUMIDIFIER_GROUP": "climate",
    "HEATING_COOLING_GROUP": "climate",
    "HEATING_CHANGEOVER_GROUP": "climate",
    "HEATING_FAILURE_ALERT_GROUP": "climate",
    "FLOOR_TERMINAL_BLOCK_10_GROUP": "climate",
    "FLOOR_TERMINAL_BLOCK_12_GROUP": "climate",
    "TEMPERATURE_HUMIDITY_SENSOR_CHANNEL": "sensor",
    "TEMPERATURE_SENSOR_CHANNEL": "sensor",
    "WALL_MOUNTED_THERMOSTAT_PRO_CHANNEL": "sensor",
    "WALL_MOUNTED_THERMOSTAT_WITHOUT_DISPLAY_CHANNEL": "sensor",
    # Switches
    "SWITCH_CHANNEL": "switch",
    "SWITCH_MEASURING_CHANNEL": "switch",
    "PRINTED_CIRCUIT_BOARD_SWITCH_CHANNEL": "switch",
    "PRINTED_CIRCUIT_BOARD_SWITCH_2_CHANNEL": "switch",
    "MULTI_MODE_INPUT_SWITCH_CHANNEL": "switch",
    "WIRED_SWITCH_4_CHANNEL": "switch",
    "WIRED_SWITCH_8_CHANNEL": "switch",
    "WIRED_BINARY_TRANSMITTER_32_CHANNEL": "switch",
    # Lights / dimmers
    "DIMMER_CHANNEL": "light",
    "UNIVERSAL_LIGHT_CHANNEL": "light",
    "UNIVERSAL_LIGHT_GROUP": "light",
    "RGBW_DIMMER_CHANNEL": "light",
    "RGB_DIMMER_CHANNEL": "light",
    "TUNABLE_WHITE_DIMMER_CHANNEL": "light",
    "WIRED_DIMMER_3_CHANNEL": "light",
    "NOTIFICATION_LIGHT_CHANNEL": "light",
    "DOOR_BELL_CHANNEL": "light",
    # Covers / blinds
    "BLIND_CHANNEL": "cover",
    "SHUTTER_CHANNEL": "cover",
    "GARAGE_DOOR_CHANNEL": "cover",
    "TORMATIC_CHANNEL": "cover",
    "HOERMANN_DRIVE_CHANNEL": "cover",
    "SLAT_CHANNEL": "cover",
    # Locks
    "DOOR_LOCK_CHANNEL": "lock",
    "DOOR_LOCK_SENSOR_CHANNEL": "binary_sensor",
    # Sensors – binary
    "SHUTTER_CONTACT_CHANNEL": "binary_sensor",
    "SMOKE_DETECTOR_CHANNEL": "binary_sensor",
    "MOTION_DETECTION_CHANNEL": "binary_sensor",
    "PRESENCE_DETECTION_CHANNEL": "binary_sensor",
    "WATER_SENSOR_CHANNEL": "binary_sensor",
    "RAIN_SENSOR_CHANNEL": "binary_sensor",
    "PASSAGE_DETECTOR_CHANNEL": "binary_sensor",
    "PASSAGE_DETECTOR_DIRECTION_CHANNEL": "binary_sensor",
    "IMPULSE_OUTPUT_CHANNEL": "binary_sensor",
    # Sensors – numeric / state
    "ENERGY_SENSORS_INTERFACE_CHANNEL": "sensor",
    "CURRENT_FLOW_SENSOR_CHANNEL": "sensor",
    "LIGHT_SENSOR_CHANNEL": "sensor",
    "PARTICULATE_MATTER_SENSOR_CHANNEL": "sensor",
    "WIND_SENSOR_CHANNEL": "sensor",
    "WEATHER_SENSOR_CHANNEL": "sensor",
    "WEATHER_SENSOR_PLUS_CHANNEL": "sensor",
    "WEATHER_SENSOR_PRO_CHANNEL": "sensor",
    # Buttons / event
    "DEVICE_GLOBAL_PUMP_CONTROL": "button",
    "KEY_CHANNEL": "event",
    "DOOR_BELL_INPUT_CHANNEL": "event",
    "MULTI_MODE_INPUT_CHANNEL": "event",
    # Misc
    "ANALOG_OUTPUT_CHANNEL": "number",
    "ANALOG_INPUT_CHANNEL": "sensor",
    "INTERNAL_SWITCH_CHANNEL": "switch",
    "ACCESS_AUTHORIZATION_CHANNEL": "text",
    "DISPLAY_CHANNEL": "select",
    # Wired bus
    "WIRED_INPUT_32_CHANNEL": "binary_sensor",
    "WIRED_4_CHANNEL": "switch",
}

# ---------------------------------------------------------------------------
# Device model type → HA platform overrides
# (used when channel type is ambiguous or missing)
# ---------------------------------------------------------------------------
MODEL_PLATFORM_OVERRIDES: dict[str, str] = {
    "HmIP-MP3P": "light",   # doorbell with LED
    "HmIP-BSL": "light",    # panel LED
    "HmIP-MOD-HO": "cover",
    "HmIP-MOD-TM": "cover",
    "HMIP-MOD-RC8": "switch",
}

# ---------------------------------------------------------------------------
# Sensor channel types → (device_class, unit, state_class)
# ---------------------------------------------------------------------------
SENSOR_CHANNEL_TYPES: dict[str, tuple[str | None, str | None, str | None]] = {
    # Temperature / humidity
    "TEMPERATURE_HUMIDITY_SENSOR_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    "TEMPERATURE_SENSOR_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    "WALL_MOUNTED_THERMOSTAT_PRO_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    "WALL_MOUNTED_THERMOSTAT_WITHOUT_DISPLAY_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    # Energy
    "ENERGY_SENSORS_INTERFACE_CHANNEL": (SensorDeviceClass.ENERGY, "kWh", "total_increasing"),
    "CURRENT_FLOW_SENSOR_CHANNEL": (SensorDeviceClass.POWER, "W", "measurement"),
    # Light
    "LIGHT_SENSOR_CHANNEL": (SensorDeviceClass.ILLUMINANCE, "lx", "measurement"),
    # Air quality
    "PARTICULATE_MATTER_SENSOR_CHANNEL": (SensorDeviceClass.PM25, "μg/m³", "measurement"),
    # Wind
    "WIND_SENSOR_CHANNEL": (SensorDeviceClass.WIND_SPEED, "km/h", "measurement"),
    # Weather
    "WEATHER_SENSOR_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    "WEATHER_SENSOR_PLUS_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    "WEATHER_SENSOR_PRO_CHANNEL": (SensorDeviceClass.TEMPERATURE, "°C", "measurement"),
    # Analog
    "ANALOG_INPUT_CHANNEL": (None, None, "measurement"),
}

# ---------------------------------------------------------------------------
# Binary sensor channel types → device_class
# ---------------------------------------------------------------------------
BINARY_SENSOR_CHANNEL_TYPES: dict[str, str] = {
    "SHUTTER_CONTACT_CHANNEL": BinarySensorDeviceClass.WINDOW,
    "SMOKE_DETECTOR_CHANNEL": BinarySensorDeviceClass.SMOKE,
    "MOTION_DETECTION_CHANNEL": BinarySensorDeviceClass.MOTION,
    "PRESENCE_DETECTION_CHANNEL": BinarySensorDeviceClass.PRESENCE,
    "WATER_SENSOR_CHANNEL": BinarySensorDeviceClass.MOISTURE,
    "RAIN_SENSOR_CHANNEL": BinarySensorDeviceClass.MOISTURE,
    "DOOR_LOCK_SENSOR_CHANNEL": BinarySensorDeviceClass.LOCK,
    "PASSAGE_DETECTOR_CHANNEL": BinarySensorDeviceClass.MOTION,
    "PASSAGE_DETECTOR_DIRECTION_CHANNEL": BinarySensorDeviceClass.MOTION,
    "IMPULSE_OUTPUT_CHANNEL": None,
    "WIRED_INPUT_32_CHANNEL": None,
}

# ---------------------------------------------------------------------------
# HmIP-BSL color constants
# ---------------------------------------------------------------------------
BSL_COLORS: dict[str, tuple[int, int, int]] = {
    "RED": (255, 0, 0),
    "GREEN": (0, 255, 0),
    "BLUE": (0, 0, 255),
    "YELLOW": (255, 255, 0),
    "WHITE": (255, 255, 255),
    "PURPLE": (128, 0, 128),
    "TURQUOISE": (0, 128, 128),
    "ORANGE": (255, 165, 0),
    "BLACK": (0, 0, 0),
}

# ---------------------------------------------------------------------------
# Siren tone constants (HmIP-ASIR)
# ---------------------------------------------------------------------------
SIREN_TONES: list[str] = [
    "FREQUENCY_RISING",
    "FREQUENCY_FALLING",
    "FREQUENCY_RISING_AND_FALLING",
    "FREQUENCY_ALTERNATING_LOW_HIGH",
    "FREQUENCY_ALTERNATING_MID_HIGH",
    "FREQUENCY_7",
    "FREQUENCY_8",
    "FREQUENCY_9",
    "REPEATING_SINGLE_TONE",
    "REPEATING_DOUBLE_TONE",
    "REPEATING_TRIPLE_TONE",
    "REPEATING_SINGLE_BURST",
    "REPEATING_DOUBLE_BURST",
    "TONE_14",
    "TONE_15",
    "TONE_16",
]

# ---------------------------------------------------------------------------
# Lock error types (for repair issues)
# ---------------------------------------------------------------------------
LOCK_ERROR_INVALID_PIN = "INVALID_AUTHORIZATION_PIN"
LOCK_ERROR_ACCESS_DENIED = "ACCESS_AUTHORIZATION_DENIED"

# ---------------------------------------------------------------------------
# Groups that may be empty (e.g. heating groups with no radiator valves)
# ---------------------------------------------------------------------------
EMPTY_GROUP_ALLOWLIST: set[str] = {
    "HEATING_GROUP",
    "HEATING_DEHUMIDIFIER_GROUP",
    "HEATING_COOLING_GROUP",
    "HEATING_CHANGEOVER_GROUP",
    "HEATING_FAILURE_ALERT_GROUP",
    "FLOOR_TERMINAL_BLOCK_10_GROUP",
    "FLOOR_TERMINAL_BLOCK_12_GROUP",
    "UNIVERSAL_LIGHT_GROUP",
}
