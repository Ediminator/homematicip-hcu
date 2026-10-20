# How It Works

This page explains how the integration connects to your Home Control Unit (HCU), fetches initial data, receives updates, and manages device availability.

## Data Updates via Local Push

The integration uses a local push architecture. Instead of polling your HCU at regular intervals, Home Assistant opens persistent WebSocket connections directly to your HCU on your local network.

Whenever a sensor changes, a button is pressed, or a climate profile switches, your HCU sends an event over the open WebSocket. Home Assistant processes this event immediately and updates the affected entities. This design ensures instant responses and eliminates unnecessary network polling.

## Connection Channels and Ports

The integration supports three connection modes. Each mode uses specific local ports and protocols:

| Mode | Primary Channel | Secondary Channel | Ports Used |
|---|---|---|---|
| **Plugin User** | Plugin WebSocket | None | `9001` (WebSocket) |
| **App User** | App WebSocket | None | `8888` (WebSocket), `6969` (HTTPS REST) |
| **DualBridge** | App WebSocket | Plugin WebSocket | `8888` (WebSocket), `6969` (HTTPS REST), `9001` (WebSocket) |

### Plugin User Mode
- Home Assistant connects to `wss://<hcu-ip>:9001` using an authentication token obtained during setup.
- The connection passes the plugin identifier `de.homeassistant.hcu.integration` and requests system events (`hmip-system-events: true`).
- On connection startup, the integration announces readiness (`PluginStateResponse`) so the HCU registers the plugin.
- Events arrive wrapped as `HMIP_SYSTEM_EVENT` messages containing transaction updates.

### App User Mode
- Home Assistant acts as an authorized client application and connects to `wss://<hcu-ip>:8888` (with an automatic fallback to port `9001` if needed).
- The connection uses headers for `AUTHTOKEN`, `CLIENTAUTH`, and `ACCESSPOINT-ID`.
- System state requests use HTTPS REST calls (`POST https://<hcu-ip>:6969/hmip/home/getCurrentState`).
- Events arrive directly as JSON event dictionaries without the plugin wrapper.

### DualBridge Mode
- Combines both channels to deliver full functionality.
- The App User connection on port `8888` acts as the primary data channel for complete state queries and device control.
- A secondary Plugin User connection runs concurrently on port `9001`. This secondary channel powers the HA Entity Bridge, allowing you to expose Home Assistant entities back into the HCU as virtual devices.
- If the secondary Plugin WebSocket experiences a temporary disruption, entity state updates and control actions continue uninterrupted through the primary App User channel.

## Initial State Load

When Home Assistant starts or reloads the integration:
1. The coordinator creates the background WebSocket listener task.
2. The integration establishes the WebSocket connection to the HCU.
3. The client queries the complete system state from the HCU (`get_system_state()`). For App User and DualBridge modes, this retrieves the full snapshot via `getCurrentState`.
4. The coordinator caches all devices, functional channels, groups, and home-level settings in memory.
5. Entities register and initialize their state against this cached data. Entity updates remain paused until this initial load completes successfully.
6. The integration identifies the primary HCU device entry and resolves network connection attributes.

## Automatic Reconnection

If network connectivity drops or the HCU reboots:
1. The WebSocket connection closes, and Home Assistant logs a disconnection warning.
2. The coordinator enters an automatic reconnection loop.
3. Reconnection starts with an initial delay of 5 seconds (`WEBSOCKET_RECONNECT_INITIAL_DELAY`).
4. To avoid connection storms, the coordinator adds a random jitter of up to 5 seconds (`WEBSOCKET_RECONNECT_JITTER_MAX`).
5. If the attempt fails, the delay doubles after each failed try (exponential backoff) up to a maximum delay of 60 seconds (`WEBSOCKET_RECONNECT_MAX_DELAY`).
6. Once the connection succeeds, the coordinator resets the retry timer, re-registers event callbacks, announces plugin readiness if applicable, and resumes live push updates.

## Device Availability and Offline Detection

Entities determine their availability in Home Assistant based on connection status and device type:

- **Central Connection**: If the WebSocket to the HCU disconnects, all entities provided by the integration become unavailable.
- **Permanently Reachable Devices**: Mains-powered devices (such as wall switches, dimmers, plug adapters, and wired bus actuators) report `permanentlyReachable: true` in the HCU state. As long as the integration is connected to the HCU, these entities remain available.
- **Battery-Powered Devices**: Battery devices sleep between transmissions. The integration inspects the maintenance channel (channel `0`) for the `unreach` attribute. If the HCU marks a battery device as unreachable (`unreach: true`), the corresponding entities switch to unavailable in Home Assistant.
- **Group Entities**: Groups remain available as long as the WebSocket connection is active and the group exists in the HCU configuration.

## Automatic Reload on Device Changes

When you add, rename, or remove devices using the Homematic IP smartphone app, the HCU pushes change notifications over the WebSocket:

- **Device Exclusion**: When you remove a device from the HCU, the integration receives an exclusion event and automatically initiates a reload of the integration entry. This purges stale entities from the entity registry.
- **Configuration Changes**: When device channels or functional roles change, the HCU signals that a reload is required. The coordinator debounces these events and reloads the integration after 10 seconds. This delay allows you to finish multi-step edits in the Homematic IP app without triggering repeated restarts.

- **New Devices**: A newly paired device does not get Home Assistant entities by itself yet. Reload the integration (**Settings → Devices & services → Homematic IP Local (HCU) → ⋮ → Reload**) after pairing new hardware.

You can enable or disable the automatic reloads under the integration options (**Auto reload on device change**).

## The Reverse Direction: HA Entity Bridge

While the integration primarily imports Homematic IP devices into Home Assistant, the HA Entity Bridge operates in reverse:

```
[ Home Assistant Entities ] ---> [ HA Entity Bridge ] ---> [ HCU Plugin API (Port 9001) ] ---> [ Homematic IP App ]
```

1. You select specific Home Assistant entities (lights, switches, sensors) in the integration options.
2. Home Assistant registers virtual devices with the HCU via the Plugin WebSocket channel.
3. When the state of an exposed Home Assistant entity changes, the bridge sends a status update to the HCU.
4. If you toggle or dim the virtual device in the Homematic IP app or through an HCU automation, the HCU sends a control command to Home Assistant. The bridge receives this command and executes the corresponding Home Assistant action (`light.turn_on`, `switch.turn_off`, etc.).
5. Bridged virtual devices receive an identifier starting with `ha.`. The integration recognizes this prefix and excludes them from regular device discovery, preventing devices from being re-imported back into Home Assistant.
