from collections import defaultdict


class State:
    def __init__(self, entity_id, state, attributes=None, last_changed=None, last_updated=None, context=None):
        self.entity_id = entity_id
        self.state = str(state)
        self.attributes = attributes or {}
        self.last_changed = last_changed
        self.last_updated = last_updated
        self.context = context


class CoreState:
    RUNNING = "RUNNING"
    STARTING = "STARTING"
    STOPPED = "STOPPED"



class Event:
    def __init__(self, event_type, data=None):
        self.event_type = event_type
        self.data = data or {}


class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)

    def async_listen(self, event_type, listener):
        self._listeners[event_type].append(listener)

    def async_fire(self, event_type, event_data=None):
        event = Event(event_type, event_data)
        for listener in list(self._listeners.get(event_type, [])):
            listener(event)


class HomeAssistant:
    def __init__(self):
        self.bus = EventBus()
        self.data = {}
        self.config_entries = None
        self.services = None

    async def async_block_till_done(self):
        pass

    def async_create_task(self, coro):
        return coro

    async def async_add_executor_job(self, target, *args):
        return target(*args)


class ServiceCall:
    def __init__(self, data):
        self.data = data


def split_entity_id(entity_id):
    return entity_id.split(".", 1)


def callback(func):
    return func
