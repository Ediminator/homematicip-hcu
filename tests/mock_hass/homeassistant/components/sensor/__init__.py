class MetaDeviceClass(type):
    def __getattr__(cls, name):
        return name.lower()

class SensorDeviceClass(metaclass=MetaDeviceClass):
    TEMPERATURE = "temperature"
    POWER = "power"
    ENERGY = "energy"
    CURRENT = "current"
    VOLTAGE = "voltage"
    FREQUENCY = "frequency"
    DATA_SIZE = "data_size"
    DURATION = "duration"
    ILLUMINANCE = "illuminance"
    HUMIDITY = "humidity"
    BATTERY = "battery"
    SIGNAL_STRENGTH = "signal_strength"
    TIMESTAMP = "timestamp"
    GAS = "gas"
    WIND_SPEED = "wind_speed"
    PRECIPITATION = "precipitation"
    MOISTURE = "moisture"
    CO2 = "carbon_dioxide"
    ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
    
class SensorStateClass:
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"
    TOTAL = "total"

class SensorEntity:
    pass
