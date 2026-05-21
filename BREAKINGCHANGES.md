# ⚠️ BREAKING CHANGES

## 💡 Best way to get notified about issues in Home Assistant

The best approach is using [Spook](https://github.com/frenck/spook) —
a powerful custom integration (installable via HACS) that extends
Home Assistant with advanced monitoring and repair tools.

It surfaces broken entities, missing integrations, and configuration
issues directly in the HA Repairs panel — so you get notified
before things silently fail.

## 2.0.0

- The Doorbell sensor now uses the event type `ring` on `hcu_integration_event` (#40)
- The button event types (`ring`, `press`, `press_short`, `press_long`, `press_long_start` or `press_long_stop`) are now lowercase and no longer prefixed with `key_`
- The `channel` field in the event data of `hcu_integration_event` has been renamed to `subtype`. Update your automations accordingly.
- On devices where individual buttons can be combined into a button pair, button presses were reported on the wrong channel. This has been corrected via a workaround. If you are affected, update your automations accordingly.
- Switches are now displayed as outlet, switch or light depending on the setting in the Homematic IP app.
  Note: Existing switch entities configured as "Light" may no longer appear under the switch platform. Please check your automations and dashboards after updating.
- The Global PIN will be removed in a future version. It is strongly recommended to migrate all existing implementations to use the Device Code exclusively.

## 1.19.6 - 2026-01-23

- **Eco mode can no longer be set via heating groups**  
  (#268) Eco mode has been disabled for heating groups. To enable Eco mode globally, use the service hcu_integration.activate_eco_mode.

## 1.19.5 - 2026-01-13

- **WINDOW state supported only for `ROTARY_HANDLE_CHANNEL` (HmIP-SRH) (#175)**  
  For all other devices, these entities will be removed. Non-available entities must be deleted manually via **Settings -> Devices & Services -> Entities**.  
  Tip: Filter by **integration** and the status **"not available"** to make cleanup easier. You can also delete multiple entities/devices at once.
