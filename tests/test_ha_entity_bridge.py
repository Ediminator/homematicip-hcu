"""Tests for HaEntityBridge (Task T3)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from custom_components.hcu_integration.const import (
    HA_DEVICE_TYPE_LIGHT,
    HA_DEVICE_TYPE_SWITCH,
    HA_FEATURE_BRIGHTNESS,
    HA_FEATURE_COLOR_TEMP,
    HA_FEATURE_ON_OFF,
    HA_FEATURE_ON_TIME,
     PLUGIN_ID,
)
from custom_components.hcu_integration.ha_entity_bridge import (
    HaEntityBridge,
    _feature_value,
)


def _make_state(state_str: str, attributes: dict | None = None) -> MagicMock:
    st = MagicMock()
    st.state = state_str
    st.attributes = attributes or {}
    return st


async def test_start_listening_uses_async_track_state_change_event(
    hass: HomeAssistant,
) -> None:
    """Test that start_listening subscribes via async_track_state_change_event instead of global bus."""
    ha_devices = [
        {
            "id": "dev1",
            "name": "Kitchen Switch",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.kitchen"},
        }
    ]
    send_fn = AsyncMock()
    bridge = HaEntityBridge(hass, ha_devices, send_fn, PLUGIN_ID)

    unsub_mock = MagicMock()
    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.async_track_state_change_event",
        return_value=unsub_mock,
    ) as track_mock:
        bridge.start_listening()
        track_mock.assert_called_once()
        args = track_mock.call_args[0]
        assert args[0] is hass
        assert list(args[1]) == ["switch.kitchen"]
        assert callable(args[2])

    bridge.stop_listening()
    unsub_mock.assert_called_once()


async def test_color_temp_kelvin_feature_value_and_control(
    hass: HomeAssistant,
) -> None:
    """Test that colorTemperature uses color_temp_kelvin (with mired fallback) and sends color_temp_kelvin."""
    # 1. Modern HA state with color_temp_kelvin
    state_kelvin = _make_state(STATE_ON, {"color_temp_kelvin": 4000})
    assert _feature_value(HA_FEATURE_COLOR_TEMP, state_kelvin) == {
        "type": "colorTemperature",
        "colorTemperature": 4000,
    }

    # 2. Legacy HA state with mireds only (250 mireds == 4000K)
    state_mireds = _make_state(STATE_ON, {"color_temp": 250})
    assert _feature_value(HA_FEATURE_COLOR_TEMP, state_mireds) == {
        "type": "colorTemperature",
        "colorTemperature": 4000,
    }

    # 3. Control request passes color_temp_kelvin to light.turn_on
    ha_devices = [
        {
            "id": "light1",
            "name": "Desk Lamp",
            "type": HA_DEVICE_TYPE_LIGHT,
            "features": {
                HA_FEATURE_ON_OFF: "light.desk",
                HA_FEATURE_COLOR_TEMP: "light.desk",
            },
        }
    ]
    hass.services.async_call = AsyncMock()
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    await bridge.handle_control_request(
        {
            "deviceId": "ha.light1",
            "features": [{"type": "colorTemperature", "colorTemperature": 3200}],
        }
    )

    hass.services.async_call.assert_awaited_once_with(
        "light",
        "turn_on",
        {"entity_id": "light.desk", "color_temp_kelvin": 3200},
        blocking=True,
    )


async def test_on_time_and_off_light_features_included_in_discover_response(
    hass: HomeAssistant,
) -> None:
    """Test that HA_FEATURE_ON_TIME and features of an off light are advertised in DISCOVER_RESPONSE."""
    ha_devices = [
        {
            "id": "sw1",
            "name": "Porch Light",
            "type": HA_DEVICE_TYPE_LIGHT,
            "features": {
                HA_FEATURE_ON_OFF: "light.porch",
                HA_FEATURE_BRIGHTNESS: "light.porch",
                HA_FEATURE_ON_TIME: "number.porch_on_time",
            },
        }
    ]
    states = {
        "light.porch": _make_state(STATE_OFF),
        "number.porch_on_time": _make_state("30"),
    }
    hass.states.get = MagicMock(side_effect=lambda eid: states.get(eid))

    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)
    discovered = bridge.build_discover_devices()

    assert len(discovered) == 1
    feature_types = {f["type"] for f in discovered[0]["features"]}
    assert "switchState" in feature_types
    assert "dimming" in feature_types
    assert "onTime" in feature_types


async def test_auto_off_timer_cancelled_on_retrigger_turn_off_and_stop_listening(
    hass: HomeAssistant,
) -> None:
    """Test that active onTime auto-off timers are tracked and cancelled on retrigger, turn_off, or stop_listening."""
    ha_devices = [
        {
            "id": "sw1",
            "name": "Garden Pump",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.pump"},
        }
    ]
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock(
        side_effect=lambda coro, name=None: asyncio.create_task(coro, name=name)
    )

    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    # 1. Turn on with onTime=60 -> schedules first timer task
    await bridge.handle_control_request(
        {
            "deviceId": "ha.sw1",
            "features": [{"type": "switchState", "on": True, "onTime": 60}],
        }
    )
    first_task = bridge._auto_off_tasks.get("switch.pump")
    assert first_task is not None
    assert not first_task.done()

    # 2. Re-trigger turn_on with onTime=120 -> cancels first_task and replaces it
    await bridge.handle_control_request(
        {
            "deviceId": "ha.sw1",
            "features": [{"type": "switchState", "on": True, "onTime": 120}],
        }
    )
    await asyncio.sleep(0)
    assert first_task.cancelled() or first_task.done()
    second_task = bridge._auto_off_tasks.get("switch.pump")
    assert second_task is not None
    assert second_task is not first_task
    assert not second_task.done()

    # 3. Turn off manually -> cancels second_task
    await bridge.handle_control_request(
        {
            "deviceId": "ha.sw1",
            "features": [{"type": "switchState", "on": False}],
        }
    )
    await asyncio.sleep(0)
    assert second_task.cancelled() or second_task.done()
    assert "switch.pump" not in bridge._auto_off_tasks

    # 4. Turn on again and call stop_listening() -> cancels third_task
    await bridge.handle_control_request(
        {
            "deviceId": "ha.sw1",
            "features": [{"type": "switchState", "on": True, "onTime": 60}],
        }
    )
    third_task = bridge._auto_off_tasks.get("switch.pump")
    assert third_task is not None
    bridge.stop_listening()
    await asyncio.sleep(0)
    assert third_task.cancelled() or third_task.done()
    assert len(bridge._auto_off_tasks) == 0


async def test_auto_off_timer_cancelled_when_entity_turned_off_outside_hcu(
    hass: HomeAssistant,
) -> None:
    """Turning the entity off in HA (not via the HCU) must end a pending auto-off.

    Otherwise a later manual turn-on would be cut short by the old timer.
    """
    ha_devices = [
        {
            "id": "sw1",
            "name": "Garden Pump",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.pump"},
        }
    ]
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock(
        side_effect=lambda coro, name=None: asyncio.create_task(coro, name=name)
    )
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)

    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.async_track_state_change_event",
        return_value=MagicMock(),
    ) as track_mock:
        bridge.start_listening()
        on_state_changed = track_mock.call_args[0][2]

    bridge.send_status_event = AsyncMock()  # type: ignore[method-assign]

    # HCU turns the pump on for 60 s -> timer scheduled.
    await bridge.handle_control_request(
        {
            "deviceId": "ha.sw1",
            "features": [{"type": "switchState", "on": True, "onTime": 60}],
        }
    )
    timer = bridge._auto_off_tasks.get("switch.pump")
    assert timer is not None and not timer.done()

    # Unrelated "on" state update must not cancel the timer.
    on_state_changed(
        MagicMock(data={"entity_id": "switch.pump", "new_state": _make_state(STATE_ON)})
    )
    assert bridge._auto_off_tasks.get("switch.pump") is timer

    # User turns the pump off in Home Assistant -> timer cancelled.
    on_state_changed(
        MagicMock(data={"entity_id": "switch.pump", "new_state": _make_state(STATE_OFF)})
    )
    await asyncio.sleep(0)
    assert timer.cancelled() or timer.done()
    assert "switch.pump" not in bridge._auto_off_tasks
    hass.services.async_call.assert_awaited_once()  # only the HCU turn_on, no auto-off

    bridge.stop_listening()


async def test_auto_off_elapsed_turn_off_is_not_cancelled_by_its_own_off_state(
    hass: HomeAssistant,
) -> None:
    """When the timer fires, the resulting off state must not cancel the turn_off call."""
    ha_devices = [
        {
            "id": "sw1",
            "name": "Garden Pump",
            "type": HA_DEVICE_TYPE_SWITCH,
            "features": {HA_FEATURE_ON_OFF: "switch.pump"},
        }
    ]
    bridge = HaEntityBridge(hass, ha_devices, AsyncMock(), PLUGIN_ID)
    with patch(
        "custom_components.hcu_integration.ha_entity_bridge.async_track_state_change_event",
        return_value=MagicMock(),
    ) as track_mock:
        bridge.start_listening()
        on_state_changed = track_mock.call_args[0][2]
    bridge.send_status_event = AsyncMock()  # type: ignore[method-assign]

    async def _turn_off_and_report(domain, service, data, blocking=False):
        # Simulate HA reporting the new off state while the service call runs.
        on_state_changed(
            MagicMock(data={"entity_id": "switch.pump", "new_state": _make_state(STATE_OFF)})
        )

    hass.services.async_call = AsyncMock(side_effect=_turn_off_and_report)
    hass.async_create_task = MagicMock(
        side_effect=lambda coro, name=None: asyncio.create_task(coro, name=name)
    )

    task = asyncio.create_task(bridge._auto_off_after("switch.pump", "switch", 0))
    bridge._auto_off_tasks["switch.pump"] = task
    await task

    assert not task.cancelled()
    hass.services.async_call.assert_awaited_once_with(
        "switch", "turn_off", {"entity_id": "switch.pump"}, blocking=True
    )
    assert "switch.pump" not in bridge._auto_off_tasks
    bridge.stop_listening()
