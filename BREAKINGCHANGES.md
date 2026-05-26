# ⚠️ BREAKING CHANGES

> 💡 **Tip:** The best way to get notified about issues in Home Assistant
> is [Spook](https://github.com/frenck/spook) — a powerful HACS integration
> that surfaces broken entities and config issues directly in the HA Repairs panel.
> See [spook.boo](https://spook.boo) for more.

---

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
