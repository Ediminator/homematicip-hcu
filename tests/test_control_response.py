"""Tests for the CONTROL_RESPONSE of the HA entity bridge (Connect API 6.3.3)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.hcu_integration.api import HcuApiClient
from custom_components.hcu_integration.const import (
    CONTROL_ERROR_FAILED,
    CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
    CONTROL_ERROR_UNKNOWN_DEVICE,
    HA_DEVICE_TYPE_LIGHT,
    HA_DEVICE_TYPE_SWITCH,
    HA_FEATURE_BRIGHTNESS,
    HA_FEATURE_COLOR_TEMP,
    HA_FEATURE_ON_OFF,
    HA_FEATURE_RGB_COLOR,
    PLUGIN_ID,
)
from custom_components.hcu_integration.ha_entity_bridge import HaEntityBridge

_SWITCH = {
    "id": "sw1",
    "name": "Garden Pump",
    "type": HA_DEVICE_TYPE_SWITCH,
    "features": {HA_FEATURE_ON_OFF: "switch.pump"},
}
_LIGHT = {
    "id": "lt1",
    "name": "Desk Lamp",
    "type": HA_DEVICE_TYPE_LIGHT,
    "features": {
        HA_FEATURE_ON_OFF: "light.desk",
        HA_FEATURE_BRIGHTNESS: "light.desk",
        HA_FEATURE_COLOR_TEMP: "light.desk",
        HA_FEATURE_RGB_COLOR: "light.desk",
    },
}


@pytest.fixture
def websocket(api_client: HcuApiClient) -> AsyncMock:
    """Connect the client to a fake Plugin WebSocket and return it."""
    ws = AsyncMock()
    ws.closed = False
    api_client._websocket = ws
    return ws


def _bridge(hass: HomeAssistant, api_client: HcuApiClient) -> HaEntityBridge:
    bridge = HaEntityBridge(
        hass, [_SWITCH, _LIGHT], api_client._send_message, PLUGIN_ID
    )
    api_client.set_ha_entity_bridge(bridge)
    return bridge


def _control_request(device_id: Any, features: list[dict[str, Any]]) -> dict:
    return {
        "pluginId": PLUGIN_ID,
        "id": "ctrl-1",
        "type": "CONTROL_REQUEST",
        "body": {"deviceId": device_id, "features": features},
    }


def _sent_control_response(websocket: AsyncMock) -> dict:
    responses = [
        call.args[0]
        for call in websocket.send_json.call_args_list
        if call.args[0]["type"] == "CONTROL_RESPONSE"
    ]
    assert len(responses) == 1
    response = responses[0]
    assert response["id"] == "ctrl-1"
    assert response["pluginId"] == PLUGIN_ID
    return response["body"]


async def test_success_reports_device_and_success(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    turn_on = async_mock_service(hass, "switch", "turn_on")
    _bridge(hass, api_client)

    await api_client._handle_control_request(
        _control_request("ha.sw1", [{"type": "switchState", "on": True}])
    )

    assert len(turn_on) == 1
    assert _sent_control_response(websocket) == {
        "deviceId": "ha.sw1",
        "success": True,
    }


async def test_failed_service_call_reports_failure(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    async def _fail(call: ServiceCall) -> None:
        raise HomeAssistantError("Pump offline")

    hass.services.async_register("switch", "turn_on", _fail)
    _bridge(hass, api_client)

    await api_client._handle_control_request(
        _control_request("ha.sw1", [{"type": "switchState", "on": True}])
    )

    assert _sent_control_response(websocket) == {
        "deviceId": "ha.sw1",
        "success": False,
        "error": {
            "code": CONTROL_ERROR_FAILED,
            "message": "switch.turn_on for switch.pump failed: Pump offline",
        },
    }


async def test_unknown_device_reports_failure(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    bridge = _bridge(hass, api_client)
    bridge.send_status_event = AsyncMock()  # type: ignore[method-assign]

    await api_client._handle_control_request(
        _control_request("ha.gone", [{"type": "switchState", "on": True}])
    )

    assert _sent_control_response(websocket) == {
        "deviceId": "ha.gone",
        "success": False,
        "error": {
            "code": CONTROL_ERROR_UNKNOWN_DEVICE,
            "message": "Unknown device ha.gone",
        },
    }
    bridge.send_status_event.assert_not_awaited()


async def test_unknown_device_without_bridge_reports_failure(
    api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    await api_client._handle_control_request(
        _control_request("ha.sw1", [{"type": "switchState", "on": True}])
    )

    assert _sent_control_response(websocket) == {
        "deviceId": "ha.sw1",
        "success": False,
        "error": {
            "code": CONTROL_ERROR_UNKNOWN_DEVICE,
            "message": "Unknown device ha.sw1",
        },
    }


async def test_request_without_device_id_reports_failure(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    _bridge(hass, api_client)

    await api_client._handle_control_request(
        {"id": "ctrl-1", "type": "CONTROL_REQUEST", "body": {"features": []}}
    )

    body = _sent_control_response(websocket)
    assert body["deviceId"] == ""
    assert body["success"] is False
    assert body["error"]["code"] == CONTROL_ERROR_UNKNOWN_DEVICE


@pytest.mark.parametrize(
    ("device_id", "feature"),
    [
        # A feature type the bridge cannot apply at all.
        ("ha.sw1", {"type": "setPointTemperature", "setPointTemperature": 21.0}),
        # A known feature type without a configured entity for it.
        ("ha.sw1", {"type": "colorTemperature", "colorTemperature": 3000}),
        ("ha.sw1", {"type": "color", "hue": 120, "saturationLevel": 1.0}),
        # Dimming needs a light entity.
        ("ha.sw1", {"type": "dimming", "dimLevel": 0.5}),
    ],
)
async def test_unsupported_feature_reports_failure(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    device_id: str,
    feature: dict[str, Any],
) -> None:
    async_mock_service(hass, "light", "turn_on")
    _bridge(hass, api_client)

    await api_client._handle_control_request(_control_request(device_id, [feature]))

    assert _sent_control_response(websocket) == {
        "deviceId": device_id,
        "success": False,
        "error": {
            "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
            "message": f"Feature {feature['type']} is not supported by {device_id}",
        },
    }


async def test_switch_feature_without_entity_reports_failure(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    bridge = HaEntityBridge(
        hass,
        [
            {
                "id": "lt2",
                "name": "Brightness only",
                "type": HA_DEVICE_TYPE_LIGHT,
                "features": {HA_FEATURE_BRIGHTNESS: "light.strip"},
            }
        ],
        api_client._send_message,
        PLUGIN_ID,
    )
    api_client.set_ha_entity_bridge(bridge)

    await api_client._handle_control_request(
        _control_request("ha.lt2", [{"type": "switchState", "on": True}])
    )

    body = _sent_control_response(websocket)
    assert body["success"] is False
    assert body["error"]["code"] == CONTROL_ERROR_FEATURE_NOT_SUPPORTED


async def test_partial_failure_applies_the_rest_and_reports_failure(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    turn_on = async_mock_service(hass, "light", "turn_on")
    _bridge(hass, api_client)

    await api_client._handle_control_request(
        _control_request(
            "ha.lt1",
            [
                {"type": "dimming", "dimLevel": 0.2},
                {"type": "setPointTemperature", "setPointTemperature": 21.0},
                {"type": "switchState", "on": True},
            ],
        )
    )

    # Both supported features were applied.
    assert [call.data for call in turn_on] == [
        {"entity_id": "light.desk", "brightness": 51},
        {"entity_id": "light.desk"},
    ]
    assert _sent_control_response(websocket) == {
        "deviceId": "ha.lt1",
        "success": False,
        "error": {
            "code": CONTROL_ERROR_FEATURE_NOT_SUPPORTED,
            "message": "Feature setPointTemperature is not supported by ha.lt1",
        },
    }


async def test_several_failures_are_joined_in_one_error(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    async def _fail(call: ServiceCall) -> None:
        raise HomeAssistantError("Lamp offline")

    hass.services.async_register("light", "turn_on", _fail)
    _bridge(hass, api_client)

    await api_client._handle_control_request(
        _control_request(
            "ha.lt1",
            [
                {"type": "dimming", "dimLevel": 0.2},
                {"type": "setPointTemperature", "setPointTemperature": 21.0},
            ],
        )
    )

    # The first failure sets the code; all messages are kept.
    assert _sent_control_response(websocket)["error"] == {
        "code": CONTROL_ERROR_FAILED,
        "message": "Dimming light.desk failed: Lamp offline; "
        "Feature setPointTemperature is not supported by ha.lt1",
    }


@pytest.mark.parametrize(
    "feature",
    [
        # onTime only modifies a switchState in the same request (6.7.18).
        {"type": "onTime", "onTime": 30},
        # Features without a target value leave the device unchanged (6.4.3).
        {"type": "dimming"},
        {"type": "colorTemperature"},
        {"type": "color", "hue": 120},
    ],
)
async def test_feature_without_action_reports_success(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    feature: dict[str, Any],
) -> None:
    turn_on = async_mock_service(hass, "light", "turn_on")
    _bridge(hass, api_client)

    await api_client._handle_control_request(_control_request("ha.lt1", [feature]))

    assert turn_on == []
    assert _sent_control_response(websocket) == {
        "deviceId": "ha.lt1",
        "success": True,
    }


async def test_status_event_follows_a_failed_control(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    """After a failure the real state is pushed, so the HCU can show it again."""

    async def _fail(call: ServiceCall) -> None:
        raise HomeAssistantError("Pump offline")

    hass.services.async_register("switch", "turn_on", _fail)
    hass.states.async_set("switch.pump", "off")
    bridge = _bridge(hass, api_client)
    bridge.build_discover_devices()

    await api_client._handle_control_request(
        _control_request("ha.sw1", [{"type": "switchState", "on": True}])
    )

    sent_types = [call.args[0]["type"] for call in websocket.send_json.call_args_list]
    assert sent_types == ["CONTROL_RESPONSE", "STATUS_EVENT"]
    status = websocket.send_json.call_args_list[1].args[0]["body"]
    assert status == {
        "deviceId": "ha.sw1",
        "features": [{"type": "switchState", "on": False}],
    }


async def test_bridge_returns_error_object_or_none(hass: HomeAssistant) -> None:
    async_mock_service(hass, "switch", "turn_on")
    bridge = HaEntityBridge(hass, [_SWITCH], AsyncMock(), PLUGIN_ID)

    assert (
        await bridge.handle_control_request(
            {"deviceId": "ha.sw1", "features": [{"type": "switchState", "on": True}]}
        )
        is None
    )
    assert await bridge.handle_control_request(
        {"deviceId": "ha.nope", "features": [{"type": "switchState", "on": True}]}
    ) == {
        "code": CONTROL_ERROR_UNKNOWN_DEVICE,
        "message": "Unknown device ha.nope",
    }
