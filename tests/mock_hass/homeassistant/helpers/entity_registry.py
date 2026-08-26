from enum import Enum


class RegistryEntryDisabler(Enum):
    INTEGRATION = "integration"
    USER = "user"
    DEVICE = "device"


class EntityRegistry:
    def __init__(self):
        self.entities = {}

    def async_get_entity_id(self, domain, platform, unique_id):
        return None


def async_get(hass):
    return getattr(hass, "entity_registry", EntityRegistry())


def async_entries_for_config_entry(registry, config_entry_id):
    return []
