from homeassistant.helpers.entity import Entity

class ValveDeviceClass:
    WATER = "water"
    GAS = "gas"

class ValveEntityFeature:
    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8

class ValveEntity(Entity):
    pass
