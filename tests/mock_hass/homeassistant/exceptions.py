"""Mock exceptions for Home Assistant."""

class HomeAssistantError(Exception):
    """General Home Assistant exception."""
    pass

class ServiceValidationError(HomeAssistantError):
    """Raised when a service validation error occurs."""
    pass
