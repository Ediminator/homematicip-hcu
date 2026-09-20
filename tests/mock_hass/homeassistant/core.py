class HomeAssistant:
    pass

class Callback:
    pass

class State:
    def __init__(self, entity_id, state, attributes=None, last_changed=None, last_updated=None, context=None):
        self.entity_id = entity_id
        self.state = str(state) if state is not None else ""
        self.attributes = attributes or {}
        self.last_changed = last_changed
        self.last_updated = last_updated
        self.context = context

class ServiceCall:
    def __init__(self, data):
        self.data = data

def split_entity_id(entity_id):
    return entity_id.split(".", 1)

def callback(func):
    return func

