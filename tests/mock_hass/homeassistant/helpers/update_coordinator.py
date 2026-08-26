class UpdateFailed(Exception):
    """Exception to indicate an update failure."""
    pass


class DataUpdateCoordinator:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, hass, logger, name, update_interval=None, update_method=None, request_refresh_debouncer=None, always_update=True):
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval
        self.update_method = update_method
        self.data = {}
        self.entities = {}
        
    async def async_refresh(self):
        pass

    def async_set_updated_data(self, data):
        self.data = data


class CoordinatorEntity:
    def __class_getitem__(cls, item):
        return cls

    def __init__(self, coordinator):
        self.coordinator = coordinator
        
    @property
    def available(self):
        return True
