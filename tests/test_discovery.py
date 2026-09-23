"""Tests for device and group discovery."""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.const import SYSTEM_RULE_GROUPS
from custom_components.hcu_integration.discovery import async_discover_entities


def test_heat_demand_rule_in_system_rule_groups():
    """Test that HEAT_DEMAND_RULE is recognized as a system rule group."""
    assert "HEAT_DEMAND_RULE" in SYSTEM_RULE_GROUPS


async def test_heat_demand_rule_group_skipped_without_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test that HEAT_DEMAND_RULE group is skipped without logging a warning."""
    mock_hcu_client.state = {
        "devices": {},
        "groups": {
            "heat-demand-rule-id": {
                "id": "heat-demand-rule-id",
                "type": "HEAT_DEMAND_RULE",
                "label": "Heat Demand Rule",
                "channels": ["some_channel"],
            }
        },
    }

    with caplog.at_level(logging.DEBUG):
        entities = await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )

    # No entities created for any platform from HEAT_DEMAND_RULE
    for platform, platform_entities in entities.items():
        assert len(platform_entities) == 0

    # Ensure no warning was logged for unknown group type
    assert not any(
        record.levelno >= logging.WARNING and "Unknown group type" in record.message
        for record in caplog.records
    )

    # Ensure debug message confirms skipping system rule group
    assert any(
        "Skipping system rule group 'Heat Demand Rule'" in record.message
        for record in caplog.records
    )


def test_plugin_version_matches_manifest():
    """Test that PLUGIN_VERSION in const.py matches version in manifest.json."""
    import json
    from pathlib import Path
    from custom_components.hcu_integration.const import PLUGIN_VERSION

    manifest_path = Path(__file__).parent.parent / "custom_components" / "hcu_integration" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert PLUGIN_VERSION == manifest["version"]

