"""End-to-end setup tests against the real Home Assistant test harness.

These go through `hass.config_entries.async_setup` and `hass.services.async_call`
instead of constructing entities by hand, so platform setup, action
registration and unloading are exercised the way Home Assistant runs them.
"""

from __future__ import annotations

import asyncio
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import yaml

from custom_components.hcu_integration.api import (
    HcuApiClient,
    HcuApiError,
    ProcessEventsResult,
)
from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.util import get_entry_coordinator

# The integration depends on zeroconf, which would open real sockets.
pytestmark = pytest.mark.usefixtures("mock_async_zeroconf")

GROUP_ID = "00000000-0000-0000-0000-00000000abcd"


def _heating_group() -> dict:
    return {
        "id": GROUP_ID,
        "type": "HEATING",
        "label": "Living Room",
        "controllable": True,
        "controlMode": "AUTOMATIC",
        "activeProfile": "PROFILE_1",
        "setPointTemperature": 20.0,
        "actualTemperature": 19.5,
        "minTemperature": 4.5,
        "maxTemperature": 30.5,
        "ecoAllowed": True,
        "cooling": False,
        "boostMode": False,
        "partyMode": False,
        "profiles": {
            "PROFILE_1": {
                "index": "PROFILE_1",
                "name": "Standard",
                "enabled": True,
                "visible": True,
            }
        },
        # Groups without channels are skipped by discovery.
        "channels": [{"deviceId": "3014F711A0000000000000AA", "channelIndex": 1}],
    }


def _make_client() -> MagicMock:
    group = _heating_group()
    client = MagicMock(spec=HcuApiClient)
    client.state = {
        "home": {
            "id": "home-1",
            "functionalHomes": {"INDOOR_CLIMATE": {"absenceType": "NOT_ABSENT"}},
        },
        "devices": {},
        "groups": {GROUP_ID: group},
    }
    client.hcu_device_id = "hcu-1"
    client.hcu_part_device_ids = set()
    client.is_connected = True
    client.plugin_id = "de.homeassistant.hcu.integration"
    client.get_device_by_address = MagicMock(return_value=None)
    client.get_group_by_id = MagicMock(
        side_effect=lambda gid: client.state["groups"].get(gid)
    )
    client.process_events = MagicMock(return_value=ProcessEventsResult())
    client.disconnect = AsyncMock()
    client.disconnect_plugin = AsyncMock()
    client.async_activate_group_party_mode = AsyncMock()
    return client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Homematic IP HCU",
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        options={"comfort_temperature": 21.0},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def client() -> Generator[MagicMock]:
    mock_client = _make_client()
    with patch(
        "custom_components.hcu_integration.HcuApiClient", return_value=mock_client
    ):
        yield mock_client


async def test_setup_action_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """Set up the entry, call an action with a single-string entity_id, then unload."""
    with patch(
        "custom_components.hcu_integration.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data.client is client
    assert get_entry_coordinator(config_entry) is config_entry.runtime_data
    # Every action described in services.yaml must actually be registered.
    services_yaml = Path(__file__).parents[1] / (
        "custom_components/hcu_integration/services.yaml"
    )
    described = set(yaml.safe_load(services_yaml.read_text(encoding="utf-8")))
    assert described <= set(hass.services.async_services_for_domain(DOMAIN))

    climate_ids = hass.states.async_entity_ids("climate")
    assert len(climate_ids) == 1
    climate_id = climate_ids[0]

    # Single entity passed as a plain string, as scripts and automations do.
    await hass.services.async_call(
        DOMAIN,
        "activate_party_mode",
        {"entity_id": climate_id, "temperature": 22.0, "duration": 3600},
        blocking=True,
    )
    client.async_activate_group_party_mode.assert_awaited_once()
    assert (
        client.async_activate_group_party_mode.await_args.kwargs["group_id"] == GROUP_ID
    )

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert get_entry_coordinator(config_entry) is None


async def test_setup_retries_when_hcu_unreachable(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """If the HCU can't be reached, setup is retried and connections are closed."""
    with patch(
        "custom_components.hcu_integration.HcuCoordinator.async_setup",
        AsyncMock(return_value=False),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    client.disconnect.assert_awaited()
    client.disconnect_plugin.assert_awaited()
    assert getattr(config_entry, "runtime_data", None) is None


@pytest.mark.parametrize(
    ("language", "alarm", "vacation"),
    [("en", "Alarm", "Vacation mode"), ("de", "Alarmanlage", "Urlaubsmodus")],
)
async def test_home_entities_show_translated_names(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    client: MagicMock,
    language: str,
    alarm: str,
    vacation: str,
) -> None:
    """The alarm panel and vacation sensor get their names from the translations."""
    hass.config.language = language
    with patch(
        "custom_components.hcu_integration.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    names = {
        state.entity_id.split(".")[0]: state.attributes["friendly_name"]
        for state in hass.states.async_all(["alarm_control_panel", "binary_sensor"])
        if state.entity_id.startswith("alarm_control_panel.")
        or state.attributes.get("friendly_name", "").endswith(vacation)
    }
    assert names["alarm_control_panel"].endswith(alarm)
    assert names["binary_sensor"].endswith(vacation)


async def test_pending_device_reload_is_cancelled_on_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """A delayed reload after a device change does not run after the entry is unloaded."""
    client.process_events = MagicMock(
        return_value=ProcessEventsResult(reload_required={"dev-1"})
    )
    with patch(
        "custom_components.hcu_integration.coordinator.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
    coordinator = config_entry.runtime_data
    coordinator._initial_state_loaded = True

    # Hold the 10 s delay until the test releases it.
    release = asyncio.Event()

    async def _wait(_seconds: float) -> None:
        await release.wait()

    with patch.object(hass.config_entries, "async_reload", AsyncMock()) as reload:
        # `coordinator.asyncio` is the asyncio module, so only patch while
        # the delayed reload is scheduled and the entry is unloaded.
        with patch(
            "custom_components.hcu_integration.coordinator.asyncio.sleep", _wait
        ):
            coordinator._handle_event_message(
                {
                    "type": "HMIP_SYSTEM_EVENT",
                    "body": {"eventTransaction": {"events": {"0": {}}}},
                }
            )
            assert coordinator._pending_device_reload_task is not None
            assert await hass.config_entries.async_unload(config_entry.entry_id)
        release.set()
        await hass.async_block_till_done()

    reload.assert_not_awaited()
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_action_failure_via_hass_service_call_raises_translated_error(
    hass: HomeAssistant, config_entry: MockConfigEntry, client: MagicMock
) -> None:
    """Calling HA service that fails communicates failure with HomeAssistantError."""
    with patch(
        "custom_components.hcu_integration.HcuCoordinator.async_setup",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    climate_ids = hass.states.async_entity_ids("climate")
    assert len(climate_ids) == 1
    climate_id = climate_ids[0]

    client.async_activate_group_party_mode.side_effect = HcuApiError("Network failure")

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            "activate_party_mode",
            {"entity_id": climate_id, "temperature": 22.0, "duration": 3600},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == "entities_failed"

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
