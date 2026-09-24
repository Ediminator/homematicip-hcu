class DeviceEntryType:
    SERVICE = "service"


class DeviceRegistry:
    def __init__(self):
        self.devices = {}

    def async_get(self, device_id):
        return self.devices.get(device_id)

    def async_remove_device(self, device_id):
        self.devices.pop(device_id, None)


_REGISTRY = DeviceRegistry()


def async_get(hass):
    return _REGISTRY


def async_entries_for_config_entry(registry, config_entry_id):
    return []
