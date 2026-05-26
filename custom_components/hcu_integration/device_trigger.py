# custom_components/hcu_integration/device_trigger.py
"""Device triggers for Homematic IP HCU button and doorbell event entities."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

import logging
_LOGGER = logging.getLogger(__name__)

from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
from homeassistant.components.event import DOMAIN as EVENT_DOMAIN
from homeassistant.components.homeassistant.triggers import event as event_trigger


from .const import DOMAIN, EVENT_TYPES

# Button event trigger types — match HcuButtonEvent._attr_event_types

TRIGGER_TYPES_BUTTON = frozenset({
    "press_short",
    "press_long",
    "press_long_start",
    "press_long_stop"
})

# Doorbell event trigger types — match HcuDoorbellEvent._attr_event_types

TRIGGER_TYPES_DOORBELL = frozenset({"ring"})

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES_BUTTON | TRIGGER_TYPES_DOORBELL),
        vol.Required("subtype"): str,
    }
)

def _get_channel_subtype(unique_id: str) -> str:
    base = unique_id.replace("_button_event", "").replace("_doorbell_event", "")
    channel_idx = base.split("_")[-1]
    return channel_idx

async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return a list of triggers for the given device."""
    entity_reg = er.async_get(hass)
    triggers = []

    for entry in er.async_entries_for_device(entity_reg, device_id):
        if entry.domain != EVENT_DOMAIN or entry.platform != DOMAIN:
            continue

        # Determine trigger types based on entity unique_id suffix
        if entry.unique_id and entry.unique_id.endswith("_button_event"):
            trigger_types = TRIGGER_TYPES_BUTTON
        elif entry.unique_id and entry.unique_id.endswith("_doorbell_event"):
            trigger_types = TRIGGER_TYPES_DOORBELL
        else:
            continue

        subtype = _get_channel_subtype(entry.unique_id)

        for trigger_type in sorted(trigger_types):
            triggers.append(
                {
                    CONF_PLATFORM: "device",
                    CONF_DOMAIN: DOMAIN,
                    CONF_DEVICE_ID: device_id,
                    CONF_TYPE: trigger_type,
                    "subtype": subtype,
                }
            )

    return triggers

async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger to a device event on the event bus."""
    # The bus event uses the HCU device SGTIN as device_id, not the HA device registry UUID.
    # Look up the HCU identifier from the device registry entry.
    device_reg = dr.async_get(hass)
    hcu_device_id = None
    if device := device_reg.async_get(config[CONF_DEVICE_ID]):
        hcu_device_id = next(
            (id_val for domain_name, id_val in device.identifiers if domain_name == DOMAIN),
            None,
        )

    if not hcu_device_id:
        _LOGGER.error(
            "Cannot attach trigger: HCU device ID not found for HA device %s",
            config[CONF_DEVICE_ID],
        )
        return lambda: None

    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            event_trigger.CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_event",
            event_trigger.CONF_EVENT_DATA: {
                CONF_DEVICE_ID: hcu_device_id,
                CONF_TYPE: config[CONF_TYPE],
                "subtype": config["subtype"],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )

    
async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """Return capabilities of a trigger — no extra fields needed."""
    return {}
