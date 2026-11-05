# Known Limitations

This document lists known limitations, firmware behaviors, and API constraints affecting the integration.

---

### 1. Eco Mode Is Global Only
- **Context**: In Homematic IP, Eco mode (absence mode) applies to the entire home installation.
- **Limitation**: Individual heating groups cannot be placed into Eco mode independently. Setting Eco mode on a single room would lower temperatures across your whole house.
- **Solution**: Room thermostats show the `eco` preset only while the home-wide Eco mode is active, so you can see the real state, but you cannot select it for a single room. To control whole-home Eco mode, use the action `hcu_integration.activate_eco_mode` and restore the normal schedules with `hcu_integration.deactivate_absence_mode`.
- **Reference**: Issue [#268](https://github.com/Ediminator/homematicip-hcu/issues/268).

---

### 2. Internal Inputs on Switch and Dimmer Actuators Not Exposed
- **Context**: Flush-mounted and DIN-rail actuators (such as HmIP-BSM, HmIP-BS2, HmIP-BSL, HmIP-DRSI1, HmIP-MOD-OC8, and HmIP-WRCR) have physical input terminals or rockers.
- **Limitation**: When you press the physical rocker or close an input switch wired to these actuators, the device toggles its internal relay. The HCU Connect API does not publish `DEVICE_CHANNEL_EVENT` messages for these internal inputs. As a result, Home Assistant cannot distinguish between a physical press and an automated switch event, and cannot trigger custom automations from the physical rocker alone.
- **Note**: Dedicated wall transmitters and remotes (such as HmIP-BRC2, HmIP-WRC2, HmIP-WRC6, HmIP-KRC4, and HmIP-FCI6) do not have built-in relays and emit button events normally.
- **Reference**: Tracking issue [#184](https://github.com/Ediminator/homematicip-hcu/issues/184).

---

### 3. Heating Profile Names and Cooling Profiles
- **Context**: Homematic IP allows customizing heating profiles in the smartphone app.
- **Limitation**: Heating profiles appear as presets of the thermostat with the name you gave them in the app. The first profile is called `Standard` if it has no name. Further profiles without a name are not listed, so give a profile a name in the app if you want to select it in Home Assistant. Dedicated cooling profiles are not offered as presets.
- **Reference**: Tracking issue [#229](https://github.com/Ediminator/homematicip-hcu/issues/229) and [#170](https://github.com/Ediminator/homematicip-hcu/issues/170).

---

### 4. Lock Access Authorization Display in Homematic IP App
- **Context**: Controlling smart door locks (such as HmIP-DLD) requires authorizing the "Home Assistant Integration" user under an access profile in the Homematic IP app.
- **Limitation**: Due to a known user interface bug in the HCU firmware (present even on firmware 1.6.16 and newer), the integration user may appear grayed out or marked as expired in the smartphone app list. The integration authorization is still active on the HCU.
- **Verification**: Check the `has_access_authorization` attribute on your lock entity in Home Assistant to verify whether the lock is authorized.

---

### 5. Siren Tone and Groups
- **Context**: The HCU organizes sirens and smoke detectors used as sirens in `ALARM_SWITCHING` groups (such as `SIREN`).
- **Limitation**: The siren entity switches the whole group; individual members cannot be switched separately. The alarm tone and optical signal are set on the group in the Homematic IP app and cannot be chosen when turning the siren on. Safety alarm groups (`..._SAFETY`) and the backup alarm group get no siren entity.
- **Reference**: Issue [#380](https://github.com/Ediminator/homematicip-hcu/issues/380).

---

### 6. HmIP-ASIR-2 Indoor Siren Documentation
- **Context**: The HmIP-ASIR-2 is an indoor alarm siren.
- **Limitation**: eQ-3 has not published Connect API documentation for the siren channel of the HmIP-ASIR-2. The integration therefore controls it through its `ALARM_SWITCHING` group (see limitation 5), which the Connect API documents as a switching group.
- **Reference**: Tracking issue [#229](https://github.com/Ediminator/homematicip-hcu/issues/229) and [#117](https://github.com/Ediminator/homematicip-hcu/issues/117).

---

### 7. HA Entity Bridge Status
- **Context**: The HA Entity Bridge exposes Home Assistant entities back into the HCU as virtual devices.
- **Limitation**: The bridge is in alpha status. While lights, switches, and basic binary sensors function well, complex multi-feature devices or rare entity types may display unexpected states in the Homematic IP app.

---

### 8. Developer Mode Prerequisite
- **Context**: Connecting via Plugin User or DualBridge mode requires generating an activation key.
- **Limitation**: You must enable Developer Mode in the HCU local web interface. If Developer Mode is disabled or wiped during a major HCU firmware reset, plugin connections on port 9001 will fail until you re-enable Developer Mode and enter a new activation key. App User mode does not have this requirement.
