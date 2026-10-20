# ⚠️ BREAKING CHANGES

> 💡 **Tip:** The best way to get notified about issues in Home Assistant
> is [Spook](https://github.com/frenck/spook) — a powerful HACS integration
> that surfaces broken entities and config issues directly in the HA Repairs panel.
> See [spook.boo](https://spook.boo) for more.

---

## Unreleased

- **`activate_party_mode` with both `end_time` and `duration`:** such a call used to start party mode with `end_time` and ignore `duration`. It now fails with an error, as `end_time` and `duration` were always documented as mutually exclusive. Remove one of the two from the action.
- **Entity names in German installations:** entity names are now translated. In a German Home Assistant, existing entities show German names (for example "Wohnzimmer Thermostat Temperatur"); their entity IDs do not change. Entities created after the update get German-based entity IDs, as Home Assistant does for every translated integration. Names you set yourself are kept. English installations are not affected.

## 2.4.0 - 2026-10-19

- **Entity names follow Home Assistant's naming scheme:** every entity is now named after its device, followed by the entity name. Entity IDs do not change, so automations, scripts and dashboards keep working. Only the displayed names change:
  - Entities on labelled channels show the device name first, e.g. "Wall Switch Kitchen Light" instead of "Kitchen Light".
  - The alarm panel and vacation mode sensor belong to the HCU device: "Home Control Unit Alarm" and "Home Control Unit Vacation mode" instead of "Homematic IP Alarm" and "Vacation Mode".
  - HCU sensors drop the duplicated "Homematic IP HCU" in their names.
  - Unlabelled channels of devices with several channels get a number, e.g. "Garden Actuator Switch 2" instead of just "Garden Actuator".
  - If you renamed an entity yourself, your name is kept.
- **Home Assistant 2026.8.0 or newer required:** older versions are no longer supported. HACS will not offer this update on older Home Assistant versions.
- **Entity name prefix removed:** the prefix option was taken out of the setup in 2.1.0; prefixes stored in older config entries are now removed as well. A repair notice explains the change. To tell devices of several hubs apart, assign them to areas or floors, or rename the devices.

## 2.3.0 - 2026-10-18

- **Heating groups at minimum temperature now report `off`:** A heating group in manual mode whose setpoint is at or below its minimum temperature (for example 4.5 °C) now shows HVAC mode `off` instead of `heat`. Automations or templates that check for `heat` in this situation must be updated.
- **Eco preset is only listed while Eco is active:** Eco mode is home-wide and cannot be set per heating group (see 1.19.6, #268). The `eco` preset now only appears in a thermostat's preset list while the home-wide Eco/absence mode is active, so it shows the real state. Use `hcu_integration.activate_eco_mode` to turn Eco on.
- **Integration actions now report errors:** Actions such as `hcu_integration.play_sound`, `activate_party_mode`, `switch_on_with_time`, `activate_vacation_mode` and `send_api_command` used to log failures and finish silently. They now raise an error, so a failing action stops the automation or script, as Home Assistant expects. Add `continue_on_error: true` to the action if your automation should keep running. When an action targets several entities, every entity is still processed first and one error lists all entities that failed.
- **HA Entity Bridge (alpha) devices report more features:** Bridged devices now also report the on-time (auto-off) feature, and features of devices that are currently off. Devices that were already added to the HCU may not show the new features until they are removed and added again in the Homematic IP app.

## 2.1.0 - 2026-06

- **Watering actuator entities changed from switch to valve:** `WATERING_ACTUATOR` and `WATERING_CONTROLLER` channels are now exposed as **valve** entities instead of switches. The entity IDs change from `switch.<name>` to `valve.<name>`. Any automations, scripts, or dashboards that reference the old `switch.*` entity IDs must be updated. The old switch entities will appear as unavailable after the update and can be removed from the entity registry.
- **Global PIN removed:** The optional System PIN field has been fully removed from the App User authentication flow. As announced in v2.0.0, the Global PIN is no longer supported. Use the per-device Access Authorization PIN (Device Code) exclusively. Existing installations are not affected — the PIN was never stored in the config entry and no migration is required.
- **Entity prefix option removed:** The "Entity Prefix" field has been removed from the setup and options flow — new prefixes can no longer be configured. Existing prefixes already stored in your config entry are preserved and continue to work. Home Assistant automatically includes the area name in entity IDs, so assigning your devices to an area gives you a natural prefix for disambiguation (e.g. devices in an area named "House 1" will have entity IDs like `sensor.house_1_living_room_temperature`). Use **Settings → Areas** to organize and prefix your devices going forward.

## 2.0.0 - 2025-05-26

- **Doorbell sensor** now uses event type `ring` on `hcu_integration_event` (#40)
- **Button event types** (`ring`, `press`, `press_short`, `press_long`, `press_long_start`, `press_long_stop`) are now lowercase and no longer prefixed with `key_`
- **Event data field renamed:** `channel` → `subtype` in `hcu_integration_event`. Update your automations accordingly.
- **Button pair fix:** Button presses on combined button pairs were reported on the wrong channel. This has been corrected — update your automations if affected.
- **Switches** are now displayed as outlet, switch, or light depending on the setting in the Homematic IP app.  
  Note: Existing switch entities configured as "Light" may no longer appear under the switch platform. Check your automations and dashboards after updating.
- **Global PIN deprecation:** The Global PIN will be removed in a future version. Migrate all existing implementations to use the Device Code exclusively.

## 1.19.6 - 2026-01-23

- **Eco mode can no longer be set via heating groups**  
  (#268) Eco mode has been disabled for heating groups. To enable Eco mode globally, use the service `hcu_integration.activate_eco_mode`.

## 1.19.5 - 2026-01-13

- **WINDOW state supported only for `ROTARY_HANDLE_CHANNEL` (HmIP-SRH) (#175)**  
  For all other devices, these entities will be removed. Non-available entities must be deleted manually via **Settings → Devices & Services → Entities**.  
  Tip: Filter by **integration** and status **"not available"** to simplify cleanup. Multiple entities/devices can be deleted at once.
