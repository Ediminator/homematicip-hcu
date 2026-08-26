from enum import IntFlag


class UpdateDeviceClass:
    FIRMWARE = "firmware"


class UpdateEntityFeature(IntFlag):
    INSTALL = 1
    BACKUP = 2
    PROGRESS = 4


class UpdateEntity:
    pass
