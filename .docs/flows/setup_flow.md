# Setup Flow (Initial Setup)

## Overview

The setup flow is executed once when the integration is added for the first time. It can be started via two entry points: manually or automatically via Zeroconf discovery.

## Flow Diagram

```mermaid
flowchart TD
    ZEROCONF([Zeroconf Discovery\nHCU found on network]) --> CONFIRM
    MANUAL([Add manually\nSettings → Integrations → +]) --> S0

    CONFIRM["**Confirm**\nSet up the discovered HCU?"]
    CONFIRM --> AUTH_TYPE

    S0["**Step 0: IP Address**\nInput: host"]
    S0 --> AUTH_TYPE

    AUTH_TYPE["**Select Connection Mode**\n─────────────────────────────\n• App User\n• Plugin User\n• Both (DualBridge)\n─────────────────────────────\nAt least one option required"]

    AUTH_TYPE -->|"App User\nor DualBridge"| APP_INIT
    AUTH_TYPE -->|"Plugin User only"| PLUGIN_AUTH

    APP_INIT["**App Auth: Init**\nEnter SGTIN (auto-detected)\n→ send connectionRequest"]
    APP_INIT --> APP_CONFIRM

    APP_CONFIRM["**App Auth: Confirm**\nPress blue button on HCU\n→ fetch token"]
    APP_CONFIRM -->|"DualBridge"| PLUGIN_AUTH
    APP_CONFIRM -->|"App User only"| OEMS

    PLUGIN_AUTH["**Plugin Auth**\nEnter activation key\n(HCU WebUI → Settings → Developer Mode)\n→ fetch token"]
    PLUGIN_AUTH --> OEMS

    OEMS{"Third-party devices\npresent?"}
    OEMS -->|"Yes"| SELECT_OEMS
    OEMS -->|"No / connection failed"| SAVE

    SELECT_OEMS["**OEM Selection**\nWhich third-party manufacturers\nshould be imported?\n(all pre-selected)"]
    SELECT_OEMS --> SAVE

    SAVE(["Integration saved\nEntities are created"])
```

## Step Details

### Entry: Zeroconf Discovery
- HCU is automatically discovered on the network (`_ssh._tcp.local.` / `hcu1*`)
- IPv4 address is extracted
- Notification appears in HA → confirming starts the flow

### Entry: Manual
- User enters hostname or IP address
- Unique ID is set to the host → prevents duplicate setup

### Select Connection Mode

| Option | Description |
|--------|-------------|
| **App User** | Authentication via blue button on the HCU. REST + WebSocket (port 8888). |
| **Plugin User** | Authentication via activation key (Developer Mode). WebSocket (Plugin port). |
| **DualBridge** | Both modes in parallel. App User for state/commands, Plugin for advanced features. ⭐ Recommended |

At least one option must be selected.

### App Auth: Init → Confirm
1. **Init**: SGTIN is auto-detected. `connectionRequest` is sent to the HCU.
2. **Confirm**: User presses blue button → token + client ID are fetched and saved.
- With DualBridge: continue to Plugin Auth
- With App User only: continue to OEM selection

### Plugin Auth
- Generate a new activation key in HCU WebUI: **Settings → Developer Mode**
- Token is fetched and verified
- `auth_type` is set: `plugin` or `dual`

### OEM Selection
- Connection to the HCU is briefly established to detect third-party devices
- If no third-party devices found or connection fails → save directly
- If third-party devices found → user selects which to import (all pre-selected)
- Deselected OEMs are stored in `disabled_oems` in options

## Auth Types

| `auth_type` | App Token | Plugin Token |
|-------------|:---------:|:------------:|
| `app` | ✅ | — |
| `plugin` | — | ✅ |
| `dual` | ✅ | ✅ |
