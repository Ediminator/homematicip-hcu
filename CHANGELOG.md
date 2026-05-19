# Changelog

All notable changes to the Homematic IP Local (HCU) integration will be documented in this file.

## 2.0.0.beta7 - 2026-05-x

> [!NOTE]
> Please take your time with this update. Due to the breaking changes listed below, carefully review all your automations before updating.

### ⚠️ Breaking Changes

- The Doorbell sensor now uses the event type `ring` on `hcu_integration_event` (#40)
- The button event types (`ring`, `press`, `press_short`, `press_long`, `press_long_start` or `press_long_stop`) are now lowercase and no longer prefixed with `key_`
- The `channel` field in the event data of `hcu_integration_event` has been renamed to `subtype`. Update your automations accordingly.
- On devices where individual buttons can be combined into a button pair, button presses were reported on the wrong channel. This has been corrected via a workaround. If you are affected, update your automations accordingly.
- Switches are now displayed as outlet, switch or light depending on the setting in the Homematic IP app.
  Note: Existing switch entities configured as "Light" may no longer appear under the switch platform. Please check your automations and dashboards after updating.
  
### 🐛 Bug Fixes 

- Fixed serial number assignment for devices with non-standard model type casing (e.g. HMIP-PS, HMIP-SWDO).

### ✨ New Features

- The internal logic has been completely redesigned for a more stable and flexible structure. (#175)
  - Introduced Channel Role as an additional basis for entity creation
  - Doorbell sensor is now properly integrated and working as expected
- Added device trigger support, making it easier to use button presses directly as triggers in automations. More in README.md
- Device Channels that have not been configured in the Homematic IP app are no longer displayed. (#255)
- Added **"Use Internal On Time"** config switch entity per channel. When enabled, turning on a switch or light channel passes the `onTime` configured in the Homematic IP app for the internal button, causing the device to turn itself off automatically after the set duration. This makes it possible to use the configured on-time via HomeKit as well — useful for example for staircase lighting (e.g. HmIP-DRSI1) or water valves on devices like the (e.g. HmIP-MOD-OC8). The entity is disabled by default and only appears on channels where an `onTime` value is configured. State is persisted across HA restarts.
- Added **set_cooling_mode** action to simplify enabling and disabling cooling mode in the HCU

### HmIP-FDC & Lock

- Full support for HmIP-FDC: the integration now finds and uses the correct `ACCESS_AUTHORIZATION_CHANNEL` to trigger the pull latch, respecting the HCU's access-authorization model
- The integration's `clientId` is now saved during setup and used for authorization checks; refresh it via **Settings → Integrations → HCU → Configure**
- Reconfigure flow is now two steps: first update host/ports, then renew the activation token — the `clientId` is refreshed automatically
- PIN failures and missing access-authorization entries are now reported as actionable issues in **Settings → Repairs** instead of triggering a full re-authentication
- **New PIN logic** for all access profile devices. Each access profile device now has its own Access Authorization PIN (authorizationPin).
  **Important**: The Global PIN will be removed in a future version. It is strongly recommended to migrate all existing implementations to use the Device Code exclusively.

**In this release**, the groundwork has been laid to submit this integration as **HACS default**. The required validation checks have been addressed, bringing the integration in line with the quality standards expected of default integrations.

---
## 1.21.12 - 2026-04-30

### ✨ New Features

- add Diagnostic Sensor for internalLinkConfiguration onTime
  
---
## 1.21.11 - 2026-04-29

### ✨ New Features

- Climate entities now correctly display cooling mode in Home Assistant
- add soilTemperature, soilMoisture, soilMoistureRawValue

### 🐛 Bug Fixes

- Prepare HmIP-FDC with the correct api command
  
---
## 1.21.10 - 2026-04-12

### ✨ New Features

****DOOR_LOCK_DRIVE_PRO****
- Prepare for DOOR_LOCK_DRIVE_PRO
  
**USER MESSAGE SERVICE**
- rebuild User Message Service for userfriendly UI

### 🐛 Bug Fixes

- error log #325

---
## 1.21.9 - 2026-04-10

### ✨ New Features

**USER MESSAGE SERVICE**
- rebuild User Message Service for userfriendly UI
  
**WATERING ACTUATOR CHANNEL**
- add wateringAmountTarget, waterFlow, waterVolume, waterVolumeSinceOpen and resetWaterVolume for WATERING_ACTUATOR_CHANNEL
- add WATERING_ACTUATOR_CHANNEL to hcu_integration.switch_on_with_time

### 🐛 Bug Fixes

- The suggested_area of the device is now correctly applied.

**Files Changed:**
- `custom_components/hcu_integration/translation/de.py` — add new translations for new fields in User Message Service
- `custom_components/hcu_integration/translation/en.py` — add new translations for new fields in User Message Service
- `custom_components/hcu_integration/api.py` — add set_watering_switch_state, reset_water_volume and add variable for User Message Service
- `custom_components/hcu_integration/button.py` — add class HcuResetWaterVolume
- `custom_components/hcu_integration/const.py` — add all sensors and API_PATHS for WATERING_ACTUATOR_CHANNEL 
- `custom_components/hcu_integration/discvoery.py` — add logic to add HcuResetWaterVolume
- `custom_components/hcu_integration/entity.py` — fix meta to suggested_area for devices
- `custom_components/hcu_integration/services.py` — rebuild User Message Service for userfriendly UI
- `custom_components/hcu_integration/services.yaml` — add new fields for User Message Service for userfriendly UI
- `custom_components/hcu_integration/switch.py` — add async_turn_on_with_time

---
## 1.21.8 - 2026-04-03

### 🐛 Bug Fixes

**Cover Improvements**
add close_cover_tilt, open_cover_tilt, stop_cover_tilt to cover devices and cover groups

**Disable logging for empty groups**
add groups to ALLOWED_EMPTY_GROUPS
SECURITY_ZONE, META, INDOOR_CLIMATE, ENERGY, SECURITY, ACCESS_CONTROL, ENVIRONMENT, SECURITY_BACKUP_ALARM_SWITCHING

**Files Changed:**
- `custom_components/hcu_integration/const.py` — add groups to ALLOWED_EMPTY_GROUPS.
- `custom_components/hcu_integration/cover.py` — Cover Improvement
- `custom_components/hcu_integration/discovery.py` — Disable logging for empty groups.

---
## 1.21.7 - 2026-04-03

### ✨ New Features

**Apple HomeKit Door Unlatch Bypass (Issue #30)**

Added a dedicated `HcuDoorUnlatchButton` for HmIP-DLD door locks. Because Apple HomeKit natively refuses to support an "Open Latch" button for Lock accessories, this update creates a separate Home Assistant button entity alongside your lock. You can now easily export this dummy button into HomeKit to pull your door latch!

### 🐛 Bug Fixes

**Enhanced Authentication Diagnostics for Plugin Users**

Fixed confusing error logs when Home Assistant cannot authenticate with the HCU for specific locks. The integration now catches `CLIENT_INVALID_AUTHORIZATION` errors and prints a crystal clear **1-to-5 step troubleshooting flow** to the logs, forcing users to delete stale profiles and verify they are on HCU Firmware 1.6.16+.

**Centralized Lock Error Handling**

Refactored lock error handling into a shared `handle_lock_api_error()` utility in `util.py`. API side-effects (like triggering re-authentication) were moved specifically to the entity platforms (`lock.py`, `button.py`) to align with Home Assistant architectural patterns. Extracted all lock and motor state strings and error patterns to named constants.

**Advanced Entity Discovery Registry**

Implemented a more flexible, registry-based discovery mechanism in `discovery.py`. Secondary entities (like the HomeKit Unlatch button) are now discovered through an `extra_entities` mapping in `const.py`, removing hardcoded platform-specific logic and improving codebase maintainability.

**Files Changed:**
- `custom_components/hcu_integration/button.py` — Removed redundant error handling; updated unlatch button re-auth logic.
- `custom_components/hcu_integration/lock.py` — Updated re-auth logic for API authentication errors.
- `custom_components/hcu_integration/util.py` — Refactored to separate error identification from side-effects.
- `custom_components/hcu_integration/discovery.py` — Implemented registry-based discovery for extra entities.
- `custom_components/hcu_integration/const.py` — Added extra entity mapping for door lock channels.
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.21.7.

---
## 1.21.6 - 2026-04-03

### ✨ New Features

**HCU Plugin Configuration Dashboard**

This release fixes the ""blank plugin user"" issue where clicking the gear icon for the Home Assistant integration on the HCU webview would open an empty page. The configuration page now displays a useful informational dashboard:

- **Status Dashboard:** Shows real-time integration status (READY/ERROR), version number, and total connected device count directly on the HCU.
- **Resource Links:** Provides clickable shortcuts to your Home Assistant dashboard, official documentation, and the issue tracker.
- **Spec Compliance:** Correctly implements the `friendlyName` parameter in `PluginStateResponse` as required by the Connect API reference implementations.

**Files Changed:**
- `custom_components/hcu_integration/api.py` — Implemented dashboard logic and spec-compliant responses.
- `custom_components/hcu_integration/const.py` — Added plugin metadata constants and version bump.
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.21.6.

---
## 1.21.5 - 2026-03-31

### ✨ New Features

- Add Create and Delete User Message from HA to HCU. See Documenation for Details.

---
## 1.21.4 - 2026-03-26

### ✨ New Features

- Closing and Opening State for shutter actuators

---
## 1.21.3 - 2026-03-14

### ✨ New Features

**Diagnostic Entity Clutter Cleanup & Native Valve Position (Issue #296)**

This release significantly cleans up the entity list by disabling obscure diagnostic sensors by default and re-enabling critical thermodynamic data. 

**What Changed:**
- **Diagnostic Silence:** 11 obscure diagnostic entities (e.g., `dirtLevel`, `chamberDegraded`, `operationDays`) are now **disabled by default** for new installations.
- **Retroactive Cleanup:** For existing users, the integration will now automatically disable these 11 entities in the Home Assistant registry IF they were previously enabled by default and HAVEN'T been manually modified by the user. This ensures a cleaner UI without overriding your manual configurations.
- **Valve Position Enabled:** The `valvePosition` sensor is now enabled by default for all climate devices, providing immediate visibility into heating demand without manual activation.
- **Robust Feature Parsing:** Refactored the internal entity registry cleanup logic to be more resilient and performant, ensuring accurate identification of entities even as Homematic IP expands its feature set.

**Files Changed:**
- `custom_components/hcu_integration/const.py` — Updated default enabled status for diagnostic and valve sensors.
- `custom_components/hcu_integration/discovery.py` — Implemented proactive registry cleanup and robust feature extraction.
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.21.3.

---
## 1.21.2 - 2026-03-14

### 🐛 Bug Fixes

**Fix Missing Entities for RF Devices on Startup (Issue/PR #298)**

Fixed an issue where battery (`lowBat`), window state (`windowState`), and connectivity (`unreach`) entities were completely missing for HmIP-SWDM and other RF devices if their value reported as `null` during integration startup.

**What Changed:**
- **Mandatory RF Features:** Introduced a whitelist for core features (`windowState`, `unreach`) that should always be created even when initially `null`.
- **Optional Features Guard:** Restored the `supportedOptionalFeatures` check so features like `lowBat` are correctly discovered when initially `null`.
- **Accurate Sensor States:** Refactored `HcuBinarySensor` classes so that `null` values map to an `unknown` state in Home Assistant, instead of defaulting to `False` (e.g., showing a device as "Connected" when its unreach state is actually unknown).
- **Code Maintainability:** Extracted complex logic into a `_should_skip_null_feature` helper function.

**Files Changed:**
- `custom_components/hcu_integration/discovery.py` — Hardware support guard logic extraction and fix.
- `custom_components/hcu_integration/const.py` — Added `MANDATORY_RF_FEATURES` whitelist.
- `custom_components/hcu_integration/binary_sensor.py` — Refactored null value handling for boolean sensors.
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.21.2.

---
## 1.21.1 - 2026-03-10

### 🐛 Bug Fixes

**Restore Legacy Group Discovery (Issue #294)**

Resolved a regression introduced in version 1.20.0 that incorrectly filtered out user-created groups assigned to rooms (e.g., "Extended Linked Switching Groups"). This restoration ensures all groups are discovered correctly by removing hardcoded room-group filters. Users can continue to hide unwanted group types using the existing "Hide Groups" configuration option.

**What Changed:**
- Removed hardcoded filtering logic in `discovery.py` that skipped groups with `metaGroupId`.
- Removed `ROOM_BASED_SWITCHING_GROUP_TYPES` constant from `const.py`.
- Cleaned up obsolete log messages and counters related to room group filtering in `discovery.py`.
- Verified that all group types are now correctly discovered and respect the "Hide Groups" configuration.

**Files Changed:**
- `custom_components/hcu_integration/discovery.py` — Removed room group filtering.
- `custom_components/hcu_integration/const.py` — Removed unused constant.
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.21.1.

---
## 1.21.0 - 2026-03-09

### 🐛 Bug Fixes

**Fix False Press Events During Startup and Reload (Issue #183, PR #288)**

Fixed a race condition where button devices (especially HmIP-FCI6) triggered false `PRESS_SHORT` events during Home Assistant startup or integration reload.

**Root Cause:**
The WebSocket listener starts receiving events *before* the initial system state is fetched via `get_system_state()`. Events arriving during this window are processed against an empty device state, causing `_detect_timestamp_based_button_presses()` to treat every initial timestamp as a "change" and fire false button press events.

**What Changed:**
- Added `_initial_state_loaded` flag to `HcuCoordinator` — set to `False` during initialization, `True` after `get_system_state()` completes
- `_handle_event_message()` now ignores all `HMIP_SYSTEM_EVENT` messages until the flag is set
- On integration reload, a fresh `HcuCoordinator` is created, so the guard is automatically re-applied

**Impact:**
- ✅ No more false button press events during startup or reload
- ✅ No impact on normal event processing after initialization
- ✅ Existing `MULTI_MODE_INPUT_CHANNEL` exclusion (v1.18.7) continues to prevent false events during normal operation

### 📝 Files Changed

- `custom_components/hcu_integration/__init__.py` — Startup safeguard for event processing
- `tests/test_issue_183.py` — Tests for the startup safeguard and channel exclusion
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.21.0

---
## 1.20.0 - 2026-03-08

### ✨ New Features

**Prepared Advanced Group Types (HEATING_COOLING_DEMAND, HOT_WATER)**

Added support for three previously ignored Homematic IP group types. These groups are **conditionally exposed** — they only appear when physical devices are actually assigned to them, preventing empty entities from cluttering the UI.

- `HEATING_COOLING_DEMAND_BOILER` → `binary_sensor` (heat demand indicator)
- `HEATING_COOLING_DEMAND_PUMP` → `binary_sensor` (heat demand indicator)
- `HOT_WATER` → `switch` (hot water profile control)

> **💡 Why do I see "Heating Cooling Demand" entities?**
> Your HCU automatically assigns thermostat radiator valves to these groups. The HCU aggregates all valve positions across your home to calculate a single answer: *"Does the boiler need to fire right now?"*
> 
> Even without a physical Homematic IP boiler actuator (like HmIP-WHS2), you can use this binary sensor in Home Assistant to:
> - **Control a third-party relay** (e.g., a Shelly or Zigbee plug) connected to your boiler
> - **Build energy dashboards** tracking when your boiler is demanded vs idle
> - **Create automations** like *"If heatDemand has been off for 30 minutes, reduce boiler standby temperature"*
> 
> The `HOT_WATER` entity will only appear when you configure a hot water profile with a physical actuator in the Homematic IP app.

New entity classes added:
- `HcuGroupBinarySensor` — Base class for group-level binary sensors
- `HcuHeatDemandBinarySensorGroup` — Boiler/pump heat demand indicator

**Human-Readable Group Labels**

Group labels that use ALL_CAPS_UNDERSCORED naming (e.g., `HOT_WATER`) are now automatically formatted to title case (`Hot Water`) in both entity names and device registry entries.

### 🐛 Bug Fixes

**Fix Zombie Group Devices Not Being Cleaned Up**

Fixed a bug where orphaned group devices persisted in the Home Assistant device registry even after they were no longer discovered.

- **Root Cause:** `valid_device_ids.add(group_id)` was called *before* the `metaGroupId` skip check, marking filtered groups as "valid" and preventing the cleanup logic from removing them.
- **Fix:** Moved `valid_device_ids.add(group_id)` to after all skip checks, so the existing registry cleanup correctly identifies and removes orphaned group devices.

### 🔧 Improvements

**Room-Based Switching Groups Now Filtered**

Auto-created room groups (`SWITCHING`, `LIGHT`, `EXTENDED_LINKED_SWITCHING` with `metaGroupId`) are now skipped during discovery to reduce UI clutter. User-created Direct Connection groups (which do not have a `metaGroupId`) continue to be discovered normally.

> **Note:** This reverses the behavior introduced in v1.18.2/v1.18.3 (Issue #146), which allowed all `metaGroupId` groups. Users who need room-based switching groups can request a configuration option in a future release.

### 📝 Files Changed

- `custom_components/hcu_integration/discovery.py` — Advanced group mappings, conditional exposure, room-group filtering, zombie cleanup fix
- `custom_components/hcu_integration/entity.py` — Label formatting for entity names and device registry
- `custom_components/hcu_integration/binary_sensor.py` — New group binary sensor classes
- `custom_components/hcu_integration/manifest.json` — Version bump to 1.20.0

---
## 1.19.11 - 2026-03-07

### ✨ New Features
- Exposed 11 new diagnostic data points for HmIP-SWSD-2 smoke detectors (dirt levels, degradation, operations days, heat indicators, test timestamps).
- Added `HcuTimestampSensor` mapping millisecond UNIX timestamps natively into Home Assistant datetime values.

### 🐛 Bug Fixes
- Restored `meta` and `switchVisualization` state attributes that were accidentally hidden behind the advanced debugging configuration flag in the previous update.
- Improved robustness of the API timestamp parsing to prevent datetime overflow exceptions in case of faulty smoke detector data.

## 1.19.10 - 2026-02-09

### 🐛 Bug Fixes
- Fixed an error during setup #275

## 1.19.9 - 2026-02-04

### ✨ New Features
- show groups as service
- add firmware readonly entities for devices

### ✅ Update Note
This release has been **thoroughly tested**. However, it is always recommended to **create a backup before updating**.

### 🧹 Browser Cache Note
Some of these changes are cached by your browser. After updating, please hard refresh / reload the page to ensure all changes are applied.

## 1.19.8 - 2026-02-02

### ✨ New Features
- Added HmIP-DRDI3
- Prepared group **EXTENDED_LINKED_GARAGE_DOOR**.

### ✅ Update Note
This release has been **thoroughly tested**. However, it is always recommended to **create a backup before updating**.

### 🧹 Browser Cache Note
Some of these changes are cached by your browser. After updating, please hard refresh / reload the page to ensure all changes are applied.

## 1.19.7 - 2026-01-27

### ✨ New Features
- Added **meta group** and **switchVisualization** as extra state attributes.
- Going forward, newly discovered devices will be automatically assigned to the corresponding Home Assistant area — **if the Homematic IP areas already exist in Home Assistant.**
- Move Connectivity, Low Battery, Duty Cycle, and RSSI sensors to the **Diagnostic category**.
- Prepared groups **EXTENDED_LINKED_NOTIFICATION** and **EXTENDED_LINKED_WATERING**.
- Added logic **to clean up unused / orphaned entities** from the entity registry.

### ✅ Update Note
This release has been **thoroughly tested**. However, it is always recommended to **create a backup before updating**.

### 🧹 Browser Cache Note
Some of these changes are cached by your browser. After updating, please hard refresh / reload the page to ensure all changes are applied.

## 1.19.6 - 2026-01-23

### ⚠️ BREAKING CHANGES
- **Eco mode can no longer be set via heating groups**  
  (#268) Eco mode has been disabled for heating groups. To enable Eco mode globally, use the service hcu_integration.activate_eco_mode.

### ✨ New Features
- Add translations for events and buttons.
- add extra attribute window_state to the HcuClimate entity.

### ✅ Update Note
This release has been **thoroughly tested**. However, it is always recommended to **create a backup before updating**.

### 🧹 Browser Cache Note
Some of these changes are cached by your browser. After updating, please hard refresh / reload the page to ensure all changes are applied.

## 1.19.5 - 2026-01-13

### ⚠️ BREAKING CHANGES
- **WINDOW state supported only for `ROTARY_HANDLE_CHANNEL` (HmIP-SRH) (#175)**  
  For all other devices, these entities will be removed. Non-available entities must be deleted manually via **Settings -> Devices & Services -> Entities**.  
  Tip: Filter by **integration** and the status **"not available"** to make cleanup easier. You can also delete multiple entities/devices at once.

### 🐛 Bug Fixes
- **Add `shutterLevel` to move the tilt cover-groups (#216)**

### ✨ New Features
- Add **Identify** button for DIN rail devices with new logic that evaluates the optional functions of the devices.
- Add configuration option to **disable groups**.
- Add configuration option **Advanced Debugging** to view the raw `HMIP_EVENT_DATA`.
- Add translations for **window states**.
- Add state icons for **tilt window**.
- Add additional translations for configuration.

### ✅ Update Note
This release has been **thoroughly tested**. However, it is always recommended to **create a backup before updating**.
  
## 1.19.4 - 2026-01-05

### ✨ New Features

- Add extra attribute is_group:False to none group entities
- Add extra attribute device_id, channel_index, and functional_channel_type in all entities
- Add extra attribute group type in all group entities
- Add #254 air pressure for ELV-SH-CAP
- Add #254 air quality for HmIP-SFD
- add "ELV-" serial numbers to device info

## 1.19.3 - 2026-01-03

### 🐛 Bug Fixes

- **Add effects in lowercase to prepare for hacs default**
- **rollback heating preset mode logic to prevent showing cooling profiles from issue #170 and open API Issue in #229**
- **add secondaryshadinglevel on shading groups**

### ✨ New Features

- add icons for services, effects and climate profiles
  
## 1.19.2 - 2025-12-29

### 🐛 Bug Fixes

- **Fix Issue Climate Visualisation (Issue #164)**
- **Heating Profiles Control (Issue #170)**
- **Add translations for service turn on with time and light effects**

### ✨ New Features

- serial number in device info incl. HCU
- Add HMIP-MP3P
- Add SimpleColor for HCU TOPLIGHT and HmIPW-WRC6
- Add Attribut is_group in groups
- Add impulse button for HmIP-WGC
- Add service send_api_command
- prepare for default HACS integration

## 1.19.1 - 2025-12-16

### 🐛 Bug Fixes

**Fix Zombie Groups and Registry Cleanup (Issue #185)**

Fixed an issue where "zombie" groups (empty groups or groups deleted in HCU) persisted in the Home Assistant device registry as orphaned entities.

- **Automated Registry Cleanup**: Implemented a robust cleanup mechanism that automatically removes devices and groups from the Home Assistant registry if they are no longer reported by the HCU API.
- **Initialization Fix**: Fixed a bug where the `config_entry` was not correctly accessible in the `HcuCoordinator`, which could cause issues during entity setup.
- **Improved Group Logic**: Refined the logic for identifying valid groups to ensure only functional groups are discovered.

## 1.19.0 - 2025-12-15

### ✨ New Features

**Initial Configuration OEM Selection**

Added a new step to the initial configuration flow that allows users to select which third-party OEMs (like Philips Hue) to import *before* the integration is fully set up.
- **Improved UX**: Uses a clean multi-select list instead of individual boolean toggles, improving readability (e.g., "Philips Hue" instead of "import_Philips%20Hue").
- Users can now filter out unwanted third-party bridges immediately.
- The same selection logic is available in "Configure" options after setup to change these settings later.

### 🐛 Bug Fixes

**Correct 3rd Party Device Identification (Issue #177)**

Fixed incorrect identification of third-party devices (like Philips Hue) which were previously defaulting to "eQ-3" manufacturer.
- Devices now correctly report their actual manufacturer (e.g., "Philips Hue").
- Enhanced detection logic prioritizes explicit OEM fields and specific Hue model identifiers.
- Fixed handling of manufacturer names with spaces or special characters in the Options flow.

### 🔧 Improvements

**Robust Device Removal**

- Improved logic for removing devices when their OEM is disabled in options.
- Device removal now works reliably even if the HCU is temporarily unreachable, using robust fallback identification.
- Refactored internal logic for cleaner code and better maintainability.
## 1.18.7 - 2025-12-13

### 🐛 Bug Fixes

**Fix False Button Press Events (Issue #183)**
- Fixed an issue where "ghost" button press events were triggered for multi-mode input channels during configuration updates or cyclic status reports.
- `MULTI_MODE_INPUT_CHANNEL` types are now correctly excluded from timestamp-based event detection and rely solely on explicit device channel events.

### ✨ New Features

**Expanded Button Device Support**
- Added explicit support for `HmIP-FCI6` (Contact Interface 6-channel) and `HmIPW-DRI16` (Wired Input Module 16-channel) to generic button event discovery.
- These devices will now properly create event entities for button presses.

## 1.18.6 - 2025-12-13

### 🐛 Bug Fixes

**Fix Shutter Group Classification**
- Fixed an issue where cover groups containing only shutter devices (e.g. HmIP-BROLL) were incorrectly classified as `BLIND` because `secondaryShadingLevel` (tilt) was present but `None` in the API response.
- These groups are now correctly classified as `SHUTTER` with appropriate features.

### 🔧 Improvements

**Refactor Test Assertions**
- Simplified feature assertions in `test_cover.py` to use strict equality checks, addressing code review feedback.

## 1.18.5 - 2025-12-13

### 🐛 Bug Fixes

**Fix Cover Entity Behavior and Test Improvements**

Addresses comprehensive feedback for PR #210, improving `HcuCoverGroup` logic, rounding precision, validity checks, and test coverage.

**What Changed:**
- **Cover Groups:**
  - `HcuCoverGroup` now correctly uses `primaryShadingLevel` (position) and `secondaryShadingLevel` (tilt), fixing errors from using device-specific properties.
  - Added explicit support for `OPEN_TILT`, `CLOSE_TILT`, and `STOP_TILT` capabilities.
  - Dynamic `device_class` assignment: `BLIND` if tilt supported, otherwise `SHUTTER`.
- **Logic & Safety:**
  - Improved `round()` logic for position calculations to prevent off-by-one errors (e.g. 99.6% -> 100%).
  - Added robustness checks to `async_set_cover_tilt_position` to prevent crashes when current level is unknown.
  - Added proper logging configuration to `cover.py`.
- **Testing:**
  - Major refactoring of `tests/test_cover.py` to use `pytest.mark.parametrize` for cleaner, more robust tests.
  - Added specific test cases for group properties, device class detection, and tilt-level passing.

**Impact:**
- ✅ Reliable control and status reporting for Cover Groups.
- ✅ Correct `device_class` icons and behaviors in Home Assistant UI.
- ✅ More accurate position feedback.
- ✅ Enhanced error handling and stability.

---

## 1.18.4 - 2025-12-12

### 🐛 Bug Fixes

**Fix Cover Entities Regression (Issue #207)**

Fixed a critical regression where roller shutter devices (HmIP-BROLL, HmIP-FROLL) and cover groups became unavailable after updating to version 1.18.3.

**Root Cause:**
The `HcuCover` class was using non-existent methods and incorrect property references:
- Used `get_parameter_value("LEVEL")` instead of `self._channel.get("shutterLevel")`
- Used `async_set_device_parameter()` instead of `async_set_shutter_level()`
- Used `async_stop_device()` instead of `async_stop_cover()`
- `HcuCoverGroup` referenced `_group_data` instead of the correct `_group` property

**What Changed:**
- Fixed `HcuCover` to use correct channel data access (`shutterLevel`, `slatsLevel`)
- Fixed `HcuCover` to use correct API methods for shutter control
- Fixed `HcuCoverGroup` to use correct `_group` property
- Corrected position conversion between HomematicIP (0.0=open, 1.0=closed) and Home Assistant (0=closed, 100=open)
- Added `round()` for more accurate position conversions

**Impact:**
- ✅ Roller shutter devices (HmIP-BROLL, HmIP-FROLL) now work correctly
- ✅ Cover groups (SHUTTER, EXTENDED_LINKED_SHUTTER) now work correctly
- ✅ Position reporting and control functions properly

---

## 1.18.3 - 2025-12-11

### 🐛 Bug Fixes

**Fix Missing Direct Connection Groups (Issue #146)**

Fix missing entities for `EXTENDED_LINKED_SWITCHING` (Light) and `EXTENDED_LINKED_SHUTTER` (Cover) groups (Issue #146).

Ensure "Direct Connections" (user-created groups) are discovered even if they have a `metaGroupId`.

---

## 1.18.2 - 2025-12-10

### 🐛 Bug Fixes

**Fix Missing Direct Connection Groups (Issue #146)**

Fixed an issue where user-created "Direct Connection" groups (Direktverknüpfungen) of type `SWITCHING` or `LIGHT` were missing from Home Assistant.

**Root Cause:**
These groups were incorrectly filtered out by logic intended to suppress redundant auto-created "Room Groups", which share the same `metaGroupId` property as Direct Connections.

**What Changed:**
- The filter excluding `SWITCHING` and `LIGHT` groups with `metaGroupId` has been removed.
- Direct Connection groups are now correctly discovered and created as entities.
- **Note:** This may also expose auto-created Room Groups as entities, which were previously suppressed.

**Impact:**
- ✅ User-created Direct Connection groups are now available in Home Assistant.

---

## 1.18.1 - 2025-12-01

### 🐛 Bug Fixes

**Fix Redundant Duty Cycle Sensors for HCU (Issue #120)**

Fixed an issue where redundant "Duty Cycle Level" sensors were created for the main HCU device, duplicating the information already provided by the "HCU Duty Cycle" entity.

**What Changed:**
- The `dutyCycleLevel` sensor (created from device channel data) is now suppressed for the main HCU device.
- The `dutyCycle` sensor (created from the Home object data) remains the primary source for this information for the HCU.
- Access Points (HmIP-HAP) and other devices will continue to have their individual `dutyCycleLevel` sensors.

**Impact:**
- ✅ Cleaner entity list with no duplicate duty cycle sensors for the HCU.
- ✅ Resolves user confusion regarding two identical sensors.

---

## 1.18.0 - 2025-12-01

### 🏗️ Architecture Refactoring

**Extracted Service Handlers to Dedicated Module**

Improved code organization and maintainability by extracting all service handlers from `__init__.py` into a new `services.py` module.

#### What Changed

1. **New `services.py` Module**
   - All 7 service handlers moved to dedicated module
   - `async_handle_play_sound()`
   - `async_handle_set_rule_state()`
   - `async_handle_activate_party_mode()`
   - `async_handle_activate_vacation_mode()`
   - `async_handle_activate_eco_mode()`
   - `async_handle_deactivate_absence_mode()`
   - `async_handle_switch_on_with_time()`
   - Added `async_register_services()` and `async_unregister_services()` functions
   - Single source of truth for `INTEGRATION_SERVICES` list

2. **Slimmed Down `__init__.py`**
   - Reduced from ~550+ lines to ~385 lines
   - `async_setup_entry()` reduced from ~200 lines to ~40 lines
   - Removed 9 nested function definitions
   - Cleaner imports and better separation of concerns
   - `HcuCoordinator` class now focused solely on WebSocket/event handling

#### Benefits

- ✅ Better code organization following Home Assistant best practices
- ✅ Service handlers are now testable in isolation
- ✅ Easier to maintain and extend
- ✅ Reduced complexity in main integration file

### 🐛 Bug Fixes

**Fix Entity State Updates Not Being Received (Critical)**

Fixed a critical bug introduced during refactoring where entities (alarm panel, sensors, switches, etc.) would not receive state updates from the HCU after commands were sent.

**Root Cause:**
The event message path was incorrectly simplified during refactoring. Events from the HCU WebSocket are nested at `body.eventTransaction.events`, not `body.events`.

**What Was Broken:**
- Alarm control panel stuck in "Arming" state after activation
- All entity states not updating from HCU push events
- Only initial state was displayed, no real-time updates

**What Was Fixed:**
```python
# Before (broken)
events = body.get("events", {})

# After (correct)
events = body.get("eventTransaction", {}).get("events", {})
```

**Impact:**
- ✅ All entities now receive real-time state updates
- ✅ Alarm panel correctly shows Armed/Disarmed states
- ✅ All device state changes reflected immediately in Home Assistant

### 🔧 Code Quality Improvements

- Removed unused imports from `__init__.py`
- Standardized type hints across service module
- Improved logging messages for conciseness
- Removed redundant `self.entry` attribute (using `self.config_entry` from base class)

### 📝 Files Changed

- `custom_components/hcu_integration/__init__.py` - Major refactoring, slimmed down
- `custom_components/hcu_integration/services.py` - **NEW FILE** - Service handlers module

---

## 1.17.6 - 2025-11-29

### 🐛 Bug Fixes

**Fix Connectivity Entities Misassignment (Issue #120)**
- Fixed an issue where `HmIP-WLAN-HAP` devices were not being correctly excluded from the HCU device group.
- This caused connectivity entities (like `unreach`) to be assigned to the main HCU device instead of the WLAN Access Point.
- Added `HmIP-WLAN-HAP` to the list of excluded device prefixes.

## 1.17.5 - 2025-11-29

### 🐛 Bug Fixes

**Fix OnTime Selection Regression (Issue #161)**
- Fixed a regression where the `switch_on_with_time` service was not correctly selecting the "WithTime" API endpoint.
- Switches now correctly turn on for the specified duration.

---

## 1.17.4 - 2025-11-28

### ✨ New Features

**Climate Valve Visualization (#164)**
- Added `valve_position` attribute to climate entities.
- Returns the **maximum** valve position of all devices in the heating group, representing peak demand.

**HmIP-STV Support (#163)**
- Added support for Tilt/Vibration sensors (HmIP-STV).
- Mapped `ACCELERATION_SENSOR_CHANNEL` to `HcuGenericSensor` feature to ensure correct entity creation.

**OnTime Selection for Switches (#161)**
- Added `hcu_integration.switch_on_with_time` service.
- Allows turning on switches for a specific duration (in seconds).
- Supports `on_time` parameter in `HcuApiClient`.

### 🐛 Bug Fixes

**Entity Prefix Fix (#158)**
- Fixed issue where `entity_prefix` was not correctly applied to Entity IDs.
- Logic now correctly handles prefixing for both main and child entities.

**Robustness Improvements**
- **Service Calls**: `switch_on_with_time` service now safely handles missing `entity_id` or `on_time` parameters with clear error logging.
- **Entity Naming**: Simplified and corrected logic for constructing entity names with prefixes, ensuring consistent naming conventions.

---

## 1.17.2 - 2025-11-17

### 🐛 Critical Bug Fixes

**Fix Button Events Completely Broken - Two Critical Issues (#134)**

Fixed TWO critical bugs that broke button events since v1.15.20, affecting devices like HmIP-BRC2, HmIP-WRC2, HmIP-WRC6-A, and HmIP-WKP.

**Bug #1: DEVICE_CHANNEL_EVENT Events Don't Update UI**

**Root Cause:**
The `process_events()` method in `api.py` only handles DEVICE_CHANGED, GROUP_CHANGED, and HOME_CHANGED events. It completely ignores DEVICE_CHANNEL_EVENT messages that modern button devices send for actual button presses.

**Result:**
- Button event entities receive button presses internally
- But coordinator never calls `async_set_updated_data()`
- Home Assistant never gets notified of state changes
- **Event entities don't update in UI until integration reload!**

**What Was Fixed:**
1. Modified `_handle_device_channel_events()` to return set of device IDs
2. Merge these IDs into `updated_ids` after processing events
3. Coordinator now properly notifies Home Assistant of DEVICE_CHANNEL_EVENT state changes

**Bug #2: False Button Presses from Configuration Changes**

**Root Cause:**
Devices like HmIP-BRC2 using `SINGLE_KEY_CHANNEL` were included in timestamp-based button detection. When users changed button configuration in HomematicIP app:
1. HCU sends DEVICE_CHANGED event with updated `lastStatusUpdate`
2. Timestamp detection sees the change
3. **False "button press" event fires and triggers automations!**

These devices send explicit DEVICE_CHANNEL_EVENT messages for real button presses - they should NOT use timestamp-based detection.

**What Was Fixed:**
1. Created `DEVICE_CHANNEL_EVENT_ONLY_TYPES` constant for channel types that exclusively use DEVICE_CHANNEL_EVENT
2. Added `SINGLE_KEY_CHANNEL` and `KEY_CHANNEL` to this list
3. Modified `_extract_event_channels()` to skip these channels in timestamp-based detection

**Bonus Fix: Missing Channel Type Mappings**

Also restored three channel type mappings that were accidentally removed in v1.17.0:
- `BRAND_REMOTE_CONTROL`
- `BRAND_WALL_MOUNTED_TRANSMITTER`
- `REMOTE_CONTROL_TRANSMITTER`

**Impact:**
- ✅ Button event entities now update immediately in UI (no more waiting for integration reload!)
- ✅ No more false button events from configuration changes
- ✅ Real button presses work correctly with proper event types (press_short, press_long, etc.)
- ✅ All button device channel types now properly supported
- ✅ Both modern entity-based events and legacy `hcu_integration_event` fire correctly

**How to Apply:**
1. Update to version 1.17.2
2. Restart Home Assistant
3. Test button presses - events should fire immediately and UI should update

**Files Changed:**
- `custom_components/hcu_integration/__init__.py` - Fixed DEVICE_CHANNEL_EVENT UI update issue and false positive detection
- `custom_components/hcu_integration/const.py` - Added DEVICE_CHANNEL_EVENT_ONLY_TYPES and missing channel mappings

**Reported by:** Community users in Issue #134 with detailed diagnostic logs
**Affects:** Versions 1.15.20 - 1.17.1 (all button devices, especially HmIP-BRC2/WRC2)
**Fixed in:** Version 1.17.2
## 1.17.1 - 2025-11-17

### 🐛 Critical Bug Fix

**Fix Button Events Completely Broken - Restore Missing Channel Type Mappings**

Fixed a critical regression introduced in v1.17.0 where button events stopped working entirely for devices using certain channel types.

**Root Cause:**

In v1.17.0 (commit d4da009), a refactoring removed the dynamic channel type mapping loop and replaced it with explicit mappings. However, THREE critical channel types were removed from `EVENT_CHANNEL_TYPES` but were NEVER added to `HMIP_CHANNEL_TYPE_TO_ENTITY`:
- `BRAND_REMOTE_CONTROL`
- `BRAND_WALL_MOUNTED_TRANSMITTER`
- `REMOTE_CONTROL_TRANSMITTER`

This caused any device using these channel types to:
1. NOT have button event entities created during discovery
2. NOT fire any button events (neither modern entity-based events nor legacy hcu_integration_event)
3. Be completely non-functional for button presses

**What Was Fixed:**

1. **Restored Missing Channel Types**: Added all three missing channel types back to `EVENT_CHANNEL_TYPES`
2. **Added Explicit Mappings**: Created explicit `HcuButtonEvent` mappings for all three channel types in `HMIP_CHANNEL_TYPE_TO_ENTITY`
3. **Comprehensive Coverage**: Ensures all button devices work regardless of which channel type their firmware reports

**Impact:**
- ✅ Button events now work for ALL button devices
- ✅ Devices using BRAND_REMOTE_CONTROL, BRAND_WALL_MOUNTED_TRANSMITTER, or REMOTE_CONTROL_TRANSMITTER channel types are now functional
- ✅ Both modern entity-based events and legacy hcu_integration_event now fire correctly
- ✅ No breaking changes - existing working devices continue to work

**How to Apply:**
1. Update to version 1.17.1
2. Restart Home Assistant
3. Button events should immediately start working

**Files Changed:**
- `custom_components/hcu_integration/const.py` - Added missing channel type mappings

**Reported by:** Community users experiencing broken button events after v1.15.20
**Affects:** Version 1.17.0 (all button devices using the three missing channel types)
**Fixed in:** Version 1.17.1

---

## 1.17.0 - 2025-11-17

### 🐛 Critical Bug Fixes

**Fix Missing Button Events for Multiple Device Types - Issues #134, #98**

Fixed critical issues where button press events were not firing for several device types, preventing users from creating automations based on button presses.

**Devices Affected:**
- **HmIP-WRC2** (Wall Remote Control 2-button)
- **HmIP-BRC2** (Brand Wall Remote Control 2-button)
- **HmIP-WRC6-A** (Wall Remote Control 6-button)
- **HmIP-WKP** (Keypad)
- **HmIP-BSL** (Brand Switch with Notification Light)

**Root Causes:**

1. **Missing Channel Type Mappings (Issue #134)**: Six channel types used by button devices were missing from `HMIP_CHANNEL_TYPE_TO_ENTITY`, preventing event entity creation:
   - `KEY_CHANNEL` (HmIP-WRC2, HmIP-BRC2)
   - `WALL_MOUNTED_TRANSMITTER_CHANNEL` (HmIP-WRC6-A)
   - `KEY_REMOTE_CONTROL_CHANNEL` (HmIP-WKP)
   - `SWITCH_INPUT_CHANNEL`, `SINGLE_KEY_CHANNEL`, `MULTI_MODE_INPUT_CHANNEL`

2. **Multi-Function Channel Issue (Issue #98)**: HmIP-BSL uses `NOTIFICATION_LIGHT_CHANNEL` for dual purposes (LED backlight control AND button input). The integration only created light entities, missing the button event functionality.

**What Was Fixed:**

1. **Added Missing Channel Mappings**: All six button channel types now properly map to `HcuButtonEvent` entity class
2. **Multi-Function Channel Support**: Created `MULTI_FUNCTION_CHANNEL_DEVICES` constant to identify channels serving multiple purposes
3. **Dual Entity Creation**: HmIP-BSL now creates BOTH light entities (for LED control) AND button event entities (for button presses)
4. **Enhanced Logging**: Added debug logging showing device type, channel index, and functions when creating multi-function channel entities

**Impact:**
- ✅ Button events now fire for all affected devices
- ✅ All button press types work: `PRESS_SHORT`, `PRESS_LONG`, `PRESS_LONG_START`, `PRESS_LONG_STOP`
- ✅ HmIP-BSL buttons functional alongside LED backlight control
- ✅ Users can now create automations for previously non-functional buttons

**Fix Multicolor Issues for HmIP-BSL and Similar Devices - Issue #112**

Fixed color control issues where setting certain colors (particularly ORANGE) would fail with API errors.

**Root Cause:**

The HCU API only officially supports 8 colors for `simpleRGBColorState` devices:
- BLACK, BLUE, GREEN, TURQUOISE, RED, PURPLE, YELLOW, WHITE

Despite ORANGE being defined in device specifications, the HCU API does not accept it and returns errors when attempting to set it.

**What Was Fixed:**

1. **Removed ORANGE Color Support**:
   - Removed `HMIP_COLOR_ORANGE` constant and all references
   - Removed ORANGE from `HMIP_RGB_COLOR_MAP`
   - Updated color mappings in both `HcuLight` and `HcuNotificationLight` classes

2. **Remapped Orange Hue Range**:
   - Hues 0-30° now map to RED (closer to red on color wheel)
   - Hues 30-90° now map to YELLOW (expanded to include orange range)
   - Users selecting orange colors will get the closest supported alternative

3. **Unified Color Conversion Logic**:
   - Extracted duplicated `_hs_to_simple_rgb()` methods into shared module-level helper
   - Unified hue boundaries between `HcuLight` and `HcuNotificationLight` for consistency
   - Both classes now use identical color mapping algorithm

**Impact:**
- ✅ Color changes no longer fail with API errors
- ✅ Consistent color behavior across all simple RGB devices
- ✅ Orange hue selections gracefully map to RED or YELLOW
- ✅ Better maintainability through shared color conversion logic

### ✨ Improvements

**Enhanced Group Discovery Diagnostics - Issue #146**

Added comprehensive logging to help diagnose missing group entities and understand group discovery behavior.

**What Was Added:**

1. **Discovery Statistics**:
   - Counts groups successfully created
   - Tracks auto-created meta groups that are skipped
   - Reports unknown group types that couldn't be mapped

2. **Detailed Per-Group Logging**:
   - Debug logs show each created group with type, label, and ID
   - Warning logs alert for unknown group types with user-friendly messages
   - Info summary shows discovery statistics

3. **Meta Group Filtering**:
   - Auto-created SWITCHING and LIGHT meta groups are intentionally skipped (reduces entity clutter)
   - Debug logs explain why each meta group is skipped
   - User-created functional groups still discovered normally

4. **Robustness Improvements**:
   - Added defensive null-checking for group IDs
   - Prevents silent failures when HCU API omits group ID field
   - Debug logging when groups are skipped due to missing data

**Example Log Output:**
```
Group discovery summary: 12 created, 8 skipped (meta groups), 0 unknown types
```

**Impact:**
- ✅ Users can easily diagnose why groups aren't appearing
- ✅ Clear guidance to report missing group type support
- ✅ Better visibility into integration's group discovery process
- ✅ Reduced entity clutter from unwanted auto-generated groups

**Enhanced Error Logging with Device Context - PR Review Feedback**

Improved error messages during entity discovery to include device ID and channel index for easier debugging.

**What Was Enhanced:**

All entity creation error messages now include:
- **Device ID**: Identifies which specific device encountered the error
- **Channel Index**: Pinpoints the exact channel that failed
- **Feature/Type Info**: Shows what was being created when error occurred

**Before:**
```
Failed to create entity for feature windowState (HcuWindowStateSensor): ...
```

**After:**
```
Failed to create entity for device 3014F711A000123456789ABC, channel 1, feature windowState (HcuWindowStateSensor): ...
```

**Impact:**
- ✅ Dramatically easier to identify problem devices when users report issues
- ✅ Channel-specific errors can be diagnosed without guesswork
- ✅ Helps developers quickly locate and fix device-specific compatibility issues

### 🔧 Code Quality & Maintainability

**Refactored Color Conversion Logic**

- Extracted duplicated `_hs_to_simple_rgb()` method from both `HcuLight` and `HcuNotificationLight` classes
- Created shared `_convert_hs_to_simple_rgb()` module-level helper function
- Reduced code duplication by ~60 lines while maintaining identical behavior
- Comprehensive docstring with Args and Returns documentation
- Both light classes now delegate to the same helper for consistent color mapping

**Extracted Magic Numbers to Named Constants**

- Created `_LOW_SATURATION_THRESHOLD = 20` constant for color conversion
- Improves code clarity and makes threshold easily adjustable
- Documents that low saturation values are interpreted as white

**Improved Documentation Accuracy**

- Clarified color hue range descriptions in docstrings
- Removed misleading "60-degree divisions" reference
- More accurately describes varied hue range sizes (RED=45°, YELLOW=60°, PURPLE=75°)
- Updated comments to reflect actual HCU API support limitations

**Enhanced Defensive Programming**

- Added null-checking for group IDs during discovery
- Prevents crashes when HCU API omits expected fields
- Debug logging for skipped invalid groups

### 📝 Files Changed

- `custom_components/hcu_integration/const.py` - Added button channel mappings, removed ORANGE constant, added multi-function device config
- `custom_components/hcu_integration/discovery.py` - Multi-function channel support, enhanced group logging, defensive null-checks, improved error messages
- `custom_components/hcu_integration/light.py` - Removed ORANGE support, refactored color conversion, extracted constants, unified color boundaries

### 🙏 Acknowledgments

**Issues Addressed:**
- Issue #134 - Button events for WRC2/BRC2/WRC6-A/WKP (reported by community)
- Issue #98 - HmIP-BSL button events not firing
- Issue #112 - Multicolor/ORANGE color issues
- Issue #146 - Missing group entities diagnostics

**Code Review:**
- Special thanks to Gemini Code Assist for thorough code review feedback that led to significant improvements in code quality, maintainability, and error diagnostics

---

## 1.16.2 - 2025-11-15

### Fixes & Improvements

- **Backward Compatibility for Button Events**: Ensured that both modern, entity-based events and the legacy `hcu_integration_event` are fired for button presses. This maintains compatibility with existing user automations while introducing the new event system.
- **Refactored Event Handling Logic**: Simplified and improved the internal logic for detecting and handling button press events, increasing code readability and maintainability.

---

## 1.16.0 - 2025-11-15

### Features

- **Added Support for New Devices**:
  - `HmIP-WRC2`
  - `HmIP-BRC2`
  - `HmIP-WRC6-A`
- **Enhanced Button Events**: Events for newly supported devices include `press_short`, `press_long`, `press_long_start`, and `press_long_stop`.

### Fixes & Improvements

- **Refactored Event Handling**: Migrated button-like devices to a modern, entity-based event system for more consistent and reliable event handling.
- **Fixed Stateless Button Presses**: Corrected an issue where stateless button presses were not being correctly processed.

## 1.15.19 - 2025-11-13

### Fixes & Improvements

Fixed Light Control for Notification Devices (HmIP-BSL, etc.): Corrected an issue where setting the color or brightness on lights using the `NOTIFICATION_LIGHT_CHANNEL` (e.g., HmIP-BSL) would sometimes fail to visually turn the light on (the "invisible light" bug).

The HcuLight entity's `turn_on` and `turn_off` methods now explicitly manage the `opticalSignalBehaviour` state, ensuring the physical LED function is activated and deactivated correctly in conjunction with color/brightness settings.

API Improvement: Added support for the `/hmip/device/control/setSimpleRGBColorDimLevelWithTime` endpoint to enable future support for transitions/ramp times on simple RGB devices.

---

## Version 1.15.18 - 2025-11-13

### 🐛 Bug Fixes

**Fix API Endpoints and Remove Invalid Parameters - PR #129**

Fixed critical API integration issues identified through diagnostic file analysis and official HCU API documentation review.

#### Issues Addressed

1. **Incorrect RGB Color Control Endpoint**
   - **Problem**: Integration was calling `/setSimpleRGBColorState` endpoint which doesn't exist in the HCU API
   - **Fix**: Corrected endpoint to `/setSimpleRGBColorDimLevel` (matches API documentation section 6.8.1.26)
   - **Impact**: RGB color control for devices like HmIP-BSL now works correctly

2. **Invalid rampTime Parameter Usage**
   - **Problem**: Integration was sending `rampTime` parameter to endpoints that don't accept it:
     - `/setDimLevel` doesn't accept `rampTime`
     - `/setColorTemperatureDimLevel` doesn't accept `rampTime`
     - `/setHueSaturationDimLevel` doesn't accept `rampTime`
   - **Fix**: Implemented dynamic endpoint selection:
     - When `ramp_time` is provided: use `*WithTime` variant endpoints
     - When `ramp_time` is `None`: use base endpoints without the parameter
   - **Added Endpoints**:
     - `SET_DIM_LEVEL_WITH_TIME` → `/setDimLevelWithTime`
     - `SET_COLOR_TEMP_WITH_TIME` → `/setColorTemperatureDimLevelWithTime`
     - `SET_HUE_WITH_TIME` → `/setHueSaturationDimLevelWithTime`
   - **Impact**: Light transitions now work correctly without API errors

3. **Invalid onLevel Parameter**
   - **Problem**: Integration was sending `onLevel` parameter to switch commands
   - **Analysis**: Diagnostic file confirmed switches only support boolean `on` field, not `onLevel`
   - **Fix**: Removed `onLevel` parameter from:
     - `async_set_switch_state()` in `api.py`
     - `_call_switch_api()` in `switch.py`
     - `_call_switch_api()` (unused) in `siren.py`
   - **Impact**: Switch commands no longer send invalid parameters

#### Code Quality Improvements

1. **Extracted Helper Method**
   - Created `_get_api_path_with_ramp_time()` helper method following DRY principles
   - Eliminated code duplication across three light control methods
   - Centralized API path selection logic with clear documentation

2. **Organized Constants**
   - Sorted `API_PATHS` dictionary alphabetically for improved readability and maintainability

3. **Removed Dead Code**
   - Deleted unused `_call_switch_api()` method from `HcuSiren` class

#### Validated "Undocumented" Fields

Confirmed these fields are **valid** per diagnostic file analysis, despite not being in official documentation:
- `vaporAmount` - HmIP-BWTH Wall Thermostat (absolute humidity in g/m³)
- `valvePosition` - HmIP-FALMOT-C12 Floor Heating Controller (valve position percentage)
- `dutyCycleLevel` - HmIP-HCU1 Home Control Unit (duty cycle level percentage)

These fields are retained in the integration as they contain valid device data.

#### Technical Details

**Files Modified**:
- `custom_components/hcu_integration/const.py` - Added WithTime endpoints, sorted API_PATHS
- `custom_components/hcu_integration/api.py` - Fixed endpoint selection, removed invalid parameters, added helper method
- `custom_components/hcu_integration/light.py` - No changes (uses corrected API)
- `custom_components/hcu_integration/switch.py` - Removed onLevel parameter
- `custom_components/hcu_integration/siren.py` - Removed onLevel parameter and dead code

**Documentation References**:
- HCU API Documentation sections 6.8.1.7-9 (Dim Level)
- HCU API Documentation sections 6.8.1.8-9 (Color Temperature)
- HCU API Documentation sections 6.8.1.15-16 (Hue/Saturation)
- HCU API Documentation section 6.8.1.26 (RGB Color)

---

## Version 1.15.15 - 2025-11-13

### 🐛 Bug Fix

**Fix Home-Level Entities Being Assigned to HAP Instead of HCU - Issue #120**

Fixed a bug where home-level entities (duty cycle, radio traffic, alarm, vacation mode) were being incorrectly assigned to HAP (Home Assistant Proxy) devices instead of the actual HCU in multi-access-point setups.

#### Root Cause

The primary HCU selection logic in `api.py` had several issues:

1. **Incomplete Model Type List**: The `HCU_MODEL_TYPES` constant only included "HmIP-HCU-1" and "HmIP-HCU1-A", missing other HCU variants
2. **No HAP Exclusion**: HAP/DRAP devices weren't explicitly excluded from selection
3. **Strict Matching**: Only exact model type matches were accepted, not flexible pattern matching
4. **Fallback Issue**: When no exact match was found, the code fell back to `home.accessPointId`, which often points to a HAP device in multi-access-point configurations

This caused the integration to incorrectly assign home-level entities to the HAP device instead of the main HCU.

#### The Fix

Implemented a robust 3-tier primary HCU selection strategy in `api.py:_update_hcu_device_ids()`:

**Code Improvements**
- Removed dependency on incomplete `HCU_MODEL_TYPES` constant
- Defined `HAP_DRAP_PREFIXES` as module-level constant following PEP 8 conventions
- Updated both initial HCU collection and primary selection to use flexible pattern matching with `startswith("HmIP-HCU")`
- This ensures consistent matching logic throughout the entire method

**Strategy 1: Flexible HCU Pattern Matching**
- Match any device with `modelType` starting with `"HmIP-HCU"`
- This covers all known models ("HmIP-HCU-1", "HmIP-HCU1-A") and future variants
- Explicitly exclude `"HmIP-HAP"` and `"HmIP-DRAP"` prefixes using module-level constant

```python
# Module-level constant
HAP_DRAP_PREFIXES = ("HmIP-HAP", "HmIP-DRAP")

# Initial HCU collection using flexible pattern matching
hcu_ids = {
    device_id
    for device_id, device_data in self.state.get("devices", {}).items()
    if device_data.get("modelType", "").startswith("HmIP-HCU")
}

# Single-pass candidate selection
sorted_hcu_ids = sorted(hcu_ids)
primary_hcu_candidates = []
non_hap_candidates = []

for device_id in sorted_hcu_ids:
    model_type = devices.get(device_id, {}).get("modelType", "")

    if model_type.startswith(HAP_DRAP_PREFIXES):
        continue

    non_hap_candidates.append(device_id)

    if model_type.startswith("HmIP-HCU"):
        primary_hcu_candidates.append(device_id)
```

**Strategy 2: Validated accessPointId**
- Use `home.accessPointId` if it's NOT a HAP/DRAP model
- If `accessPointId` IS a HAP/DRAP, search for non-HAP alternatives
- Log warning when HAP/DRAP is detected and alternative is selected

**Strategy 3: Fallback with HAP Avoidance**
- Prefer any non-HAP/DRAP device from available access points
- Only use HAP/DRAP if absolutely no other options exist

#### Enhanced Logging

Added detailed logging to help diagnose device assignment:
- Debug logs show which selection strategy was used
- Warning logs alert when `home.accessPointId` points to HAP/DRAP
- Helps users understand device association in multi-AP setups

#### Impact

- ✅ Home-level entities now correctly link to HCU device, not HAP
- ✅ Works with any `HmIP-HCU-*` model variant (future-proof)
- ✅ Handles edge cases in multi-access-point setups
- ✅ Better diagnostics via enhanced logging
- ✅ Explicit HAP/DRAP exclusion prevents misassignment

**Reported by:** @holsteiner-kiel in Issue #120
**Affects:** Versions 1.15.14 and earlier with multi-access-point setups
**Fixed in:** Version 1.15.15

**Fix Entity Discovery Crash for Home-Level Sensors**

Fixed a crash during entity discovery when home-level sensor features (like `dutyCycle` or `carrierSense`) were found on device channels. The discovery code was incorrectly trying to instantiate `HcuHomeSensor` with device/channel arguments, causing a `TypeError`.

The fix generalizes the solution by skipping all features mapped to `HcuHomeSensor` class in the device-channel entity creation loop, as these sensors are handled separately in the home entity creation section with the correct signature.

```python
# Skip home-level sensors in device-channel loop
if mapping.get("class") == "HcuHomeSensor":
    continue
```

This prevents crashes for `dutyCycle`, `carrierSense`, and any future home-level sensors, making the discovery logic more robust.

**Fix HAP/DRAP Entities Being Linked to HCU Device**

Fixed an issue where entities from HAP (Home Assistant Proxy) and DRAP devices were incorrectly being linked to the main HCU device instead of appearing on their respective access point devices.

The root cause was that `hcu_part_device_ids` included all access point devices (HCU, HAP, DRAP). When the entity's `device_info` property checked if the device was "part of the HCU hardware complex", it would link HAP/DRAP entities to the HCU.

HAP and DRAP are separate physical devices, not parts of the HCU hardware. The fix excludes HAP/DRAP devices from `hcu_part_device_ids`:

```python
# Only include non-HAP/DRAP devices as part of HCU hardware complex
self._hcu_device_ids = set(non_hap_candidates)
```

Now HAP and DRAP devices appear as separate devices in Home Assistant with their own entities (like `dutyCycleLevel` sensors), while only the actual HCU device has home-level entities linked to it.

#### Files Changed

- `custom_components/hcu_integration/api.py` - Enhanced `_update_hcu_device_ids()` with 3-tier selection and HAP exclusion, exclude HAP/DRAP from hardware complex
- `custom_components/hcu_integration/discovery.py` - Skip home-level sensors in device-channel entity loop

---

## Version 1.15.14 - 2025-11-12

### 🐛 Critical Bug Fix

**Fix Radio Traffic Sensor Showing Incorrect Values Up to 2000% - Issue #112**

Fixed a critical bug where the Radio Traffic (carrierSense) sensor was displaying values multiplied by 100, causing readings to spike up to 2000% instead of the correct 20%.

#### Root Cause

The HCU API already transmits `carrierSense` values as percentages (e.g., 0.20 = 20%). The integration was incorrectly multiplying this value by 100 in `sensor.py`, resulting in:
- Actual HCU value: 0.20 (20%)
- Displayed value: 20.0% (0.20 × 100 = 20%)
- User report: Values spiking to 2000% (20% × 100)

#### The Fix

Removed the erroneous multiplication in `HcuHomeSensor.native_value` (`sensor.py:67-69`):

**Before (incorrect):**
```python
if self._feature == "carrierSense":
    return round(value * 100.0, 1)  # ❌ Wrong - already a percentage
```

**After (correct):**
```python
# carrierSense and dutyCycle are already in percentage from HCU
if self._feature in ("carrierSense", "dutyCycle"):
    return round(value, 1)  # ✅ Correct - just round to 1 decimal
```

#### Impact

- ✅ Radio Traffic sensor now shows correct percentage values
- ✅ No more 2000% spikes in readings
- ✅ Consistent with how HCU reports radio performance metrics
- ✅ Applies same fix to new duty cycle sensors

**Reported by:** Users in Issue #112
**Affects:** All previous versions with carrierSense sensor
**Fixed in:** Version 1.15.14

---

### ✨ New Features

**Add Duty Cycle Monitoring Entities - Issue #112**

Added comprehensive duty cycle monitoring capabilities to track radio transmission limits and network health.

#### Background

Homematic IP devices operate on sub-GHz radio frequencies with strict transmission duty cycle limits (typically 1% per hour) to comply with regulations. The HCU provides three types of duty cycle information:

1. **System-wide duty cycle** - Overall network transmission percentage
2. **Access point duty cycle levels** - Per-device metrics for HCU and additional access points (HmIP-HAP)
3. **Device duty cycle warnings** - Boolean flags when individual devices exceed their 1% limit

#### New Entities

**1. Overall Duty Cycle Sensor** (`home.dutyCycle`)
- **Type:** Percentage sensor
- **Location:** Home object (system-wide)
- **Purpose:** Monitor overall radio network transmission levels
- **Icon:** `mdi:radio-tower`
- **Default:** Disabled (enable in entity settings)
- **Value:** Rounded to 1 decimal place (e.g., 5.3%)

**2. Duty Cycle Level Sensor** (`dutyCycleLevel`)
- **Type:** Percentage sensor
- **Location:** Device channels (HCU and access points like HmIP-HAP)
- **Purpose:** Track duty cycle for each access point individually
- **Icon:** `mdi:radio-tower`
- **Default:** Disabled
- **Value:** Rounded to 1 decimal place (e.g., 13.5%)

**3. Duty Cycle Limit Binary Sensor** (`dutyCycle` boolean)
- **Type:** Binary sensor (Problem device class)
- **Location:** Device channels (most devices)
- **Purpose:** Warning flag when a specific device exceeds its 1% transmit limit
- **Default:** Disabled
- **Category:** Diagnostic
- **Value:** `on` = limit exceeded, `off` = normal operation

#### Technical Implementation

**Challenge: Dictionary Key Collision**

The HCU API uses the same field name `dutyCycle` for two different purposes:
- On `home` object: Percentage value (system-wide duty cycle)
- On device channels: Boolean flag (device limit warning)

This created a key collision in `HMIP_FEATURE_TO_ENTITY` where the second definition would overwrite the first.

**Solution:**
1. Created separate `DUTY_CYCLE_BINARY_SENSOR_MAPPING` constant in `const.py`
2. Added special handling in `discovery.py` to detect `dutyCycle` as boolean in device channels
3. Uses type checking (`isinstance(channel_data["dutyCycle"], bool)`) to differentiate contexts
4. Similar approach to how temperature sensors are handled as special cases

**Code highlights** (`discovery.py:203-218`):
```python
# Special handling for dutyCycle binary sensor (device-level warning flag)
# Note: dutyCycle exists in both home object (percentage) and device channels (boolean)
if "dutyCycle" in channel_data and isinstance(channel_data["dutyCycle"], bool):
    entities[Platform.BINARY_SENSOR].append(
        binary_sensor.HcuBinarySensor(
            coordinator, client, device_data, channel_index, "dutyCycle", entity_mapping
        )
    )
```

#### Impact

- ✅ Full visibility into radio network duty cycle usage
- ✅ Monitor system-wide transmission levels
- ✅ Track individual access point performance
- ✅ Get warnings when devices exceed regulatory limits
- ✅ All entities disabled by default to avoid clutter
- ✅ Consistent percentage formatting across all duty cycle sensors

#### Files Changed

- `custom_components/hcu_integration/const.py` - Added duty cycle entity mappings and special constant
- `custom_components/hcu_integration/sensor.py` - Fixed carrierSense, added rounding for duty cycle sensors
- `custom_components/hcu_integration/discovery.py` - Added special handling for duty cycle binary sensors

---

## Version 1.15.13 - 2025-11-12

### 🐛 Critical Bug Fix

**Fix Wired Switch Actuators Becoming Unavailable After Click (Issue #94)**

Fixed a critical regression introduced in recent refactoring where wired switching actuators (HmIP-DRS8 and similar devices) would become unavailable immediately after being toggled.

#### Root Cause

The `process_events` method in `api.py` had flawed merge logic for partial WebSocket updates:
- When a switch was toggled, the HCU would send a `DEVICE_CHANGED` event with updated state
- If this event didn't include `functionalChannels` (common for state-only updates), the **entire device object was replaced** with the partial update data
- This caused loss of critical device metadata like `permanentlyReachable`, `modelType`, `firmwareVersion`, and all channel information
- Without `permanentlyReachable`, the availability check failed, marking the entity as unavailable
- The entity would remain stuck in unavailable state until Home Assistant restart

#### The Fix

Completely rewrote the device/group merge logic to handle partial updates correctly:

1. **Smart merging**: Existing devices/groups now **always merge** incoming data instead of replacing
2. **Preserved metadata**: Critical fields like `permanentlyReachable` are preserved across state updates
3. **Channel preservation**: Channel data is only updated if included in the event, otherwise preserved
4. **Top-level updates**: State changes and other top-level fields merge properly without data loss

**Technical details** (`api.py:473-487`):
```python
elif existing_entity := self._state.get(data_key, {}).get(data_id):
    # Merge partial updates - preserves fields not in the update
    for key, value in data.items():
        if key == "functionalChannels":
            # Special handling: merge channel data at the channel level
            existing_entity.setdefault("functionalChannels", {})
            for ch_idx, ch_data in value.items():
                existing_entity["functionalChannels"].setdefault(ch_idx, {}).update(ch_data)
        else:
            # Regular top-level fields: direct assignment
            existing_entity[key] = value
```

#### Impact

- ✅ DRS8 and all wired switch actuators remain available after toggling
- ✅ Prevents data loss from partial WebSocket updates
- ✅ More robust state management for all device types
- ✅ Fixes the same issue for dimmers (DRD3) and other actuators

**Reported by:** @hennengrint in Issue #94
**Affects:** Versions 1.15.5 - 1.15.12
**Fixed in:** Version 1.15.13

### 🔘 Enhanced Button Event Support

**Add Multi-Function Channel Support for HmIP-BSL - Issue #98**

Improved handling of devices like HmIP-BSL where channels serve multiple purposes (button input + backlight control).

**Device Architecture Clarification**

HmIP-BSL (BRAND_SWITCH_NOTIFICATION_LIGHT) channel structure:
- **Channel 0**: `DEVICE_BASE` (maintenance/status)
- **Channel 1**: `SWITCH_CHANNEL` with `DOUBLE_INPUT_SWITCH` - Relay control only (friendly name: "Relais")
- **Channel 2**: `NOTIFICATION_LIGHT_CHANNEL` - **Top button input AND backlight LED** (friendly name: "An")
- **Channel 3**: `NOTIFICATION_LIGHT_CHANNEL` - **Bottom button input AND backlight LED** (friendly name: "Aus")

**What Was Fixed**

1. **Added Multi-Function Channel Metadata**:
   - New `MULTI_FUNCTION_CHANNEL_DEVICES` constant in `const.py`
   - Explicitly documents which device types have channels serving dual purposes
   - Maps channel types to their multiple functions (button + light)

2. **Enhanced Event Logging**:
   - Button presses on multi-function channels now log with context: `"Button press on multi-function channel: ...functions=['button', 'light']"`
   - Helps diagnose which channel is actually triggering events
   - Shows friendly channel names from device configuration

3. **Corrected Documentation**:
   - Fixed incorrect comment claiming `KEY_CHANNEL` is used by HmIP-BSL
   - HmIP-BSL actually uses `NOTIFICATION_LIGHT_CHANNEL` for button inputs (channels 2-3)
   - Added clear comments explaining multi-function channel behavior

4. **Discovery Documentation**:
   - Added inline comments in `discovery.py` explaining dual-function channels
   - Light entities are created for backlight control
   - Same channels respond to button presses via `DEVICE_CHANNEL_EVENT`

**Technical Details**

The HCU sends `DEVICE_CHANNEL_EVENT` messages when physical buttons are pressed:
- Top button press: `functionalChannelIndex: 2`, `channelEventType: "PRESS_SHORT"` (or PRESS_LONG, etc.)
- Bottom button press: `functionalChannelIndex: 3`, `channelEventType: "PRESS_SHORT"` (or PRESS_LONG, etc.)

These events are handled by `_handle_device_channel_events()` regardless of the channel type. The enhanced logging now explicitly identifies when these events come from multi-function channels.

**Impact**
- ✅ Better visibility into multi-function channel behavior
- ✅ Clearer documentation for devices with dual-purpose channels
- ✅ Enhanced diagnostics for troubleshooting button event issues
- ✅ Foundation for supporting other devices with multi-function channels

**Files Changed**
- `custom_components/hcu_integration/const.py` - Added `MULTI_FUNCTION_CHANNEL_DEVICES`, corrected documentation
- `custom_components/hcu_integration/__init__.py` - Enhanced `_handle_device_channel_events()` with multi-function logging
- `custom_components/hcu_integration/discovery.py` - Added documentation about dual-function channels

---

## Version 1.15.11 - 2025-11-11

### 🐛 Bug Fixes

**CRITICAL FIX: Correct API Parameter Usage for Siren Activation - Issue #100**

Fixed critical bug where siren activation was failing silently due to sending invalid parameters to the HCU API endpoint.

**Root Cause**

The integration was **misunderstanding the HCU API specification**:

1. **Invalid API Parameters**: The `/hmip/group/switching/setState` endpoint ONLY accepts `on` (boolean) and `groupId` parameters. It does NOT accept `signalAcoustic`, `signalOptical`, or `onTime` parameters.

2. **Wrong Assumption**: We incorrectly assumed these parameters could be sent dynamically. In reality, they are **properties configured on the ALARM_SWITCHING group in the HCU** itself and cannot be set via the API call.

3. **Silent Failure**: The HCU was either rejecting or silently ignoring the invalid parameters, causing the siren to never actually activate.

**Previous behavior (v1.15.10 - broken):**
```python
await client.async_set_alarm_switching_group_state(
    group_id=group_id,
    on=True,
    signal_acoustic=tone,        # ❌ Invalid parameter
    signal_optical=optical_signal,  # ❌ Invalid parameter
    on_time=duration,               # ❌ Invalid parameter
)
```

**New behavior (v1.15.11 - correct):**
```python
await client.async_set_alarm_switching_group_state(
    group_id=group_id,
    on=True,  # ✅ Only valid parameter
)
# Siren uses tone/duration/optical_signal configured in HCU group settings
```

**What Was Fixed**

1. **Simplified API Call**:
   - Only send `on: true` to activate the siren
   - Removed invalid `signalAcoustic`, `signalOptical`, and `onTime` parameters
   - HCU now uses the settings configured in the ALARM_SWITCHING group

2. **Removed Unsupported Features**:
   - Removed `TONES` and `DURATION` from supported features
   - Tone and duration must now be configured in the HCU's ALARM_SWITCHING group
   - Cannot be controlled dynamically from Home Assistant

3. **Code Cleanup**:
   - Removed scheduled state refresh logic (no longer needed without dynamic duration)
   - Removed tone validation and parameter handling
   - Simplified `async_turn_on()` and `async_turn_off()` methods
   - Improved group selection to prefer audio-enabled groups
   - Fixed default value for `acousticFeedbackEnabled` to `False` for safety

**Impact**

- ✅ **Sirens now actually activate** when turned on
- ⚠️ **Configuration Required**: Users must configure tone, duration, and optical signal in the HCU's ALARM_SWITCHING group settings (these cannot be controlled from Home Assistant)
- ✅ Group selection logic improved to prefer audio-enabled groups
- ✅ State updates handled by normal coordinator polling

**Changes:**
- `custom_components/hcu_integration/api.py`: Simplified `async_set_alarm_switching_group_state()` to only accept `on` parameter
- `custom_components/hcu_integration/siren.py`: Removed dynamic tone/duration/optical_signal handling, simplified activation logic, improved group selection

---

## Version 1.15.10 - 2025-11-11

### 🐛 Bug Fixes

**Fix HmIP-ASIR2 Audio Not Playing - Issue #100**

Fixed critical bug where HmIP-ASIR2 siren tones were not playing when activated. The HCU was rejecting all siren commands with error 400 `INVALID_REQUEST`.

**Root Cause**

The siren was being controlled using the **wrong API endpoint**. The integration was using `/hmip/device/control/setSoundFileVolumeLevelWithTime` (designed for doorbell devices like HmIP-MP3P that play sound *files*), but the HmIP-ASIR2 siren requires control via an **ALARM_SWITCHING group** using the `/hmip/group/switching/setState` endpoint with group-specific parameters.

**Previous behavior (broken):**
```python
# Siren controlled via DEVICE API (wrong!)
await client.async_set_sound_file(
    device_id=device_id,
    channel_index=1,
    sound_file=tone,  # HCU rejected with INVALID_REQUEST
    volume=1.0,
    duration=duration
)
```

**What Was Fixed**

The siren is now properly controlled through its ALARM_SWITCHING group:

1. **Find ALARM_SWITCHING group** during siren initialization
2. **Use group API** `/hmip/group/switching/setState` instead of device API
3. **Send correct parameters**: `signalAcoustic` (tone), `signalOptical` (LED pattern), `onTime` (duration)
4. **Added tone list corrections**: Fixed incorrect tone names (BATTERY_STATUS→LOW_BATTERY, etc.) and added missing tones (EXTERNALLY_ARMED, INTERNALLY_ARMED, etc.)
5. **Sorted tones alphabetically** within groups for better maintainability
6. **Added optical_signal parameter**: Users can now customize the LED visual pattern (defaults to BLINKING_ALTERNATELY_REPEATING)

**New behavior (working):**
```python
# Siren controlled via ALARM_SWITCHING GROUP (correct!)
await client.async_set_alarm_switching_group_state(
    group_id=alarm_group_id,
    on=True,
    signal_acoustic=tone,                        # Acoustic tone
    signal_optical=optical_signal,               # LED pattern (customizable)
    on_time=duration                             # Duration in seconds
)
```

**Example Usage:**
```yaml
service: siren.turn_on
target:
  entity_id: siren.alarmsirene
data:
  tone: FREQUENCY_RISING
  duration: 10
  optical_signal: BLINKING_ALTERNATELY_REPEATING  # Optional, defaults to this value
```

**Impact**
- ✅ Audio tones now play correctly when siren is activated
- ✅ All 18 official HomematicIP acoustic tones work (FREQUENCY_RISING, EXTERNALLY_ARMED, etc.)
- ✅ HCU accepts commands and siren activates immediately
- ✅ LED visual signals work alongside acoustic signals
- ✅ LED visual pattern is now customizable via optical_signal parameter
- ✅ Duration control works properly
- ✅ Turn off command successfully stops the siren

---

## Version 1.15.8 - 2025-11-11

### 🐛 Bug Fixes

**Fix HmIP-BSL False Button Events - Issue #98**

Fixed a critical bug where HmIP-BSL devices triggered false button events whenever the light was toggled via Home Assistant, not just on actual physical button presses. This caused automations to trigger unexpectedly.

**Root Cause**

The integration was treating `SWITCH_CHANNEL` with `DOUBLE_INPUT_SWITCH` internal link configuration as an event channel for timestamp-based button detection. The problem is that this channel's `lastStatusUpdate` timestamp changes whenever the switch state changes - whether from a physical button press OR from a programmatic toggle via Home Assistant.

**Previous behavior (broken):**
```python
# SWITCH_CHANNEL with DOUBLE_INPUT_SWITCH was included in event_channels
# Timestamp-based detection fired on ANY state change:
#   - Physical button press → timestamp changed → event fired ✓
#   - HA light toggle → timestamp changed → event fired ✗ (false positive)
```

**What Was Fixed**

- **Removed DOUBLE_INPUT_SWITCH detection** from `_extract_event_channels()` method
- **HmIP-BSL now uses ONLY DEVICE_CHANNEL_EVENT** for button press detection (no timestamp-based detection)
- **Enhanced logging** with device model, channel index, channel label, and channel type
- **Elevated log level to INFO** for button presses to help diagnose channel identification issues
- **Code cleanup**: Refactored logging using fallback empty dict pattern for cleaner, more concise code

**New behavior (working):**
```python
# SWITCH_CHANNEL excluded from timestamp-based detection
# Button presses detected ONLY via DEVICE_CHANNEL_EVENT:
#   - Physical button press → DEVICE_CHANNEL_EVENT → event fired ✓
#   - HA light toggle → no event fired ✓
```

**Technical Details**

HmIP-BSL device channel structure:
- **Channel 0**: `DEVICE_BASE` (maintenance/status)
- **Channel 1**: `SWITCH_CHANNEL` with `DOUBLE_INPUT_SWITCH` (relay control)
  - State changes on every toggle (physical or programmatic)
  - NOT suitable for timestamp-based button detection
- **Channels 2-3**: `NOTIFICATION_LIGHT_CHANNEL` (button backlights)

Button press events are properly sent via `DEVICE_CHANNEL_EVENT` with the actual channel index that was pressed. The enhanced logging will help identify which channel indices correspond to upper vs lower buttons.

**Enhanced Logging Example**
```
Button press: device=3014F711A00018D9992FBF94 (HmIP-BSL), channel=2 (Upper Button, NOTIFICATION_LIGHT_CHANNEL), event=PRESS_SHORT
```

**Impact**
- ✅ HmIP-BSL button presses now trigger events only on actual physical button presses
- ✅ No false events when toggling lights via Home Assistant
- ✅ Automations triggered by button presses work correctly
- ✅ Enhanced logging helps identify which channel corresponds to upper vs lower buttons
- ✅ Event detection more reliable and predictable

**Files Changed**
- `custom_components/hcu_integration/discovery.py` - Removed DOUBLE_INPUT_SWITCH from timestamp-based event detection
- `custom_components/hcu_integration/event.py` - Enhanced logging with device model, channel info, and event type

---

## Version 1.15.7 - 2025-11-11

### 🐛 Bug Fixes

**Fix HmIP-BSL Multicolor Functionality - Issue #99**

Fixed a critical bug where HmIP-BSL notification light color changes failed with error `404 UNKNOWN_REQUEST`. The issue affected all HmIP-BSL devices with `NOTIFICATION_LIGHT_CHANNEL` (notification light backlights).

**Root Cause**

The `HcuLight` class was incorrectly sending both `simpleRGBColorState` and `dimLevel` parameters in a single API call to `/hmip/device/control/setSimpleRGBColorState`. The HCU API endpoint only accepts color and optical signal behavior parameters, not dimLevel.

**Previous behavior (broken):**
```python
# Single API call with both color and dimLevel
payload = {"simpleRGBColorState": "RED", "dimLevel": 1.0}
# Result: 404 UNKNOWN_REQUEST error
```

**What Was Fixed**

- **Separated API calls**: Color changes now use `/hmip/device/control/setSimpleRGBColorState` (color only)
- **Separate dimming**: Brightness changes use `/hmip/device/control/setDimLevel` (separate call)
- **Preserved functionality**: All features still work (color, brightness, effects)
- **Proper sequencing**: When both color and brightness are changed, color is set first, then brightness

**New behavior (working):**
```python
# Color/effect API call (no dimLevel)
payload = {"simpleRGBColorState": "RED", "opticalSignalBehaviour": "BLINKING_MIDDLE"}

# Separate brightness API call if needed
await async_set_dim_level(device_id, channel, dim_level)
```

**Impact**
- ✅ HmIP-BSL notification lights now properly change colors
- ✅ All 7 colors work: WHITE, RED, BLUE, GREEN, YELLOW, PURPLE, TURQUOISE
- ✅ Brightness control works independently
- ✅ Optical signal effects (blinking, flashing, billowing) work correctly
- ✅ No more 404 errors when setting colors

---

## Version 1.15.6 - 2025-11-10

### 🐛 Bug Fixes

**Fix Siren JSON Serialization Error (frozenset)**

Fixed a `TypeError: Type is not JSON serializable: frozenset` error that occurred when Home Assistant tried to serialize the siren entity's state and attributes. This error appeared in the logs when the siren entity was loaded or updated.

The issue was caused by assigning the `HMIP_SIREN_TONES` `frozenset` directly to the `_attr_available_tones` attribute in `siren.py`.

The attribute is now correctly converted from a `frozenset` to a `list` during the entity's initialization, resolving the serialization issue.

**Fix Entities Stuck in "Unavailable" State After Startup**

Fixed a bug where entities (especially battery-powered ones like sirens `HmIP-ASIR2` or weather sensors) could get stuck in an `unavailable` state with a `restored: true` attribute after a Home Assistant restart.

- **Root Cause:** The integration would load the entity, which defaults to `unavailable` when restored. It would then wait for a *new* WebSocket event from the device to trigger its first state update. Battery-powered devices that don't change state often (e.g., a siren that isn't triggered) would never send this update, causing the entity to remain "unavailable" indefinitely, even though the coordinator's initial state fetch confirmed it was reachable.
- **The Fix:** The coordinator now forces a state update for *all* discovered entities (devices, groups, and home) immediately after the initial `get_system_state()` call succeeds during startup. This ensures all entities refresh their availability and state from the coordinator's cache right away, moving them from the "restored" state to their correct (available) state without waiting for a push event.

---

## Version 1.15.5 - 2025-11-10

### 🐛 Bug Fixes

#### Fix Missing Entities for Weather Sensors and Other Devices - Issue #71

**Fixed: Entities Disappearing After Updates (HmIP-SWO-PR Weather Sensor)**

Weather sensor entities (HmIP-SWO-PR) and potentially other devices were showing as "unavailable" or missing after HCU updates.

**Root Cause**

The base entity's availability check included `if not self._channel`, which evaluates to `True` when channel data is an empty dict `{}`. This was introduced in commit 2d137f86 (Oct 17, 2025) as part of "Improved Entity Availability" changes.

The problem:
- When `self._channel` returns `{}` (empty dict), Python evaluates `not {}` as `True`
- This caused entities to become unavailable even though devices were reachable
- Many channels (weather sensors, sirens, etc.) have sparse data or are temporarily omitted from HCU updates
- This is normal HCU behavior - channels don't need all state fields in every update

**What Was Fixed**

- **Removed faulty check**: Removed `not self._channel` from base `HcuBaseEntity.available` property
- **Robust availability logic**: Availability now based solely on:
  - Client connection status
  - Device data presence (not channel data)
  - Device reachability (permanentlyReachable flag or maintenance channel status)
- **Updated siren override**: Simplified siren's `available` override to focus on diagnostic logging
- **Documentation**: Added detailed comments explaining why channel data check is intentionally omitted

**Impact**
- ✅ Weather sensor entities (HmIP-SWO-PR) remain available with sparse channel data
- ✅ All entities more resilient to temporary channel data omissions from HCU updates
- ✅ Fixes the same root cause that affected sirens in issue #82
- ✅ No more entities disappearing after integration updates

#### Add Missing Weather Sensor Entities - Issue #22

**Fixed: Rain Counter and Sunshine Duration Sensors Not Created (HmIP-SWO-PL Weather Sensor Plus)**

Weather sensor Plus devices (HmIP-SWO-PL) were missing entities for rain counters and sunshine duration, causing these sensors to show as "unavailable" with "restored: true" in diagnostics.

**Root Cause**

Feature mappings were missing from `const.py` for the following weather sensor fields:
- `totalRainCounter` - Total accumulated rainfall
- `todayRainCounter` - Today's rainfall
- `yesterdayRainCounter` - Yesterday's rainfall
- `totalSunshineDuration` - Total sunshine duration
- `todaySunshineDuration` - Today's sunshine duration
- `yesterdaySunshineDuration` - Yesterday's sunshine duration

Without these mappings, the discovery logic skipped creating entities for these features even though the data was present in the HCU API.

**What Was Fixed**

- **Added rain counter sensors**: All three rain counter features now properly create precipitation sensors
  - Uses `UnitOfPrecipitationDepth.MILLIMETERS` with appropriate device class
  - `totalRainCounter` uses `TOTAL_INCREASING` state class (cumulative total)
  - `todayRainCounter` and `yesterdayRainCounter` use `TOTAL` state class (daily measurements)
- **Added sunshine duration sensors**: All three sunshine duration features now properly create duration sensors
  - Uses `UnitOfTime.MINUTES` with duration device class
  - Proper state classes for total, today, and yesterday measurements
- **Proper icons**: Added weather-appropriate icons (weather-pouring, weather-rainy, weather-sunny, etc.)

**Impact**
- ✅ HmIP-SWO-PL devices now expose all 6 additional weather sensors
- ✅ Rain counter sensors properly track daily and total precipitation
- ✅ Sunshine duration sensors track daily and total sun exposure
- ✅ Entities will be auto-discovered on next integration reload
- ✅ Previously "unavailable" entities will become functional again

---

## Version 1.15.4 - 2025-11-10

This release includes critical bug fixes for siren entities, climate ECO mode, button events, and temperature sensors.

### 🚨 Critical Siren Fix (HmIP-ASIR2) - Issue #82, PR #95

**Fixed: Siren Entity Incorrectly Showing as Unavailable**

HmIP-ASIR2 siren entities were showing as "unavailable" in Home Assistant despite devices being reachable and functioning normally.

#### Root Cause
The base entity's availability check included `if not self._channel`, which evaluates to `True` when channel data is an empty dict `{}`. Since empty dicts are falsy in Python, this caused false unavailability.

ALARM_SIREN_CHANNEL behaves differently from other channel types:
- Often has minimal/sparse data (only metadata fields like `functionalChannelType`, `groups`, `channelRole`)
- May be omitted entirely from some HCU state updates
- Doesn't require state fields when siren is inactive (no `acousticAlarmActive` field present)

#### What Was Fixed
- **Override `available` property**: Removed faulty `not self._channel` check that caused false unavailability
- **Device reachability**: Availability now based solely on device reachability (`permanentlyReachable` flag or maintenance channel status)
- **State synchronization fix**: Critical bug where siren remained stuck in "on" state when `acousticAlarmActive` field disappeared from updates
- **Diagnostic logging**: Added comprehensive logging to troubleshoot availability issues
- **Code quality**: Replaced magic strings with constants (`CHANNEL_TYPE_ALARM_SIREN`, `HMIP_CHANNEL_KEY_ACOUSTIC_ALARM_ACTIVE`)

#### Impact
- ✅ Siren entities remain available as long as device is reachable
- ✅ Empty or missing channel data doesn't affect availability
- ✅ State correctly updates to "off" when `acousticAlarmActive` field is missing
- ✅ No more stuck "on" state issue
- ✅ Reduced log noise during normal sparse updates

### 🌡️ Temperature Sensor Fix (HmIP-STE2-PCB) - Issue #28, PR #90

**Fixed: Missing Temperature Values for External Temperature Sensors**

HmIP-STE2-PCB devices now properly report all three temperature values.

#### What Was Fixed
- **Added `TEMPERATURE_SENSOR_2_EXTERNAL_DELTA_CHANNEL`** to channel type mapping
- **Fixed HcuTemperatureSensor class**: Changed from hardcoded field names to dynamic `_feature` attribute access
- **Three temperature sensors now discovered**:
  - `temperatureExternalOne` - First external sensor
  - `temperatureExternalTwo` - Second external sensor
  - `temperatureExternalDelta` - Temperature difference between sensors

#### Root Cause
The original implementation hardcoded specific temperature field names, causing external sensors to return no values. The sensor class now dynamically accesses the correct temperature field for each entity.

### 🌡️ Climate ECO Mode Fix - PR #92

**Fixed: Climate Preset Mode Not Updating for ECO Modes**

Climate entities now correctly show "ECO" preset mode when ECO mode is activated globally.

#### What Was Fixed
- **Switched to INDOOR_CLIMATE functional group**: Fixed incorrect functional group lookup (was checking `HEATING` instead of `INDOOR_CLIMATE`)
- **Support for PERIOD absence type**: Extended ECO mode recognition to include both `PERMANENT` and `PERIOD` absence types
- **Added `ecoAllowed` validation**: ECO mode only activates when room permits it (thermostats can, underfloor heating cannot)
- **Added absence type constants**: Introduced `ABSENCE_TYPE_PERIOD` and `ABSENCE_TYPE_PERMANENT` to replace magic strings

#### Impact
- ✅ Rooms with thermostats correctly display "ECO" preset when global ECO mode is active
- ✅ Rooms with underfloor heating remain in "Standard" mode (as they cannot use ECO)
- ✅ Preset mode attribute updates properly in Home Assistant UI

### 🔘 Button Event Fix (HmIP-BSL) - Issues #91, #81, PR #93

**Fixed: HmIP-BSL Button Events Not Firing**

Button presses on HmIP-BSL switch actuators now properly trigger `hcu_integration_event` events for automations.

#### Root Cause
The integration incorrectly assumed HmIP-BSL devices used `KEY_CHANNEL` for buttons. In reality, these devices use `SWITCH_CHANNEL` with `DOUBLE_INPUT_SWITCH` configuration. The event extraction method also only processed `DEVICE_CHANGED` events, but HmIP-BSL sends `DEVICE_CHANNEL_EVENT` type events for button presses.

#### What Was Fixed
- **Corrected channel type detection**: Properly handle `SWITCH_CHANNEL` with dual input configuration
- **Fixed event type handling**: Process both `DEVICE_CHANGED` and `DEVICE_CHANNEL_EVENT` events
- **Button events now fire** for all press types: SHORT, LONG, LONG_START, LONG_STOP

#### Device Structure
HmIP-BSL (BRAND_SWITCH_NOTIFICATION_LIGHT) contains:
- Channel 0: Device base configuration
- Channel 1: Switch channel with dual input (physical buttons)
- Channels 2-3: Notification light channels (button backlights)

### 💡 Optical Signal Behavior Support (HmIP-BSL) - Issue #81, PR #93

**Added: Visual Effect Support for HmIP-BSL Notification Lights**

Notification light channels on HmIP-BSL devices now support configurable visual effects beyond simple on/off.

#### New Visual Effects
- **OFF** – No light
- **ON** – Steady illumination
- **BLINKING_MIDDLE** – Medium-speed blinking effect
- **FLASH_MIDDLE** – Medium-speed flash effect
- **BILLOWING_MIDDLE** – Medium-speed pulsing/breathing effect

#### Usage
Set visual effects independently or combine with color and brightness:
```yaml
service: light.turn_on
target:
  entity_id: light.bsl_switch_backlight
data:
  effect: "BLINKING_MIDDLE"
  hs_color: [0, 100]  # Red
  brightness: 255
```

#### Technical Implementation
- Added `opticalSignalBehaviour` field support in HcuNotificationLight
- Immutable `HMIP_OPTICAL_SIGNAL_BEHAVIOURS` constant with all available effects
- Effect list exposed via `effect_list` attribute for Home Assistant UI

---

## Version 1.15.0 - 2025-11-09

### 🪟 Window Sensor State Enhancement (HmIP-SRH)

**Add Dedicated Window State Sensor (GitHub Issue #48)**

The v1.10.0 fix for window state was incomplete - it only exposed the state as an attribute on a binary sensor. This release adds a proper text sensor that shows the actual window state.

#### What Changed
- **New Sensor Entity**: "Window State" sensor now displays "Open", "Tilted", or "Closed" as its main state value
- **Binary Sensor Kept**: The existing binary sensor (on/off) remains for compatibility
- **No More Hidden Attributes**: Users can now see the window state directly without checking attributes

#### Why This Matters
- **v1.10.0 limitation**: Window state (OPEN/TILTED/CLOSED) was only visible as an attribute on the binary sensor
- **Binary sensors** can only show on/off in their main state, making the tilted state invisible in the UI
- **User experience**: The new text sensor makes the state immediately visible in dashboards and automations

#### Usage
Both entities will now appear for HmIP-SRH devices:
- **Binary Sensor**: "Window" - Shows on (open or tilted) / off (closed)
- **Text Sensor**: "Window State" - Shows Open / Tilted / Closed

Use the text sensor in automations that need to distinguish between open and tilted states:
```yaml
trigger:
  - platform: state
    entity_id: sensor.bedroom_window_window_state
    to: "Tilted"
```

### 🔘 Switch Actuator Enhancements (HmIP-BSL)

**Fix Button Event Detection (GitHub Issue #67)**

Button presses on HmIP-BSL switch actuators now properly generate `hcu_integration_event` events.

#### What Was Fixed
- Added `KEY_CHANNEL` to `EVENT_CHANNEL_TYPES`
- BSL button inputs (channels 1-2) now trigger events for automations
- Supports all button press types: SHORT, LONG, LONG_START, LONG_STOP

#### Usage
Button events now work as documented:
```yaml
trigger:
  - platform: event
    event_type: hcu_integration_event
    event_data:
      device_id: "YOUR_BSL_DEVICE_ID"
      channel: 1
      type: "KEY_PRESS_SHORT"
```

**Add Full Color Support for Backlight (GitHub Issue #68)**

The illuminated backlight on HmIP-BSL switches now supports all 7 colors instead of just white.

#### Supported Colors
- **White** (default)
- **Blue**
- **Green**
- **Turquoise** (Light Blue)
- **Red**
- **Violet** (Purple)
- **Yellow**

#### How It Works
- HcuLight entities now detect and handle `simpleRGBColorState`
- Automatic color mapping from HS color picker to closest BSL color
- Uses same RGB system as HmIP-MP3P notification lights

#### Usage
Set backlight color from UI or automation:
```yaml
service: light.turn_on
target:
  entity_id: light.bsl_switch_backlight
data:
  hs_color: [240, 100]  # Blue
```

**Technical Implementation:**
- Added `_has_simple_rgb` detection in HcuLight.__init__
- Enhanced `hs_color` property to read `simpleRGBColorState`
- Added `_hs_to_simple_rgb()` color conversion method
- Modified `async_turn_on()` to use `/hmip/device/control/setRgbDimLevel` API for RGB devices

### 🔊 Siren Enhancements (HmIP-ASIR2)

**Implement Tone and Duration Support for Alarm Sirens (GitHub Issue #73)**

The HMIP-ASIR2 and compatible siren devices now properly support acoustic signal selection and duration control.

#### New Siren Features
- **Tone Selection** - Choose from 18 different acoustic signals:
  - Frequency patterns (rising, falling, alternating, etc.)
  - Status tones (battery, armed, event, error)
  - Customizable alert sounds
- **Duration Control** - Set alarm duration in seconds (default: 10s)
- **Full Home Assistant Siren Integration** - Proper `siren.turn_on` service support with tone and duration parameters

#### Usage Example
```yaml
service: siren.turn_on
target:
  entity_id: siren.alarm_siren
data:
  tone: "FREQUENCY_RISING"
  duration: 30
```

**Technical Details:**
- Added `HMIP_SIREN_TONES` constant with 18 available tones
- Updated siren entity to support `SirenEntityFeature.TONES` and `SirenEntityFeature.DURATION`
- Switched from switch API to sound file API for proper siren control
- Default tone: `FREQUENCY_RISING`, default duration: 10 seconds

### 🪟 Cover Device Support (HmIP-HDM1)

**Add Support for HunterDouglas Blind Devices (GitHub Issue #64)**

Added channel mapping for HmIP-HDM1 (HunterDouglas) roller blinds to properly expose cover entities.

#### Changes
- Added `BRAND_BLIND_CHANNEL` mapping for HunterDouglas and third-party blind devices
- Ensures HDM1 devices appear as controllable covers in Home Assistant

**Note:** This fix is based on device type analysis. If your HDM1 device still doesn't appear, please provide diagnostics via GitHub issue #64.

---

## Version 1.14.0 - 2025-11-09

### 🔒 Door Lock Enhancements (HmIP-DLD)

**Complete Implementation of Lock State Properties (GitHub Issue #30, PR #75)**

This release significantly enhances the door lock integration by implementing missing state properties and diagnostic capabilities that were previously claimed but not implemented.

#### New Lock State Properties
- **`is_locking`** - Returns `True` when lock motor is actively locking
- **`is_unlocking`** - Returns `True` when lock motor is actively unlocking
- **`is_jammed`** - Returns `True` when lock mechanism is jammed
- **`is_opening`** - Returns `True` when lock is opening the latch

These properties enable:
- Real-time lock operation status in Home Assistant UI
- Automation triggers based on lock state (e.g., notify if jammed)
- Better visual feedback during lock/unlock operations

#### Enhanced Diagnostic Attributes

New state attributes for troubleshooting:
- **`motor_state`** - Current motor status ("STOPPED", "LOCKING", "UNLOCKING", "OPENING", "JAMMED")
- **`lock_jammed`** - Boolean jam detection from device channel 0
- **`auto_relock_enabled`** - Whether auto-relock is configured
- **`auto_relock_delay`** - Auto-relock delay in seconds
- **`has_access_authorization`** - Whether plugin has any access authorization
- **`authorized_access_channels`** - List of authorized access profile channels

#### Access Control Diagnostics & Error Messages

**New Permission Error Detection:**
- Detects `ACCESS_DENIED` and `INVALID_REQUEST` errors
- Provides step-by-step instructions for fixing access control issues
- Documents known HCU limitation where plugin user appears grayed out in HomematicIP app
- Helps users diagnose authorization problems via state attributes

**Improved Error Messages:**
- Clear guidance for PIN configuration issues
- Detailed instructions for access profile setup
- Explanation of HCU firmware limitations
- Links to documentation

#### Technical Improvements

**Accurate State Reporting:**
- Fixed critical logic error where properties returned `None` for known states instead of `False`
- `None` now correctly means "state unknown" (device offline/data missing)
- `False` correctly means "we know it's not in this state"
- `True` correctly means "we know it is in this state"
- Improves UI rendering and automation reliability

**Implementation Based on Real Device Data:**
- Refined using actual HmIP-DLD diagnostic data (firmware 1.4.12)
- Removed speculative field checks (`activityState`, `errorJammed`, `sabotage`) that don't exist on HmIP-DLD
- Uses correct field names: `lockJammed` on channel 0, `motorState` and `lockState` on channel 1
- Verified against `IOptionalFeatureDeviceErrorLockJammed` supported feature

**Code Quality:**
- Refactored for maintainability (reduced code duplication)
- Dictionary comprehensions for cleaner attribute assignment
- Proper `None` vs `False` semantics throughout
- Clear inline documentation

#### Known Limitations

**HCU Access Control Issue (Issue #30):**
The HomematicIP app may show the "Home Assistant Integration" plugin user as grayed out or expired, preventing assignment to access profiles. This is a known HCU firmware limitation, not an integration bug. The integration now:
- Detects this situation and provides helpful error messages
- Exposes `has_access_authorization` attribute for easy diagnosis
- Explains the issue and workarounds in logs

Users experiencing access control issues should:
1. Check the `has_access_authorization` state attribute
2. Follow error message instructions for access profile setup
3. Monitor for HCU firmware updates that may fix this limitation

#### References
- GitHub Issue #30 - PIN and access control configuration
- PR #75 - Complete door lock implementation
- Diagnostic data from real HmIP-DLD devices (firmware 1.4.12)

---

## Version 1.13.0 - 2025-11-08

### ✨ New Device Support

**HmIP-DRI32 Wired Input Actuator (Issue #31)**
- Added support for HmIP-DRI32 (32-channel digital radio input actuator)
- All 32 input channels now properly discovered
- Button press events fire via `hcu_integration_event`
- Contact state binary sensors created for all channels
- Device disabled by default (input-only device with many channels)

### 🔧 Technical Improvements

**Platform Override Infrastructure (Issue #38 - Partial)**
- Added `CONF_PLATFORM_OVERRIDES` configuration constant
- Lays groundwork for future light/switch toggle feature
- Full UI implementation deferred to future release

---

## Version 1.12.1 - 2025-11-08

### 🐛 Bug Fixes

**Duplicate Group Entity Names**
- Fixed issue where group entity names were displayed twice (e.g., "Wohnzimmer Wohnzimmer")
- Affected heating groups (HcuClimate), cover groups (HcuCoverGroup), and switching/light groups
- Root cause: Missing `_attr_has_entity_name = False` flag caused Home Assistant to combine device name with entity name
- Users will see correct single names after restarting Home Assistant

**Auto-Created Meta Groups**
- Integration now skips auto-created meta groups for SWITCHING and LIGHT types
- These groups are automatically created by HCU for rooms and were causing unexpected/redundant entities
- User-created functional groups (without `metaGroupId`) are still discovered and created
- Significantly reduces entity clutter from unwanted auto-generated groups

---

## Version 1.12.0 - 2025-11-08

### ✨ Enhancements

**SWITCHING and LIGHT Group Entity Support (Issue #44)**
- Added support for SWITCHING group entities that control multiple switches together
- Added support for LIGHT group entities that control multiple lights together
- Achieves feature parity with the official Homematic IP cloud integration for these group types
- Groups are automatically discovered from HCU configuration and appear as switch/light entities in Home Assistant
- Example: A "Living Room Lights" group can now control all living room lights with a single on/off toggle
- Groups use the `/hmip/group/switching/setState` API endpoint for synchronized control

### 🔧 Technical Improvements

**Clean Architecture for Group Entities**
- Created `HcuSwitchingGroupBase` base class to eliminate code duplication between switch and light groups
- Implemented `SwitchingGroupMixin` for shared state management logic (optimistic updates, error handling)
- Optimistic state updates provide instant UI feedback before API confirmation
- Robust error handling with automatic state rollback if API calls fail
- Dictionary-based discovery mapping in `discovery.py` for scalable group type handling
- Consistent type hints across all group entity classes (`dict[str, Any]`)
- Removed unused group entity mappings from `class_module_map` for clearer discovery flow

**Code Quality**
- Reduced code duplication by ~50 lines through base class consolidation
- Direct attribute access instead of `getattr()` for improved code clarity
- Consistent entity naming pattern across all group types

---

## Version 1.11.0 - 2025-11-07

### 🐛 Bug Fixes

**HCU Device Registration in Multi-Access-Point Setups (Issue #42)**
- Fixed critical issue where the actual HCU device was missing from device registry in setups with multiple access points (HCU + HAP + DRAP)
- Home-level entities (vacation mode, alarm) are now correctly assigned to the HCU device instead of auxiliary access points
- Updated logic to prioritize actual HCU models (HmIP-HCU-1, HmIP-HCU1-A) when determining the primary device
- HAP and DRAP are now properly recognized as auxiliary access points connected to the main HCU
- Devices that were incorrectly associated with HAP now correctly show as children of the HCU

**Heating Group Auto Mode Preservation (Issue #35)**
- Fixed behavior where manually adjusting temperature switched from AUTO to MANUAL mode permanently
- Temperature adjustments in AUTO mode now create temporary overrides that automatically revert at the next scheduled temperature change
- Matches the original Homematic IP app behavior - users can adjust temperature without disrupting heating schedules
- System automatically resumes scheduled operation at the next programmed time
- Manual temperature adjustments in AUTO mode no longer force the system into MANUAL mode unless explicitly set to HEAT

**Alarm Siren Device Classification (Issue #50)**
- HmIP-ASIR2 alarm siren now properly classified as siren entity instead of switch
- Users can now use `siren.turn_on` and `siren.turn_off` services
- Added new siren platform with proper entity features
- Created `HcuSiren` class for alarm siren devices

### ✨ Enhancements

**Door Opener Button for HmIP-FDC (Issue #41)**
- Added button entity to trigger door opener on HmIP-FDC (Full Flush Door Controller)
- Creates "Open Door" button that sends 1-second pulse to open door
- Provides the primary functionality that was missing from this device
- Matches functionality available in the Homematic IP app

**HmIP-RC8 Button Events (Issue #33)**
- Confirmed HmIP-RC8 button events are working correctly (supported since v1.8.1)
- `SINGLE_KEY_CHANNEL` is included in event handling
- Added documentation for proper automation configuration (channel numbers should not be quoted)

### 🔧 Technical Improvements

- Added Platform.SIREN to platforms list
- Updated HCU_MODEL_TYPES to correctly identify actual HCU devices (removed HmIP-HAP as it's an auxiliary access point)
- Enhanced device identification logic with proper fallback hierarchy
- Refactored turn_on/turn_off methods to eliminate code duplication (DRY principle)
- Added deterministic sorting for consistent primary HCU selection across restarts

---

## Version 1.10.0 - 2025-11-07

### 🐛 Bug Fixes

**Window Sensor State Attribute (Issue #48)**
- HmIP-SRH window sensors now expose the actual window state ("OPEN", "TILTED", or "CLOSED") as a state attribute
- Users can now distinguish between tilted and fully open windows in automations
- Binary sensor still shows on/off (on for both OPEN and TILTED), but the `window_state` attribute provides the precise state

**Improved Lock PIN Error Messages (Issue #30)**
- Door lock PIN configuration errors now include detailed step-by-step instructions
- Error messages point directly to the configuration location in Home Assistant
- Includes link to README documentation for additional help

**Entity Prefix Applied to All Entities (PR #61 Critical Fixes)**
- Fixed critical bug where entity prefix was not applied to main entities on unlabeled channels
- Affected devices like HmIP-FROLL, HmIP-PSM-2, HmIP-BSM now correctly show prefix
- Added fallback logic to ensure prefix is applied even when labels are missing:
  - Device entities: Falls back to device label → model type → device ID
  - Climate groups: Falls back to group label → group ID
  - Cover groups: Falls back to group label → group ID
- Example: With prefix "House1", device "HmIP-PSM-2" becomes "House1 HmIP-PSM-2"
- Ensures prefix is applied to ALL entities without exception

### ✨ Enhancements

**Entity Name Prefix for Multi-Home Setups (Issue #43)**
- Added optional entity name prefix during integration setup
- Perfect for users with multiple HCU instances (e.g., multiple houses)
- Prefix is applied to all entity names (e.g., "House1 Living Room")
- Helps avoid naming conflicts and improves organization
- Configured in Settings → Devices & Services → Add Integration → Enter optional prefix

### 🔧 Code Quality Improvements

**Refactored Entity Prefix Logic (PR #61 Feedback)**
- Created `HcuEntityPrefixMixin` to eliminate code duplication across base entity classes
- Added `_apply_prefix()` helper method to centralize prefix application logic
- Consolidated prefix application in `_set_entity_name` method (DRY principle)
- Updated all entity classes to use the helper method (alarm_control_panel, binary_sensor, climate, cover, sensor)
- Removed redundant None check in `_set_entity_name` method
- Moved documentation URL to constant (`DOCS_URL_LOCK_PIN_CONFIG`) for better maintainability
- Improved code clarity and eliminated repetitive prefix logic across 6 files

### 📝 Documentation

**Issue #20 Closure**
- Confirmed that HmIP-WGS and HmIP-WRC6 button event issues were fixed in v1.8.1
- Created comprehensive closure documentation with testing instructions

**Issue #55 Investigation**
- Created diagnostics request for HmIP-BSM energy counter issue
- Requires user diagnostics file to determine root cause

---

## Version 1.9.0 - 2025-11-07

### 🐛 Bug Fixes

**Fixed Entity Naming for Unlabeled Channels (Issue #27)**
- Entities without channel labels now display with proper names instead of showing unique IDs
- Affected devices like HmIP-FROLL, HmIP-PSM-2, HmIP-BSM, and others now show friendly names (e.g., "HmIP-PSM-2" instead of "domain_id_1_on")
- Fixed by correctly setting `has_entity_name=True` when entity name is `None`

### ✨ Enhancements

**Comprehensive API Response Validation**
- Added robust validation for all API responses and WebSocket messages
- System now gracefully handles malformed data, missing fields, and unexpected types
- Enhanced error logging provides specific details for troubleshooting
- Improved stability when HCU returns unexpected data structures

**Enhanced Code Documentation**
- Improved docstrings throughout the codebase with detailed parameter and return descriptions
- Better inline comments explaining complex logic (button detection, state management)
- Added validation pattern documentation for developers

### 📚 New Developer Documentation

**CONTRIBUTING.md**
- Comprehensive developer guide (650+ lines)
- Detailed code structure explanation for all modules
- Testing guidelines and coverage goals (80% minimum, 90% target)
- Pull request process and coding standards
- Step-by-step guides for common tasks (adding devices, services)
- API response validation patterns and best practices
- Debugging tips and troubleshooting workflow

### 🧪 Testing

**Phase 3: Comprehensive Test Suite**
- Added 32+ unit tests covering core infrastructure
- 90%+ test coverage for api.py, coordinator, and entity modules
- Tests for all critical paths including edge cases
- Validates button detection, state management, and event processing

### 🔧 Technical Improvements

**API Client Enhancements**
- `get_system_state()`: Validates response structure and ensures critical keys exist
- `process_events()`: Type validation and required field checking
- `_handle_incoming_message()`: Message structure validation with specific error logging
- `_handle_device_channel_events()`: Validates complete event data before processing

---

## Version 1.8.1 - 2025-10-26

### 🐛 Critical Bug Fix

**Fixed Button Events for Stateless Devices (HmIP-WGS, HmIP-WRC6, and similar)**

This release fixes a critical bug that prevented button press events from firing for certain wall-mounted switches and remote controls, specifically:
- **HmIP-WGS** (Wall-mounted Glass Switch)
- **HmIP-WRC6** (6-button Wall Remote)
- Other devices with button channels that don't report channel-level timestamps

**What was broken:**
- Button presses on these devices were received via WebSocket but never triggered `hcu_integration_event` events
- Users couldn't create automations for these buttons
- Events monitor showed no activity when buttons were pressed

**What's fixed:**
- Implemented dual-path button detection that works with both timestamp-based and stateless button channels
- Events now fire correctly for all button devices regardless of their timestamp behavior
- Added debug logging to help diagnose button press detection

**Technical Details:**
The fix enhances the `_handle_event_message` method in the coordinator to:
1. Track which specific channels are present in WebSocket events (not just which devices)
2. Detect button presses via timestamp changes (existing behavior - preserved)
3. Detect button presses via event presence for channels without timestamps (new fallback)
4. Prevent false positives by only firing events for channels actually in the WebSocket message

This change is **backward compatible** and won't affect existing button devices that already work correctly.

**User Action Required:**
If you have HmIP-WGS or HmIP-WRC6 devices (or similar button devices that weren't working), please:
1. Update to version 1.8.1
2. Restart Home Assistant
3. Test your buttons using Developer Tools → Events (listen to `hcu_integration_event`)
4. Refer to the updated README for automation examples

---

## Version 1.8.0 - 2025-10-24

**<-- This feature is still in beta and still has some issues**

### 🐛 Bug Fixes
* **Fixed Unresponsive Switches:** Resolved a critical bug that caused certain switch models (e.g., `HmIP-BSM`, `HmIP-DRSI1`) to become unresponsive to commands from Home Assistant. The integration now correctly sends the `onLevel` parameter to the API for all switch operations.
* **HmIP-FSI16 Full Channel Support:** Fixed an issue where only the first 8 channels of the `HmIP-FSI16` (16-channel flush-mount switch actuator) were created. All 16 switch entities are now correctly discovered and functional.
* **HmIP-ESI Energy Meter Support:** Added comprehensive support for all features of the `HmIP-ESI` (Energy Meter and Sensor Interface). New sensors are now created for:
  * Energy Counter T1 (Low Tariff)
  * Energy Counter T2 (High Tariff)
  * Power Production (Current Grid Feed-in)
  * Energy Production (Total Grid Feed-in)
* **HmIP-SLO Light Sensor:** The `illumination` sensor for the `HmIP-SLO` (Light Sensor Outdoor) is now correctly discovered and created.
* **Alarm Control Panel Syntax Error:** Fixed a syntax error in `alarm_control_panel.py` that could prevent the alarm panel from arming correctly.
* **Duplicate Siren Entities:** Removed a redundant mapping for `acousticAlarmActive` that was causing duplicate siren switch entities to be created for some devices.

### ✨ Improvements
* **Modernized Stateless Button Handling:** Refactored how stateless buttons (e.g., wall switches like `HmIP-BRC2`, remote controls like `HmIP-KRC4`) are handled. These devices no longer create button entities and instead fire `hcu_integration_event` on the Home Assistant event bus, which is the standard and more flexible way to handle stateless device triggers in automations. See the README for automation examples.
* **Instant UI Updates for Absence Modes:** Implemented proactive state synchronization for Vacation and Eco modes. When you activate an absence mode from Home Assistant, related entities (such as `binary_sensor.vacation_mode`) now update instantly, matching the behavior of the official Homematic IP app for a more responsive user experience.
* **Enhanced Device Compatibility:** Added numerous new device types and channel type definitions to improve device mapping accuracy and ensure better support for future Homematic IP devices.

---

## Version 1.6.1 - 2025-10-20

### 🚀 New Device Support
* Added support for `HmIP-FSI16` (`FULL_FLUSH_SWITCH_16`), enabling all 16 switch channels.
* Added support for the `HmIP-WGS` (Wall-mounted Glass Switch), creating switch entities for its channels.
* Added support for `HmIP-BS2` (`BRAND_SWITCH_2`), ensuring it is correctly identified as a switch.
* The backlight of the `HmIP-WGS` is now properly discovered and created as a light entity, allowing for brightness control.

### 🐛 Bug Fixes
* **Fixed Unresponsive Switches:** Corrected a bug that caused certain switch models, particularly the `HmIP-BSM`, to become unresponsive to commands from Home Assistant. The API payload now includes the `onLevel` parameter for broader compatibility.

### ✨ Improvements
* **Optimistic State for Switches:** All switch entities now use optimistic state updates. This provides instant feedback in the Home Assistant UI when a switch is toggled, improving the user experience.
* **Robust Switch Error Handling:** Added `try...except` blocks to switch turn-on/off actions. If a command fails, an error is logged, and the entity's state reverts, preventing it from getting stuck in an incorrect state.

---

## Version 1.5.0 - 2025-10-15

### ✨ Improvements
- **Robust Service Handling:** Service calls (like play_sound and activate_party_mode) have been refactored to call entity methods directly instead of parsing entity IDs. This makes the implementation more robust and less prone to breaking with future changes.
- **Idiomatic Button Events:** Stateless physical buttons (like wall switches) no longer create a confusing button entity in the UI. Instead, they now fire a hcu_integration_event on the Home Assistant event bus, which is the standard and more flexible way to handle stateless device triggers in automations.
- **Smarter Climate Entity:** The climate card will now correctly display temperature and humidity readings from radiator thermostats (HmIP-eTRV) if a dedicated wall thermostat is not present in the room.
- **Smoother Climate Control:** The logic for changing HVAC modes has been completely overhauled to provide an instant, optimistic UI update. This eliminates the "jumpy" or delayed feeling when switching between Auto, Heat, and Off.
- **Dynamic Climate Presets:** The climate entity now dynamically discovers and displays heating profiles from the HCU as presets, allowing users to switch between their custom heating schedules directly from Home Assistant.
- **Improved Entity Availability:** The core logic for determining if an entity is available has been hardened. Entities will now more reliably report as unavailable if the connection to the HCU is lost or if the device data is temporarily missing from the API payload, fixing issues for devices like the HmIP-SWO-PR Weather Sensor and various switch models.
- **Enhanced Lock State:** The lock entity now reports jammed, locking, and unlocking states for better real-time feedback.
