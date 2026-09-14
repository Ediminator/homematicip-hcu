class Entity:
    _attr_supported_features = 0

    @property
    def supported_features(self):
        return self._attr_supported_features

    _attr_device_class = None
    _attr_translation_key = None
    _attr_name = None
    _attr_has_entity_name = False
    hass = None

    @property
    def device_class(self):
        return self._attr_device_class
    
class DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__dict__.update(kwargs)

class EntityCategory:
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"
