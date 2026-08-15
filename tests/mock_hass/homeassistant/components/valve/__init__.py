"""Mock valve platform for Home Assistant."""
from enum import IntFlag

class ValveDeviceClass:
    WATER = "water"
    GAS = "gas"

class ValveEntityFeature(IntFlag):
    OPEN = 1
    CLOSE = 2
    SET_POSITION = 4
    STOP = 8

class ValveEntity:
    pass
