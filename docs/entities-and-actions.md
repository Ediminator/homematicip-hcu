# Entities and Actions

This document describes the Home Assistant platforms provided by the integration, their capabilities, and the full action (service) reference.

## Supported Platforms

### Climate (`climate`)
Created for room heating groups (`HEATING`).
- **HVAC Modes**:
  - `auto`: Follows the active heating profile schedule configured on the HCU.
  - `heat`: Manual heating mode (or active when the setpoint is above minimum).
  - `cool`: Manual cooling mode (available when whole-home cooling mode is enabled on the HCU).
  - `off`: Switched off (setpoint at minimum, or when whole-home cooling is active but cooling is blocked or ignored for this room group).
- **Target Temperature**: Configurable setpoint between 5.0 °C and 30.0 °C.
- **Preset Modes**:
  - **Heating Profiles**: Dynamically populated from active profiles on the HCU group (for example `Standard`, `Profile 1`, `Profile 2`, `Profile 3`). Selecting a profile switches the active schedule on the HCU.
  - **Special Presets**: `boost` (activates valve boost mode), `party` (activates party temperature mode), and `eco` (displayed when whole-home eco or absence mode is active).
- **Attributes**: `current_temperature`, `window_state` (`OPEN` when an assigned window sensor detects an open window).

### Cover (`cover`)
Created for shutters, Venetian blinds, and garage door modules.
- **Roller Shutters**: Position control (0% closed to 100% open), open, close, and stop.
- **Venetian Blinds**: Position control, slat tilt angle (`slatsLevel`), and secondary shading level (`secondaryShadingLevel`).
- **Garage Doors**: Open, close, stop, and partial opening (ventilation position).

### Light (`light`)
Created for dimmers, color controllers, notification indicators, and switches configured with light visualization.
- **Dimming**: Brightness level from 1 to 255.
- **Color Temperature**: Warm white to cold white in Kelvin.
- **Color Modes**: HS and RGB color modes for LED controllers (such as HmIP-RGBW).
- **Notification Lights**: Supports simple color states (`RED`, `GREEN`, `BLUE`, `YELLOW`, `PURPLE`, `CYAN`, `WHITE`) and visual flashing effects.
- **Companion Ramp Time**: Dimmer channels provide a `number` entity to configure default fade durations.

### Switch (`switch`)
Created for relay actuators, smart plugs, wired bus outputs, and switching groups.
- Standard `turn_on`, `turn_off`, and `toggle` controls.
- **Companion Internal On Time**: Channels with an on-time configured in the Homematic IP app provide a `switch` entity (`Use Internal On Time`). Enabling this switch passes the preset duration with every `turn_on` command.

### Lock (`lock`)
Created for smart door locks (such as HmIP-DLD).
- **Commands**: `lock`, `unlock`, and `open` (unlatches the door).
- **PIN Protection**: If your lock requires an authorization PIN, enter it in Home Assistant on the lock device page using the companion **Access Authorisation PIN** text entity. The integration stores this PIN per device.

### Siren (`siren`)
Siren entities are currently not created. They were removed in 2.1.0 because they repeated the device name ([#380](https://github.com/Ediminator/homematicip-hcu/issues/380)); siren support is being reworked in [#447](https://github.com/Ediminator/homematicip-hcu/issues/447). Use the alarm control panel, the alarm binary sensors and the acoustic/optical signal selects of the alarm group instead.

### Valve (`valve`)
Created for garden watering channels and irrigation valves.
- Supports open and close controls with flow rate and volume monitoring.

### Binary Sensor (`binary_sensor`)
Created for discrete states:
- **Doors and Windows**: Device classes `door` and `window`.
- **Motion and Presence**: Device classes `motion` and `occupancy`.
- **Safety and Environmental**: Device classes `smoke`, `moisture` (water leaks, rain), `safety` (storm), `heat` (overheating).
- **Hardware Status**: Device classes `battery` (low battery), `connectivity` (unreach), `tamper` (sabotage), `problem` (mains failure).
- **Security System**: Intrusion alarm active (`binary_sensor.<hcu>_intrusion_alarm`), safety alarm active (`binary_sensor.<hcu>_safety_alarm`), vacation mode active (`binary_sensor.<hcu>_vacation_mode`).

### Sensor (`sensor`)
Created for numeric values and diagnostic metrics:
- **Climate and Weather**: Temperature, humidity, air pressure, wind speed, wind direction, rain totals, sunshine duration.
- **Air Quality**: CO2 concentration, PM1, PM2.5, PM10, AQI.
- **Energy and Power**: Active power (W), accumulated energy consumption (kWh), solar generation (kWh), gas volume (m3).
- **Water**: Flow rate (L/min), volume (L).
- **Hardware Diagnostics**: Duty cycle (%), carrier sense radio traffic (%), signal strength (RSSI in dBm), passage height, distance.

### Event (`event`)
Created for stateless button transmitters and wall remotes:
- **Wall Switches and Remotes**: Event types `press_short`, `press_long`, `press_long_start` and `press_long_stop`.
- **Doorbell Inputs**: Event type `ring`.

### Update (`update`)
Created for the HCU central unit and connected Homematic IP devices:
- Displays installed firmware version and notifies you when new firmware is available.

### Button (`button`)
Created for one-shot commands:
- **Identify Device**: Flashes device status LEDs.
- **Door Operations**: Unlatch door, send momentary impulse.
- **Acknowledge Safety Alarm**: Silences active smoke or water alarms without disarming intrusion protection.
- **Counter Resets**: Reset accumulated energy or water volume counters.

### Select (`select`)
Configuration choices:
- **Power-up Switch State**: Relay behavior after power loss (`OFF`, `ON`, `LAST_VALUE`).
- **Alarm Signals**: Acoustic tone selection and optical signal selection on alarm switching groups.

### Number (`number`)
Numeric settings:
- **Ramp Time**: Configures default transition time (0.1 to 16383 seconds) for dimming channels.

### Text (`text`)
Configuration fields:
- **Device PIN**: Configures device-specific authorization PIN for door locks and latches.

---

## Action Reference

The integration provides 11 actions (services) under the `hcu_integration` domain. Every action and parameter is verified against `services.yaml`.

### `hcu_integration.play_sound`
Plays a sound file on a compatible device such as the HmIP-MP3P. Target the device's `light` (or `switch`) entity; siren entities are not supported.

- **Targets**: Entities in domain `switch` or `light`.
- **Fields**:
  - `sound_file` (*Required*, string): Identifier or file name of the sound (for example `"SOUND_01"`, `"ALARM_01"`).
  - `volume` (*Optional*, float, default: `1.0`): Volume level from `0.0` to `1.0`.
  - `duration` (*Optional*, float, default: `5.0`): Playback duration in seconds (0.1 to 16383 s).

```yaml
action: hcu_integration.play_sound
target:
  entity_id: switch.doorbell
data:
  sound_file: "SOUND_01"
  volume: 0.8
  duration: 4.5
```

### `hcu_integration.set_rule_state`
Enables or disables an automation rule inside the HCU.

- **Targets**: None.
- **Fields**:
  - `rule_id` (*Required*, string): The unique identifier of the rule in the HCU.
  - `enabled` (*Required*, boolean): Set to `true` to enable, or `false` to disable.

```yaml
action: hcu_integration.set_rule_state
data:
  rule_id: "00000000-0000-0000-0000-000000000000"
  enabled: true
```

### `hcu_integration.activate_party_mode`
Activates party mode for a specific heating group with a custom setpoint temperature.

- **Targets**: Entities in domain `climate`.
- **Fields**:
  - `temperature` (*Required*, float): Target temperature (5.0 °C to 30.0 °C, step 0.5 °C).
  - `end_time` (string): End date and time, for example `'2026-12-24 23:00'`. Any format Home Assistant can parse works, as does the HCU format `'2026_12_24 23:00'`. Required unless `duration` is given.
  - `duration` (integer): Duration in seconds (minimum 60 s). Required unless `end_time` is given.
  - Give exactly one of `end_time` and `duration`; a call with neither is rejected.

```yaml
action: hcu_integration.activate_party_mode
target:
  entity_id: climate.living_room
data:
  temperature: 21.5
  end_time: "2026-12-31 23:00"
```

### `hcu_integration.activate_vacation_mode`
Activates system-wide vacation mode for all heating groups until a specified date and time.

- **Targets**: None.
- **Fields**:
  - `temperature` (*Required*, float): Target setback temperature (5.0 °C to 30.0 °C, step 0.5 °C).
  - `end_time` (*Required*, string): End date and time, for example `'2026-12-24 23:00'`. Any format Home Assistant can parse works, as does the HCU format `'2026_12_24 23:00'`. A time with an offset is converted to Home Assistant's time zone.

```yaml
action: hcu_integration.activate_vacation_mode
data:
  temperature: 16.0
  end_time: "2026-12-24 18:00"
```

### `hcu_integration.activate_eco_mode`
Activates system-wide permanent absence (Eco) mode for all heating groups.

- **Targets**: None.
- **Fields**: None.

```yaml
action: hcu_integration.activate_eco_mode
```

### `hcu_integration.deactivate_absence_mode`
Deactivates any active absence mode (Vacation mode or Eco mode) and restores standard heating schedules.

- **Targets**: None.
- **Fields**: None.

```yaml
action: hcu_integration.deactivate_absence_mode
```

### `hcu_integration.switch_on_with_time`
Turns on a switch actuator for a specific duration in seconds. The actuator turns off automatically when the timer expires.

- **Targets**: Entities in domain `switch`.
- **Fields**:
  - `on_time` (*Required*, float): On duration in seconds (0.1 to 16383 s).

```yaml
action: hcu_integration.switch_on_with_time
target:
  entity_id: switch.garden_irrigation_valve
data:
  on_time: 120.0
```

### `hcu_integration.set_cooling_mode`
Enables or disables system-wide cooling mode for all heating groups.

- **Targets**: None.
- **Fields**:
  - `cooling` (*Required*, boolean): Set to `true` to activate cooling mode, or `false` to deactivate.

```yaml
action: hcu_integration.set_cooling_mode
data:
  cooling: true
```

### `hcu_integration.send_api_command`
Sends a raw command to the HCU Connect API. Useful for specialized device features documented in eQ-3 API specifications.

- **Targets**: None.
- **Fields**:
  - `path` (*Required*, string): API endpoint path (for example `'/hmip/device/control/setOpticalSignal'`).
  - `body` (*Required*, object): JSON payload dictionary matching the endpoint requirements.

```yaml
action: hcu_integration.send_api_command
data:
  path: "/hmip/device/control/setOpticalSignal"
  body:
    deviceId: "3014F711A00023E0C9A5E9356"
    channelIndex: 8
    opticalSignalBehaviour: "FLASH_MIDDLE"
    simpleRGBColorState: "PURPLE"
    dimLevel: 0.42
```

### `hcu_integration.create_user_message_request`
Creates an interactive notification message displayed in the Homematic IP smartphone app.

- **Targets**: None.
- **Fields**:
  - `message_category` (*Required*, string): Category: `INFO`, `WARN`, or `ERROR`.
  - `user_message_id` (*Required*, string): Unique identifier for this message.
  - `title` (*Required*, string or object): Notification title text, or dictionary with language keys (for example `{"en": "Title", "de": "Titel"}`).
  - `message` (*Required*, string or object): Notification body text, or dictionary with language keys.
  - `behavior_type` (*Required*, string): Dismissal behavior:
    - `ACKNOWLEDGEABLE_BY_OK`
    - `ACKNOWLEDGEABLE_BY_YES_NO`
    - `DISMISSIBLE`
    - `NOT_DISMISSIBLE`

```yaml
action: hcu_integration.create_user_message_request
data:
  message_category: "INFO"
  user_message_id: "WASHER_FINISHED"
  title: "Washing Machine"
  message: "The laundry cycle has finished."
  behavior_type: "ACKNOWLEDGEABLE_BY_OK"
```

### `hcu_integration.delete_user_message_request`
Removes a previously published user message from the Homematic IP app.

- **Targets**: None.
- **Fields**:
  - `user_message_id` (*Required*, string): The unique identifier used when creating the message.

```yaml
action: hcu_integration.delete_user_message_request
data:
  user_message_id: "WASHER_FINISHED"
```
