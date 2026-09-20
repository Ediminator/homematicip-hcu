from unittest.mock import MagicMock

def __getattr__(name):
    return MagicMock()
