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
