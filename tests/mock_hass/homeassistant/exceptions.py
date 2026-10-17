class HomeAssistantError(Exception):
    pass


class ServiceValidationError(HomeAssistantError):
    pass


class ConfigEntryNotReady(HomeAssistantError):
    pass


class ConfigEntryAuthFailed(HomeAssistantError):
    pass

