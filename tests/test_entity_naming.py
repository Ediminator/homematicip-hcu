"""Entity naming: Home Assistant names entities after their device."""

from __future__ import annotations

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration import async_migrate_entry
from custom_components.hcu_integration.alarm_control_panel import HcuAlarmControlPanel
from custom_components.hcu_integration.binary_sensor import (
    HcuHeatDemandBinarySensorGroup,
    HcuVacationModeBinarySensor,
)
from custom_components.hcu_integration.const import DOMAIN
from custom_components.hcu_integration.switch import HcuSwitchGroup


def test_home_entities_use_translated_names(
    mock_coordinator: MagicMock, mock_hcu_client: MagicMock
) -> None:
    panel = HcuAlarmControlPanel(mock_coordinator, mock_hcu_client)
    vacation = HcuVacationModeBinarySensor(mock_coordinator, mock_hcu_client)

    assert panel.has_entity_name is True
    assert panel.translation_key == "hcu_alarm"
    assert not hasattr(panel, "_attr_name")
    assert vacation.has_entity_name is True
    assert vacation.translation_key == "hcu_vacation_mode"
    assert not hasattr(vacation, "_attr_name")


def test_group_entity_is_named_after_its_group_device(
    mock_coordinator: MagicMock, mock_hcu_client: MagicMock
) -> None:
    group = {"id": "group-1", "type": "SWITCHING", "label": "GARDEN_LIGHTS"}
    mock_hcu_client.get_group_by_id = MagicMock(return_value=group)

    entity = HcuSwitchGroup(mock_coordinator, mock_hcu_client, group)

    assert entity.has_entity_name is True
    assert entity._attr_name is None
    assert entity.device_info["name"] == "Garden Lights"


def test_unlabeled_heat_demand_group_gets_a_device_name(
    mock_coordinator: MagicMock, mock_hcu_client: MagicMock
) -> None:
    group = {"id": "group-2", "type": "HEATING_COOLING_DEMAND_BOILER"}
    mock_hcu_client.get_group_by_id = MagicMock(return_value=group)

    entity = HcuHeatDemandBinarySensorGroup(mock_coordinator, mock_hcu_client, group)

    assert entity._attr_name is None
    assert entity.device_info["name"] == "Boiler Heat Demand"


async def test_migration_removes_entity_prefix_and_explains_why(
    hass: HomeAssistant,
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=6,
        data={"host": "192.0.2.10", "entity_prefix": "House 1"},
        unique_id="hcu-1",
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 7
    assert "entity_prefix" not in entry.data
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"entity_prefix_removed_{entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_placeholders == {"prefix": "House 1"}


async def test_migration_without_prefix_creates_no_issue(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, version=6, data={"host": "192.0.2.10"}, unique_id="hcu-1"
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)

    assert entry.version == 7
    assert not ir.async_get(hass).issues
