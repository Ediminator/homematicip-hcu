"""Mock config_validation for homeassistant.helpers."""

def string(value):
    return str(value)

def boolean(value):
    return bool(value)

def config_entry_only_config_schema(domain):
    return lambda val: val
