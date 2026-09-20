class MetaBinarySensor(type):
    def __getattr__(cls, name):
        return name.lower()

class BinarySensorDeviceClass(metaclass=MetaBinarySensor):
    BATTERY = "battery"
    CONNECTIVITY = "connectivity"
    DOOR = "door"
    WINDOW = "window"
    MOTION = "motion"
    OCCUPANCY = "occupancy"
    LIGHT = "light"
    PROBLEM = "problem"
    TAMPER = "tamper"
    MOISTURE = "moisture"
    SMOKE = "smoke"
    SAFETY = "safety"
    RUNNING = "running"

class BinarySensorEntity:
    pass
