from homeassistant.helpers.entity import Entity

class RestoreEntity(Entity):
    async def async_get_last_state(self):
        return None
