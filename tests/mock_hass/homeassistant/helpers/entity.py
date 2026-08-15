from ..const import EntityCategory


class Entity:
    _attr_supported_features = 0
    _attr_device_class = None
    _attr_translation_key = None
    _attr_name = None
    _attr_has_entity_name = False

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def device_class(self):
        return self._attr_device_class


class DeviceInfo(dict):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            setattr(self, k, v)
