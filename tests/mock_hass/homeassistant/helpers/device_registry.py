class DeviceEntryType:
    SERVICE = "service"


class DeviceRegistry:
    def __init__(self):
        self.devices = {}

    def async_get_device(self, identifiers):
        return None


def async_get(hass):
    return getattr(hass, "device_registry", DeviceRegistry())


def async_entries_for_config_entry(registry, config_entry_id):
    return []
