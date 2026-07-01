# HA Entity Bridge Flow (Alpha)

## Overview

The HA Entity Bridge allows exposing Home Assistant entities to the HCU as virtual plugin devices. The HCU sees them as native devices with typed features (e.g. `switchState`, `actualTemperature`, `maintenance`) and can display, automate, and — for controllable types — switch them.

The feature is configured via **Settings → Integrations → HCU → Configure → Home Assistant Entities → HCU (Alpha)**.

---

## Options Flow Diagram

```mermaid
flowchart TD
    MENU_MAIN(["Options Menu\n(main)"]) -->|"ha_devices"| MENU

    MENU["**HA Entity Bridge Menu**\n─────────────────────────────\nAlways shown:\n  • Add device\nOnly if devices exist:\n  • Edit device\n  • Remove device(s)"]

    MENU -->|"ha_devices_add"| ADD_TYPE
    MENU -->|"ha_devices_edit"| EDIT_SELECT
    MENU -->|"ha_devices_remove"| REMOVE

    ADD_TYPE["**Add — Phase 1: Select Type**\nDropdown of the 19 supported\ndevice types (Light, Switch,\nThermostat, Window Covering, …)"]
    ADD_TYPE -->|Type selected| ADD_FORM

    ADD_FORM["**Add — Phase 2: Configure**\n─────────────────────────────\nRequired: name + the type's\nrequired feature(s)\nOptional: the type's optional\nfeatures + Maintenance\n(low_bat, sabotage, unreach)"]
    ADD_FORM -->|Submit| SAVE

    EDIT_SELECT["**Edit — Phase 1: Select Device**\nDropdown list of existing devices"]
    EDIT_SELECT -->|Device selected| EDIT_FORM

    EDIT_FORM["**Edit — Phase 2: Edit Form**\nPre-populated with existing values\nFields limited to the device's\nstored (or inferred) type"]
    EDIT_FORM -->|Submit| SAVE

    REMOVE["**Remove Device(s)**\nMulti-select list of existing devices"]
    REMOVE -->|Submit| SAVE

    SAVE(["Save options\n→ HaEntityBridge reloaded"])
```

---

## Step Details

### Menu (`ha_devices`)

| Condition | Available actions |
|-----------|-------------------|
| No devices configured | Add |
| ≥ 1 device configured | Add · Edit · Remove |

### Add Device (`ha_devices_add`) — Two-Phase

**Phase 1** — Device-type selector: dropdown with all 19 supported types (see [Supported Device Types and Features](#supported-device-types-and-features)). The choice determines which fields phase 2 shows.

**Phase 2** — Configuration form:

| Field | Type | Description |
|-------|------|-------------|
| `name` | Text | Display name shown on the HCU (required) |
| Required feature field(s) | Entity selector | The type's required feature(s), e.g. `on_off` for `SWITCH`/`LIGHT` |
| Optional feature fields | Entity selector | The type's optional features, plus Maintenance (`low_bat`, `sabotage`, `unreach`), always offered |

On submit: a new device dict `{id, name, type, features}` is appended to `CONF_HA_DEVICES` and options are saved. `type` is the value chosen in phase 1.

### Edit Device (`ha_devices_edit`) — Two-Phase

**Phase 1** — Device selector: dropdown with all configured devices (label = device name).

**Phase 2** — Edit form: identical to Add's phase 2, pre-populated with the existing entity assignments and limited to the fields relevant for the device's type. The `id` and `type` are preserved unchanged. The type itself cannot be changed here — remove and re-add the device to change its type.

On submit: the device in `CONF_HA_DEVICES` is replaced in-place.

### Remove Device(s) (`ha_devices_remove`)

Multi-select list. Multiple devices can be deleted in one step.

On submit: selected `id`s are filtered out of `CONF_HA_DEVICES`.

---

## Device Type Detection

Since 2.1.0 the device type is chosen explicitly in the Add flow and persisted as `type` on the device dict — several types (e.g. `EV_CHARGER` vs. `ENERGY_METER`, both just `power`/`energy`) share identical feature keys and can't be told apart from features alone.

`determine_ha_device_type()` in `const.py` still exists as a **fallback for devices saved before this field existed** (and is used opportunistically once, on first edit, after which the resolved type is persisted too). Its priority order:

```
LIGHT               if brightness / color_temp / rgb_color present
                    OR on_off entity starts with "light."
HEAT_PUMP           if climate_operation_mode present
THERMOSTAT          if set_point_temp present
WINDOW_COVERING     if shutter_level present
ENERGY_METER        if power or energy present
PARTICULATE_MATTER_SENSOR  if pm1 / pm25 / pm10 present
CLIMATE_SENSOR      if temperature / humidity / illuminance / co2 /
                       wind_speed / precipitation / storm / sunshine /
                       raining / wind_direction / sunshine_duration present
OCCUPANCY_SENSOR    if motion or occupancy present
CONTACT_SENSOR      if door or window present
SMOKE_ALARM         if smoke present
WATER_SENSOR        if moisture or moisture_detected present
VEHICLE             if vehicle_range present
BATTERY             if battery present
SWITCH              (fallback)
```

Note `EV_CHARGER`, `GRID_CONNECTION_POINT`, `HVAC`, `INVERTER`, and `SWITCH_INPUT` are intentionally absent from this list — they are only reachable via explicit selection in the Add flow.

---

## HCU Protocol Integration

Once saved, `HaEntityBridge` is active and responds to HCU plugin protocol messages:

### DISCOVER_REQUEST → DISCOVER_RESPONSE

All configured devices, of any of the 19 supported types, are returned as plugin devices with typed feature descriptors — this is currently unverified against real HCU firmware; if a `deviceType` value turns out to be rejected or ignored, restrict `_DISCOVERABLE_DEVICE_TYPES` in `ha_entity_bridge.py` back down.

```json
{
  "deviceId": "ha.<uuid>",
  "friendlyName": "Living Room Light",
  "modelType": "HOME_ASSISTANT",
  "firmwareVersion": "1.0.0",
  "deviceType": "LIGHT",
  "features": [
    {"type": "switchState"},
    {"type": "dimming"},
    {"type": "maintenance"}
  ]
}
```

### STATUS_REQUEST → STATUS_RESPONSE / STATUS_EVENT

Current HA state is read and mapped to HCU feature value objects.

```json
{
  "deviceId": "ha.<uuid>",
  "features": [
    {"type": "switchState", "on": true},
    {"type": "dimming", "dimLevel": 0.75},
    {"type": "maintenance", "lowBat": false, "sabotage": false, "unreach": false}
  ]
}
```

`STATUS_EVENT` is pushed automatically on every HA state change (throttled to one event per 5 seconds per device).

### CONTROL_REQUEST (SWITCH / LIGHT only)

The HCU can turn SWITCH and LIGHT devices on/off. Dimming and color control are also supported for LIGHT devices.

**Optional `onTime` (auto-off timer)**

If an `onTime` entity is configured or the CONTROL_REQUEST itself contains an `onTime` feature, the device is automatically turned off after the specified number of seconds.

Priority: value in CONTROL_REQUEST > value from configured `on_time` entity.

```
turn_on called
  └─ if on_time_secs > 0
       └─ async task: sleep(on_time_secs) → turn_off
```

---

## Maintenance Composite Feature

Three separate HA `binary_sensor` entities combine into a single HCU `maintenance` feature object. All three are optional.

| Config key | HCU field | Meaning |
|---|---|---|
| `low_bat` | `lowBat` | Battery low |
| `sabotage` | `sabotage` | Tamper contact triggered |
| `unreach` | `unreach` | Device unreachable |

In DISCOVER_RESPONSE a single `{"type": "maintenance"}` descriptor is emitted.  
In STATUS_RESPONSE / STATUS_EVENT the combined object is sent only if at least one of the three entities has a valid (non-unavailable) state.

---

## Supported Device Types and Features

| Device type | Required | Optional |
|---|---|---|
| `SWITCH` | `on_off` | `on_time`, Maintenance |
| `LIGHT` | `on_off` | `brightness`, `color_temp`, `rgb_color`, `on_time`, Maintenance |
| `ENERGY_METER` | — | `power`, `energy`, Maintenance |
| `PARTICULATE_MATTER_SENSOR` | — | `pm1`, `pm25`, `pm10`, Maintenance |
| `CLIMATE_SENSOR` | — | `temperature`, `humidity`, `illuminance`, `co2`, `wind_speed`, `precipitation`, `storm`, `sunshine`, `raining`, `wind_direction`, `sunshine_duration`, Maintenance |
| `OCCUPANCY_SENSOR` | `occupancy` | `motion`, Maintenance |
| `CONTACT_SENSOR` | — | `door`, `window`, Maintenance |
| `SMOKE_ALARM` | `smoke` | Maintenance |
| `WATER_SENSOR` | `moisture` | `moisture_detected`, Maintenance |
| `BATTERY` | `battery` | `power`, `energy`, Maintenance |
| `EV_CHARGER` | `power` | `energy`, Maintenance |
| `GRID_CONNECTION_POINT` | `power` | `energy`, Maintenance |
| `HEAT_PUMP` | `climate_operation_mode` | `cooling_temp_offset`, `heating_temp_offset`, `presence_mode`, `hot_water_boost`, `supply_temperature`, Maintenance |
| `HVAC` | `power` | `energy`, Maintenance |
| `INVERTER` | `power` | `energy`, Maintenance |
| `SWITCH_INPUT` | — | Maintenance |
| `THERMOSTAT` | `set_point_temp` | `temperature`, `humidity`, `co2`, Maintenance |
| `VEHICLE` | `battery` | `vehicle_range`, Maintenance |
| `WINDOW_COVERING` | `shutter_level` | `slats_level`, `shutter_direction`, Maintenance |

**Maintenance** = `low_bat` + `sabotage` + `unreach` (all optional `binary_sensor` entities)
