class MockConfigEntry:
    def __init__(self, domain="hcu_integration", unique_id="test", data=None, entry_id="test", options=None, title=None, **kwargs):
        self.domain = domain
        self.unique_id = unique_id
        self.data = data or {}
        self.entry_id = entry_id
        self.options = options or {}
        self.title = title
        for k, v in kwargs.items():
            setattr(self, k, v)
        
    def add_to_hass(self, hass):
        pass
