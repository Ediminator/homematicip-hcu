# Supported Devices

This document outlines all supported device categories, channel types, Homematic IP groups, and the Home Assistant entities created for them.

All entity mappings derive directly from the integration source code. Support depends on the channel types a device reports, not on the model name. The models listed under "Hardware examples" are confirmed in this project (issues, tests or diagnostics). Other Homematic IP devices with the same channel types work the same way.

## 1. Heating and Climate Control

The integration integrates heating groups and climate hardware directly. In Homematic IP, individual thermostats are bound to room heating groups. Controllable climate entities represent these groups.

### Heating Groups

| Group Type | Platform | Description |
|---|---|---|
| `HEATING` | `climate` | Room thermostat control with temperature setpoint, target temperature, current temperature, heating profiles, eco/party mode, and window open status. |
| `HEATING_COOLING_DEMAND_BOILER` | `binary_sensor` | Aggregates all valve positions to signal whether the central boiler needs to fire. |
| `HEATING_COOLING_DEMAND_PUMP` | `binary_sensor` | Indicates whether the central heating circulation pump should run. |
| `HOT_WATER` | `switch` | Controls hot water circulation and profiles. Requires a dedicated actuator. |

### Device Channels and Sensors

| Channel Type / Feature | Platform | Entity Name | Description |
|---|---|---|---|
| `actualTemperature` | `sensor` | Temperature | Current ambient temperature (°C, measurement). |
| `valveActualTemperature` | `sensor` | Temperature | Temperature measured at the radiator valve (°C, measurement). |
| `valvePosition` | `sensor` | Valve Position | Current valve opening position in percent (0-100%). |
| `humidity` | `sensor` | Humidity | Relative indoor humidity in percent (0-100%). |
| `vaporAmount` | `sensor` | Absolute Humidity | Absolute humidity in grams per cubic meter (g/m³, disabled by default). |

### Hardware examples
- Radiator thermostats: HmIP-eTRV-2, HmIP-eTRV-E
- Wall thermostats: HmIP-WTH-1, HmIP-BWTH, HmIP-STH, HmIP-STHD
- Floor heating controllers: HmIP-FALMOT-C12
- Multi-IO and switch actuators: HmIP-WHS2

---

## 2. Covers and Blinds

The integration provides complete control for roller shutters, external blinds, Venetian blinds, and awnings.

### Shutter Groups

| Group Type | Platform | Description |
|---|---|---|
| `SHUTTER` | `cover` | Synchronized control for roller shutters in a room. |
| `EXTENDED_LINKED_SHUTTER` | `cover` | Direct connection shutter and blind groups. |

### Actuator Channels

| Channel Type | Platform | Features Supported |
|---|---|---|
| `SHUTTER_CHANNEL` | `cover` | Open, close, stop, and absolute position (0-100%). |
| `BLIND_CHANNEL` | `cover` | Position plus slat tilt angle adjustment (`slatsLevel`). |
| `BRAND_BLIND_CHANNEL` | `cover` | Brand-specific flush-mount blind actuator control. |
| `SHADING_CHANNEL` | `cover` | Shading position and secondary shading levels. |
| `MULTI_MODE_INPUT_BLIND_CHANNEL` | `cover` | Multi-mode DIN-rail and flush-mount blind actuators. |

### Hardware examples
- Roller shutter actuators: HmIP-BROLL, HmIP-FROLL, HmIP-DRBLI4
- Blind actuators: HmIPW-DRBL4

---

## 3. Switches and Lights

The integration discovers switch channels, dimmers, colored lights, and notification indicators.

### Groups

| Group Type | Platform | Description |
|---|---|---|
| `SWITCHING` | `switch` or `light` | User-created switching groups. Automatically exposed as a `light` group if all member actuators are lights. |
| `SWITCHING_PROFILE` | `switch` or `light` | Switching profile groups. |
| `LINKED_SWITCHING` | `switch` or `light` | Direct-linked switching groups. |
| `LIGHT` | `light` | Direct-linked light groups with dimming and color synchronization. |
| `EXTENDED_LINKED_SWITCHING` | `switch` or `light` | Extended switching groups. Also provides a group on-time sensor (`sensor`). |
| `EXTENDED_LINKED_NOTIFICATION` | `light` | Synchronized notification indicator groups. |

### Actuator Channels

| Channel Type | Platform | Companion Entities | Description |
|---|---|---|---|
| `SWITCH_CHANNEL` | `switch` (or `light`) | `HcuConfigUseInternalOnTime` (switch) | Standard relay switch. Automatically mapped to `light` if configured with light visualization in the Homematic IP app. |
| `SWITCH_MEASURING_CHANNEL` | `switch` (or `light`) | `HcuConfigUseInternalOnTime` (switch) | Switch actuator with integrated power and energy metering. |
| `WIRED_SWITCH_CHANNEL` | `switch` | `HcuConfigUseInternalOnTime` (switch) | Wired bus switch actuator. |
| `EXTERNAL_SWITCH_CHANNEL` | `switch` | None | External auxiliary switch. |
| `CONDITIONAL_SWITCH_CHANNEL`| `switch` | None | Conditional switch channel. |
| `MULTI_MODE_INPUT_SWITCH_CHANNEL` | `switch` | `HcuConfigUseInternalOnTime` (switch) | Multi-mode input switch actuator. |
| `OPEN_COLLECTOR_CHANNEL_8` | `switch` | None | Open collector 8-channel module output. |
| `DIMMER_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Dimmer actuator supporting brightness control. |
| `MULTI_MODE_INPUT_DIMMER_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Multi-mode dimmer input channel. |
| `UNIVERSAL_LIGHT_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Universal lighting channel. |
| `NOTIFICATION_LIGHT_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Notification light with color and signal support. |
| `NOTIFICATION_MP3_SOUND_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Combination light and MP3 acoustic signal channel. |
| `OPTICAL_SIGNAL_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Optical signal indicator channel. |
| `RGBW_AUTOMATION_CHANNEL` | `light` | `HcuConfigRampTime` (number) | RGBW LED strip and accent lighting controller. |
| `BACKLIGHT_CHANNEL` | `light` | `HcuConfigRampTime` (number) | Display or device backlighting channel. |

### Config Entities for Switches and Lights
- **Use Internal On Time** (`switch`): Appears on channels with a configured on-time in the Homematic IP app. When enabled, any `turn_on` command automatically turns off after the configured duration without an external timer.
- **Ramp Time** (`number`): Appears on dimming channels. Specifies the transition duration in seconds (0.1-16383 s). A value of 0 disables ramp time.
- **Power-up Switch State** (`select`): Available in App User mode. Configures relay state following a power outage (Permanent Off, Permanent On, Previous State).

### Hardware examples
- Plugs and switches: HmIP-PS, HmIP-PSM, HmIP-PSM-2
- Wall and flush actuators: HmIP-BSM, HmIP-FSI16, HmIP-DRSI1
- Dimmers: HmIP-BDT, HmIP-DRDI3
- Lighting and signals: HmIP-BSL, HmIP-MP3P

---

## 4. Sensors

The integration supports environmental, weather, safety, and diagnostic sensors.

### Doors and Windows

| Role / Channel | Platform | Device Class | Description |
|---|---|---|---|
| `WINDOW_SENSOR` | `binary_sensor` | `window` | Window contact state (on = open, off = closed). |
| `DOOR_SENSOR` | `binary_sensor` | `door` | Door contact state (on = open, off = closed). |
| `ROTARY_HANDLE_CHANNEL` | `sensor` | None | Rotary handle state: `CLOSED`, `TILTED`, or `OPEN`. |
| `SHUTTER_CONTACT_CHANNEL` | `binary_sensor` | `window` | Magnetic or optical contact sensor. |

### Motion, Presence, and Light

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `motionDetected` | `binary_sensor` | `motion` | Motion detection status. |
| `presenceDetected` | `binary_sensor` | `occupancy` | Presence detection status. |
| `illumination` | `sensor` | `illuminance` | Ambient brightness in lux (lx). |
| `currentIllumination` | `sensor` | `illuminance` | Unfiltered current brightness in lux. |
| `averageIllumination` | `sensor` | `illuminance` | Averaged brightness in lux (diagnostic). |
| `illuminationDetected` | `binary_sensor` | `light` | Illumination threshold exceeded flag. |
| `sunshine` | `binary_sensor` | `light` | Active sunshine indicator. |
| `todaySunshineDuration` | `sensor` | `duration` | Sunshine duration today in minutes. |
| `totalSunshineDuration` | `sensor` | `duration` | Total accumulated sunshine duration in minutes. |
| `yesterdaySunshineDuration` | `sensor` | `duration` | Sunshine duration yesterday in minutes. |

### Weather and Environment

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `airPressure` | `sensor` | `atmospheric_pressure` | Barometric air pressure in hectopascals (hPa). |
| `raining` | `binary_sensor` | `moisture` | Active precipitation flag. |
| `todayRainCounter` | `sensor` | `precipitation` | Rain volume today in millimeters (mm). |
| `totalRainCounter` | `sensor` | `precipitation` | Total rain volume in millimeters (mm). |
| `yesterdayRainCounter` | `sensor` | `precipitation` | Rain volume yesterday in millimeters (mm). |
| `windSpeed` | `sensor` | `wind_speed` | Wind speed in km/h. |
| `windDirection` | `sensor` | None | Wind direction in degrees (0-360°). |
| `windDirectionVariation` | `sensor` | None | Variation of wind direction in degrees. |
| `storm` | `binary_sensor` | `safety` | Storm warning indicator. |
| `temperatureExternalOne` | `sensor` | `temperature` | External temperature sensor 1 (°C). |
| `temperatureExternalTwo` | `sensor` | `temperature` | External temperature sensor 2 (°C). |
| `temperatureExternalDelta` | `sensor` | `temperature` | Temperature differential between external probes (°C). |

### Air Quality

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `carbonDioxideConcentration` | `sensor` | `carbon_dioxide` | CO₂ concentration in parts per million (ppm). |
| `particulateMassConcentrationOne` | `sensor` | `pm1` | PM1 fine dust mass concentration (µg/m³). |
| `particulateMassConcentrationTwoPointFive` | `sensor` | `pm25` | PM2.5 fine dust mass concentration (µg/m³). |
| `particulateMassConcentrationTen` | `sensor` | `pm10` | PM10 dust mass concentration (µg/m³). |
| `airQualityIndexTwoPointFive` | `sensor` | `aqi` | Air Quality Index calculated from PM2.5. |
| `airQualityIndexTen` | `sensor` | `aqi` | Air Quality Index calculated from PM10. |
| `particulateTypicalSize` | `sensor` | None | Typical particle diameter in micrometers (µm). |

### Soil, Moisture, and Water

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `soilMoisture` | `sensor` | `moisture` | Soil moisture percentage (0-100%). |
| `soilMoistureRawValue` | `sensor` | None | Raw soil moisture value (diagnostic). |
| `soilTemperature` | `sensor` | `temperature` | Soil temperature in °C. |
| `waterlevelDetected` | `binary_sensor` | `moisture` | Water level alarm trigger. |
| `moistureDetected` | `binary_sensor` | `moisture` | Moisture detection trigger. |
| `moistureLevel` | `sensor` | `moisture` | Measured moisture level in percent. |

### Acceleration, Tilt, and Passage

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `accelerationSensorTriggered` | `binary_sensor` | `vibration` | Vibration or movement detected. |
| `accelerationSensorValueX/Y/Z` | `sensor` | None | Raw axis acceleration (diagnostic). |
| `accelerationSensorEventCounter` | `sensor` | None | Total count of vibration events. |
| `tiltState` | `sensor` | None | Tilt orientation state. |
| `calculatedHeight` | `sensor` | `distance` | Calculated passage height in centimeters (cm). |
| `distance` | `sensor` | `distance` | Distance measurement in centimeters (cm). |

### Diagnostics and Maintenance

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `lowBat` | `binary_sensor` | `battery` | Low battery warning. |
| `unreach` | `binary_sensor` | `connectivity` | Device communication loss flag. |
| `sabotage` | `binary_sensor` | `tamper` | Device tamper or sabotage alert. |
| `mainsFailureActive` | `binary_sensor` | `problem` | Mains power failure indicator. |
| `mainsVoltage` | `sensor` | `voltage` | Measured mains supply voltage (V). |
| `rssiDeviceValue` / `rssiPeerValue` | `sensor` | `signal_strength` | Radio signal strength in dBm. |

### Hardware examples
- Window/door sensors: HmIP-SWDO, HmIP-SWDM, HmIP-SRH
- Weather stations: HmIP-SWO-PR, HmIP-SWO-PL
- Environmental sensors: HmIP-STHD, HmIP-STHO, HmIP-SFD, HmIP-SWD

---

## 5. Locks and Door Openers

The integration supports smart door locks, electric strikes, and motorized garage doors.

### Channels and Entities

| Channel Type | Platform | Companion Entities | Description |
|---|---|---|---|
| `DOOR_LOCK_CHANNEL` / `DOOR_LOCK_PRO_CHANNEL` | `lock` | `HcuDoorUnlatchButton` (button), `HcuDevicePin` (text) | Smart door lock. Supports lock, unlock, and unlatch commands. Protected by an authorization PIN. |
| `DOOR_SWITCH_CHANNEL` | `button` | `HcuDevicePin` (text) | Door opener or electric strike. Triggers a pull-latch action. |
| `DOOR_CHANNEL` / `GARAGE_DOOR_CHANNEL` | `cover` | None | Motorized garage door actuator with position detection. |
| `IMPULSE_OUTPUT_CHANNEL` | `button` | None | Momentary impulse trigger (e.g. for garage door openers). |

### Groups

| Group Type | Platform | Description |
|---|---|---|
| `EXTENDED_LINKED_GARAGE_DOOR` | `switch` | Direct-linked garage door group. |

### Hardware examples
- Door locks: HmIP-DLD
- Door opener actuators: HmIP-WGC
- Garage door modules: HmIP-MOD-HO

---

## 6. Sirens, Alarm, and Smoke Detectors

The integration exposes full safety alarm, intrusion alarm, and smoke detection systems.

### Home Alarm Entities

| Entity Name | Platform | Description |
|---|---|---|
| `alarm_control_panel.homematic_ip_hcu` | `alarm_control_panel` | Central alarm control panel supporting Armed Home, Armed Away, and Disarmed states. |
| `binary_sensor.<hcu>_intrusion_alarm` | `binary_sensor` | Active intrusion alarm indicator. |
| `binary_sensor.<hcu>_safety_alarm` | `binary_sensor` | Active safety alarm indicator (water, smoke). |
| `button.<hcu>_acknowledge_safety_alarm` | `button` | Silences and acknowledges a safety alarm without disarming the intrusion system. |

### Sirens and Signal Selection

Each `ALARM_SWITCHING` group with members (for example `SIREN`, shown as "Indoor Sirene") provides a siren and signal tests. The group can contain alarm sirens as well as smoke detectors that the HCU uses as sirens.

| Channel / Group | Platform | Description |
|---|---|---|
| `ALARM_SWITCHING` Group | `siren` | Turns the alarm signal of all group members on or off, optionally for a duration (`HcuAlarmSiren`). |
| `ALARM_SWITCHING` Group | `select` | Acoustic signal test (`HcuAlarmSignalAcoustic`) and optical signal test (`HcuAlarmSignalOptical`). |

### Smoke Detectors

| Feature | Platform | Device Class | Description |
|---|---|---|---|
| `smokeDetectorAlarmType` | `binary_sensor` | `smoke` | Smoke alarm triggered status. |
| `smokeAlarmCounter` | `sensor` | None | Total number of smoke alarms triggered. |
| `smokeTestCounter` | `sensor` | None | Total number of test alarms performed. |
| `lastSmokeTestTimestamp` | `sensor` | `timestamp` | Date and time of the last smoke test. |
| `lastCommunicationTestTimestamp` | `sensor` | `timestamp` | Date and time of the last communication check. |
| `inclusionTimestamp` | `sensor` | `timestamp` | Date and time of device inclusion. |
| `chamberDegraded` | `binary_sensor` | `problem` | Smoke chamber degradation warning. |

### Hardware examples
- Smoke detectors: HmIP-SWSD, HmIP-SWSD-2

---

## 7. Buttons and Remote Controls

Homematic IP buttons and wall remotes are stateless transmitters. Instead of maintaining static on/off state entities, they fire momentary event notifications.

### Event Entities and Event Bus

Each physical button channel creates an `event` entity (`HcuButtonEvent` or `HcuDoorbellEvent`) with event types:
- `press_short` (short press)
- `press_long` (long press, repeated while held)
- `press_long_start` and `press_long_stop` (start and end of a long press)
- `ring` (doorbell event)

In addition, each button press fires the `hcu_integration_event` on the Home Assistant event bus for YAML automations. On the event bus, devices that only report a plain press send the type `press`.

### Channel Types and Roles

| Channel Type / Role | Event Entity | Description |
|---|---|---|
| `KEY_CHANNEL`, `SINGLE_KEY_CHANNEL` | `event` | Standard push button channel. |
| `MULTI_MODE_INPUT_CHANNEL` | `event` | Multi-mode binary input channel configured as button. |
| `MULTI_MODE_INPUT_TRANSMITTER` | `event` | Wireless wall switch transmitter channel. |
| `KEY_OR_SWITCH_FOR_GROUP` | `event` | Button allocated to a direct connection group. |
| `KEY_OR_SWITCH_FOR_ALARM_ZONE` | `event` | Arming/disarming button for alarm zones. |
| `ECO_MODE_ACTIVATION` | `event` | Dedicated Eco mode activation button. |
| `HOT_WATER_PROFILE` | `event` | Dedicated hot water booster button. |
| `DOOR_BELL_INPUT` | `event` | Doorbell push button input. |

### Supported Button Devices
- **Wall Switches**: HmIP-WGS, HmIP-WRC2, HmIP-WRC6, HmIP-WRC6-A, HmIP-WRCC2, HmIP-BRC2
- **Remote Controls**: HmIP-KRC4, HmIP-RC8, HmIP-KRCK
- **Contact Interfaces**: HmIP-FCI1, HmIP-FCI6, HmIP-SCI
- **Wired Bus Inputs**: HmIPW-DRI16

---

## 8. Watering Systems

The integration integrates Homematic IP garden irrigation controllers and valves.

### Channels and Entities

| Channel / Feature | Platform | Description |
|---|---|---|
| `WATERING_ACTUATOR_CHANNEL` | `valve` | Irrigation valve actuator supporting open, close, and timed watering. |
| `WATERING_CONTROLLER_CHANNEL` | `valve` | Central multi-channel irrigation controller. |
| `waterFlow` | `sensor` | Measured water flow rate in liters per minute (L/min). |
| `waterVolume` | `sensor` | Total accumulated water volume in liters (L). |
| `waterVolumeSinceOpen` | `sensor` | Water volume dispensed during the current open cycle (L). |
| `wateringOnTime` | `sensor` | Active watering duration in seconds (s). |
| Reset Water Volume | `button` | Resets the accumulated water volume counter. |

### Groups

| Group Type | Platform | Description |
|---|---|---|
| `EXTENDED_LINKED_WATERING` | `switch` | Direct-linked watering group. |

### Hardware examples
- Irrigation actuators: HmIP-MOD-OC8, HmIP-FSI16

---

## 9. Energy and Metering

The integration provides energy monitoring entities compatible with the Home Assistant Energy Dashboard.

### Features and Entities

| Feature | Platform | Device Class | State Class | Description |
|---|---|---|---|---|
| `currentPowerConsumption` | `sensor` | `power` | `measurement` | Instantaneous electrical power draw in watts (W). |
| `energyCounter` | `sensor` | `energy` | `total_increasing` | Total accumulated energy consumed in kilowatt-hours (kWh). |
| `energyCounterOne/Two/Three` | `sensor` | `energy` | `total_increasing` | Multi-tariff or multi-channel energy counter (kWh). |
| `energyProduction` | `sensor` | `energy` | `total_increasing` | Total solar or generated energy in kilowatt-hours (kWh). |
| `powerProduction` | `sensor` | `power` | `measurement` | Current electrical generation in watts (W). |
| `gasVolume` | `sensor` | `gas` | `total_increasing` | Gas volume in cubic meters (m³). |
| `currentGasFlow` | `sensor` | None | `measurement` | Gas flow rate in cubic meters per hour (m³/h). |
| Reset Energy Counter | `button` | None | None | Resets the device energy consumption counter. |

### Hardware examples
- Measuring plugs and switches: HmIP-PSM, HmIP-PSM-2, HmIP-BSM

---

## 10. HCU Gateway Device

The integration registers your Home Control Unit hardware as a central device in Home Assistant.

### System Diagnostics and Management

| Entity Name | Platform | Category | Description |
|---|---|---|---|
| Radio Traffic (Carrier Sense) | `sensor` | Diagnostic | Radio channel load percentage (0-100%). |
| Duty Cycle | `sensor` | Diagnostic | HCU 868 MHz transmission budget percentage (0-100%). |
| Duty Cycle Level | `sensor` | Diagnostic | Categorical duty cycle status. |
| Connectivity | `binary_sensor` | Diagnostic | Central communication reachability flag. |
| Firmware Update | `update` | Firmware | Notifies you when new HCU firmware updates become available. |
| Vacation Mode | `binary_sensor` | Status | Reports whether system-wide vacation mode is currently active. |
| Identify Device | `button` | Diagnostic | Flashes the HCU central status LED to locate or verify the unit. |
