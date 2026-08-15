class ClimateEntity:
    pass

class ClimateEntityFeature:
    TARGET_TEMPERATURE = 1
    PRESET_MODE = 16

class HVACMode:
    OFF = "off"
    HEAT = "heat"
    COOL = "cool"
    HEAT_COOL = "heat_cool"
    AUTO = "auto"
    DRY = "dry"
    FAN_ONLY = "fan_only"

class HVACAction:
    OFF = "off"
    HEATING = "heating"
    COOLING = "cooling"
    IDLE = "idle"
    DRYING = "drying"
    FAN = "fan"

PRESET_BOOST = "boost"
