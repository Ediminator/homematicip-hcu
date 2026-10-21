"""Comprehensive behavior-pinning coverage tests for discovery.py."""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import MagicMock, patch

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hcu_integration.binary_sensor import (
    HcuBinarySensor,
    HcuHeatDemandBinarySensorGroup,
    HcuVacationModeBinarySensor,
    HcuWindowBinarySensor,
)
from custom_components.hcu_integration.button import (
    HcuDeviceIdentifyButton,
    HcuResetEnergyButton,
    HcuResetWaterVolume,
)
from custom_components.hcu_integration.climate import HcuClimate
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_PLUGIN,
    CONF_DISABLE_UNCONFIGURED_CHANNELS,
    CONF_DISABLED_GROUPS,
    DOMAIN,
    HA_DEVICE_ID_PREFIX,
)
from custom_components.hcu_integration.cover import HcuCoverGroup
from custom_components.hcu_integration.discovery import (
    _discover_entities_for_device,
    _is_channel_light,
    _is_switching_group_lights_only,
    _resolve_translation_prefixes,
    async_discover_entities,
    async_discover_entities_for_device,
)
from custom_components.hcu_integration.event import HcuButtonEvent
from custom_components.hcu_integration.light import (
    HcuLightGroup,
    HcuSwitchLight,
)
from custom_components.hcu_integration.number import HcuConfigRampTime
from custom_components.hcu_integration.select import (
    HcuAlarmSignalAcoustic,
    HcuAlarmSignalOptical,
    HcuPowerUpSwitchState,
)
from custom_components.hcu_integration.sensor import (
    HcuGenericSensor,
    HcuHomeSensor,
    HcuTemperatureSensor,
    HcuWindowStateSensor,
)
from custom_components.hcu_integration.switch import (
    HcuConfigUseInternalOnTime,
    HcuSwitch,
    HcuSwitchGroup,
    HcuWateringGroup,
)
from custom_components.hcu_integration.update import HcuFirmwareUpdate

# -----------------------------------------------------------------------------
# 1. HA Entity Bridge & Manufacturer / OEM Filtering
# -----------------------------------------------------------------------------


def test_ha_entity_bridge_device_skipped(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Devices imported from Home Assistant Entity Bridge must be skipped."""
    device_data = {
        "id": "bridge-dev-1",
        "pluginDeviceId": f"{HA_DEVICE_ID_PREFIX}light.kitchen_ceiling",
        "label": "Bridged Kitchen Light",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    for p, entity_list in entities.items():
        assert len(entity_list) == 0, f"Expected no entities for {p}"
    assert len(valid_unique_ids) == 0


async def test_ha_entity_bridge_device_omitted_from_valid_device_ids(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Bridged devices must be excluded from valid_device_ids so orphaned bridge devices get removed."""
    mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)
    orphaned_bridge_device = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "bridge-dev-1")},
        name="Old Bridged Device",
    )

    mock_hcu_client.state = {
        "devices": {
            "bridge-dev-1": {
                "id": "bridge-dev-1",
                "pluginDeviceId": f"{HA_DEVICE_ID_PREFIX}switch.fan",
                "label": "Bridged Fan",
                "functionalChannels": {},
            }
        },
        "groups": {},
    }

    await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )

    # Device should have been removed by device registry cleanup
    assert dev_reg.async_get(orphaned_bridge_device.id) is None


@pytest.mark.parametrize(
    "options,expected_disabled",
    [
        ({"disabled_oems": ["Somfy"]}, True),
        ({"disabled_oems": ["Other"]}, False),
        ({"disabled_oems": None, "import_Somfy": False}, True),
        ({"disabled_oems": None, "import_Somfy": True}, False),
        ({}, False),
    ],
)
def test_oem_manufacturer_filtering(
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
    options: dict,
    expected_disabled: bool,
) -> None:
    """Test filtering of 3rd party OEM devices via disabled_oems or import_OEM flags."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options=options)
    device_data = {
        "id": "oem-dev-1",
        "label": "Somfy Blind",
        "oem": "Somfy",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SHUTTER_CHANNEL",
                "groups": ["g1"],
            }
        },
    }

    with caplog.at_level(logging.DEBUG):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, entry, mock_coordinator, mock_hcu_client
        )

    if expected_disabled:
        assert (
            "Skipping device oem-dev-1 (Somfy Blind) as manufacturer Somfy is disabled"
            in caplog.text
        )
        assert len(valid_unique_ids) == 0
        assert len(entities[Platform.COVER]) == 0
    else:
        assert len(valid_unique_ids) > 0
        assert len(entities[Platform.COVER]) == 1


# -----------------------------------------------------------------------------
# 2. Firmware Update Discovery
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "update_state,fw_version,should_create",
    [
        ("UPDATE_AVAILABLE", "2.4.1", True),
        (None, "2.4.1", False),
        ("UPDATE_AVAILABLE", None, False),
        ("UPDATE_AVAILABLE", "", False),
        ("UPDATE_AVAILABLE", "UNKNOWN", False),
    ],
)
def test_firmware_update_discovery(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    update_state: str | None,
    fw_version: str | None,
    should_create: bool,
) -> None:
    """Test HcuFirmwareUpdate entity creation based on updateState and availableFirmwareVersion."""
    device_data = {
        "id": "dev-fw-1",
        "label": "Test Thermostat",
        "type": "HEATING_THERMOSTAT",
        "updateState": update_state,
        "availableFirmwareVersion": fw_version,
        "functionalChannels": {},
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )

    update_entities = entities[Platform.UPDATE]
    if should_create:
        assert len(update_entities) == 1
        assert isinstance(update_entities[0], HcuFirmwareUpdate)
        assert update_entities[0].unique_id == "dev-fw-1_firmware_update"
        assert "dev-fw-1_firmware_update" in valid_unique_ids
    else:
        assert len(update_entities) == 0


# -----------------------------------------------------------------------------
# 3. Channel Mapping, Prefix Matching & Unconfigured Channels
# -----------------------------------------------------------------------------


def test_switch_visualization_light_converts_hcu_switch(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """A SWITCH_CHANNEL with switchVisualization=LIGHT creates HcuSwitchLight instead of HcuSwitch."""
    device_data = {
        "id": "dev-sw-light",
        "label": "Light Switch",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "groups": ["g1"],
                "switchVisualization": "LIGHT",
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert len(entities[Platform.LIGHT]) == 1
    assert isinstance(entities[Platform.LIGHT][0], HcuSwitchLight)
    assert len(entities[Platform.SWITCH]) == 0
    assert entities[Platform.LIGHT][0].unique_id in valid_unique_ids

    # Non-switch channel with switchVisualization=LIGHT does not become HcuSwitchLight
    sensor_data = {
        "id": "dev-contact",
        "label": "Window Contact",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SHUTTER_CHANNEL",
                "groups": ["g1"],
                "switchVisualization": "LIGHT",
            }
        },
    }
    s_entities, _ = _discover_entities_for_device(
        sensor_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert len(s_entities[Platform.LIGHT]) == 0
    assert len(s_entities[Platform.COVER]) == 1


def test_channel_mapping_feature_prevents_duplicate_feature_discovery(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """When a channel mapping claims a feature, the later HMIP_FEATURE_TO_ENTITY loop skips it."""
    custom_channel_mapping = {
        "CUSTOM_HUMIDITY_ROLE": {
            "class": "HcuGenericSensor",
            "feature": "humidity",
            "name": "Humidity",
        }
    }
    device_data = {
        "id": "dev-custom-role",
        "label": "Custom Role Device",
        "functionalChannels": {
            "1": {
                "channelRole": "CUSTOM_HUMIDITY_ROLE",
                "groups": ["g1"],
                "humidity": 55.0,
            }
        },
    }
    with patch.dict(
        "custom_components.hcu_integration.discovery.HMIP_CHANNEL_ROLE_TO_ENTITY",
        custom_channel_mapping,
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
    humidity_sensors = [
        e
        for e in entities[Platform.SENSOR]
        if getattr(e, "unique_id", "").endswith("humidity")
    ]
    assert len(humidity_sensors) == 1
    assert len(entities[Platform.SENSOR]) == 1
    assert humidity_sensors[0].unique_id in valid_unique_ids


def test_channel_prefix_matching(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Test prefix-matching for channel types (e.g. SWITCH_CHANNEL_CUSTOM)."""
    device_data = {
        "id": "dev-switch-pfx",
        "label": "Custom Switch",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL_EXTENDED",
                "groups": ["g1"],
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    switches = entities[Platform.SWITCH]
    assert len(switches) == 1
    assert isinstance(switches[0], HcuSwitch)
    assert "dev-switch-pfx_1_on" in valid_unique_ids


def test_deactivated_by_default_device_unused_channel_skipped(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """FLOOR_TERMINAL_BLOCK channels without groups must be skipped."""
    device_data = {
        "id": "dev-fal-1",
        "type": "FLOOR_TERMINAL_BLOCK_12",
        "label": "Floor Heating Controller",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                # no groups
            },
            "2": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "groups": ["group-room-2"],
            },
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    # Channel 1 skipped, channel 2 created
    switches = entities[Platform.SWITCH]
    assert len(switches) == 1
    assert switches[0].unique_id == "dev-fal-1_2_on"
    assert "dev-fal-1_1_on" not in valid_unique_ids


@pytest.mark.parametrize(
    "disable_unconfigured,should_create",
    [
        (True, False),
        (False, True),
    ],
)
def test_unconfigured_channel_skipping(
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
    disable_unconfigured: bool,
    should_create: bool,
) -> None:
    """Test skipping unconfigured channels when CONF_DISABLE_UNCONFIGURED_CHANNELS is True."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_DISABLE_UNCONFIGURED_CHANNELS: disable_unconfigured},
    )
    device_data = {
        "id": "dev-plug-1",
        "label": "Unassigned Plug",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                # no groups assigned
            }
        },
    }
    with caplog.at_level(logging.DEBUG):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, entry, mock_coordinator, mock_hcu_client
        )

    switches = entities[Platform.SWITCH]
    if should_create:
        assert len(switches) == 1
        assert "dev-plug-1_1_on" in valid_unique_ids
    else:
        assert len(switches) == 0
        assert "dev-plug-1_1_on" not in valid_unique_ids
        assert (
            "Skipping channel 1 (SWITCH_CHANNEL) on device dev-plug-1 (Unassigned Plug): not assigned to a room in the Homematic IP app"
            in caplog.text
        )


def test_channel_role_with_feature_mapping(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Test channel role WINDOW_SENSOR maps to HcuWindowBinarySensor with feature windowState."""
    device_data = {
        "id": "dev-contact-1",
        "label": "Window Contact",
        "functionalChannels": {
            "1": {
                "channelRole": "WINDOW_SENSOR",
                "functionalChannelType": "SHUTTER_CONTACT_CHANNEL",
                "groups": ["g1"],
                "windowState": "CLOSED",
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    binary_sensors = entities[Platform.BINARY_SENSOR]
    assert len(binary_sensors) == 1
    assert isinstance(binary_sensors[0], HcuWindowBinarySensor)
    assert binary_sensors[0].unique_id == "dev-contact-1_1_windowState"
    assert "dev-contact-1_1_windowState" in valid_unique_ids


def test_channel_extra_entities_configurations(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test extra_entities parsing: string, dict with only_channel_types filter, empty class, and exception handling."""
    # Test 1: String extra entity (DIMMER_CHANNEL -> HcuConfigRampTime)
    dimmer_device = {
        "id": "dev-dim-1",
        "label": "Dimmer",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DIMMER_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    entities, _ = _discover_entities_for_device(
        dimmer_device, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert len(entities[Platform.LIGHT]) == 1
    assert any(isinstance(e, HcuConfigRampTime) for e in entities[Platform.NUMBER])

    # Test 2: Dict extra entity with only_channel_types filter
    # WINDOW_SENSOR has extra_entities: [{"class": "HcuWindowStateSensor", "only_channel_types": ["ROTARY_HANDLE_CHANNEL"]}]
    rotary_device = {
        "id": "dev-rot-1",
        "label": "Rotary Handle",
        "functionalChannels": {
            "1": {
                "channelRole": "WINDOW_SENSOR",
                "functionalChannelType": "ROTARY_HANDLE_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    entities, _ = _discover_entities_for_device(
        rotary_device, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert any(isinstance(e, HcuWindowStateSensor) for e in entities[Platform.SENSOR])

    # With SHUTTER_CONTACT_CHANNEL -> only_channel_types does not match, so extra entity NOT created
    contact_device = {
        "id": "dev-ct-1",
        "label": "Contact",
        "functionalChannels": {
            "1": {
                "channelRole": "WINDOW_SENSOR",
                "functionalChannelType": "SHUTTER_CONTACT_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    entities, _ = _discover_entities_for_device(
        contact_device, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert not any(
        isinstance(e, HcuWindowStateSensor) for e in entities[Platform.SENSOR]
    )

    # Test 3: Extra entity exception handling
    with (
        patch(
            "custom_components.hcu_integration.number.HcuConfigRampTime.__init__",
            side_effect=TypeError("Mock ramp time init error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, _ = _discover_entities_for_device(
            dimmer_device, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create extra entity 'HcuConfigRampTime' for device dev-dim-1, channel 1: Mock ramp time init error"
            in caplog.text
        )


def test_channel_entity_creation_exception(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when primary channel entity constructor raises an exception."""
    device_data = {
        "id": "dev-err-1",
        "label": "Broken Switch",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    with (
        patch(
            "custom_components.hcu_integration.switch.HcuSwitch.__init__",
            side_effect=TypeError("Switch error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create entity for device dev-err-1, channel 1 (type: SWITCH_CHANNEL, base: SWITCH_CHANNEL, class: HcuSwitch): Switch error"
            in caplog.text
        )
        assert len(entities[Platform.SWITCH]) == 0
        assert len(valid_unique_ids) == 0


# -----------------------------------------------------------------------------
# 4. Multi-Function Channels & Temperature Features
# -----------------------------------------------------------------------------


def test_multi_function_channel_button_event(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """BRAND_SWITCH_NOTIFICATION_LIGHT NOTIFICATION_LIGHT_CHANNEL must create HcuButtonEvent."""
    device_data = {
        "id": "dev-bsl-1",
        "type": "BRAND_SWITCH_NOTIFICATION_LIGHT",
        "label": "HmIP-BSL",
        "functionalChannels": {
            "2": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    events = entities[Platform.EVENT]
    assert len(events) == 1
    assert isinstance(events[0], HcuButtonEvent)
    assert "dev-bsl-1_2_button_event" in valid_unique_ids


def test_multi_function_channel_exception(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when multi-function channel entity constructor raises an exception."""
    device_data = {
        "id": "dev-bsl-err",
        "type": "BRAND_SWITCH_NOTIFICATION_LIGHT",
        "label": "HmIP-BSL Broken",
        "functionalChannels": {
            "2": {
                "functionalChannelType": "NOTIFICATION_LIGHT_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    with (
        patch(
            "custom_components.hcu_integration.event.HcuButtonEvent.__init__",
            side_effect=AttributeError("Button event error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create button event entity for device dev-bsl-err, channel 2 (type: NOTIFICATION_LIGHT_CHANNEL): Button event error"
            in caplog.text
        )
        assert len(entities[Platform.EVENT]) == 0
        assert "dev-bsl-err_2_button_event" not in valid_unique_ids


@pytest.mark.parametrize(
    "temp_key",
    ["actualTemperature", "valveActualTemperature"],
)
def test_temperature_features_discovery(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    temp_key: str,
) -> None:
    """Test discovery of actualTemperature and valveActualTemperature sensors."""
    device_data = {
        "id": "dev-temp-1",
        "label": "Temperature Sensor",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "CLIMATE_SENSOR_CHANNEL",
                temp_key: 21.5,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    temp_sensors = [
        e for e in entities[Platform.SENSOR] if isinstance(e, HcuTemperatureSensor)
    ]
    assert len(temp_sensors) == 1
    assert temp_sensors[0].unique_id == f"dev-temp-1_1_{temp_key}"
    assert f"dev-temp-1_1_{temp_key}" in valid_unique_ids


def test_temperature_sensor_creation_exception(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when HcuTemperatureSensor raises an exception."""
    device_data = {
        "id": "dev-temp-err",
        "label": "Broken Temp Sensor",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "CLIMATE_SENSOR_CHANNEL",
                "actualTemperature": 20.0,
            }
        },
    }
    with (
        patch(
            "custom_components.hcu_integration.sensor.HcuTemperatureSensor.__init__",
            side_effect=TypeError("Temp sensor error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create temperature sensor for dev-temp-err: Temp sensor error"
            in caplog.text
        )
        assert len(entities[Platform.SENSOR]) == 0
        assert len(valid_unique_ids) == 0


# -----------------------------------------------------------------------------
# 5. Channel Features from HMIP_FEATURE_TO_ENTITY
# -----------------------------------------------------------------------------


def test_feature_requires_app_user(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Features with requires_app_user (e.g. powerUpSwitchState) are skipped without APP/DUAL auth."""
    device_data = {
        "id": "dev-psm-1",
        "label": "Smart Plug",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                "groups": ["g1"],
                "powerUpSwitchState": "PERMANENT_ON",
            }
        },
    }

    # When client._auth_type is PLUGIN: powerUpSwitchState must be skipped
    mock_hcu_client._auth_type = AUTH_TYPE_PLUGIN
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert not any(
        isinstance(e, HcuPowerUpSwitchState) for e in entities[Platform.SELECT]
    )

    # When client._auth_type is APP: powerUpSwitchState must be created
    mock_hcu_client._auth_type = AUTH_TYPE_APP
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    selects = [
        e for e in entities[Platform.SELECT] if isinstance(e, HcuPowerUpSwitchState)
    ]
    assert len(selects) == 1
    assert "dev-psm-1_1_powerUpSwitchState" in valid_unique_ids


def test_feature_class_hcu_home_sensor_skipped_on_device(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Features mapped to HcuHomeSensor (carrierSense, dutyCycle) are skipped on devices."""
    device_data = {
        "id": "dev-ap-1",
        "label": "Access Point",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "carrierSense": 5,
            }
        },
    }
    entities, _ = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert not any(isinstance(e, HcuHomeSensor) for e in entities[Platform.SENSOR])


def test_feature_duty_cycle_level_skipped_for_hcu_device(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """dutyCycleLevel feature is skipped when device id matches client.hcu_device_id."""
    mock_hcu_client.hcu_device_id = "hcu-self-id"

    # Device matches HCU itself -> dutyCycleLevel skipped
    hcu_device = {
        "id": "hcu-self-id",
        "label": "Homematic IP HCU",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "dutyCycleLevel": 12,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        hcu_device, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert not any(
        getattr(e, "unique_id", "") == "hcu-self-id_0_dutyCycleLevel"
        for e in entities[Platform.SENSOR]
    )

    # Device does not match HCU -> dutyCycleLevel created
    other_device = {
        "id": "other-rf-id",
        "label": "RF Gateway",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "dutyCycleLevel": 12,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        other_device, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert any(
        getattr(e, "unique_id", "") == "other-rf-id_0_dutyCycleLevel"
        for e in entities[Platform.SENSOR]
    )
    assert "other-rf-id_0_dutyCycleLevel" in valid_unique_ids


@pytest.mark.parametrize(
    "supported_flag,should_create",
    [
        (True, True),
        (False, False),
    ],
)
def test_feature_optional_flag(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    supported_flag: bool,
    should_create: bool,
) -> None:
    """Features with optional_flag (e.g. energyCounterOne) require supportedOptionalFeatures."""
    device_data = {
        "id": "dev-meter-1",
        "label": "Energy Interface",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "ENERGY_SENSING_INTERFACE",
                "energyCounterOne": 1234.5,
                "supportedOptionalFeatures": {
                    "IOptionalFeatureEnergyCounterOne": supported_flag
                },
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    sensors = [
        e
        for e in entities[Platform.SENSOR]
        if getattr(e, "unique_id", "") == "dev-meter-1_1_energyCounterOne"
    ]
    if should_create:
        assert len(sensors) == 1
        assert "dev-meter-1_1_energyCounterOne" in valid_unique_ids
    else:
        assert len(sensors) == 0


@pytest.mark.parametrize(
    "power_value,should_create",
    [
        (150.0, True),
        (None, False),
    ],
)
def test_feature_skip_if_null(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    power_value: float | None,
    should_create: bool,
) -> None:
    """Features with skip_if_null (e.g. currentPowerConsumption) must be skipped when None."""
    device_data = {
        "id": "dev-psm-null",
        "label": "Plug with Null Power",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                "groups": ["g1"],
                "currentPowerConsumption": power_value,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    power_sensors = [
        e
        for e in entities[Platform.SENSOR]
        if getattr(e, "unique_id", "") == "dev-psm-null_1_currentPowerConsumption"
    ]
    if should_create:
        assert len(power_sensors) == 1
        assert "dev-psm-null_1_currentPowerConsumption" in valid_unique_ids
    else:
        assert len(power_sensors) == 0


def test_feature_energy_counter_and_water_volume_reset_buttons(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """energyCounter and waterVolume features must automatically spawn reset button entities."""
    device_data = {
        "id": "dev-resets-1",
        "label": "Multi Meter",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                "groups": ["g1"],
                "energyCounter": 500.0,
                "waterVolume": 1000.0,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )

    buttons = entities[Platform.BUTTON]
    energy_reset = [e for e in buttons if isinstance(e, HcuResetEnergyButton)]
    water_reset = [e for e in buttons if isinstance(e, HcuResetWaterVolume)]

    assert len(energy_reset) == 1
    assert energy_reset[0].unique_id == "dev-resets-1_1_reset_energy_counter"
    assert "dev-resets-1_1_reset_energy_counter" in valid_unique_ids

    assert len(water_reset) == 1
    assert water_reset[0].unique_id == "dev-resets-1_1_reset_water_volume"
    assert "dev-resets-1_1_reset_water_volume" in valid_unique_ids

    # Isolated energy-only channel: creates only energy reset, not water reset
    energy_only_dev = {
        "id": "dev-energy-only",
        "label": "Energy Meter",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                "groups": ["g1"],
                "energyCounter": 123.0,
            }
        },
    }
    e_entities, _ = _discover_entities_for_device(
        energy_only_dev, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    e_buttons = e_entities[Platform.BUTTON]
    assert len([e for e in e_buttons if isinstance(e, HcuResetEnergyButton)]) == 1
    assert len([e for e in e_buttons if isinstance(e, HcuResetWaterVolume)]) == 0
    assert len(e_buttons) == 1

    # Isolated water-only channel: creates only water reset, not energy reset
    water_only_dev = {
        "id": "dev-water-only",
        "label": "Water Meter",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_MEASURING_CHANNEL",
                "groups": ["g1"],
                "waterVolume": 456.0,
            }
        },
    }
    w_entities, _ = _discover_entities_for_device(
        water_only_dev, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    w_buttons = w_entities[Platform.BUTTON]
    assert len([e for e in w_buttons if isinstance(e, HcuResetWaterVolume)]) == 1
    assert len([e for e in w_buttons if isinstance(e, HcuResetEnergyButton)]) == 0
    assert len(w_buttons) == 1

    # Channel without energy or water resets creates no reset buttons
    neither_dev = {
        "id": "dev-neither",
        "label": "Thermometer",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DEVICE_BASE",
                "groups": ["g1"],
                "actualTemperature": 21.0,
            }
        },
    }
    n_entities, _ = _discover_entities_for_device(
        neither_dev, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert len(n_entities[Platform.BUTTON]) == 0


def test_feature_config_companion_creation_and_error(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test config_companion entity creation (e.g. HcuConfigUseInternalOnTime) and error handling."""
    device_data = {
        "id": "dev-ontime-1",
        "label": "Switch with OnTime",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "groups": ["g1"],
                "onTime": 60,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    companions = [
        e
        for e in entities[Platform.SWITCH]
        if isinstance(e, HcuConfigUseInternalOnTime)
    ]
    assert len(companions) == 1
    assert companions[0].unique_id == "dev-ontime-1_1_use_internal_on_time"
    assert "dev-ontime-1_1_use_internal_on_time" in valid_unique_ids

    # Test error handling when companion constructor raises an error
    with (
        patch(
            "custom_components.hcu_integration.switch.HcuConfigUseInternalOnTime.__init__",
            side_effect=TypeError("Companion init error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, _ = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create config companion 'HcuConfigUseInternalOnTime' for device dev-ontime-1, channel 1: Companion init error"
            in caplog.text
        )


def test_feature_entity_creation_exception(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling when feature entity constructor raises an exception."""
    device_data = {
        "id": "dev-hum-err",
        "label": "Broken Humidity Sensor",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "CLIMATE_SENSOR_CHANNEL",
                "humidity": 45,
            }
        },
    }
    with (
        patch(
            "custom_components.hcu_integration.sensor.HcuGenericSensor.__init__",
            side_effect=TypeError("Generic sensor init error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create entity for device dev-hum-err, channel 1, feature humidity (HcuGenericSensor): Generic sensor init error"
            in caplog.text
        )
        assert len(entities[Platform.SENSOR]) == 0
        assert len(valid_unique_ids) == 0


# -----------------------------------------------------------------------------
# 6. Optional Features (HMIP_OPTIONAL_FEATURE_TO_ENTITY) & DutyCycle Channel
# -----------------------------------------------------------------------------


def test_optional_feature_identify_button_and_branches(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optional features from HMIP_OPTIONAL_FEATURE_TO_ENTITY: identify button and custom branches."""
    # Test 1: IFeatureDeviceIdentify supported -> creates HcuDeviceIdentifyButton
    device_data = {
        "id": "dev-id-1",
        "label": "Identify Device",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "supportedOptionalFeatures": {
                    "IFeatureDeviceIdentify": True,
                },
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    buttons = [
        e for e in entities[Platform.BUTTON] if isinstance(e, HcuDeviceIdentifyButton)
    ]
    assert len(buttons) == 1
    assert buttons[0].unique_id == "dev-id-1_0_identify"
    assert "dev-id-1_0_identify" in valid_unique_ids

    # Test 2: IFeatureDeviceIdentify unsupported -> not created
    device_data_unsupported = {
        "id": "dev-id-2",
        "label": "No Identify Device",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "supportedOptionalFeatures": {
                    "IFeatureDeviceIdentify": False,
                },
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data_unsupported,
        mock_config_entry,
        mock_coordinator,
        mock_hcu_client,
    )
    assert not any(
        isinstance(e, HcuDeviceIdentifyButton) for e in entities[Platform.BUTTON]
    )

    # Test 3: branches with custom optional feature mappings
    custom_optional_mappings = {
        "OptFeatureA": {
            "class": "HcuGenericSensor",
            "requires_data_key": True,
            "data_key": "humidity",  # already in HMIP_FEATURE_TO_ENTITY
        },
        "OptFeatureB": {
            "class": "HcuGenericSensor",
            "requires_data_key": True,
            "data_key": "customMissingKey",
        },
        "OptFeatureC": {
            "class": "UnknownClass",
            "requires_data_key": False,
        },
        "OptFeatureD": {
            "class": "HcuGenericSensor",
            "name": "Custom Optional Sensor",
            "requires_data_key": False,
            "simple_init": False,
        },
    }
    custom_device = {
        "id": "dev-opt-custom",
        "label": "Custom Opt Device",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DEVICE_BASE",
                "supportedOptionalFeatures": {
                    "OptFeatureA": True,
                    "OptFeatureB": True,
                    "OptFeatureC": True,
                    "OptFeatureD": True,
                },
            }
        },
    }

    with (
        patch(
            "custom_components.hcu_integration.discovery.HMIP_OPTIONAL_FEATURE_TO_ENTITY",
            custom_optional_mappings,
        ),
        caplog.at_level(logging.DEBUG),
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            custom_device, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Optional feature supported but not created (missing data key): device=dev-opt-custom channel=1 feature=OptFeatureB data_key=customMissingKey"
            in caplog.text
        )
        assert (
            "Optional feature supported but not created (no module mapping): device=dev-opt-custom channel=1 feature=OptFeatureC class=UnknownClass"
            in caplog.text
        )
        sensors = [
            e for e in entities[Platform.SENSOR] if isinstance(e, HcuGenericSensor)
        ]
        assert len(sensors) == 1
        assert sensors[0].unique_id == "dev-opt-custom_1_OptFeatureD"
        assert sensors[0].name == "Custom Optional Sensor"
        assert "dev-opt-custom_1_OptFeatureD" in valid_unique_ids

    # Test 4: constructor error handling tested separately
    error_mapping = {
        "OptFeatureE": {
            "class": "HcuGenericSensor",
            "name": "Error Sensor",
            "requires_data_key": False,
            "simple_init": False,
        },
    }
    error_device = {
        "id": "dev-opt-err",
        "label": "Error Opt Device",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "DEVICE_BASE",
                "supportedOptionalFeatures": {
                    "OptFeatureE": True,
                },
            }
        },
    }
    with (
        patch(
            "custom_components.hcu_integration.discovery.HMIP_OPTIONAL_FEATURE_TO_ENTITY",
            error_mapping,
        ),
        patch(
            "custom_components.hcu_integration.sensor.HcuGenericSensor.__init__",
            side_effect=TypeError("Simulated opt init failure"),
        ),
        caplog.at_level(logging.DEBUG),
    ):
        err_entities, err_valid_unique_ids = _discover_entities_for_device(
            error_device, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Optional feature entity not created: device=dev-opt-err channel=1 feature=OptFeatureE class=HcuGenericSensor"
            in caplog.text
        )
        assert not any(
            isinstance(e, HcuGenericSensor) for e in err_entities[Platform.SENSOR]
        )
        assert "dev-opt-err_1_OptFeatureE" not in err_valid_unique_ids


def test_channel_duty_cycle_binary_sensor_and_error(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test channel-level dutyCycle boolean flag creating HcuBinarySensor and error handling."""
    device_data = {
        "id": "dev-dc-1",
        "label": "RF Actuator",
        "functionalChannels": {
            "0": {
                "functionalChannelType": "DEVICE_BASE",
                "dutyCycle": True,
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    binary_sensors = [
        e
        for e in entities[Platform.BINARY_SENSOR]
        if getattr(e, "unique_id", "") == "dev-dc-1_0_dutyCycle"
    ]
    assert len(binary_sensors) == 1
    assert "dev-dc-1_0_dutyCycle" in valid_unique_ids

    # Error handling
    with (
        patch(
            "custom_components.hcu_integration.binary_sensor.HcuBinarySensor.__init__",
            side_effect=TypeError("DutyCycle binary sensor error"),
        ),
        caplog.at_level(logging.ERROR),
    ):
        entities, _ = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
        assert (
            "Failed to create dutyCycle binary sensor for device dev-dc-1: DutyCycle binary sensor error"
            in caplog.text
        )


# -----------------------------------------------------------------------------
# 7. _is_channel_light Exhaustive Branch Coverage
# -----------------------------------------------------------------------------


def test_is_channel_light_exhaustive() -> None:
    """Test all branches of _is_channel_light."""
    # 1. Maintenance channel 0 -> returns None
    assert _is_channel_light({"functionalChannelType": "DEVICE_BASE"}, "0") is None
    assert _is_channel_light({"functionalChannelType": "DEVICE_BASE"}, 0) is None

    # 2. Light actuator types (exact match and prefix match) -> returns True
    assert _is_channel_light({"functionalChannelType": "DIMMER_CHANNEL"}, 1) is True
    assert (
        _is_channel_light({"functionalChannelType": "DIMMER_CHANNEL_EXTENDED"}, 1)
        is True
    )

    # 3. Switch actuator with switchVisualization in channel_data
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "SWITCH_CHANNEL",
                "switchVisualization": "LIGHT",
            },
            1,
        )
        is True
    )
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "SWITCH_CHANNEL",
                "switchVisualization": "OUTLET",
            },
            1,
        )
        is False
    )

    # 4. Switch actuator with switchVisualization prefix match
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "SWITCH_CHANNEL_CUSTOM",
                "switchVisualization": "LIGHT",
            },
            1,
        )
        is True
    )

    # 5. Switch actuator with switchVisualization fallback to internalConfiguration / internalLinkConfiguration
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "SWITCH_CHANNEL",
                "internalConfiguration": {"switchVisualization": "LIGHT"},
            },
            1,
        )
        is True
    )
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "SWITCH_CHANNEL",
                "internalLinkConfiguration": {"switchVisualization": "LIGHT"},
            },
            1,
        )
        is True
    )
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "SWITCH_CHANNEL",
            },
            1,
        )
        is False
    )

    # 6. Non-actuator channel roles -> returns None
    assert (
        _is_channel_light(
            {
                "functionalChannelType": "OTHER_TYPE",
                "channelRole": "WINDOW_SENSOR",
            },
            1,
        )
        is None
    )

    # 7. Non-actuator channel types (exact and prefix match) -> returns None
    assert _is_channel_light({"functionalChannelType": "SINGLE_KEY_CHANNEL"}, 1) is None
    assert (
        _is_channel_light({"functionalChannelType": "SINGLE_KEY_CHANNEL_EXTENDED"}, 1)
        is None
    )

    # 8. Channel types mapped to None in HMIP_CHANNEL_TYPE_TO_ENTITY -> returns None
    assert (
        _is_channel_light({"functionalChannelType": "ACCELERATION_SENSOR_CHANNEL"}, 1)
        is None
    )

    # 9. Non-light actuators (cover, unknown) -> returns False
    assert _is_channel_light({"functionalChannelType": "SHUTTER_CHANNEL"}, 1) is False
    assert _is_channel_light({"functionalChannelType": "UNKNOWN_ACTUATOR"}, 1) is False


# -----------------------------------------------------------------------------
# 8. _is_switching_group_lights_only Exhaustive Branch Coverage
# -----------------------------------------------------------------------------


def test_is_switching_group_lights_only_exhaustive() -> None:
    """Test all defensive branches of _is_switching_group_lights_only."""
    devices = {
        "dev-light": {
            "id": "dev-light",
            "functionalChannels": {
                "1": {
                    "functionalChannelType": "SWITCH_CHANNEL",
                    "switchVisualization": "LIGHT",
                }
            },
        },
        "dev-int-key": {
            "id": "dev-int-key",
            "functionalChannels": {
                1: {  # Integer key instead of string
                    "functionalChannelType": "DIMMER_CHANNEL",
                }
            },
        },
        "dev-no-fc": {
            "id": "dev-no-fc",
            "functionalChannels": None,
        },
    }

    # 1. Malformed channels field
    assert _is_switching_group_lights_only({}, devices) is False
    assert _is_switching_group_lights_only({"channels": None}, devices) is False
    assert _is_switching_group_lights_only({"channels": "not-a-list"}, devices) is False
    assert _is_switching_group_lights_only({"channels": []}, devices) is False

    # 2. Member channel ref not a dict
    assert _is_switching_group_lights_only({"channels": ["bad-ref"]}, devices) is False

    # 3. Missing deviceId or channelIndex
    assert (
        _is_switching_group_lights_only({"channels": [{"channelIndex": 1}]}, devices)
        is False
    )
    assert (
        _is_switching_group_lights_only(
            {"channels": [{"deviceId": "dev-light"}]}, devices
        )
        is False
    )

    # 4. Unknown device ID
    assert (
        _is_switching_group_lights_only(
            {"channels": [{"deviceId": "unknown-dev", "channelIndex": 1}]},
            devices,
        )
        is False
    )

    # 5. Malformed functionalChannels
    assert (
        _is_switching_group_lights_only(
            {"channels": [{"deviceId": "dev-no-fc", "channelIndex": 1}]},
            devices,
        )
        is False
    )

    # 6. Unknown channel index
    assert (
        _is_switching_group_lights_only(
            {"channels": [{"deviceId": "dev-light", "channelIndex": 99}]},
            devices,
        )
        is False
    )

    # 7. Integer channel index resolution
    assert (
        _is_switching_group_lights_only(
            {"channels": [{"deviceId": "dev-int-key", "channelIndex": 1}]},
            devices,
        )
        is True
    )


# -----------------------------------------------------------------------------
# 9. Group Discovery: All Supported Group Types & Skipped Groups
# -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "group_type,expected_platform,expected_class",
    [
        ("HEATING", Platform.CLIMATE, HcuClimate),
        ("SHUTTER", Platform.COVER, HcuCoverGroup),
        ("SWITCHING", Platform.SWITCH, HcuSwitchGroup),
        ("SWITCHING_PROFILE", Platform.SWITCH, HcuSwitchGroup),
        ("LINKED_SWITCHING", Platform.SWITCH, HcuSwitchGroup),
        ("LIGHT", Platform.LIGHT, HcuLightGroup),
        ("EXTENDED_LINKED_SHUTTER", Platform.COVER, HcuCoverGroup),
        ("EXTENDED_LINKED_NOTIFICATION", Platform.LIGHT, HcuLightGroup),
        ("EXTENDED_LINKED_WATERING", Platform.SWITCH, HcuWateringGroup),
        ("EXTENDED_LINKED_GARAGE_DOOR", Platform.SWITCH, HcuSwitchGroup),
        (
            "HEATING_COOLING_DEMAND_BOILER",
            Platform.BINARY_SENSOR,
            HcuHeatDemandBinarySensorGroup,
        ),
        (
            "HEATING_COOLING_DEMAND_PUMP",
            Platform.BINARY_SENSOR,
            HcuHeatDemandBinarySensorGroup,
        ),
        ("HOT_WATER", Platform.SWITCH, HcuSwitchGroup),
    ],
)
async def test_group_types_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    group_type: str,
    expected_platform: Platform,
    expected_class: type,
) -> None:
    """Test discovery for all single-entity group types."""
    gid = f"grp-{group_type.lower()}"
    mock_hcu_client.state = {
        "devices": {},
        "groups": {
            gid: {
                "id": gid,
                "type": group_type,
                "label": f"Test {group_type}",
                "channels": ["ch1"],
            }
        },
    }
    entities = await async_discover_entities(
        hass, mock_hcu_client, mock_config_entry, mock_coordinator
    )
    group_entities = [
        e for e in entities[expected_platform] if isinstance(e, expected_class)
    ]
    assert len(group_entities) == 1
    assert group_entities[0].unique_id == gid


async def test_alarm_switching_group_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """ALARM_SWITCHING groups create both acoustic and optical signal select entities."""
    mock_hcu_client.state = {
        "devices": {},
        "groups": {
            "grp-alarm-1": {
                "id": "grp-alarm-1",
                "type": "ALARM_SWITCHING",
                "label": "Alarm Siren Group",
                "channels": ["ch1"],
            }
        },
    }
    with caplog.at_level(logging.INFO):
        entities = await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )
    selects = entities[Platform.SELECT]
    assert any(isinstance(e, HcuAlarmSignalAcoustic) for e in selects)
    assert any(isinstance(e, HcuAlarmSignalOptical) for e in selects)
    assert "Group discovery summary: 1 created, 0 unknown types" in caplog.text


async def test_group_skips_and_diagnostics(
    hass: HomeAssistant,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test skipped groups: missing id, disabled group types, malformed channels, empty channels, safety alarm, and unknown types."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_DISABLED_GROUPS: ["SWITCHING_PROFILE"]},
    )

    mock_hcu_client.state = {
        "devices": {},
        "groups": {
            # 1. Missing group id
            "no-id": {
                "type": "SWITCHING",
                "label": "No ID Group",
                "channels": ["ch1"],
            },
            # 2. Disabled group type
            "grp-disabled": {
                "id": "grp-disabled",
                "type": "SWITCHING_PROFILE",
                "label": "Disabled Profile",
                "channels": ["ch1"],
            },
            # 3. Malformed channels
            "grp-malformed": {
                "id": "grp-malformed",
                "type": "SWITCHING",
                "label": "Malformed Channels",
                "channels": "invalid-string",
            },
            # 4. Empty channels not in ALLOWED_EMPTY_GROUPS
            "grp-empty": {
                "id": "grp-empty",
                "type": "SWITCHING",
                "label": "Empty Switch Group",
                "channels": [],
            },
            # 5. Empty channels in ALLOWED_EMPTY_GROUPS (e.g. SECURITY_ZONE)
            "grp-allowed-empty": {
                "id": "grp-allowed-empty",
                "type": "SECURITY_ZONE",
                "label": "Security Zone",
                "channels": [],
            },
            # 6. ALARM_SWITCHING safety group
            "grp-alarm-safety": {
                "id": "grp-alarm-safety",
                "type": "ALARM_SWITCHING",
                "label": "Siren_SAFETY",
                "channels": ["ch1"],
            },
            # 7. Unknown group type
            "grp-unknown": {
                "id": "grp-unknown",
                "type": "MY_CUSTOM_GROUP",
                "label": "Custom Mystery Group",
                "channels": ["ch1"],
            },
        },
    }

    with caplog.at_level(logging.DEBUG):
        entities = await async_discover_entities(
            hass, mock_hcu_client, entry, mock_coordinator
        )

    # Assert debug logs for each skipped group
    assert (
        "Skipping group without valid ID (type: SWITCHING, label: No ID Group)"
        in caplog.text
    )
    assert (
        "Skipping group 'Disabled Profile' (id: grp-disabled) because group type 'SWITCHING_PROFILE' is disabled"
        in caplog.text
    )
    assert (
        "Group 'Malformed Channels' (id: grp-malformed) has malformed 'channels' data (expected list, got str) - skipping"
        in caplog.text
    )
    assert (
        "Skipping group without channels: Empty Switch Group (id: grp-empty)"
        in caplog.text
    )
    assert (
        "Skipping ALARM_SWITCHING safety group 'Siren_SAFETY' (id: grp-alarm-safety)"
        in caplog.text
    )
    assert (
        "Unknown group type 'MY_CUSTOM_GROUP' for group 'Custom Mystery Group' (id: grp-unknown) - no entity created"
        in caplog.text
    )
    assert "Group discovery summary: 0 created, 1 unknown types" in caplog.text

    # No entities created for any of these
    for platform_entities in entities.values():
        assert len(platform_entities) == 0


# -----------------------------------------------------------------------------
# 10. Home-Level Sensors & Entities
# -----------------------------------------------------------------------------


async def test_home_level_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """carrierSense and dutyCycle on home object create HcuHomeSensor entities."""
    mock_hcu_client.state = {
        "home": {
            "id": "home-root",
            "carrierSense": 3,
            "dutyCycle": 15,
        },
        "devices": {},
        "groups": {},
    }
    with caplog.at_level(logging.INFO):
        entities = await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )
    assert "Group discovery summary" not in caplog.text

    sensors = entities[Platform.SENSOR]
    home_sensors = [e for e in sensors if isinstance(e, HcuHomeSensor)]
    assert len(home_sensors) == 2
    uids = {s.unique_id for s in home_sensors}
    assert f"{mock_hcu_client.hcu_device_id}_carrierSense" in uids
    assert f"{mock_hcu_client.hcu_device_id}_dutyCycle" in uids

    # Vacation mode binary sensor
    vacation_sensors = [
        e
        for e in entities[Platform.BINARY_SENSOR]
        if isinstance(e, HcuVacationModeBinarySensor)
    ]
    assert len(vacation_sensors) == 1


# -----------------------------------------------------------------------------
# 11. Device Registry Cleanup & Error Handling
# -----------------------------------------------------------------------------


async def test_device_registry_cleanup_orphans_and_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test device registry cleanup: removes orphaned devices, handles exceptions, re-raises CancelledError."""
    mock_config_entry.add_to_hass(hass)
    dev_reg = dr.async_get(hass)

    # Create 3 devices in device registry:
    # 1: Still valid device
    valid_dev = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "active-dev-id")},
        name="Active Device",
    )
    # 2: Orphaned device that will be removed normally
    orphan_dev = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "old-orphan-id")},
        name="Old Orphaned Device",
    )
    # 3: Device from another domain
    other_domain_dev = dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={("other_domain", "other-dev-id")},
        name="Other Domain Device",
    )

    mock_hcu_client.state = {
        "devices": {
            "active-dev-id": {
                "id": "active-dev-id",
                "label": "Active Device",
                "functionalChannels": {},
            }
        },
        "groups": {},
    }

    with caplog.at_level(logging.INFO):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )

    # Valid device kept, other domain device kept, orphan removed
    assert dev_reg.async_get(valid_dev.id) is not None
    assert dev_reg.async_get(other_domain_dev.id) is not None
    assert dev_reg.async_get(orphan_dev.id) is None
    assert "Removing orphaned device from registry: Old Orphaned Device" in caplog.text

    # Test error handling when async_remove_device raises Exception
    caplog.clear()
    dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "fail-dev-id")},
        name="Failing Device",
    )
    with (
        patch.object(
            dev_reg,
            "async_remove_device",
            side_effect=RuntimeError("Cannot delete device"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )
        assert "Failed to remove orphaned device 'Failing Device'" in caplog.text

    # Test CancelledError re-raised
    dev_reg.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={(DOMAIN, "cancel-dev-id")},
        name="Cancel Device",
    )
    with (
        patch.object(
            dev_reg,
            "async_remove_device",
            side_effect=asyncio.CancelledError(),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )


# -----------------------------------------------------------------------------
# 12. Entity Registry Cleanup
# -----------------------------------------------------------------------------


async def test_entity_registry_cleanup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test entity registry cleanup: orphaned entities are removed, other entities keep their enabled state."""
    mock_config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)

    # 1. Other domain platform entity -> ignored
    other_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform="other_platform",
        unique_id="other_unique_id",
        config_entry=mock_config_entry,
    )

    # 2. Orphaned entity in DOMAIN -> removed
    orphan_ent = ent_reg.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id="dev-old_1",
        config_entry=mock_config_entry,
    )

    # 3. Disabled-by-default feature (dirtLevel) that is enabled -> stays enabled
    dirt_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="dev-active_1_dirtLevel",
        config_entry=mock_config_entry,
    )
    assert dirt_ent.disabled_by is None

    # 4. Disabled-by-default feature disabled by the user -> kept as-is
    user_disabled_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="dev-active_1_operationDays",
        config_entry=mock_config_entry,
        disabled_by=er.RegistryEntryDisabler.USER,
    )

    # 5. Entity of a feature that is enabled by default
    normal_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id="dev-active_1_actualTemperature",
        config_entry=mock_config_entry,
    )

    # 6. Pre-existing home-level entities (alarm control panel, security entities, home sensors)
    hcu_id = mock_hcu_client.hcu_device_id
    alarm_ent = ent_reg.async_get_or_create(
        domain="alarm_control_panel",
        platform=DOMAIN,
        unique_id=f"{hcu_id}_security",
        config_entry=mock_config_entry,
    )
    sec_ent = ent_reg.async_get_or_create(
        domain="binary_sensor",
        platform=DOMAIN,
        unique_id=f"{hcu_id}_intrusion_alarm",
        config_entry=mock_config_entry,
    )
    safety_ent = ent_reg.async_get_or_create(
        domain="button",
        platform=DOMAIN,
        unique_id=f"{hcu_id}_acknowledge_safety_alarm",
        config_entry=mock_config_entry,
    )
    carrier_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{hcu_id}_carrierSense",
        config_entry=mock_config_entry,
    )
    duty_ent = ent_reg.async_get_or_create(
        domain="sensor",
        platform=DOMAIN,
        unique_id=f"{hcu_id}_dutyCycle",
        config_entry=mock_config_entry,
    )

    mock_hcu_client.state = {
        "home": {
            "id": "home-root",
            "carrierSense": 3,
            "dutyCycle": 15,
            "functionalHomes": {
                "sec": {
                    "solution": "SECURITY_AND_ALARM",
                }
            },
        },
        "devices": {
            "dev-active": {
                "id": "dev-active",
                "label": "Active Device",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "DEVICE_BASE",
                        "actualTemperature": 20.0,
                        "dirtLevel": 5,
                        "operationDays": 100,
                    }
                },
            }
        },
        "groups": {},
    }

    with caplog.at_level(logging.INFO):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )

    # Other platform entity was untouched
    assert ent_reg.async_get(other_ent.entity_id) is not None
    # Orphan entity removed
    assert ent_reg.async_get(orphan_ent.entity_id) is None
    # dirtLevel is disabled by default, but the integration never disables an
    # entity that is enabled in the registry
    updated_dirt = ent_reg.async_get(dirt_ent.entity_id)
    assert updated_dirt.disabled_by is None
    # operationDays kept USER disabled
    updated_user = ent_reg.async_get(user_disabled_ent.entity_id)
    assert updated_user.disabled_by == er.RegistryEntryDisabler.USER
    # normal entity not disabled
    updated_normal = ent_reg.async_get(normal_ent.entity_id)
    assert updated_normal.disabled_by is None
    # Home-level security and sensor entities preserved in registry
    assert ent_reg.async_get(alarm_ent.entity_id) is not None
    assert ent_reg.async_get(sec_ent.entity_id) is not None
    assert ent_reg.async_get(safety_ent.entity_id) is not None
    assert ent_reg.async_get(carrier_ent.entity_id) is not None
    assert ent_reg.async_get(duty_ent.entity_id) is not None


async def test_entity_registry_cleanup_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling and CancelledError in entity registry operations."""
    mock_config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)

    orphan = ent_reg.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id="orphan-uid",
        config_entry=mock_config_entry,
    )

    mock_hcu_client.state = {"devices": {}, "groups": {}}

    # 1. async_remove raises RuntimeError
    with (
        patch.object(
            ent_reg,
            "async_remove",
            side_effect=RuntimeError("Cannot delete entity"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )
        assert (
            f"Failed to remove orphaned entity '{orphan.name}' (entity_id: {orphan.entity_id}, unique_id: orphan-uid)"
            in caplog.text
        )

    # 2. async_remove raises CancelledError
    with (
        patch.object(
            ent_reg,
            "async_remove",
            side_effect=asyncio.CancelledError(),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )


async def test_entity_registry_platform_migration_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test exception handling during platform migration entity removal."""
    mock_config_entry.add_to_hass(hass)
    ent_reg = er.async_get(hass)

    # Entity is currently in 'switch' domain in registry
    ent_reg.async_get_or_create(
        domain="switch",
        platform=DOMAIN,
        unique_id="migrating-grp-1",
        config_entry=mock_config_entry,
    )

    # In state, this group now resolves to light (SWITCHING group where all members are lights)
    mock_hcu_client.state = {
        "devices": {
            "dev-light": {
                "id": "dev-light",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "switchVisualization": "LIGHT",
                        "groups": ["migrating-grp-1"],
                    }
                },
            }
        },
        "groups": {
            "migrating-grp-1": {
                "id": "migrating-grp-1",
                "type": "SWITCHING",
                "label": "Migrating Light Group",
                "channels": [{"deviceId": "dev-light", "channelIndex": 1}],
            }
        },
    }

    # Test Exception logging
    with (
        patch.object(
            ent_reg,
            "async_remove",
            side_effect=RuntimeError("Migration remove failure"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )
        assert "Failed to remove platform-migrated entity" in caplog.text

    # Test CancelledError re-raising
    with (
        patch.object(
            ent_reg,
            "async_remove",
            side_effect=asyncio.CancelledError(),
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_discover_entities(
            hass, mock_hcu_client, mock_config_entry, mock_coordinator
        )


# -----------------------------------------------------------------------------
# 13. Single-Device Inclusion Discovery & Translation Prefix Resolver
# -----------------------------------------------------------------------------


def test_async_discover_entities_for_device(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_discover_entities_for_device for present and missing devices."""
    mock_hcu_client.state = {
        "devices": {
            "included-dev-1": {
                "id": "included-dev-1",
                "label": "New Included Switch",
                "functionalChannels": {
                    "1": {
                        "functionalChannelType": "SWITCH_CHANNEL",
                        "groups": ["g1"],
                    }
                },
            }
        }
    }

    # 1. Device present in state
    entities = async_discover_entities_for_device(
        mock_hcu_client, mock_config_entry, mock_coordinator, "included-dev-1"
    )
    assert len(entities[Platform.SWITCH]) == 1
    assert entities[Platform.SWITCH][0].unique_id == "included-dev-1_1_on"

    # 2. Device not present in state
    with caplog.at_level(logging.WARNING):
        missing_entities = async_discover_entities_for_device(
            mock_hcu_client,
            mock_config_entry,
            mock_coordinator,
            "missing-dev-id",
        )
        assert (
            "async_discover_entities_for_device: device missing-dev-id not found in state"
            in caplog.text
        )
        for elist in missing_entities.values():
            assert len(elist) == 0


def test_resolve_translation_prefixes() -> None:
    """Test _resolve_translation_prefixes calls entity._resolve_translation_prefix with True if siblings exist."""
    # Sibling pair sharing same base key on same device
    sib1 = MagicMock()
    sib1._base_translation_key = "switch"
    sib1._device_id = "dev-multi-channel"
    sib1._resolve_translation_prefix = MagicMock()

    sib2 = MagicMock()
    sib2._base_translation_key = "switch"
    sib2._device_id = "dev-multi-channel"
    sib2._resolve_translation_prefix = MagicMock()

    # Lone entity with distinct key
    solo = MagicMock()
    solo._base_translation_key = "temperature"
    solo._device_id = "dev-multi-channel"
    solo._resolve_translation_prefix = MagicMock()

    entities_dict = {
        Platform.SWITCH: [sib1, sib2],
        Platform.SENSOR: [solo],
    }

    _resolve_translation_prefixes(entities_dict)

    # Siblings called with True
    sib1._resolve_translation_prefix.assert_called_once_with(True)
    sib2._resolve_translation_prefix.assert_called_once_with(True)

    # Solo called with False
    solo._resolve_translation_prefix.assert_called_once_with(False)


def test_extra_entities_empty_class_skipped(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Extra entities config with empty class name must be safely skipped."""
    custom_mapping = {
        "CUSTOM_CHANNEL": {
            "class": "HcuSwitch",
            "extra_entities": [{"class": ""}],
        }
    }
    device_data = {
        "id": "dev-empty-extra",
        "label": "Empty Extra Device",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "CUSTOM_CHANNEL",
                "groups": ["g1"],
            }
        },
    }
    with patch(
        "custom_components.hcu_integration.discovery.HMIP_CHANNEL_TYPE_TO_ENTITY",
        custom_mapping,
    ):
        entities, valid_unique_ids = _discover_entities_for_device(
            device_data, mock_config_entry, mock_coordinator, mock_hcu_client
        )
    assert len(entities[Platform.SWITCH]) == 1
    assert "dev-empty-extra_1_on" in valid_unique_ids


def test_deactivated_by_default_device_used_channel_features_enabled(
    mock_config_entry: MockConfigEntry,
    mock_hcu_client: MagicMock,
    mock_coordinator: MagicMock,
) -> None:
    """Features on used channels of deactivated-by-default devices get enabled by default."""
    device_data = {
        "id": "dev-fal-used",
        "type": "FLOOR_TERMINAL_BLOCK_12",
        "label": "Floor Heating Controller Used",
        "functionalChannels": {
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "groups": ["group-room-1"],
                "humidity": 45,
                "dutyCycle": True,
                "supportedOptionalFeatures": {
                    "IFeatureDeviceIdentify": True,
                },
            }
        },
    }
    entities, valid_unique_ids = _discover_entities_for_device(
        device_data, mock_config_entry, mock_coordinator, mock_hcu_client
    )
    assert len(valid_unique_ids) > 0
    sensors = [e for e in entities[Platform.SENSOR] if isinstance(e, HcuGenericSensor)]
    assert len(sensors) == 1
    assert sensors[0].entity_registry_enabled_default is True

    binary_sensors = [
        e for e in entities[Platform.BINARY_SENSOR] if isinstance(e, HcuBinarySensor)
    ]
    assert len(binary_sensors) == 1
    assert binary_sensors[0].entity_registry_enabled_default is True

    buttons = [
        e for e in entities[Platform.BUTTON] if isinstance(e, HcuDeviceIdentifyButton)
    ]
    assert len(buttons) == 1
    assert buttons[0].entity_registry_enabled_default is True


def test_is_channel_light_unlisted_non_actuator() -> None:
    """Test _is_channel_light returns None for channel type mapped to None not in NON_ACTUATOR_CHANNEL_TYPES."""
    from custom_components.hcu_integration.const import HMIP_CHANNEL_TYPE_TO_ENTITY

    with patch.dict(
        HMIP_CHANNEL_TYPE_TO_ENTITY, {"UNLISTED_NON_ACTUATOR_CHANNEL": None}
    ):
        assert (
            _is_channel_light(
                {"functionalChannelType": "UNLISTED_NON_ACTUATOR_CHANNEL"}, 1
            )
            is None
        )
