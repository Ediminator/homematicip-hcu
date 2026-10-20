# Homematic IP Local (HCU) Integration for Home Assistant

[![HACS Default](https://img.shields.io/badge/HACS-Default-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/Ediminator/homematicip-hcu)](https://github.com/Ediminator/homematicip-hcu/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Custom integration for Home Assistant to control **Homematic IP** devices locally through the **Homematic IP Home Control Unit (HCU)**.

> **Community Project**: This is a passion project built in personal spare time. Continued development depends on the community. Every bug report, diagnostics file, and piece of user feedback directly shapes what gets improved next.

---

## 🎯 Use Cases

Here is what you can do with this integration:

- **100% Local Control Without the Cloud**: Control your lights, dimmers, thermostats, roller shutters, and door locks directly over your local home network. Your automations remain fully functional even if your internet connection goes down.
- **Heating and Climate Control**: Manage target temperatures, switch heating profiles, set party modes, and activate vacation setbacks across all rooms.
- **Smart Shading and Roller Shutters**: Automate shutters, blinds, and awnings with exact position control, slat tilt angle adjustment, and secondary shading modes.
- **Wall Switches and Remotes in Automations**: Use Homematic IP wall switches, key ring remotes, and contact interfaces as fast, stateless triggers for Home Assistant automations and scene activations.
- **Integrated Security and Safety**: Monitor your alarm control panel with separated intrusion alarm and safety alarm binary sensors. Silence false smoke or water alerts without disarming your intrusion system.
- **Interactive Messages in the Homematic IP App**: Send custom interactive alerts from Home Assistant directly to the Homematic IP mobile app, and trigger follow-up actions when family members tap OK or Yes/No.
- **Expose Home Assistant Devices to the HCU**: Use the HA Entity Bridge to expose third-party Zigbee, Matter, or Wi-Fi lights, switches, and sensors to the HCU as virtual devices, allowing you to control them in the Homematic IP app and HCU automations.

---

## 🌟 Features

- **Local Push Updates**: Persistent WebSocket connections push state changes and events instantly without polling your network.
- **Complete Platform Coverage**: Integrates climate, covers, lights, switches, locks, sirens, valves, sensors, binary sensors, events, update notifications, selects, numbers, texts, and buttons.
- **Homematic IP Group Synchronization**: Discovers and syncs room heating groups, shutter groups, switching groups, and light groups.
- **Direct Device Triggers**: Native Home Assistant device triggers let you build button automations directly in the visual editor.
- **Hardware Timing Companions**:
  - **Internal On Time**: Automatically passes hardware on-time values configured in the Homematic IP app with every `turn_on` command.
  - **Ramp Time**: Configures hardware fade durations for dimmers without requiring a transition parameter on every action.
- **HA Entity Bridge (Alpha)**: Exposes Home Assistant entities back into the HCU as virtual devices.
- **Energy and Metering Support**: Integrates power draw and accumulated energy counters directly into the Home Assistant Energy Dashboard.
- **Multiple Gateways**: Add multiple HCU units within a single Home Assistant installation.

---

## 📚 Documentation

The documentation is organized into focused guides:

- [**Supported Devices**](docs/supported-devices.md): Complete list of supported hardware categories, channel types, groups, and created entities.
- [**Entities and Actions**](docs/entities-and-actions.md): Platform features and full action reference for all 11 integration services.
- [**Automation Examples**](docs/automations.md): Button guides (device triggers, visual editor, YAML), heating schedules, doorbell chimes, alarm responses, and user messages.
- [**How It Works**](docs/how-it-works.md): Architecture details on local push updates, ports, initial state caching, automatic reconnects, offline detection, and the entity bridge.
- [**Known Limitations**](docs/known-limitations.md): Documented hardware and API limitations with issue references.
- [**Troubleshooting and FAQ**](docs/troubleshooting.md): How to download diagnostics, enable debug logging, repair notifications, and frequently asked questions.

---

## 🔌 Connection Modes

The integration supports three local connection modes. You select the mode during initial setup and can change it at any time via **Settings → Devices & services → Homematic IP Local (HCU) → Reconfigure**.

| Feature / Detail | DualBridge (App + Plugin) ⭐ | App User Mode | Plugin User Mode |
|---|---|---|---|
| **Recommendation** | Recommended for full feature set | Simplest setup, full device support | Plugin features only |
| **Prerequisites** | Access to HCU button + Developer Mode | Access to HCU button | Developer Mode activation key |
| **Primary WebSocket** | Port `8888` (App User) | Port `8888` (App User) | Port `9001` (Plugin User) |
| **Secondary WebSocket**| Port `9001` (Plugin User) | None | None |
| **State Retrieval** | Fast REST `getCurrentState` | Fast REST `getCurrentState` | Plugin system state |
| **Device Control** | Full device & group control | Full device & group control | Full device & group control |
| **User Messages** | Yes (via Plugin channel) | No | Yes |
| **HA Entity Bridge** | Yes (via Plugin channel) | No | Yes |
| **Survives HCU Reboot**| Yes | Yes | Requires active Developer Mode |

### Which mode should I use?
- Choose **DualBridge** if you want all features, including the HA Entity Bridge and interactive user messages.
- Choose **App User** if you want a simple pairing process by pressing the HCU system button, without enabling Developer Mode.
- Choose **Plugin User** if you only want to use the official plugin API on port 9001.

---

## 📦 Requirements

- **Home Assistant**: Version `2026.8.0` or newer.
- **Hardware**: Homematic IP Home Control Unit (HmIP-HCU).
- **Network**: HCU and Home Assistant must be on the same local network, or reachable across subnets without blocked ports (`8888` and `9001`).
- **Developer Mode**: Required on the HCU if using DualBridge or Plugin User modes.

---

## 🚀 Installation

### Step 1: Install via HACS
This integration is included in the default HACS repository:
1. Open **HACS** in Home Assistant.
2. Select **Integrations**.
3. Search for `Homematic IP Local (HCU)`.
4. Click **Download** and select the latest release.
5. Restart Home Assistant.

> **Note**: If you previously added this repository as a custom repository in HACS, remove it under **HACS → Integrations → three dots (⋮) → Custom repositories** to avoid repository conflicts.

### Step 2: Choose Your Connection Mode
Decide which connection mode fits your needs (DualBridge is recommended).

### Step 3: Enable Developer Mode on Your HCU (for DualBridge and Plugin User)
If you chose DualBridge or Plugin User mode:
1. Open your web browser and go to your HCU local web interface:
   - `https://hcu1-XXXX.local` (replace `XXXX` with the last 4 digits of your HCU serial number / SGTIN), or use your HCU local IP address.
   - If a self-signed certificate warning appears, proceed to the page.
2. Log in with your HCU web interface credentials.
3. Open **Developer Mode** in the menu.
4. Toggle Developer Mode to **ON**.
5. Click **Generate Key** to produce an activation key.
6. Keep this browser window open; you will paste this key into Home Assistant during setup.

### Step 4: Add the Integration in Home Assistant
1. Navigate to **Settings → Devices & services → Add integration**.
2. Search for `Homematic IP Local (HCU)`.
3. Complete the setup dialogs:

#### Dialog 1: Connection Details
- **HCU IP address**: Enter your HCU local IP address (e.g. `192.168.1.100`).
- **Connection Mode**: Select DualBridge, App User, or Plugin User.

#### Dialog 2: Authorization
- **App User**: Press the central physical system button on your HCU hardware when prompted.
- **Plugin User**: Paste the activation key generated from the HCU Developer Mode screen.
- **DualBridge**: First paste the activation key, then press the physical system button on the HCU.

#### Dialog 3: Select OEM (only shown if third-party devices exist)
If your HCU has partner devices connected (such as Philips Hue or third-party drives), select which manufacturers you want to import.

#### Verify Setup
After setup completes, Home Assistant creates the HCU device entry, imports your Homematic IP devices and groups, and registers your entities.

<a id="step-4-configure-door-lock-pin-optional"></a>
### Door Lock PIN Configuration (Optional)
If you have a smart door lock (such as HmIP-DLD):
1. In Home Assistant, open **Settings → Devices & services → Homematic IP Local (HCU)**.
2. Click **Configure**.
3. Under **Lock PIN**, enter your door lock authorization PIN.
4. Alternatively, configure a device-specific PIN directly on the lock device page using the PIN text entity.
5. In the Homematic IP smartphone app, ensure the "Home Assistant Integration" user is added to an access profile for your lock under **Settings → Access Control**.

---

## 🔧 Configuration Options

Open **Settings → Devices & services → Homematic IP Local (HCU) → Configure** to adjust settings:

- **Connection Status**: Displays the active connection mode, host IP, and live WebSocket link status.
- **Global Settings**:
  - **Disable unconfigured channels**: Hides channels that have not been assigned to a room or group in the Homematic IP app (enabled by default).
  - **Auto reload on device change**: Automatically reloads the integration when devices are added, removed, or reconfigured in the Homematic IP app (enabled by default).
  - **Lock PIN**: Sets the global door lock authorization PIN.
  - **Disabled OEMs**: Disables discovery for selected third-party partner hardware.
  - **Disabled Groups**: Prevents specific group types from creating entities.
- **Vacation Mode**: Allows you to view and set vacation mode temperatures and end times directly from the options menu.
- **Home Assistant Entities → HCU**: Manages entities exposed to the HCU via the HA Entity Bridge.

---

<a id="-working-with-buttons--remote-controls"></a>
## 🔘 Buttons and Remote Controls

Homematic IP buttons and remotes fire momentary events instead of maintaining static states. You can trigger automations using device triggers in the visual editor or with the `hcu_integration_event` event type in YAML.

> **Important**: The HCU requires a dummy automation in the Homematic IP app before it forwards button presses over the local API. See the full step-by-step instructions and YAML templates in the [**Automation Examples**](docs/automations.md) guide.

---

## 🛡️ Security System

The integration discovers the central HCU alarm system:
- `alarm_control_panel.homematic_ip_hcu`: Provides Disarmed, Armed Home, and Armed Away controls.
- `binary_sensor.<hcu>_intrusion_alarm`: Active when unauthorized entry is detected.
- `binary_sensor.<hcu>_safety_alarm`: Active when water sensors or smoke detectors trigger.
- `button.<hcu>_acknowledge_safety_alarm`: Silences danger alarms without disarming intrusion protection.

For alarm automation examples, see [**Automation Examples**](docs/automations.md#4-alarm-system-automations).

---

## User Message to HCU

You can push interactive alert notifications to the Homematic IP smartphone app using `hcu_integration.create_user_message_request`. When users tap OK, Yes, or No in the app, the integration fires `hcu_integration_user_message_ack` in Home Assistant.

Detailed action parameters and listener examples are documented in [**Entities and Actions**](docs/entities-and-actions.md#hcu_integrationcreate_user_message_request) and [**Automation Examples**](docs/automations.md#5-interactive-notifications-in-the-homematic-ip-app).

---

<a id="-ha-entity-bridge-alpha"></a><a id="ha-entity-bridge-alpha"></a>
## 🧪 HA Entity Bridge (Alpha)

The HA Entity Bridge exposes selected Home Assistant entities (such as Zigbee, Wi-Fi, or virtual lights and switches) back into the HCU as virtual devices. They appear inside the Homematic IP mobile app and can be controlled in HCU automations.

### How to Configure
1. Open **Settings → Devices & services → Homematic IP Local (HCU) → Configure**.
2. Select **Home Assistant Entities → HCU**.
3. Choose the entities you want to bridge.
4. Save the options. The bridge registers the virtual devices with the HCU over the Plugin WebSocket channel.

For technical details on how state updates and control commands flow through the bridge, see [**How It Works**](docs/how-it-works.md#the-reverse-direction-ha-entity-bridge).

---

<a id="-diagnostics--troubleshooting"></a>
## 📊 Diagnostics and Troubleshooting

If you encounter issues:
- **Download Diagnostics**: Open the three dots menu (**⋮**) on the integration entry in Home Assistant and select **Download diagnostics**.
<a id="debug-logging"></a>
- **Debug Logging**: Enable debug logging via the integration entry menu (**⋮**) or add the debug logger block to `configuration.yaml`.
- **Repair Notices**: Check **Settings → System → Repairs** for automatic issue notices created by the integration.

Full diagnostic instructions, repair resolutions, and FAQs are available in the [**Troubleshooting and FAQ**](docs/troubleshooting.md) guide.

---

## ⏱️ Use Internal On Time

<img src="https://raw.githubusercontent.com/Ediminator/homematicip-hcu/refs/heads/main/images/internalontime.png" height="300" alt="Internal On Time">

Some switch and light channels allow configuring an on-time in the Homematic IP app. The integration exposes a companion entity `switch.<channel>_use_internal_on_time`. When enabled, any `turn_on` command sent from Home Assistant passes the configured duration to the device hardware, turning it off automatically without requiring a separate timer in Home Assistant.

See [**Entities and Actions**](docs/entities-and-actions.md#switch-switch) for platform details.

---

## 💡 Ramp Time

Dimmers support a hardware ramp time. The integration exposes a companion entity `number.<channel>_ramp_time`. Setting a value greater than 0 automatically applies that transition duration to all subsequent `turn_on` and `turn_off` commands.

See [**Entities and Actions**](docs/entities-and-actions.md#number-number) for platform details.

---

## 🔄 Updating the Integration

1. Check for updates under **HACS → Integrations**.
2. Click **Update** when a new release is available.
3. Restart Home Assistant.
4. If frontend cards or icons do not update immediately, perform a hard refresh (Ctrl+F5 or Cmd+Shift+R) to clear your browser cache.

---

## 🗑️ Removing the Integration

To remove the integration completely:
1. In Home Assistant, go to **Settings → Devices & services**.
2. Find **Homematic IP Local (HCU)**, click the three dots (**⋮**), and select **Delete**.
3. In **HACS → Integrations**, find the integration, click the three dots (**⋮**), and select **Remove**.
4. Restart Home Assistant.
5. Clean up authorization on your HCU hardware:
   - **App User**: In the Homematic IP app, open **Settings → Voice control & other services**, find the Home Assistant entry, and delete it.
   - **Plugin User / DualBridge**: Open the HCU local web interface, navigate to **Developer Mode**, and revoke the plugin registration key.

---

## 💬 Support

- **Issues and Bug Reports**: [GitHub Issues](https://github.com/Ediminator/homematicip-hcu/issues)
- **Discussions and Questions**: [GitHub Discussions](https://github.com/Ediminator/homematicip-hcu/discussions)

---

## ⚠️ Disclaimer and Limitation of Liability

This integration is an independent community project. It is not affiliated with, endorsed by, or supported by eQ-3 AG. Homematic IP is a registered trademark of eQ-3 AG.

Use this integration at your own risk. The authors are not responsible for any malfunctions, data loss, or unintended device switching.

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).

---

## 🙏 Credits

Special thanks to the Home Assistant community and everyone testing and providing diagnostics for the Homematic IP Home Control Unit.
