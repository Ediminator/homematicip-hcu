"""Comprehensive coverage tests for custom_components/hcu_integration/entity.py."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.entity import DeviceInfo
import pytest

from custom_components.hcu_integration.api import HcuApiError
from custom_components.hcu_integration.const import (
    AUTH_TYPE_APP,
    AUTH_TYPE_DUAL,
    CONF_ADVANCED_ATTRIBUTES,
    CONF_APP_CLIENT_ID,
    CONF_AUTH_TYPE,
    CONF_DEVICE_PINS,
    CONF_PLUGIN_CLIENT_ID,
    DOMAIN,
    HMIP_ON_TIME_INFINITE,
)
from custom_components.hcu_integration.entity import (
    HcuAccessMixin,
    HcuBaseEntity,
    HcuGroupBaseEntity,
    HcuHomeBaseEntity,
    HcuSwitchingGroupBase,
    SwitchStateMixin,
    _resolve_via_device_info,
)


class DummySwitchEntity(SwitchStateMixin):
    """Dummy entity to test SwitchStateMixin."""

    def __init__(self, channel_data: dict, name: str = "Test Switch") -> None:
        self._channel = channel_data
        self.name = name
        self._attr_assumed_state = False
        self._init_switch_state()
        self.written_states = 0
        self.api_calls: list[bool] = []
        self.fail_api: Exception | None = None

    def async_write_ha_state(self) -> None:
        self.written_states += 1

    async def _call_switch_api(self, turn_on: bool) -> None:
        if self.fail_api:
            raise self.fail_api
        self.api_calls.append(turn_on)


class DummyAccessEntity(HcuAccessMixin):
    """Dummy entity to test HcuAccessMixin."""

    def __init__(
        self,
        coordinator: MagicMock,
        client: MagicMock,
        device: dict,
        channel: dict,
        hass: HomeAssistant,
        name: str = "Access Device",
    ) -> None:
        self.coordinator = coordinator
        self._client = client
        self._device = device
        self._channel = channel
        self.hass = hass
        self.name = name
        self._device_id = device.get("id", "dev_1")
        self._channel_index = int(channel.get("index", 1))


def test_resolve_via_device_info_none():
    """Test _resolve_via_device_info with None device id returns empty DeviceInfo."""
    res = _resolve_via_device_info(MagicMock(), None)
    assert res == DeviceInfo()


def test_resolve_via_device_info_device_registry_lookup():
    """Test resolving via device registry with async_get_device_id_by_identifier and async_get_device."""
    coordinator = MagicMock()
    coordinator.hcu_device_entry_id = None
    coordinator.hass = MagicMock()

    # Branch 1: async_get_device_id_by_identifier
    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get:
        mock_dev_reg = MagicMock()
        mock_dev_reg.async_get_device_id_by_identifier.return_value = "dev_reg_123"
        mock_dr_get.return_value = mock_dev_reg

        result = _resolve_via_device_info(coordinator, "parent_hcu_id")
        assert result == {"via_device_id": "dev_reg_123"}
        mock_dev_reg.async_get_device_id_by_identifier.assert_called_once_with(
            (DOMAIN, "parent_hcu_id")
        )

    # Branch 2: async_get_device fallback
    with patch("homeassistant.helpers.device_registry.async_get") as mock_dr_get:
        mock_dev_reg = MagicMock(spec=["async_get_device"])
        mock_parent_dev = MagicMock(id="parent_dev_456")
        mock_dev_reg.async_get_device.return_value = mock_parent_dev
        mock_dr_get.return_value = mock_dev_reg

        result = _resolve_via_device_info(coordinator, "parent_hcu_id")
        assert result == {"via_device_id": "parent_dev_456"}
        mock_dev_reg.async_get_device.assert_called_once_with(
            identifiers={(DOMAIN, "parent_hcu_id")}
        )


def test_resolve_via_device_info_exception_handling():
    """Test _resolve_via_device_info handles exception in registry lookup gracefully."""
    coordinator = MagicMock()
    coordinator.hcu_device_entry_id = None
    coordinator.hass = MagicMock()

    with patch(
        "homeassistant.helpers.device_registry.async_get",
        side_effect=RuntimeError("boom"),
    ):
        result = _resolve_via_device_info(coordinator, "hcu_123")
    assert result == {"via_device": (DOMAIN, "hcu_123")}


def test_switch_state_mixin_init_and_sync():
    """Test SwitchStateMixin initialization and sync from channel data."""
    dummy = DummySwitchEntity({"on": True})
    assert dummy.is_on is True

    dummy._channel = {"on": False}
    dummy._sync_switch_state_from_coordinator()
    assert dummy.is_on is False

    dummy._channel = {}
    dummy._sync_switch_state_from_coordinator()
    assert dummy.is_on is False


async def test_switch_state_mixin_not_implemented_call():
    """Test that base SwitchStateMixin._call_switch_api raises NotImplementedError."""
    base_mixin = SwitchStateMixin()
    with pytest.raises(
        NotImplementedError, match="Subclasses must implement _call_switch_api"
    ):
        await base_mixin._call_switch_api(True)


async def test_switch_state_mixin_optimistic_success():
    """Test _async_set_optimistic_state success branch."""
    dummy = DummySwitchEntity({"on": False})
    await dummy._async_set_optimistic_state(True, "switch")
    assert dummy.is_on is True
    assert dummy.api_calls == [True]
    assert dummy.written_states == 1


async def test_switch_state_mixin_optimistic_error_rollback(
    caplog: pytest.LogCaptureFixture,
):
    """Test _async_set_optimistic_state error rollback on HcuApiError and ConnectionError."""
    dummy = DummySwitchEntity({"on": False})
    dummy.fail_api = HcuApiError("API failure")

    with caplog.at_level(logging.ERROR):
        await dummy._async_set_optimistic_state(True, "switch")

    assert dummy.is_on is False  # Reverted
    assert dummy.written_states == 2
    assert "Failed to turn on switch Test Switch: API failure" in caplog.text

    # ConnectionError turn off failure
    dummy.fail_api = ConnectionError("Network down")
    dummy._attr_is_on = True
    with caplog.at_level(logging.ERROR):
        await dummy._async_set_optimistic_state(False, "switch")

    assert dummy.is_on is True  # Reverted
    assert "Failed to turn off switch Test Switch: Network down" in caplog.text


def test_hcu_access_mixin_get_pin():
    """Test HcuAccessMixin._get_pin with and without device PIN."""
    coordinator = MagicMock()
    coordinator.config_entry.options = {CONF_DEVICE_PINS: {"dev_pin_1": "1234"}}
    entity = DummyAccessEntity(
        coordinator, MagicMock(), {"id": "dev_pin_1"}, {"index": 1}, MagicMock()
    )
    assert entity._get_pin() == "1234"

    entity_no_pin = DummyAccessEntity(
        coordinator, MagicMock(), {"id": "dev_other"}, {"index": 1}, MagicMock()
    )
    assert entity_no_pin._get_pin() is None


def test_hcu_access_mixin_find_authorization_channel_missing_client_id(
    caplog: pytest.LogCaptureFixture,
):
    """Test _find_authorization_channel when client id is missing triggers reauth."""
    coordinator = MagicMock()
    coordinator.config_entry.data = {CONF_AUTH_TYPE: AUTH_TYPE_APP}
    hass = MagicMock()
    entity = DummyAccessEntity(
        coordinator, MagicMock(), {"id": "dev_1"}, {"index": 1}, hass
    )

    with caplog.at_level(logging.ERROR):
        result = entity._find_authorization_channel()

    assert result is None
    coordinator.config_entry.async_start_reauth.assert_called_once_with(hass)
    assert "No clientId found for this integration" in caplog.text


def test_hcu_access_mixin_find_authorization_channel_no_candidates():
    """Test _find_authorization_channel when no ACCESS_AUTHORIZATION_CHANNEL matches."""
    coordinator = MagicMock()
    coordinator.config_entry.data = {
        CONF_AUTH_TYPE: "plugin",
        CONF_PLUGIN_CLIENT_ID: "plugin_user_1",
    }
    device = {
        "id": "dev_lock",
        "functionalChannels": {
            "0": {"functionalChannelType": "DEVICE_BASE"},
            "1": {"functionalChannelType": "DOOR_LOCK_CHANNEL", "groupIndex": 1},
        },
    }
    entity = DummyAccessEntity(
        coordinator, MagicMock(), device, {"index": 1, "groupIndex": 1}, MagicMock()
    )

    assert entity._find_authorization_channel() is None


def test_hcu_access_mixin_find_authorization_channel_not_authorized(
    caplog: pytest.LogCaptureFixture,
):
    """Test _find_authorization_channel when candidates exist but profile unauthorized."""
    coordinator = MagicMock()
    coordinator.config_entry.data = {
        CONF_AUTH_TYPE: AUTH_TYPE_DUAL,
        CONF_APP_CLIENT_ID: "app_user_1",
    }
    client = MagicMock()
    client.get_group_by_id.return_value = {
        "type": "ACCESS_AUTHORIZATION_PROFILE",
        "authorizationPinAssigned": False,  # Missing PIN
        "clientIds": ["app_user_1"],
    }
    device = {
        "id": "dev_lock",
        "functionalChannels": {
            "1": {"functionalChannelType": "DOOR_LOCK_CHANNEL", "groupIndex": 10},
            "2": {
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 10,
                "groups": ["group_auth_1"],
            },
        },
    }
    entity = DummyAccessEntity(
        coordinator, client, device, {"index": 1, "groupIndex": 10}, MagicMock()
    )

    with caplog.at_level(logging.ERROR):
        result = entity._find_authorization_channel()

    assert result is None
    assert (
        "The Home Assistant Integration is not authorized to control device 'dev_lock' channel 1"
        in caplog.text
    )


def test_hcu_access_mixin_find_authorization_channel_success(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
):
    """Test _find_authorization_channel successfully resolves authorized profile."""
    coordinator = MagicMock()
    coordinator.config_entry.data = {
        CONF_AUTH_TYPE: "plugin",
        CONF_PLUGIN_CLIENT_ID: "plugin_user_1",
    }
    client = MagicMock()
    client.get_group_by_id.side_effect = lambda gid: {
        "group_1": {
            "type": "ACCESS_AUTHORIZATION_PROFILE",
            "authorizationPinAssigned": True,
            "clientIds": ["plugin_user_1"],
            "label": "Front Door Profile",
        },
        "group_2": {
            "type": "ACCESS_AUTHORIZATION_PROFILE",
            "authorizationPinAssigned": True,
            "clientIds": ["plugin_user_1"],
            "label": "Second Profile",
        },
    }.get(gid)

    device = {
        "id": "dev_lock",
        "functionalChannels": {
            "1": {"functionalChannelType": "DOOR_LOCK_CHANNEL", "groupIndex": 10},
            "2": {
                "functionalChannelType": "ACCESS_AUTHORIZATION_CHANNEL",
                "groupIndex": 10,
                "groups": ["group_1", "group_2"],
            },
        },
    }
    entity = DummyAccessEntity(
        coordinator, client, device, {"index": 1, "groupIndex": 10}, hass
    )

    # Pre-create issue to verify deletion
    ir.async_create_issue(
        hass=hass,
        domain=DOMAIN,
        issue_id="access_authorization_dev_lock_1",
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="auth_required",
    )

    with caplog.at_level(logging.WARNING):
        result = entity._find_authorization_channel()

    assert result == (2, "Front Door Profile")
    assert (
        "Multiple ACCESS_AUTHORIZATION_PROFILEs found for dev_lock channel 1"
        in caplog.text
    )

    issue_registry = ir.async_get(hass)
    assert (
        issue_registry.async_get_issue(DOMAIN, "access_authorization_dev_lock_1")
        is None
    )


def test_hcu_base_entity_translation_keys_and_placeholders():
    """Test _apply_translation_key and _resolve_translation_prefix."""
    coordinator = MagicMock()
    client = MagicMock()
    device = {
        "id": "dev_1",
        "functionalChannels": {
            "1": {"label": "Living Light", "functionalChannelType": "SWITCH_CHANNEL"},
        },
    }
    client.get_device_by_address.return_value = device

    entity = HcuBaseEntity(coordinator, client, device, "1")
    entity._apply_translation_key("test_light")
    assert entity._attr_translation_key == "test_light"
    assert entity._base_translation_key == "test_light"

    # has_siblings = True with label
    entity._resolve_translation_prefix(has_siblings=True)
    assert entity._attr_translation_placeholders == {"channel": "CH1 "}

    # has_siblings = False
    entity._resolve_translation_prefix(has_siblings=False)
    assert entity._attr_translation_placeholders == {"channel": ""}

    # channel without label
    device["functionalChannels"]["1"]["label"] = ""
    entity._resolve_translation_prefix(has_siblings=True)
    assert entity._attr_translation_placeholders == {"channel": ""}

    # has_entity_name is False
    entity._attr_has_entity_name = False
    entity._attr_translation_placeholders = {"channel": "KEEP"}
    entity._resolve_translation_prefix(has_siblings=True)
    assert entity._attr_translation_placeholders == {"channel": "KEEP"}


def test_hcu_base_entity_meta_group_label_and_suggested_area():
    """Test _meta_group_label resolution from channel 0 or current channel."""
    coordinator = MagicMock()
    coordinator.hcu_device_entry_id = "parent_entry_1"
    client = MagicMock()
    client.hcu_device_id = "hcu_main"
    client.hcu_part_device_ids = set()

    meta_group = {"id": "meta_1", "type": "META", "label": "Ground Floor"}
    client.get_group_by_id.side_effect = lambda gid: (
        meta_group if gid == "meta_1" else None
    )

    # Meta on channel 0
    device_ch0 = {
        "id": "dev_meta",
        "label": "Meta Device",
        "functionalChannels": {
            "0": {"groups": ["meta_1"]},
            "1": {"groups": []},
        },
    }
    client.get_device_by_address.return_value = device_ch0

    entity = HcuBaseEntity(coordinator, client, device_ch0, "1")
    assert entity._meta_group_label == "Ground Floor"
    info = entity.device_info
    assert info["suggested_area"] == "Ground Floor"

    # Meta only on channel 1 (not channel 0)
    device_ch1 = {
        "id": "dev_meta2",
        "label": "Meta Device 2",
        "functionalChannels": {
            "0": {"groups": []},
            "1": {"groups": ["meta_1"]},
        },
    }
    client.get_device_by_address.return_value = device_ch1
    entity2 = HcuBaseEntity(coordinator, client, device_ch1, "1")
    assert entity2._meta_group_label == "Ground Floor"


def test_hcu_base_entity_advanced_attributes():
    """Test extra_state_attributes with advanced attributes enabled."""
    coordinator = MagicMock()
    coordinator.config_entry.options = {CONF_ADVANCED_ATTRIBUTES: True}
    client = MagicMock()

    device = {
        "id": "dev_adv",
        "functionalChannels": {
            "0": {"groups": ["meta_1"]},
            "1": {
                "functionalChannelType": "SWITCH_CHANNEL",
                "switchVisualization": "OUTLET",
                "channelRole": "HEATING",
            },
        },
    }
    client.get_device_by_address.return_value = device
    client.get_group_by_id.side_effect = lambda gid: (
        {"id": "meta_1", "type": "META", "label": "Ground Floor"}
        if gid == "meta_1"
        else None
    )

    entity = HcuBaseEntity(coordinator, client, device, "1")
    entity._attr_name = None
    entity._attr_translation_key = "custom_key"
    entity.object_id_base = "base_id"
    entity._attr_suggested_object_id = "suggested_id"

    attrs = entity.extra_state_attributes
    assert attrs["device_id"] == "dev_adv"
    assert attrs["channel_index"] == 1
    assert attrs["functional_channel_type"] == "SWITCH_CHANNEL"
    assert attrs["is_group"] is False
    assert attrs["meta"] == "Ground Floor"
    assert attrs["attr_name"] is None
    assert attrs["attr_has_entity_name"] is True
    assert attrs["attr_translation_key"] == "custom_key"
    assert attrs["object_id_base"] == "base_id"
    assert "suggested_object_id" in attrs
    assert attrs["switch_visualization"] == "OUTLET"
    assert attrs["channel_role"] == "HEATING"


def test_hcu_base_entity_get_internal_on_time(hass: HomeAssistant):
    """Test _get_internal_on_time under different companion entity states."""
    coordinator = MagicMock()
    client = MagicMock()
    device = {
        "id": "dev_timer",
        "functionalChannels": {
            "1": {
                "onTime": 120.0,
                "internalLinkConfiguration": {"onTime": 60.0},
            }
        },
    }
    client.get_device_by_address.return_value = device
    entity = HcuBaseEntity(coordinator, client, device, "1")
    entity.hass = hass

    # Registry has no entry
    assert entity._get_internal_on_time() is None

    # Register companion switch
    reg = er.async_get(hass)
    comp_entry = reg.async_get_or_create(
        "switch",
        DOMAIN,
        "dev_timer_1_use_internal_on_time",
        suggested_object_id="timer_switch",
    )

    # State is missing in states
    assert entity._get_internal_on_time() is None

    # State is OFF
    hass.states.async_set(comp_entry.entity_id, STATE_OFF)
    assert entity._get_internal_on_time() is None

    # State is ON with channel onTime
    hass.states.async_set(comp_entry.entity_id, STATE_ON)
    assert entity._get_internal_on_time() == 120.0

    # Channel onTime is 0, internalLink onTime is 60.0
    device["functionalChannels"]["1"]["onTime"] = 0
    assert entity._get_internal_on_time() == 60.0

    # Both are 0 or infinite
    device["functionalChannels"]["1"]["internalLinkConfiguration"]["onTime"] = 0
    assert entity._get_internal_on_time() is None

    device["functionalChannels"]["1"]["onTime"] = HMIP_ON_TIME_INFINITE
    assert entity._get_internal_on_time() is None


def test_hcu_base_entity_get_ramp_time(hass: HomeAssistant):
    """Test _get_ramp_time with different companion entity states."""
    coordinator = MagicMock()
    client = MagicMock()
    device = {"id": "dev_dim", "functionalChannels": {"1": {}}}
    client.get_device_by_address.return_value = device

    entity = HcuBaseEntity(coordinator, client, device, "1")
    entity.hass = hass

    # Not in registry
    assert entity._get_ramp_time() is None

    # In registry
    reg = er.async_get(hass)
    comp_entry = reg.async_get_or_create(
        "number", DOMAIN, "dev_dim_1_ramp_time", suggested_object_id="ramp_time"
    )

    # State is None
    assert entity._get_ramp_time() is None

    # State is non-numeric
    hass.states.async_set(comp_entry.entity_id, "invalid")
    assert entity._get_ramp_time() is None

    # State is 0 or negative
    hass.states.async_set(comp_entry.entity_id, "0.0")
    assert entity._get_ramp_time() is None
    hass.states.async_set(comp_entry.entity_id, "-1.5")
    assert entity._get_ramp_time() is None

    # State is positive
    hass.states.async_set(comp_entry.entity_id, "2.5")
    assert entity._get_ramp_time() == 2.5


def test_hcu_base_entity_handle_coordinator_update():
    """Test _handle_coordinator_update writes state when device id in coordinator data."""
    coordinator = MagicMock()
    coordinator.data = {"dev_1": {}}
    client = MagicMock()
    device = {"id": "dev_1", "functionalChannels": {"1": {}}}
    client.get_device_by_address.return_value = device

    entity = HcuBaseEntity(coordinator, client, device, "1")
    entity.async_write_ha_state = MagicMock()
    entity._attr_assumed_state = True

    entity._handle_coordinator_update()
    assert entity._attr_assumed_state is False
    entity.async_write_ha_state.assert_called_once()

    # When device not in data
    entity.async_write_ha_state.reset_mock()
    coordinator.data = {"other_dev": {}}
    entity._handle_coordinator_update()
    entity.async_write_ha_state.assert_not_called()


def test_hcu_group_base_entity_formatting_and_meta():
    """Test HcuGroupBaseEntity label formatting, meta group label, and device_info."""
    coordinator = MagicMock()
    client = MagicMock()
    client.hcu_device_id = "hcu_main"

    group_data = {
        "id": "grp_1",
        "type": "SWITCHING",
        "label": "FIRST_FLOOR_LIGHTS",
        "metaGroupId": "meta_grp_1",
    }
    client.get_group_by_id.side_effect = lambda gid: (
        group_data if gid == "grp_1" else {"id": "meta_grp_1", "label": "Ground Floor"}
    )

    entity = HcuGroupBaseEntity(coordinator, client, group_data)
    assert entity._group_name == "First Floor Lights"
    assert entity._meta_group_label == "Ground Floor"

    info = entity.device_info
    assert info["identifiers"] == {(DOMAIN, "grp_1")}
    assert info["model"] == "Switching Group"
    assert info["suggested_area"] == "Ground Floor"

    attrs = entity.extra_state_attributes
    assert attrs["type"] == "SWITCHING"
    assert attrs["is_group"] is True
    assert attrs["meta"] == "Ground Floor"

    # Availability
    client.is_connected = True
    assert entity.available is True
    client.is_connected = False
    assert entity.available is False


def test_hcu_group_base_entity_handle_coordinator_update():
    """Test HcuGroupBaseEntity._handle_coordinator_update."""
    coordinator = MagicMock()
    coordinator.data = {"grp_1": {}}
    client = MagicMock()
    group_data = {"id": "grp_1", "label": "Group 1"}
    client.get_group_by_id.return_value = group_data

    entity = HcuGroupBaseEntity(coordinator, client, group_data)
    entity.async_write_ha_state = MagicMock()
    entity._attr_assumed_state = True

    entity._handle_coordinator_update()
    assert entity._attr_assumed_state is False
    entity.async_write_ha_state.assert_called_once()


async def test_hcu_switching_group_base_turn_on_turn_off_and_errors(
    caplog: pytest.LogCaptureFixture,
):
    """Test HcuSwitchingGroupBase turn on, turn off, and optimistic rollback on error."""
    coordinator = MagicMock()
    coordinator.data = {"grp_switch": {}}
    client = MagicMock()
    client.async_set_switching_group_state = AsyncMock()

    group_data = {"id": "grp_switch", "label": "Switch Group", "on": False}
    client.get_group_by_id.return_value = group_data

    group_entity = HcuSwitchingGroupBase(coordinator, client, group_data)
    group_entity.async_write_ha_state = MagicMock()

    assert group_entity._attr_is_on is False

    # Turn on success
    await group_entity.async_turn_on()
    assert group_entity._attr_is_on is True
    client.async_set_switching_group_state.assert_called_once_with("grp_switch", True)

    # Turn off success
    client.async_set_switching_group_state.reset_mock()
    await group_entity.async_turn_off()
    assert group_entity._attr_is_on is False
    client.async_set_switching_group_state.assert_called_once_with("grp_switch", False)

    # Error rollback
    client.async_set_switching_group_state.side_effect = HcuApiError(
        "Group unreachable"
    )
    with caplog.at_level(logging.ERROR):
        await group_entity.async_turn_on()
    assert group_entity._attr_is_on is False
    assert (
        "Failed to set switching group grp_switch state to True: Group unreachable"
        in caplog.text
    )

    # Coordinator update syncs state
    group_data["on"] = True
    group_entity._handle_coordinator_update()
    assert group_entity._attr_is_on is True


def test_hcu_home_base_entity_full_lifecycle():
    """Test HcuHomeBaseEntity device_info, availability, extra_attrs, and coordinator update."""
    coordinator = MagicMock()
    coordinator.data = {"home_uuid_1": {}}
    client = MagicMock()
    client.hcu_device_id = "hcu_main"
    client.is_connected = True
    client.state = {"home": {"id": "home_uuid_1"}}

    entity = HcuHomeBaseEntity(coordinator, client)
    entity.async_write_ha_state = MagicMock()
    entity._attr_assumed_state = True

    assert entity.available is True
    assert entity.extra_state_attributes == {"is_group": False}
    assert entity.device_info["identifiers"] == {(DOMAIN, "hcu_main")}

    entity._handle_coordinator_update()
    assert entity._attr_assumed_state is False
    entity.async_write_ha_state.assert_called_once()

    # None hcu_device_id
    client.hcu_device_id = None
    entity._hcu_device_id = None
    assert entity.device_info is None


def test_hcu_base_entity_same_type_channel_count_missing_type():
    """Test _get_same_type_channel_count returns 1 when functionalChannelType is absent."""
    coordinator = MagicMock()
    client = MagicMock()
    device = {"id": "dev_no_type", "functionalChannels": {"1": {}}}
    client.get_device_by_address.return_value = device

    entity = HcuBaseEntity(coordinator, client, device, "1")
    assert entity._get_same_type_channel_count() == 1


def test_hcu_group_base_entity_format_label_regular_string():
    """Test _format_label preserves regular mixed-case string without underscores."""
    assert HcuGroupBaseEntity._format_label("Living Room") == "Living Room"
    assert HcuGroupBaseEntity._format_label("") == ""


def test_hcu_base_entity_set_channel_index_name():
    """Test _set_channel_index_name sets translation key and placeholder and removes _attr_name."""
    coordinator = MagicMock()
    client = MagicMock()
    device = {"id": "dev_idx", "functionalChannels": {"1": {}}}
    client.get_device_by_address.return_value = device
    entity = HcuBaseEntity(coordinator, client, device, "1")
    entity._attr_name = "Initial Name"
    entity._set_channel_index_name("hcu_switch", "2")
    assert entity.translation_key == "hcu_switch"
    assert entity.translation_placeholders == {"channel_index": " 2"}
    assert not hasattr(entity, "_attr_name")

    entity2 = HcuBaseEntity(coordinator, client, device, "1")
    entity2._set_channel_index_name("hcu_switch", "3")
    assert entity2.translation_key == "hcu_switch"
