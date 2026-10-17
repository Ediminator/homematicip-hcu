class EntityRegistry:
    def __init__(self):
        self.entities = {}

    def async_get(self, entity_id):
        return self.entities.get(entity_id)

    def async_get_device_class_lookup(self, *args, **kwargs):
        return {}

    def async_remove(self, entity_id):
        self.entities.pop(entity_id, None)

_REGISTRY = EntityRegistry()

def async_get(hass):
    return _REGISTRY


def async_entries_for_config_entry(registry, config_entry_id):
    return []


def async_entries_for_device(registry, device_id, include_disabled_entities=False):
    return [
        entry
        for entry in registry.entities.values()
        if getattr(entry, "device_id", None) == device_id
    ]
