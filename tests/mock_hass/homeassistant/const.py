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
    VALVE = "valve"
    TEXT = "text"
    SELECT = "select"
    UPDATE = "update"

class EntityCategory(Enum):
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"


CONF_HOST = "host"
CONF_TOKEN = "token"

CONCENTRATION_PARTS_PER_MILLION = "ppm"
PERCENTAGE = "%"
class DynamicUnit(type):
    def __getattr__(cls, name):
        return name.lower()

UnitOfRatio = DynamicUnit("UnitOfRatio", (), {"PARTS_PER_MILLION": "ppm"})

UnitOfTemperature = DynamicUnit("UnitOfTemperature", (), {"CELSIUS": "°C"})
UnitOfPower = DynamicUnit("UnitOfPower", (), {"WATT": "W"})
UnitOfEnergy = DynamicUnit("UnitOfEnergy", (), {"KILO_WATT_HOUR": "kWh"})
UnitOfElectricCurrent = DynamicUnit("UnitOfElectricCurrent", (), {"AMPERE": "A"})
UnitOfElectricPotential = DynamicUnit("UnitOfElectricPotential", (), {"VOLT": "V"})
UnitOfFrequency = DynamicUnit("UnitOfFrequency", (), {"HERTZ": "Hz"})
UnitOfInformation = DynamicUnit("UnitOfInformation", (), {"MEGABYTES": "MB"})
UnitOfTime = DynamicUnit("UnitOfTime", (), {"SECONDS": "s", "MINUTES": "min"})
DEGREE = "°"
ATTR_TEMPERATURE = "temperature"
ATTR_ENTITY_ID = "entity_id"
LIGHT_LUX = "lx"
UnitOfLength = DynamicUnit("UnitOfLength", (), {"KILOMETERS": "km", "METERS": "m", "CENTIMETERS": "cm"})
UnitOfPrecipitationDepth = DynamicUnit("UnitOfPrecipitationDepth", (), {"MILLIMETERS": "mm"})
UnitOfSpeed = DynamicUnit("UnitOfSpeed", (), {"KILOMETERS_PER_HOUR": "km/h"})
UnitOfVolume = DynamicUnit("UnitOfVolume", (), {"CUBIC_METERS": "m³", "LITERS": "L"})

STATE_ON = "on"
STATE_OFF = "off"
STATE_UNKNOWN = "unknown"
STATE_UNAVAILABLE = "unavailable"

def __getattr__(name):
    return name.lower()


