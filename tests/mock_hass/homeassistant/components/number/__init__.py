"""Mock number platform for Home Assistant."""
from enum import StrEnum

class NumberMode(StrEnum):
    AUTO = "auto"
    BOX = "box"
    SLIDER = "slider"

class NumberEntity:
    pass
