"""Device info links and the HA device edit step when data is missing."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.binary_sensor import HcuSecurityAlarmBinarySensor
from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.entity import _resolve_via_device_info


def test_home_entity_device_info_links_to_hcu(
    mock_coordinator: MagicMock, mock_hcu_client: MagicMock
) -> None:
    sensor = HcuSecurityAlarmBinarySensor(
        mock_coordinator, mock_hcu_client, "safetyAlarmActive", "safety_alarm"
    )

    assert sensor.device_info == {"identifiers": {(DOMAIN, "test-hcu-device-id")}}


def test_home_entity_device_info_without_hcu_id(
    mock_coordinator: MagicMock, mock_hcu_client: MagicMock
) -> None:
    """No device link instead of an identifier containing None."""
    mock_hcu_client.hcu_device_id = None
    sensor = HcuSecurityAlarmBinarySensor(
        mock_coordinator, mock_hcu_client, "safetyAlarmActive", "safety_alarm"
    )

    assert sensor.device_info is None


def test_via_device_info_without_hcu_id(mock_coordinator: MagicMock) -> None:
    mock_coordinator.hcu_device_entry_id = None
    mock_coordinator.hass = None

    assert _resolve_via_device_info(mock_coordinator, None) == {}


@pytest.mark.usefixtures("mock_async_zeroconf")
async def test_ha_device_edit_when_device_was_removed(hass: HomeAssistant) -> None:
    """If the device picked for editing is gone, the selection is shown again."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"host": "192.0.2.10", "plugin_token": "token", "auth_type": "plugin"},
        options={
            "ha_devices": [
                {"id": "kept", "name": "Kept lamp", "type": "light", "features": {}}
            ]
        },
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    flow = hass.config_entries.options._progress[result["flow_id"]]
    flow._editing_device_id = "removed"

    result = await flow.async_step_ha_devices_edit()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "ha_devices_edit"
    assert "device_id" in result["data_schema"].schema
    assert flow._editing_device_id is None
