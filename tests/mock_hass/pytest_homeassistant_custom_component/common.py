class MockConfigEntry:
    def __init__(self, domain=None, unique_id=None, data=None, entry_id="test", title="", options=None, **kwargs):
        self.domain = domain
        self.unique_id = unique_id
        self.data = data or {}
        self.entry_id = entry_id
        self.title = title
        self.options = options or {}
        for k, v in kwargs.items():
            setattr(self, k, v)
        
    def add_to_hass(self, hass):
        pass
