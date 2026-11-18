"""Tests for the device lifecycle of the HA entity bridge.

Covers INCLUSION_EVENT (Connect API 6.4.11), EXCLUSION_EVENT (6.4.8) and the
reachability reported in the Maintenance feature (6.7.16).
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import issue_registry as ir
import pytest
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.hcu_integration.api import HcuApiClient
from custom_components.hcu_integration.const import (
    DOMAIN,
    HA_DEVICE_TYPE_FEATURES,
    HA_FEATURE_CONTACT_SENSOR,
    HA_FEATURE_DOOR,
    HA_FEATURE_HUMIDITY,
    HA_FEATURE_LOW_BAT,
    HA_FEATURE_MOTION,
    HA_FEATURE_ON_OFF,
    HA_FEATURE_ON_TIME,
    HA_FEATURE_PM10,
    HA_FEATURE_PM25,
    HA_FEATURE_SABOTAGE,
    HA_FEATURE_SET_POINT_TEMP,
    HA_FEATURE_TEMPERATURE,
    HA_FEATURE_UNREACH,
    HA_FEATURE_WINDOW,
    PLUGIN_ID,
)
from custom_components.hcu_integration.ha_entity_bridge import (
    _DISCOVER_FEATURE,
    HaEntityBridge,
)

SWITCH = {
    "id": "sw1",
    "name": "Garden Pump",
    "type": "SWITCH",
    "features": {HA_FEATURE_ON_OFF: "switch.pump"},
}
SENSOR = {
    "id": "cs1",
    "name": "Weather",
    "type": "CLIMATE_SENSOR",
    "features": {
        HA_FEATURE_TEMPERATURE: "sensor.temp",
        HA_FEATURE_HUMIDITY: "sensor.hum",
    },
}
REACHABLE = {"type": "maintenance", "unreach": False}
UNREACHABLE = {"type": "maintenance", "unreach": True}


def _switch_object(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "deviceId": "ha.sw1",
        "friendlyName": "Garden Pump",
        "modelType": "Homeassistant",
        "firmwareVersion": "0.0.0",
        "deviceType": "SWITCH",
        "features": features,
    }


def _sensor_object(features: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "deviceId": "ha.cs1",
        "friendlyName": "Weather",
        "modelType": "Homeassistant",
        "firmwareVersion": "0.0.0",
        "deviceType": "CLIMATE_SENSOR",
        "features": features,
    }


SWITCH_ON = _switch_object([{"type": "switchState", "on": True}, REACHABLE])
SENSOR_OK = _sensor_object(
    [
        {"type": "actualTemperature", "actualTemperature": 21.5},
        {"type": "humidity", "humidity": 40},
        REACHABLE,
    ]
)


@pytest.fixture
def websocket(api_client: HcuApiClient) -> AsyncMock:
    """Connect the client to a fake Plugin WebSocket and return it."""
    ws = AsyncMock()
    ws.closed = False
    api_client._websocket = ws
    return ws


@pytest.fixture
def bridge(hass: HomeAssistant, api_client: HcuApiClient) -> HaEntityBridge:
    """Attach a bridge with a switch and a climate sensor, all entities available."""
    hass.states.async_set("switch.pump", STATE_ON)
    hass.states.async_set("sensor.temp", "21.5")
    hass.states.async_set("sensor.hum", "40")
    bridge = HaEntityBridge(hass, [SWITCH, SENSOR], api_client._send_message, PLUGIN_ID)
    api_client.set_ha_entity_bridge(bridge)
    return bridge


def _sent(websocket: AsyncMock) -> list[dict[str, Any]]:
    return [call.args[0] for call in websocket.send_json.call_args_list]


def _event(msg_type: str, device_ids: Any) -> dict[str, Any]:
    return {
        "pluginId": PLUGIN_ID,
        "id": "evt-1",
        "type": msg_type,
        "body": {"deviceIds": device_ids},
    }


async def _dispatch(api_client: HcuApiClient, *messages: dict[str, Any]) -> None:
    """Feed messages to the client back to back, then let their handlers finish."""
    for message in messages:
        api_client._handle_incoming_message(message)
    await asyncio.gather(*api_client._background_tasks)


def _issue_ids(hass: HomeAssistant) -> list[str]:
    return [
        issue_id for (domain, issue_id) in ir.async_get(hass).issues if domain == DOMAIN
    ]


MALFORMED_BODIES = [
    pytest.param({}, id="no-body"),
    pytest.param({"body": None}, id="body-none"),
    pytest.param({"body": ["ha.sw1"]}, id="body-list"),
    pytest.param({"body": {}}, id="no-device-ids"),
    pytest.param({"body": {"deviceIds": None}}, id="ids-none"),
    pytest.param({"body": {"deviceIds": "ha.sw1"}}, id="ids-string"),
    pytest.param({"body": {"deviceIds": {"ha.sw1": 1}}}, id="ids-dict"),
    pytest.param({"body": {"deviceIds": []}}, id="ids-empty"),
    pytest.param(
        {"body": {"deviceIds": [None, 5, ["ha.sw1"], {"a": 1}]}}, id="ids-no-strings"
    ),
]


# --- INCLUSION_EVENT ---


async def test_inclusion_event_answers_with_one_status_response(
    api_client: HcuApiClient, websocket: AsyncMock, bridge: HaEntityBridge
) -> None:
    """The included devices are reported in one unsolicited STATUS_RESPONSE."""
    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.sw1", "ha.cs1"]))

    assert len(_sent(websocket)) == 1
    response = _sent(websocket)[0]
    assert set(response) == {"id", "pluginId", "type", "body"}
    assert response["type"] == "STATUS_RESPONSE"
    assert response["pluginId"] == PLUGIN_ID
    assert response["id"] != "evt-1"
    assert str(UUID(response["id"], version=4)) == response["id"]
    assert response["body"] == {"success": True, "devices": [SWITCH_ON, SENSOR_OK]}


async def test_inclusion_before_discovery_enables_status_events(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """A device named in an INCLUSION_EVENT pushes state without a discovery."""
    await bridge.send_status_event()
    assert _sent(websocket) == []

    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.sw1"]))
    assert bridge._discovered_hcu_ids == {"ha.sw1"}
    websocket.send_json.reset_mock()

    hass.states.async_set("switch.pump", STATE_OFF)
    await bridge.send_status_event()

    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        (
            "STATUS_EVENT",
            {
                "deviceId": "ha.sw1",
                "features": [{"type": "switchState", "on": False}, REACHABLE],
            },
        )
    ]


async def test_inclusion_event_reports_an_unreachable_device(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    hass.states.async_set("switch.pump", STATE_UNAVAILABLE)

    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.sw1"]))

    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        (
            "STATUS_RESPONSE",
            {"success": True, "devices": [_switch_object([UNREACHABLE])]},
        )
    ]
    assert bridge._discovered_hcu_ids == {"ha.sw1"}


async def test_inclusion_event_with_known_stale_and_foreign_ids(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """Only configured devices are reported; a stale bridge device gets a repair."""
    await _dispatch(
        api_client,
        _event(
            "INCLUSION_EVENT",
            ["ha.gone", "ha.sw1", "0001D8A9999", None, "ha.sw1", 7],
        ),
    )

    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_RESPONSE", {"success": True, "devices": [SWITCH_ON]})
    ]
    assert bridge._discovered_hcu_ids == {"ha.sw1"}
    assert _issue_ids(hass) == ["ha_entity_excluded_ha_gone"]


async def test_inclusion_event_without_known_devices_sends_nothing(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.gone", "0001D8A9999"]))

    assert _sent(websocket) == []
    assert bridge._discovered_hcu_ids == set()
    assert _issue_ids(hass) == ["ha_entity_excluded_ha_gone"]


async def test_inclusion_event_for_device_without_features_sends_nothing(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    bridge = HaEntityBridge(
        hass, [{"id": "empty", "features": {}}], api_client._send_message, PLUGIN_ID
    )
    api_client.set_ha_entity_bridge(bridge)

    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.empty"]))

    assert _sent(websocket) == []
    assert bridge._discovered_hcu_ids == set()
    assert _issue_ids(hass) == []


@pytest.mark.parametrize("message", MALFORMED_BODIES)
async def test_malformed_inclusion_event_is_ignored(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
    message: dict[str, Any],
) -> None:
    await _dispatch(api_client, {"type": "INCLUSION_EVENT", "id": "evt-1", **message})

    assert _sent(websocket) == []
    assert bridge._discovered_hcu_ids == set()
    assert _issue_ids(hass) == []


async def test_inclusion_event_survives_a_lost_connection(
    hass: HomeAssistant, api_client: HcuApiClient, bridge: HaEntityBridge
) -> None:
    """Without a connection the devices are still registered and stale ones flagged."""
    assert api_client._websocket is None

    await api_client._handle_inclusion_event(
        _event("INCLUSION_EVENT", ["ha.sw1", "ha.gone"])
    )

    assert bridge._discovered_hcu_ids == {"ha.sw1"}
    assert _issue_ids(hass) == ["ha_entity_excluded_ha_gone"]


async def test_inclusion_event_without_bridge_is_ignored(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.sw1", "ha.gone"]))

    assert _sent(websocket) == []
    assert _issue_ids(hass) == []


def test_bridge_inclusion_ignores_unknown_ids(bridge: HaEntityBridge) -> None:
    assert bridge.handle_inclusion_event(["ha.gone", "0001D8A9999"]) == []
    assert bridge._discovered_hcu_ids == set()
    assert bridge.handle_inclusion_event(["ha.cs1", "ha.cs1"]) == [SENSOR_OK]
    assert bridge._discovered_hcu_ids == {"ha.cs1"}


# --- EXCLUSION_EVENT ---


async def test_exclusion_event_stops_status_events(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """An excluded device pushes no state; the other devices keep pushing."""
    bridge.build_discover_devices()
    await bridge.send_status_event()
    assert [m["body"]["deviceId"] for m in _sent(websocket)] == ["ha.sw1", "ha.cs1"]
    assert set(bridge._last_sent) == {"ha.sw1", "ha.cs1"}
    websocket.send_json.reset_mock()

    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.sw1"]))

    assert bridge._discovered_hcu_ids == {"ha.cs1"}
    assert bridge._excluded_hcu_ids == {"ha.sw1"}
    assert set(bridge._last_sent) == {"ha.cs1"}
    assert set(bridge._last_sent_features) == {"ha.cs1"}

    hass.states.async_set("switch.pump", STATE_OFF)
    hass.states.async_set("sensor.temp", "19.0")
    await bridge.send_status_event()
    await bridge.send_status_event(["ha.sw1"])

    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        (
            "STATUS_EVENT",
            {
                "deviceId": "ha.cs1",
                "features": [
                    {"type": "actualTemperature", "actualTemperature": 19.0},
                    {"type": "humidity", "humidity": 40},
                    REACHABLE,
                ],
            },
        )
    ]


async def test_state_change_of_excluded_device_sends_nothing(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """The state listener stays silent for an excluded device."""
    bridge.build_discover_devices()
    bridge.start_listening()
    await hass.async_block_till_done()
    websocket.send_json.reset_mock()
    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.sw1"]))

    hass.states.async_set("switch.pump", STATE_OFF)
    await hass.async_block_till_done()

    assert _sent(websocket) == []
    bridge.stop_listening()


async def test_status_request_omits_excluded_devices(
    api_client: HcuApiClient, websocket: AsyncMock, bridge: HaEntityBridge
) -> None:
    """Neither a broad nor an explicit STATUS_REQUEST reports an excluded device."""
    bridge.build_discover_devices()
    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.sw1"]))

    await api_client._handle_status_request({"id": "all", "body": {}})
    await api_client._handle_status_request(
        {"id": "both", "body": {"deviceIds": ["ha.sw1", "ha.cs1"]}}
    )
    await api_client._handle_status_request(
        {"id": "excluded", "body": {"deviceIds": ["ha.sw1"]}}
    )

    assert _sent(websocket) == [
        {
            "id": "all",
            "pluginId": PLUGIN_ID,
            "type": "STATUS_RESPONSE",
            "body": {"success": True, "devices": [SENSOR_OK]},
        },
        {
            "id": "both",
            "pluginId": PLUGIN_ID,
            "type": "STATUS_RESPONSE",
            "body": {"success": True, "devices": [SENSOR_OK]},
        },
        {
            "id": "excluded",
            "pluginId": PLUGIN_ID,
            "type": "STATUS_RESPONSE",
            "body": {"success": True, "devices": []},
        },
    ]


async def test_discovery_offers_an_excluded_device_without_activating_it(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """Only an INCLUSION_EVENT activates an excluded device again."""
    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.sw1"]))
    assert bridge._excluded_hcu_ids == {"ha.sw1"}

    await api_client._send_discover_response("disc-1")

    assert _sent(websocket) == [
        {
            "id": "disc-1",
            "pluginId": PLUGIN_ID,
            "type": "DISCOVER_RESPONSE",
            "body": {"success": True, "devices": [SWITCH_ON, SENSOR_OK]},
        }
    ]
    assert bridge._discovered_hcu_ids == {"ha.cs1"}
    assert bridge._excluded_hcu_ids == {"ha.sw1"}
    websocket.send_json.reset_mock()
    hass.states.async_set("switch.pump", STATE_OFF)
    await bridge.send_status_event(["ha.sw1"])
    assert _sent(websocket) == []

    await _dispatch(api_client, _event("INCLUSION_EVENT", ["ha.sw1"]))

    assert bridge._discovered_hcu_ids == {"ha.sw1", "ha.cs1"}
    assert bridge._excluded_hcu_ids == set()
    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        (
            "STATUS_RESPONSE",
            {
                "success": True,
                "devices": [
                    _switch_object([{"type": "switchState", "on": False}, REACHABLE])
                ],
            },
        )
    ]
    websocket.send_json.reset_mock()
    hass.states.async_set("switch.pump", STATE_ON)
    await bridge.send_status_event(["ha.sw1"])
    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        (
            "STATUS_EVENT",
            {
                "deviceId": "ha.sw1",
                "features": [{"type": "switchState", "on": True}, REACHABLE],
            },
        )
    ]


async def test_exclusion_event_ignores_unknown_ids(
    api_client: HcuApiClient, bridge: HaEntityBridge
) -> None:
    bridge.build_discover_devices()

    await _dispatch(
        api_client,
        _event("EXCLUSION_EVENT", ["ha.gone", "0001D8A9999", None, "ha.cs1", "ha.cs1"]),
    )

    assert bridge._excluded_hcu_ids == {"ha.cs1"}
    assert bridge._discovered_hcu_ids == {"ha.sw1"}


async def test_exclusion_event_clears_the_stale_device_repair(
    hass: HomeAssistant, api_client: HcuApiClient, bridge: HaEntityBridge
) -> None:
    """Removing a stale bridge device from the HCU resolves its repair issue."""
    await bridge.handle_stale_inclusion_devices(["ha.gone", "ha.other-1"])
    assert _issue_ids(hass) == [
        "ha_entity_excluded_ha_gone",
        "ha_entity_excluded_ha_other_1",
    ]

    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.other-1", "ha_gone"]))

    assert _issue_ids(hass) == ["ha_entity_excluded_ha_gone"]


@pytest.mark.parametrize("message", MALFORMED_BODIES)
async def test_malformed_exclusion_event_is_ignored(
    api_client: HcuApiClient, bridge: HaEntityBridge, message: dict[str, Any]
) -> None:
    bridge.build_discover_devices()

    await _dispatch(api_client, {"type": "EXCLUSION_EVENT", "id": "evt-1", **message})

    assert bridge._excluded_hcu_ids == set()
    assert bridge._discovered_hcu_ids == {"ha.sw1", "ha.cs1"}


async def test_exclusion_event_without_bridge_is_logged(
    api_client: HcuApiClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level("INFO"):
        await _dispatch(api_client, _event("EXCLUSION_EVENT", ["d2", 5]))

    assert "EXCLUSION_EVENT for devices: ['d2']" in caplog.text


@pytest.mark.parametrize(
    ("order", "active", "excluded"),
    [
        (("INCLUSION_EVENT", "EXCLUSION_EVENT"), set(), {"ha.sw1"}),
        (("EXCLUSION_EVENT", "INCLUSION_EVENT"), {"ha.sw1"}, set()),
    ],
)
async def test_inclusion_and_exclusion_apply_in_arrival_order(
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
    order: tuple[str, str],
    active: set[str],
    excluded: set[str],
) -> None:
    """Two events that arrive back to back take effect in that order."""
    await _dispatch(api_client, *(_event(msg_type, ["ha.sw1"]) for msg_type in order))

    assert bridge._discovered_hcu_ids == active
    assert bridge._excluded_hcu_ids == excluded
    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_RESPONSE", {"success": True, "devices": [SWITCH_ON]})
    ]


@pytest.mark.parametrize(
    ("order", "issues"),
    [
        (("INCLUSION_EVENT", "EXCLUSION_EVENT"), []),
        (("EXCLUSION_EVENT", "INCLUSION_EVENT"), ["ha_entity_excluded_ha_gone"]),
    ],
)
async def test_inclusion_and_exclusion_with_yielding_socket_preserve_repair_order(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
    order: tuple[str, str],
    issues: list[str],
) -> None:
    """Stale repair updates complete before yielding on send_json."""

    async def _yielding_send(payload: dict[str, Any]) -> None:
        await asyncio.sleep(0)

    websocket.send_json.side_effect = _yielding_send
    messages = [
        _event(
            msg_type,
            ["ha.sw1", "ha.gone"] if msg_type == "INCLUSION_EVENT" else ["ha.gone"],
        )
        for msg_type in order
    ]

    await _dispatch(api_client, *messages)

    assert bridge._discovered_hcu_ids == {"ha.sw1"}
    assert bridge._excluded_hcu_ids == set()
    assert _issue_ids(hass) == issues
    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_RESPONSE", {"success": True, "devices": [SWITCH_ON]})
    ]


async def test_control_of_excluded_device_sends_no_status_event(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    turn_off = async_mock_service(hass, "switch", "turn_off")
    bridge.build_discover_devices()
    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.sw1"]))

    await api_client._handle_control_request(
        {
            "id": "ctrl-1",
            "body": {
                "deviceId": "ha.sw1",
                "features": [{"type": "switchState", "on": False}],
            },
        }
    )

    assert [call.data for call in turn_off] == [{"entity_id": "switch.pump"}]
    assert _sent(websocket) == [
        {
            "id": "ctrl-1",
            "pluginId": PLUGIN_ID,
            "type": "CONTROL_RESPONSE",
            "body": {"deviceId": "ha.sw1", "success": True},
        }
    ]


async def test_pending_auto_off_still_runs_after_exclusion(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """An excluded device is still switched off when its on time has run out."""

    async def _turn_off(call: ServiceCall) -> None:
        hass.states.async_set(call.data["entity_id"], STATE_OFF)

    async_mock_service(hass, "switch", "turn_on")
    hass.services.async_register("switch", "turn_off", _turn_off)
    bridge.build_discover_devices()
    bridge.start_listening()
    await hass.async_block_till_done()
    websocket.send_json.reset_mock()
    assert (
        await bridge.handle_control_request(
            {
                "deviceId": "ha.sw1",
                "features": [{"type": "switchState", "on": True, "onTime": 0.05}],
            }
        )
        is None
    )
    timer = bridge._auto_off_tasks["switch.pump"]

    await _dispatch(api_client, _event("EXCLUSION_EVENT", ["ha.sw1"]))

    assert bridge._auto_off_tasks == {"switch.pump": timer}
    assert not timer.done()
    await timer
    await hass.async_block_till_done()
    bridge.stop_listening()
    assert hass.states.get("switch.pump").state == STATE_OFF
    assert bridge._auto_off_tasks == {}
    assert _sent(websocket) == []


# --- Reachability ---


@pytest.mark.parametrize("device_type", sorted(HA_DEVICE_TYPE_FEATURES))
def test_every_device_type_advertises_maintenance(
    hass: HomeAssistant, device_type: str
) -> None:
    """Maintenance is discovered for each type, once, with the reachability."""
    spec = HA_DEVICE_TYPE_FEATURES[device_type]
    keys = [*spec["required"], *spec["optional"]] or [HA_FEATURE_LOW_BAT]
    device = {
        "id": "dev",
        "name": "Device",
        "type": device_type,
        "features": {key: f"sensor.{key}" for key in keys},
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge._build_discover_features(device["features"])[-1] == {
        "type": "maintenance"
    }
    features = bridge.build_discover_devices()[0]["features"]
    assert [f for f in features if f["type"] == "maintenance"] == [
        {"type": "maintenance", "unreach": device_type != "SWITCH_INPUT"}
    ]
    assert features[:-1] == [
        dict(_DISCOVER_FEATURE[key]) for key in keys if key in _DISCOVER_FEATURE
    ]


def test_discover_features_hold_one_maintenance_entry(hass: HomeAssistant) -> None:
    bridge = HaEntityBridge(hass, [], AsyncMock(), PLUGIN_ID)

    assert bridge._build_discover_features({HA_FEATURE_ON_OFF: "switch.pump"}) == [
        {"type": "switchState"},
        {"type": "maintenance"},
    ]
    assert bridge._build_discover_features(
        {
            HA_FEATURE_ON_OFF: "switch.pump",
            HA_FEATURE_LOW_BAT: "binary_sensor.bat",
            HA_FEATURE_UNREACH: "binary_sensor.unreach",
        }
    ) == [{"type": "switchState"}, {"type": "maintenance"}]


@pytest.mark.parametrize(
    ("state", "features"),
    [
        (STATE_ON, [{"type": "switchState", "on": True}, REACHABLE]),
        (STATE_OFF, [{"type": "switchState", "on": False}, REACHABLE]),
        (STATE_UNKNOWN, [REACHABLE]),
        (STATE_UNAVAILABLE, [UNREACHABLE]),
        (None, [UNREACHABLE]),
    ],
)
def test_required_entity_decides_reachability(
    hass: HomeAssistant, state: str | None, features: list[dict[str, Any]]
) -> None:
    """A missing or unavailable required entity makes the device unreachable."""
    if state is not None:
        hass.states.async_set("switch.pump", state)
    bridge = HaEntityBridge(hass, [SWITCH], AsyncMock(), PLUGIN_ID)

    assert bridge.build_status_devices() == [_switch_object(features)]
    assert bridge.build_status_devices(["ha.sw1"]) == [_switch_object(features)]
    assert bridge._build_device_object(SWITCH, include_values=True) == _switch_object(
        features
    )


@pytest.mark.parametrize(
    ("set_point", "temperature", "features"),
    [
        (
            "21.0",
            STATE_UNAVAILABLE,
            [{"type": "setPointTemperature", "setPointTemperature": 21.0}, REACHABLE],
        ),
        (
            STATE_UNAVAILABLE,
            "19.5",
            [{"type": "actualTemperature", "actualTemperature": 19.5}, UNREACHABLE],
        ),
    ],
)
def test_optional_entity_does_not_decide_reachability(
    hass: HomeAssistant,
    set_point: str,
    temperature: str,
    features: list[dict[str, Any]],
) -> None:
    hass.states.async_set("number.set_point", set_point)
    hass.states.async_set("sensor.temp", temperature)
    device = {
        "id": "th1",
        "type": "THERMOSTAT",
        "features": {
            HA_FEATURE_SET_POINT_TEMP: "number.set_point",
            HA_FEATURE_TEMPERATURE: "sensor.temp",
        },
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge._build_value_features(device) == features


def test_any_unavailable_required_entity_makes_unreachable(
    hass: HomeAssistant, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(
        HA_DEVICE_TYPE_FEATURES,
        "SWITCH",
        {"required": [HA_FEATURE_ON_OFF, HA_FEATURE_ON_TIME], "optional": []},
    )
    hass.states.async_set("switch.pump", STATE_ON)
    hass.states.async_set("number.run", STATE_UNAVAILABLE)
    device = {
        "id": "sw1",
        "type": "SWITCH",
        "features": {
            HA_FEATURE_ON_OFF: "switch.pump",
            HA_FEATURE_ON_TIME: "number.run",
        },
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge._build_value_features(device) == [
        {"type": "switchState", "on": True},
        UNREACHABLE,
    ]


@pytest.mark.parametrize(
    ("device_type", "keys"),
    [
        ("CLIMATE_SENSOR", (HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY)),
        ("PARTICULATE_MATTER_SENSOR", (HA_FEATURE_PM25, HA_FEATURE_PM10)),
        ("NOT_A_DEVICE_TYPE", (HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY)),
        (None, (HA_FEATURE_TEMPERATURE, HA_FEATURE_HUMIDITY)),
    ],
)
@pytest.mark.parametrize(
    ("first", "second", "unreach"),
    [
        ("1", "2", False),
        ("1", STATE_UNAVAILABLE, False),
        (STATE_UNAVAILABLE, "2", False),
        (STATE_UNKNOWN, STATE_UNAVAILABLE, False),
        (STATE_UNAVAILABLE, STATE_UNAVAILABLE, True),
        (STATE_UNAVAILABLE, None, True),
        (None, None, True),
    ],
)
def test_device_without_required_entity_is_unreachable_when_all_are(
    hass: HomeAssistant,
    device_type: str | None,
    keys: tuple[str, str],
    first: str | None,
    second: str | None,
    unreach: bool,
) -> None:
    for entity_id, state in (("sensor.first", first), ("sensor.second", second)):
        if state is not None:
            hass.states.async_set(entity_id, state)
    device = {
        "id": "dev",
        "type": device_type,
        "features": {keys[0]: "sensor.first", keys[1]: "sensor.second"},
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge._build_value_features(device)[-1] == {
        "type": "maintenance",
        "unreach": unreach,
    }


@pytest.mark.parametrize(
    ("device_type", "key"),
    [
        ("CONTACT_SENSOR", HA_FEATURE_DOOR),
        ("CONTACT_SENSOR", HA_FEATURE_WINDOW),
        ("OCCUPANCY_SENSOR", HA_FEATURE_MOTION),
        ("CONTACT_SENSOR", HA_FEATURE_CONTACT_SENSOR),
    ],
)
def test_device_saved_with_an_older_feature_key_reports_reachability(
    hass: HomeAssistant, device_type: str, key: str
) -> None:
    device = {"id": "dev", "type": device_type, "features": {key: "binary_sensor.a"}}
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge._build_value_features(device) == [UNREACHABLE]
    hass.states.async_set("binary_sensor.a", STATE_OFF)
    assert bridge._build_value_features(device)[-1] == REACHABLE


def test_device_with_only_maintenance_entities_is_reachable(
    hass: HomeAssistant,
) -> None:
    """Without a functional entity there is nothing that could be unreachable."""
    hass.states.async_set("binary_sensor.bat", STATE_ON)
    device = {
        "id": "btn",
        "type": "SWITCH_INPUT",
        "features": {HA_FEATURE_LOW_BAT: "binary_sensor.bat", HA_FEATURE_ON_OFF: ""},
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge._build_value_features(device) == [
        {"type": "maintenance", "lowBat": True, "unreach": False}
    ]


@pytest.mark.parametrize(
    ("explicit", "entity", "unreach"),
    [
        (STATE_ON, STATE_ON, True),
        (STATE_OFF, STATE_ON, False),
        (STATE_OFF, STATE_UNAVAILABLE, True),
        (STATE_ON, STATE_UNAVAILABLE, True),
        (STATE_UNAVAILABLE, STATE_ON, False),
        (STATE_UNKNOWN, STATE_ON, False),
        (None, STATE_ON, False),
        (STATE_UNAVAILABLE, STATE_UNAVAILABLE, True),
        (None, None, True),
    ],
)
def test_unreach_entity_and_entity_availability_are_combined(
    hass: HomeAssistant, explicit: str | None, entity: str | None, unreach: bool
) -> None:
    """The device is unreachable if the unreach entity or the availability says so."""
    hass.states.async_set("binary_sensor.bat", STATE_ON)
    hass.states.async_set("binary_sensor.tamper", STATE_OFF)
    if explicit is not None:
        hass.states.async_set("binary_sensor.unreach", explicit)
    if entity is not None:
        hass.states.async_set("switch.pump", entity)
    device = {
        "id": "sw1",
        "type": "SWITCH",
        "features": {
            HA_FEATURE_ON_OFF: "switch.pump",
            HA_FEATURE_LOW_BAT: "binary_sensor.bat",
            HA_FEATURE_SABOTAGE: "binary_sensor.tamper",
            HA_FEATURE_UNREACH: "binary_sensor.unreach",
        },
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    maintenance = bridge._build_value_features(device)[-1]

    assert maintenance == {
        "type": "maintenance",
        "lowBat": True,
        "sabotage": False,
        "unreach": unreach,
    }
    assert maintenance["unreach"] is unreach


def test_discover_response_merges_reachability(hass: HomeAssistant) -> None:
    """Discovery keeps a descriptor without value and adds the reachability."""
    hass.states.async_set("binary_sensor.bat", STATE_OFF)
    device = {
        "id": "sw1",
        "name": "Garden Pump",
        "type": "SWITCH",
        "features": {
            HA_FEATURE_ON_OFF: "switch.pump",
            HA_FEATURE_LOW_BAT: "binary_sensor.bat",
        },
    }
    bridge = HaEntityBridge(hass, [device], AsyncMock(), PLUGIN_ID)

    assert bridge.build_discover_devices() == [
        _switch_object(
            [
                {"type": "switchState"},
                {"type": "maintenance", "lowBat": False, "unreach": True},
            ]
        )
    ]
    hass.states.async_set("switch.pump", STATE_ON)
    assert bridge.build_discover_devices() == [
        _switch_object(
            [
                {"type": "switchState", "on": True},
                {"type": "maintenance", "lowBat": False, "unreach": False},
            ]
        )
    ]


async def test_outage_and_recovery_are_pushed_as_status_events(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """The state listener reports unreach true on outage and false on recovery."""
    bridge.build_discover_devices()
    bridge.start_listening()
    await hass.async_block_till_done()
    websocket.send_json.reset_mock()

    hass.states.async_set("switch.pump", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    hass.states.async_remove("switch.pump")
    await hass.async_block_till_done()
    hass.states.async_set("switch.pump", STATE_ON)
    await hass.async_block_till_done()
    bridge.stop_listening()

    assert [(m["type"], m["pluginId"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_EVENT", PLUGIN_ID, {"deviceId": "ha.sw1", "features": [UNREACHABLE]}),
        (
            "STATUS_EVENT",
            PLUGIN_ID,
            {
                "deviceId": "ha.sw1",
                "features": [{"type": "switchState", "on": True}, REACHABLE],
            },
        ),
    ]


async def test_listener_start_reports_changes_it_missed(
    hass: HomeAssistant, api_client: HcuApiClient, websocket: AsyncMock
) -> None:
    """A recovery before the listener runs is pushed when the listener starts."""
    bridge = HaEntityBridge(hass, [SWITCH, SENSOR], api_client._send_message, PLUGIN_ID)
    assert bridge.build_discover_devices() == [
        _switch_object([{"type": "switchState"}, UNREACHABLE]),
        _sensor_object(
            [{"type": "actualTemperature"}, {"type": "humidity"}, UNREACHABLE]
        ),
    ]
    hass.states.async_set("switch.pump", STATE_ON)
    hass.states.async_set("sensor.temp", "21.5")
    hass.states.async_set("sensor.hum", "40")

    bridge.start_listening()
    await hass.async_block_till_done()
    bridge.stop_listening()

    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_EVENT", {"deviceId": "ha.sw1", "features": SWITCH_ON["features"]}),
        ("STATUS_EVENT", {"deviceId": "ha.cs1", "features": SENSOR_OK["features"]}),
    ]


async def test_listener_start_reports_nothing_for_unknown_devices(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """Devices the HCU does not know, or excluded, get no state at listener start."""
    bridge.handle_inclusion_event(["ha.sw1"])
    bridge.handle_exclusion_event(["ha.sw1"])

    bridge.start_listening()
    await hass.async_block_till_done()
    bridge.stop_listening()

    assert _sent(websocket) == []


async def test_status_request_keeps_unreachable_devices(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    hass.states.async_set("switch.pump", STATE_UNAVAILABLE)
    hass.states.async_set("sensor.temp", STATE_UNAVAILABLE)
    hass.states.async_remove("sensor.hum")

    await api_client._handle_status_request({"id": "all", "body": {}})

    assert _sent(websocket) == [
        {
            "id": "all",
            "pluginId": PLUGIN_ID,
            "type": "STATUS_RESPONSE",
            "body": {
                "success": True,
                "devices": [
                    _switch_object([UNREACHABLE]),
                    _sensor_object([UNREACHABLE]),
                ],
            },
        }
    ]


async def test_stop_listening_cancels_pending_catch_up(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """Stopping the listener immediately cancels any pending catch-up task."""
    bridge.build_discover_devices()
    bridge.start_listening()
    catch_up = bridge._catch_up_task
    assert catch_up is not None and not catch_up.done()

    bridge.stop_listening()
    await hass.async_block_till_done()

    assert catch_up.cancelled()
    assert bridge._catch_up_task is None
    assert _sent(websocket) == []


async def test_double_start_listening_cancels_previous_catch_up(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """Re-subscribing cancels an unfinished catch-up task before starting a new one."""
    bridge.build_discover_devices()
    bridge.start_listening()
    first_task = bridge._catch_up_task
    assert first_task is not None and not first_task.done()

    bridge.start_listening()
    second_task = bridge._catch_up_task
    assert second_task is not None and second_task is not first_task

    await hass.async_block_till_done()
    bridge.stop_listening()

    assert first_task.cancelled()
    assert second_task.done() and not second_task.cancelled()
    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_EVENT", {"deviceId": "ha.sw1", "features": SWITCH_ON["features"]}),
        ("STATUS_EVENT", {"deviceId": "ha.cs1", "features": SENSOR_OK["features"]}),
    ]


async def test_send_status_event_rolls_back_cache_on_connection_error(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """A ConnectionError rolls back the throttle cache so retries deliver promptly."""
    bridge.build_discover_devices()
    await bridge.send_status_event(["ha.sw1"])

    hass.states.async_set("switch.pump", STATE_UNAVAILABLE)
    websocket.send_json.side_effect = ConnectionError("socket lost")
    await bridge.send_status_event(["ha.sw1"])
    assert "ha.sw1" not in bridge._last_sent
    assert "ha.sw1" not in bridge._last_sent_features

    websocket.send_json.reset_mock()
    websocket.send_json.side_effect = None
    await bridge.send_status_event(["ha.sw1"])
    assert [(m["type"], m["body"]) for m in _sent(websocket)] == [
        ("STATUS_EVENT", {"deviceId": "ha.sw1", "features": [UNREACHABLE]})
    ]


async def test_send_status_event_connection_error_does_not_clobber_newer_state(
    hass: HomeAssistant,
    api_client: HcuApiClient,
    websocket: AsyncMock,
    bridge: HaEntityBridge,
) -> None:
    """A failed send must not erase a newer state recorded while it was awaiting."""
    bridge.build_discover_devices()
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    delivered: list[dict[str, Any]] = []

    async def _send_side_effect(payload: dict[str, Any]) -> None:
        if payload["body"]["features"][0]["on"] is True:
            first_started.set()
            await release_first.wait()
            raise ConnectionError("stale socket failed")
        delivered.append(payload)

    websocket.send_json.side_effect = _send_side_effect
    first_task = asyncio.create_task(bridge.send_status_event(["ha.sw1"]))
    await first_started.wait()

    hass.states.async_set("switch.pump", STATE_OFF)
    await bridge.send_status_event(["ha.sw1"])
    release_first.set()
    await first_task

    expected_features = [{"type": "switchState", "on": False}, REACHABLE]
    assert bridge._last_sent_features["ha.sw1"] == expected_features
    assert "ha.sw1" in bridge._last_sent
    await bridge.send_status_event(["ha.sw1"])
    assert [(m["type"], m["body"]) for m in delivered] == [
        ("STATUS_EVENT", {"deviceId": "ha.sw1", "features": expected_features}),
    ]
