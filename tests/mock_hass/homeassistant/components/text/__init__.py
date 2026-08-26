"""Mock text platform for Home Assistant."""
from enum import StrEnum

class TextMode(StrEnum):
    AUTO = "auto"
    PASSWORD = "password"
    TEXT = "text"

class TextEntity:
    pass
