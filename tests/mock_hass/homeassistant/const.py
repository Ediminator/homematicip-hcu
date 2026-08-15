from enum import Enum

class Platform(Enum):
    COVER = "cover"
    BINARY_SENSOR = "binary_sensor"
    SENSOR = "sensor"
    SWITCH = "switch"
    LIGHT = "light"
    ALARM_CONTROL_PANEL = "alarm_control_panel"
    CLIMATE = "climate"
    BUTTON = "button"
    NUMBER = "number"
    EVENT = "event"
    LOCK = "lock"
    SIREN = "siren"
    UPDATE = "update"
    SELECT = "select"
    TEXT = "text"
    VALVE = "valve"

class EntityCategory(Enum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"

CONF_HOST = "host"
CONF_TOKEN = "token"

STATE_ON = "on"
STATE_OFF = "off"
STATE_UNAVAILABLE = "unavailable"
STATE_UNKNOWN = "unknown"
ATTR_FRIENDLY_NAME = "friendly_name"

CONCENTRATION_PARTS_PER_MILLION = "ppm"
PERCENTAGE = "%"
UnitOfTemperature = type("UnitOfTemperature", (), {"CELSIUS": "°C"})
UnitOfPower = type("UnitOfPower", (), {"WATT": "W", "KILO_WATT": "kW"})
UnitOfEnergy = type("UnitOfEnergy", (), {"KILO_WATT_HOUR": "kWh", "WATT_HOUR": "Wh", "MEGA_WATT_HOUR": "MWh"})
UnitOfElectricCurrent = type("UnitOfElectricCurrent", (), {"AMPERE": "A", "MILLIAMPERE": "mA"})
UnitOfElectricPotential = type("UnitOfElectricPotential", (), {"VOLT": "V", "MILLIVOLT": "mV"})
UnitOfFrequency = type("UnitOfFrequency", (), {"HERTZ": "Hz"})
UnitOfInformation = type("UnitOfInformation", (), {"MEGABYTES": "MB"})
UnitOfTime = type("UnitOfTime", (), {"SECONDS": "s", "MINUTES": "min", "HOURS": "h", "DAYS": "d"})
DEGREE = "°"
ATTR_TEMPERATURE = "temperature"
ATTR_ENTITY_ID = "entity_id"
LIGHT_LUX = "lx"
UnitOfLength = type("UnitOfLength", (), {"KILOMETERS": "km", "METERS": "m", "MILLIMETERS": "mm"})
UnitOfPrecipitationDepth = type("UnitOfPrecipitationDepth", (), {"MILLIMETERS": "mm"})
UnitOfSpeed = type("UnitOfSpeed", (), {"KILOMETERS_PER_HOUR": "km/h"})
UnitOfVolume = type("UnitOfVolume", (), {"CUBIC_METERS": "m³", "LITERS": "L"})
