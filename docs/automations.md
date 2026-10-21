# Automation Examples

This guide provides practical automation examples for your Homematic IP devices, including buttons, heating schedules, chimes, alarms, notifications, and timed switches.

---

## 1. Working with Buttons and Remotes

Homematic IP buttons, wall remotes, and key ring remotes are stateless transmitters. Instead of maintaining static on/off state entities, they fire momentary event notifications when pressed.

### Pre-requisite: Enable Button Events in the HCU

By default, the HCU firmware only routes button press events over the local API if the button is assigned to an action inside the HCU.

To enable events for a button:
1. Open the **Homematic IP app**.
2. Go to **Automations** and create a new automation.
3. Set your button channel as the **Trigger** (choose short and long press if available).
4. For the **Action**, select a dummy action (such as toggling an unused notification light, or sending an empty notification).
5. Save the automation.

The HCU will now forward events for this button to Home Assistant over the WebSocket connection.

### Testing Button Events

Before writing automations, test your button in Home Assistant:
1. Open **Developer Tools → Events**.
2. In **Listen to events**, enter `hcu_integration_event` and select **Start Listening**.
3. Press a button on your physical remote or wall switch.
4. An event appears in the listener:

```yaml
event_type: hcu_integration_event
data:
  device_id: "3014F711A00048240995D6BC"
  subtype: "1"
  type: "press_short"
```

- `device_id`: The 24-character SGTIN of your device.
- `subtype`: The physical button channel index (for example `"1"` for top button, `"2"` for bottom button).
- `type`: The event type. Buttons send `press_short`, `press_long`, `press_long_start` and `press_long_stop`; a few devices only send a plain `press`; doorbells send `ring`. If your button shows `press` in the event listener, use that value in the examples below, or match both as Example 2 does.

---

### Button Automation Methods

#### Method 0: Device Triggers (Visual Editor)
If you prefer building automations in the Home Assistant user interface:
1. Go to **Settings → Automations & scenes → Create automation**.
2. Select **Add trigger → Device**.
3. Choose your Homematic IP button device.
4. Select the trigger (for example, `"Button 1" was pressed short`).
5. Add your desired actions.

#### Method 1: Event Triggers (Visual Editor)
1. Add a trigger and choose **Event**.
2. Set **Event type** to `hcu_integration_event`.
3. In **Event data**, specify your device and channel:

```yaml
device_id: "3014F711A00048240995D6BC"
subtype: "1"
type: "press_short"
```

#### Method 2: YAML Examples

##### Example 1: Toggle a light with a wall switch button
```yaml
alias: "Living Room: Toggle Light with Wall Switch"
description: "Toggle living room ceiling light when pressing button 1"
triggers:
  - trigger: event
    event_type: hcu_integration_event
    event_data:
      device_id: "3014F711A00048240995D6BC"
      subtype: "1"
      type: "press_short"
actions:
  - action: light.toggle
    target:
      entity_id: light.living_room_ceiling
```

##### Example 2: 4-Button remote controlling different rooms
```yaml
alias: "Key Ring Remote: 4 Buttons"
description: "Control four lights with a 4-button remote control"
mode: queued
triggers:
  - trigger: event
    event_type: hcu_integration_event
    event_data:
      device_id: "3014F711A00048240995D6BC"
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.subtype == '1' and trigger.event.data.type in ('press', 'press_short') }}"
        sequence:
          - action: light.toggle
            target:
              entity_id: light.kitchen_ceiling
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.subtype == '2' and trigger.event.data.type in ('press', 'press_short') }}"
        sequence:
          - action: light.toggle
            target:
              entity_id: light.dining_table
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.subtype == '3' and trigger.event.data.type in ('press', 'press_short') }}"
        sequence:
          - action: light.turn_off
            target:
              entity_id: all
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.subtype == '4' and trigger.event.data.type in ('press', 'press_short') }}"
        sequence:
          - action: cover.close_cover
            target:
              entity_id: cover.all_shutters
```

##### Example 3: Short press vs long press
```yaml
alias: "Bedroom: Short vs Long Press"
description: "Short press turns the light to 30%, long press to 100%"
mode: restart
triggers:
  - trigger: event
    event_type: hcu_integration_event
    event_data:
      device_id: "3014F711A00048240995D6BC"
      subtype: "1"
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.type in ('press', 'press_short') }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.bedroom_lamp
            data:
              brightness_pct: 30
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.type == 'press_long' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.bedroom_lamp
            data:
              brightness_pct: 100
```

---

## 2. Heating Automations

### Vacation Mode on Extended Departure
Activate whole-home setback temperature when leaving for an extended trip:

```yaml
alias: "Climate: Activate Vacation Mode on Extended Absence"
description: "Sets setback temperature until returning home"
triggers:
  - trigger: state
    entity_id: input_boolean.extended_vacation
    to: "on"
actions:
  - action: hcu_integration.activate_vacation_mode
    data:
      temperature: 15.0
      end_time: "2026-12-28 18:00"
```

### Return Home: Deactivate Absence Mode
Restore normal heating schedules when arriving back:

```yaml
alias: "Climate: Return Home"
description: "Restores standard heating schedules upon arrival"
triggers:
  - trigger: state
    entity_id: person.homeowner
    to: "home"
actions:
  - action: hcu_integration.deactivate_absence_mode
```

### Party Mode for a Specific Room
Temporarily boost temperature in a specific room without affecting other zones:

```yaml
alias: "Climate: Living Room Party Mode"
description: "Warms living room for 4 hours during a gathering"
triggers:
  - trigger: state
    entity_id: input_boolean.host_party
    to: "on"
actions:
  - action: hcu_integration.activate_party_mode
    target:
      entity_id: climate.living_room
    data:
      temperature: 22.0
      duration: 14400
```

---

## 3. Chime and Doorbell Sound

Play a chime or alarm tone on an HmIP-MP3P combination actor when the doorbell rings:

```yaml
alias: "Doorbell: Play Chime on Ring"
description: "Plays sound file when doorbell button is pressed"
triggers:
  - trigger: state
    entity_id: event.front_door_doorbell
    to: ~
actions:
  - action: hcu_integration.play_sound
    target:
      entity_id: light.hallway_doorbell_chime
    data:
      sound_file: "SOUNDFILE_001"
      volume: 0.8
      duration: 5.0
```

---

## 4. Alarm System Automations

The integration exposes dedicated binary sensors for intrusion and safety alarms, allowing you to react appropriately to each alert type.

### Reacting to Danger and Safety Alarms
Water leaks and smoke detector triggers fire the safety alarm. You can broadcast a voice alert without triggering security sirens:

```yaml
alias: "Safety: Announce Water Leak"
description: "Sends notifications when a water sensor or smoke alarm triggers"
triggers:
  - trigger: state
    entity_id: binary_sensor.homematic_ip_hcu_safety_alarm
    to: "on"
actions:
  - action: notify.notify
    data:
      title: "Danger Alarm Detected"
      message: "The HCU safety alarm is active. Check water sensors and smoke detectors immediately."
```

### Silencing a Safety Alarm
Use the acknowledge safety alarm button to silence a false alarm without disarming your intrusion security perimeter:

```yaml
alias: "Safety: Silence False Alarm"
description: "Silences safety alarm when wall switch button is long pressed"
triggers:
  - trigger: event
    event_type: hcu_integration_event
    event_data:
      device_id: "3014F711A00048240995D6BC"
      subtype: "2"
      type: "press_long"
actions:
  - action: button.press
    target:
      entity_id: button.homematic_ip_hcu_acknowledge_safety_alarm
```

---

## 5. Interactive Notifications in the Homematic IP App

You can display actionable messages directly inside the official Homematic IP smartphone app.

### Sending an Interactive Alert
```yaml
alias: "Laundry: Washer Finished Alert"
description: "Shows actionable notification in the Homematic IP app"
triggers:
  - trigger: state
    entity_id: sensor.washing_machine_power
    to: "0"
    for:
      minutes: 2
actions:
  - action: hcu_integration.create_user_message_request
    data:
      message_category: "INFO"
      user_message_id: "LAUNDRY_DONE"
      title: "Laundry Complete"
      message: "The washing machine cycle has finished. Please empty the drum."
      behavior_type: "ACKNOWLEDGEABLE_BY_YES_NO"
```

### Listening for User Acknowledgements
When a family member taps **Yes**, **No**, or **OK** in the Homematic IP app, the integration fires the `hcu_integration_user_message_ack` event.

You can access the event payload values in templates or actions:

```jinja2
{{ trigger.event.data.user_message_id }}
{{ trigger.event.data.ack_type }}
```

```yaml
alias: "Laundry: Acknowledge Notification"
description: "Reacts when user answers the prompt in the Homematic IP app"
triggers:
  - trigger: event
    event_type: hcu_integration_user_message_ack
    event_data:
      user_message_id: "LAUNDRY_DONE"
actions:
  - choose:
      - conditions:
          - condition: template
            value_template: "{{ trigger.event.data.ack_type == 'YES' }}"
        sequence:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.laundry_pending
  - action: hcu_integration.delete_user_message_request
    data:
      user_message_id: "LAUNDRY_DONE"
```

---

## 6. Timed Switching and Ramp Time

### Direct Timed Switching with `switch_on_with_time`
Turn on a garden valve or pump for a fixed period without relying on Home Assistant timers or delays:

```yaml
alias: "Garden: Water Lawn for 15 Minutes"
description: "Turns on lawn sprinkler valve for 900 seconds"
triggers:
  - trigger: time
    at: "06:00:00"
actions:
  - action: hcu_integration.switch_on_with_time
    target:
      entity_id: switch.lawn_sprinkler_valve
    data:
      on_time: 900.0
```

### Using Internal On Time
If you configure an on-time for a channel in the Homematic IP app (e.g. 180 seconds for a staircase light), enable the companion entity `switch.<channel>_use_internal_on_time`.

Any standard call to `switch.turn_on` will automatically pass that duration to the actuator hardware:

```yaml
alias: "Hallway: Motion Triggered Light"
description: "Turns on light; actuator shuts off automatically via internal timer"
triggers:
  - trigger: state
    entity_id: binary_sensor.hallway_motion
    to: "on"
actions:
  - action: switch.turn_on
    target:
      entity_id: switch.hallway_staircase_light
```

### Smooth Dimming with Ramp Time
Set the companion number entity `number.<channel>_ramp_time` to `3.0` seconds. All subsequent calls to `light.turn_on` or `light.turn_off` fade smoothly over 3 seconds without needing a per-call `transition` parameter:

```yaml
alias: "Evening: Relaxing Ambient Lighting"
description: "Fades living room ambient lighting smoothly"
triggers:
  - trigger: sun
    event: sunset
actions:
  - action: light.turn_on
    target:
      entity_id: light.living_room_dimmer
    data:
      brightness_pct: 40
```

---

## 7. Finding Your Device ID and Channels

### Easiest Method: Use Device Info
1. Go to **Settings → Devices & services**.
2. Select the **Homematic IP Local (HCU)** integration card.
3. Find your button device in the list and click it.
4. The device identifier (24-character SGTIN) is displayed in the Device Info card.

### Manual Method: Integration Diagnostics File
1. Download the full integration diagnostics from the integration menu (**⋮ → Download diagnostics**).
2. Open the downloaded JSON file in a text editor and search for your device label.
3. Look for the device structure:

```json
"3014F711A00048240995D6BC": {
  "label": "Living Room Wall Switch",
  "functionalChannels": {
    "0": { "functionalChannelType": "DEVICE_BASE" },
    "1": { "functionalChannelType": "SINGLE_KEY_CHANNEL" },
    "2": { "functionalChannelType": "SINGLE_KEY_CHANNEL" },
    "3": { "functionalChannelType": "SINGLE_KEY_CHANNEL" },
    "4": { "functionalChannelType": "SINGLE_KEY_CHANNEL" }
  }
}
```

- The 24-character string (`3014F711A00048240995D6BC`) is your `device_id`.
- Channels 1, 2, 3, and 4 represent your physical buttons. Channel 0 is the device maintenance channel.
