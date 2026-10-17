"""Mock homeassistant.components.zeroconf for test environment."""
from unittest.mock import AsyncMock, MagicMock


class HaServiceInfo:
    """Mock ZeroconfServiceInfo."""


ZeroconfServiceInfo = HaServiceInfo


async def async_get_async_instance(hass):
    mock_zc = MagicMock()
    mock_zc.async_get_service_info = AsyncMock(return_value=None)
    return mock_zc
