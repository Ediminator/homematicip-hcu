# Troubleshooting and FAQ

This page explains how to collect diagnostic files, enable debug logging, resolve repair issues, and troubleshoot common questions.

---

## 1. Downloading Diagnostics

When reporting a bug or requesting assistance, Home Assistant diagnostics provide details about your HCU configuration and device states.

### How to Download
1. In Home Assistant, navigate to **Settings → Devices & services**.
2. Select the **Homematic IP Local (HCU)** integration.
3. Click the three dots menu (**⋮**) next to the entry and select **Download diagnostics**.
4. A JSON file will download to your computer.

### Privacy and Redaction
The integration automatically sanitizes diagnostic downloads before export. Authentication tokens, passwords, and sensitive keys are stripped. Device labels, model types, channel assignments, and group topologies remain intact to assist with diagnosis.

---

## 2. Debug Logging

Debug logs record real-time communication between Home Assistant and your HCU over the WebSocket and REST channels.

### Method 1: Quick Debug Logging (Recommended)
1. Go to **Settings → Devices & services → Homematic IP Local (HCU)**.
2. Click the three dots menu (**⋮**) and choose **Enable debug logging**.
3. Perform the action you want to test (for example, trigger a button press, switch an actuator, or wait for an error).
4. Return to the three dots menu (**⋮**) and select **Disable debug logging**.
5. Home Assistant saves and downloads the relevant log file.

### Method 2: Permanent Logging via configuration.yaml
For long-term monitoring across restarts, add the following logger configuration to your `configuration.yaml` file:

```yaml
logger:
  default: info
  logs:
    custom_components.hcu_integration: debug
```

Restart Home Assistant to apply the configuration.

---

## 3. Repair Notices Created by the Integration

The integration raises repair notices in Home Assistant under **Settings → System → Repairs** when it detects a problem:

### `Cannot connect to Homematic IP HCU` (`setup_failed`)
- **Cause**: Home Assistant could not reach the HCU over the local network or the connection timed out.
- **Resolution**:
  1. Verify the HCU is powered on and connected to your local network.
  2. Confirm your HCU IP address has not changed. When Home Assistant finds a configured HCU on the network (zeroconf) at a new address, it shows a discovery card under **Settings → Devices & services**; confirm it to switch to the new address. Only confirm if you expected the address to change, because the saved credentials are sent to the new address. An HCU that you added by IP address is recognized once it was found at that address.
  3. Click **Submit** on the repair card to retry the connection.
  4. If the error continues, open **Settings → Devices & services → Homematic IP Local (HCU) → Reconfigure** to update connection details.

### `PIN failed for <device_name>` (`pin_failed`)
- **Cause**: The door lock authorization PIN was rejected by the HCU.
- **Resolution**:
  1. In Home Assistant, open the device page for your lock under **Settings → Devices & services → Homematic IP Local (HCU)**.
  2. Under **Configuration**, enter the correct PIN in the **Access Authorisation PIN** text entity.
  3. Reload the integration or retry the lock operation.

### `Device not authorized: <device_name> channel <channel_index>` (`access_authorization`)
- **Cause**: The integration user has not been granted control permissions for this specific lock or door channel.
- **Resolution**:
  1. Open the **Homematic IP app** on your mobile phone.
  2. Navigate to **Settings → Access Control → Access Profiles** (or **More → Access authorisations**).
  3. Add the user **"Home Assistant Integration"** to the authorization profile for this lock.
  4. Verify that an authorization PIN is set.
  5. Click **Submit** in the Home Assistant repair dialog, then reload the integration.

### `HA Entity Bridge device no longer configured: <entity_id>` (`ha_entity_excluded`)
- **Cause**: A virtual device created through the HA Entity Bridge still exists on the HCU, but the corresponding entity was removed from Home Assistant.
- **Resolution**:
  1. If you no longer need the device, open the Homematic IP smartphone app and delete the virtual device.
  2. If the entity was removed accidentally, re-add it under **Settings → Devices & services → Homematic IP Local (HCU) → Configure → Home Assistant Entities → HCU**.

### `Entity name prefix removed` (`entity_prefix_removed`)
- **Cause**: Informational notice. Entity names no longer use legacy prefixes such as `"HCU "`.
- **Resolution**: Entity IDs did not change, so automations and dashboards continue to function. You can dismiss this notice.

---

## 4. Frequently Asked Questions

### Can I run both the cloud integration and this local integration simultaneously?
Yes. You can run both the official Homematic IP Cloud integration and this local HCU integration side by side during testing or migration. Both connect independently. To avoid duplicate entity triggers in automations, disable entities from one integration once you verify the local setup.

### Why is my device not showing up in Home Assistant?
Check the following:
1. **Unconfigured Channels**: By default, the integration hides channels that have not been assigned to a room or group in the Homematic IP app. Check the integration option **Disable unconfigured channels**.
2. **Unsupported Internal Inputs**: Physical switch rockers on flush-mounted actuators (such as HmIP-BSM) are internal relay switches and do not emit separate button events over the HCU Connect API.
3. **Disabled OEMs**: If you use third-party partner devices connected to the HCU, check that their manufacturer is enabled under integration options.

### How do I remove a device that no longer exists on the HCU?
Devices you remove from the HCU are removed from Home Assistant on the next reload (automatic if **Auto reload on device change** is on). You can also delete such a device yourself: open the device in Home Assistant, open the three dots (⋮) and choose **Delete**. Devices, groups and the HCU itself that still exist on the HCU cannot be deleted this way, because they would come back on the next start; remove them in the Homematic IP app instead.

### Why do my button presses not trigger automations?
The HCU only forwards button events over its Connect API if the button channel is active inside an HCU automation. Create a dummy automation inside the Homematic IP app with your button as the trigger and an empty action. Once saved, the HCU will send event packets to Home Assistant.

### The integration shows "Failed to connect" during setup
1. Verify Developer Mode is activated in the HCU local web interface (`https://hcu1-XXXX.local`).
2. Make sure you generated a fresh activation key from the Developer Mode screen. Keys expire after a short time if unused.
3. Check that local ports `6969`, `8888` and `9001` are not blocked by internal firewalls or VLAN routing rules.

### Can I control the HCU itself (reboot or trigger updates)?
The integration exposes HCU system health metrics (carrier sense radio traffic, duty cycle, and firmware updates). Device reboots and firmware installations must be initiated directly through the Homematic IP smartphone app or HCU local web interface.
