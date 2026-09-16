"""Common test fixtures for Homematic IP HCU integration."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# If Home Assistant is not installed in the test environment, fall back to mock stubs in tests/mock_hass.
# This prevents mocks from globally shadowing a real Home Assistant installation or official test fixtures.
try:
    import homeassistant  # noqa: F401
except ImportError:
    mock_hass_path = str(Path(__file__).parent / "mock_hass")
    if mock_hass_path not in sys.path:
        sys.path.append(mock_hass_path)

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.api import HcuApiClient


@pytest.fixture
def api_client(hass: HomeAssistant) -> HcuApiClient:
    """Create an API client instance."""
    session = MagicMock(spec=aiohttp.ClientSession)
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    return HcuApiClient(
        hass=hass,
        host="192.168.1.100",
        auth_token="test-token",
        session=session,
    )


@pytest.fixture
def mock_hcu_client() -> MagicMock:
    """Create a mock HCU API client."""
    client = MagicMock(spec=HcuApiClient)
    client.state = {
        "home": {
            "id": "test-home-id",
            "currentAPVersion": "1.0.0",
        },
        "devices": {},
        "groups": {},
    }
    client.hcu_device_id = "test-hcu-device-id"
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.listen = AsyncMock()
    client.get_system_state = AsyncMock(return_value=client.state)
    client.get_device_by_address = MagicMock(return_value=None)
    client.get_group_by_id = MagicMock(return_value=None)
    from custom_components.hcu_integration.api import ProcessEventsResult
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP Local (HCU)",
        data={
            "host": "192.168.1.100",
            "auth_port": 6969,
            "websocket_port": 9001,
            "token": "test-auth-token",
        },
        options={
            "comfort_temperature": 21.0,
        },
        unique_id="192.168.1.100",
    )


@pytest.fixture
def mock_device_data() -> dict:
    """Create mock device data for testing."""
    return {
        "id": "test-device-id",
        "type": "HMIP-PSM",
        "label": "Test Device",
        "modelType": "HMIP-PSM",
        "permanentlyReachable": True,
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "label": "Test Device",
            },
            "1": {
                "functionalChannelType": "SWITCH_MEASURING",
                "label": "Test Switch",
                "on": False,
                "powerConsumption": 0.0,
            },
        },
    }


@pytest.fixture
def mock_group_data() -> dict:
    """Create mock group data for testing."""
    return {
        "id": "test-group-id",
        "type": "HEATING",
        "label": "Test Heating Group",
        "controllable": True,
        "controlMode": "AUTOMATIC",
        "activeProfile": "PROFILE_1",
        "setPointTemperature": 21.0,
        "actualTemperature": 20.5,
        "humidity": 50,
        "minTemperature": 5.0,
        "maxTemperature": 30.0,
        "boostMode": False,
        "partyMode": "INACTIVE",
        "profiles": {
            "PROFILE_1": {
                "index": "PROFILE_1",
                "name": "Standard",
                "enabled": True,
                "visible": True,
            },
        },
        "channels": [],
    }


@pytest.fixture
def mock_coordinator():
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    return coordinator


@pytest.fixture
def hass():
    """Create a mock HomeAssistant instance."""
    hass_obj = MagicMock()
    hass_obj.data = {}
    hass_obj.bus = MagicMock()
    hass_obj.services = MagicMock()
    hass_obj.async_block_till_done = AsyncMock()
    return hass_obj
