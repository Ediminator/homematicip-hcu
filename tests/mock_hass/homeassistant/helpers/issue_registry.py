"""Mock issue_registry for homeassistant.helpers."""
from enum import StrEnum

class IssueSeverity(StrEnum):
    CRITICAL = "critical"
    ERROR = "error"
    WARNING = "warning"

def async_create_issue(hass, domain, issue_id, **kwargs):
    pass

def async_delete_issue(hass, domain, issue_id):
    pass
