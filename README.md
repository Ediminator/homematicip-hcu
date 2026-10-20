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
- **Homematic IP Home Control Unit (HCU)**: Powered on and connected to your local network.
- **Network Access**: Home Assistant must be able to reach the HCU over your local network without blocked ports (`8888` and `9001`).
- **Developer Mode**: Required on the HCU for **DualBridge** and **Plugin User** modes (see [Step 3](#step-3-enable-developer-mode-on-your-hcu)).

---

## 🚀 Installation

### Step 1: Install via HACS

This integration is an **official HACS default integration** (no custom repository needs to be added).

1. Open **HACS** in your Home Assistant sidebar.
2. Click on **Integrations**.
3. Search for **"Homematic IP Local (HCU)"**.
4. Click **DOWNLOAD** and confirm.
5. **Restart Home Assistant** when prompted.

Or use the link below:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Ediminator&repository=homematicip-hcu&category=integration)

> If you previously added this repository as a **custom repository** in HACS, remove it under **HACS → Integrations → three dots (⋮) → Custom repositories** to avoid repository conflicts.

---

### Step 2: Choose Your Connection Mode

Before adding the integration, decide which connection mode fits your setup. This affects what you need to prepare on the HCU and how authorization works.

| Mode | What you need | Best for |
|---|---|---|
| **DualBridge** ⭐ | Physical button access to HCU + Developer Mode enabled | Everyone (full feature set) |
| **App User** | Physical access to press the system button on the HCU | Simple setup, no Developer Mode needed |
| **Plugin User** | Developer Mode enabled on HCU | Plugin features only (user messages, discover/control) |

---

### Step 3: Enable Developer Mode on Your HCU

> **Skip this step if you chose App User only.**

DualBridge and Plugin User modes require Developer Mode to be active on the HCU.

1. Open the HCU web interface in a browser:
   - `https://hcu1-XXXX.local` (replace `XXXX` with the last 4 digits of your HCU serial number / SGTIN)
   - Or use the IP address directly: `https://YOUR_HCU_IP`
   - If you see a certificate warning, click **Advanced** and proceed (this is expected).

2. Log in to your HCU.

3. Navigate to **Developer Mode** in the menu.

4. Toggle the switch to **activate Developer Mode**.

5. Toggle the switch to **Expose the Connect API WebSocket**.
   > ⚠️ Even if the toggle already appears active, deactivate and re-activate it to ensure it is properly enabled.

6. Leave this page open. When Home Assistant prompts for an activation key during setup, you will generate it here. Do not generate the key in advance, because activation keys expire after a few minutes.

---

### Step 4: Add the Integration in Home Assistant

> 💡 **Tip:** If your Home Assistant **Area** names match your Homematic IP **Room** names exactly (e.g., "Living Room" = "Living Room"), newly discovered devices are automatically assigned to the correct area.

1. In Home Assistant, go to **Settings → Devices & Services**.
2. Click **+ ADD INTEGRATION** (bottom right).
3. Search for `Homematic IP Local (HCU)` and select it.

Or use the link below:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hcu_integration)

#### Dialog 1: Connection Details (all modes)

Enter the following and click **SUBMIT**:

- **HCU IP address**: e.g., `192.168.1.100`
- **Connection Mode**: select the mode you chose in Step 2

#### Dialog 2: Authorization

The authorization steps run as follows:

---

**App User**
1. Have physical access to your HCU.
2. **Press the system button** on the HCU when prompted.
3. Complete the pairing in Home Assistant within the time window.
4. Click **SUBMIT**.

---

**Plugin User**
1. Switch to the HCU web interface (from Step 3).
2. Click **"Generate activation key"**.
3. Copy the key (it is only valid for a few minutes).
4. Paste it into the Home Assistant dialog.
5. Click **SUBMIT**.

---

**DualBridge**
For **DualBridge**, both authorization steps run in sequence:
1. The setup wizard guides you through **App User** first: press the physical system button on the HCU when prompted.
2. After confirmation, the **Plugin User** dialog appears: switch to the HCU web interface, click **"Generate activation key"**, paste the key into Home Assistant, and click **SUBMIT**.

---

#### Dialog 3: Select OEM (only shown if third-party devices are detected)

If your HCU has partner devices connected (such as Philips Hue or third-party drives), select which manufacturers you want to hide. All others will be imported.

- Select any manufacturer you want to **hide** and click **SUBMIT**.
- If no third-party devices are present, this step is skipped automatically.

---

#### Verify Setup

Once authorized, the integration connects and discovers all your devices. This may take a moment.

- A success message confirms the connection.
- Your devices appear under **Settings → Devices & Services → Homematic IP Local (HCU)**.

---

<a id="step-4-configure-door-lock-pin-optional"></a>
### Door Lock PIN Configuration (Optional)

If you have a smart door lock (such as HmIP-DLD):

1. In Home Assistant, open the device page for your lock under **Settings → Devices & Services → Homematic IP Local (HCU)**.
2. Under **Configuration**, find the **Authorization PIN** text entity (`text.<lock_name>_authorization_pin`) and enter your door lock PIN. The integration stores this PIN per device.
3. In the Homematic IP smartphone app, ensure the "Home Assistant Integration" user is added to an access profile for your lock under **Settings → Access Control**.

---

## 🔧 Configuration Options

To open the options, go to **Settings → Devices & Services**, find the **Homematic IP Local (HCU)** card, and click **CONFIGURE**. A menu appears with the following sections:

---

### Connection Status

Read-only overview of the current setup. Shows:

- **Connection mode**: DualBridge, App User, or Plugin User
- **App User status**: Connected / Not connected / Not configured
- **Plugin User status**: Connected / Not connected / Not configured

No changes can be made here. Use **Reconfigure** (three dots ⋮ on the integration card) to change the connection mode or re-authorize.

---

### Global Settings

| Setting | Default | Description |
|---|---|---|
| **Disable unconfigured channels** | On | Hides channels that have no configuration in the Homematic IP app (reduces clutter) |
| **Auto-reload on device change** | On | Automatically reloads the integration when devices are added or removed on the HCU |
| **Comfort Temperature** | 21 °C | Temperature applied when switching a climate entity from OFF to HEAT mode |
| **Disabled manufacturers** | None | Select third-party manufacturers (e.g. Philips Hue) whose devices should be hidden in Home Assistant. Only shown if such devices are detected. |
| **Disabled groups** | None | Select group types (e.g. HEATING, SWITCHING) to hide from Home Assistant |

---

### Vacation Mode

Activates a system-wide absence mode across all heating groups.

- **Temperature**: Target temperature while away (5 °C to 30 °C)
- **End time**: Date and time when normal heating schedule resumes

> This is equivalent to the vacation mode in the Homematic IP app. It overrides all room schedules until the set end time.

---

### Home Assistant Entities → HCU

Manages entities exposed to the HCU via the HA Entity Bridge.

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
1. Open **Settings → Devices & Services → Homematic IP Local (HCU) → Configure**.
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

- The entity is **disabled by default** and only appears on channels that have an `onTime` value configured in the Homematic IP app.
- Configure the on-time in the Homematic IP app first, then enable the entity in Home Assistant.
- The enabled state is kept across Home Assistant restarts.

See [**Entities and Actions**](docs/entities-and-actions.md#switch-switch) for platform details.

---

## 💡 Ramp Time

Dimmers support a hardware ramp time. The integration exposes a companion entity `number.<channel>_ramp_time`. Setting a value greater than 0 automatically applies that transition duration to all subsequent `turn_on` and `turn_off` commands.

- The entity is **disabled by default**. Enable it for the channels where you want a fixed ramp time.
- Valid range: `0.1` to `16383` seconds. A value of `0` disables the feature.
- An explicit `transition` value in an action always takes precedence over the configured ramp time.
- The configured value is kept across Home Assistant restarts.

See [**Entities and Actions**](docs/entities-and-actions.md#number-number) for platform details.

---

## 🔄 Updating the Integration

When a new version is released:

1. Open **HACS**.
2. Go to **Integrations**.
3. Find **Homematic IP Local (HCU)**.
4. If an update is available, click **UPDATE**.
5. **Restart Home Assistant**.

> **Important:** Always check the CHANGELOG before updating for any breaking changes or new requirements.

**Browser cache note:** If frontend cards or icons do not update immediately, perform a hard refresh (Ctrl+F5 or Cmd+Shift+R) to clear your browser cache.

---

## 🗑️ Removing the Integration

1. **Remove it from Home Assistant:** go to **Settings → Devices & Services → Homematic IP Local (HCU)**, open the three dots (⋮) next to the HCU entry and choose **Delete**. Home Assistant removes all devices and entities of that entry. Repeat this for every HCU you added.
2. **Remove the files:** in **HACS**, open **Homematic IP Local (HCU)**, choose the three dots (⋮) → **Remove**, then **restart Home Assistant**.
3. **Clean up on the HCU (optional):**
   - **Plugin User / DualBridge:** if no other plugin needs it, turn off **Expose the Connect API WebSocket** and **Developer Mode** in the HCU web interface (see [Step 3](#step-3-enable-developer-mode-on-your-hcu)).
   - **App User / DualBridge:** the integration was paired with the HCU as an app client. If it is still listed in the Homematic IP app, remove it there under **Settings → Voice control & other services**.
   - **HA Entity Bridge (alpha):** Home Assistant devices that you exported to the HCU stay there after removal. Delete them in the Homematic IP app.

Automations, scripts and dashboards that use entities of this integration are not changed automatically; update or delete them afterwards.

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
