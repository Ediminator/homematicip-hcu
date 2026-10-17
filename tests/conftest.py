"""Common test fixtures for Homematic IP HCU integration.

Tests run against the real Home Assistant test harness from
`pytest-homeassistant-custom-component` (see requirements_test.txt).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.api import HcuApiClient, ProcessEventsResult
from custom_components.hcu_integration.const import DOMAIN


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load custom_components/hcu_integration in every test."""
    return


@pytest.fixture
def api_client(hass: HomeAssistant) -> HcuApiClient:
    """Create an API client instance."""
    session = MagicMock(spec=aiohttp.ClientSession)
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
def mock_coordinator() -> MagicMock:
    """Create a mock coordinator."""
    coordinator = MagicMock()
    coordinator.async_add_listener = MagicMock()
    return coordinator
