class Entity:
    _attr_supported_features = 0

    @property
    def supported_features(self):
        return self._attr_supported_features

    _attr_device_class = None
    _attr_translation_key = None
    _attr_name = None
    _attr_has_entity_name = False
    _attr_translation_placeholders = None
    hass = None

    @property
    def device_class(self):
        return self._attr_device_class

    @property
    def translation_placeholders(self):
        return self._attr_translation_placeholders

    @property
    def translation_key(self):
        return self._attr_translation_key

    @property
    def has_entity_name(self):
        return self._attr_has_entity_name

    @property
    def name(self):
        return self._attr_name
    
class DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__dict__.update(kwargs)

class EntityCategory:
    CONFIG = "config"
    DIAGNOSTIC = "diagnostic"
