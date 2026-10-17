from enum import IntFlag
from homeassistant.helpers.entity import Entity


class UpdateDeviceClass:
    FIRMWARE = "firmware"


class UpdateEntityFeature(IntFlag):
    INSTALL = 1
    SPECIFIC_VERSION = 2
    PROGRESS = 4
    BACKUP = 8
    RELEASE_NOTES = 16


class UpdateEntity(Entity):
    _attr_supported_features: UpdateEntityFeature = UpdateEntityFeature(0)

    @property
    def supported_features(self) -> UpdateEntityFeature:
        return self._attr_supported_features

