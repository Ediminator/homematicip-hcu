"""Mock restore_state for homeassistant.helpers."""

class RestoreEntity:
    async def async_get_last_state(self):
        return None
