from homeassistant.helpers.entity import Entity

class UpdateDeviceClass:
    FIRMWARE = "firmware"

class UpdateEntityFeature:
    INSTALL = 1
    PROGRESS = 2

class UpdateEntity(Entity):
    pass
