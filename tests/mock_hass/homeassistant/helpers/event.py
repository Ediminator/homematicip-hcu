def async_call_later(hass, delay, action):
    pass


def async_track_state_change_event(hass, entity_ids, action):
    return hass.bus.async_listen("state_changed", action)

