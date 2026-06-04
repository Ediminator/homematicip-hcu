## [HmIP-DRSI4_update_V3_2_0_250522.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-DRSI4_update_V3_2_0_250522.tgz)
Required CCU firmware version: &#8805; 3.49.14 / 2.49.14<br/>
<sub>sha256: 32f878124d5d4001c1cdc096064c50b86c79c324bc3c1574889585203c2fa89c</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-DRSI4 - Homematic IP Schaltaktor fÃ¼r Hutschienenmontage â 4-fach

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 3.2.0 - 2025-05-22
--------------------------------------------------------------

** Bugfix
   * Device only switches the relay back to the initial state when voltage is applied again after a power failure.
   * Undefined behavior after undervoltage switch-off
   * The device sends RequestConfigUpdate to the central unit although it has received a MAC-ACK on its SwitchCmd.

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.



Version 1.8.0 - 2021-09-20
--------------------------------------------------------------

** Improvement
   * The time information telegram does not contain a note about the sommer / winter time change.



Version 1.6.0 - 2020-05-26
--------------------------------------------------------------

** Bugfix
   * If using the device keys to simulate a key press, the visialisation of the pressed key is not release if the key is released



Version 1.4.4 - 2022-12-07
--------------------------------------------------------------

** Modification
   * HmIP-DRSI4 Firmware-Beta-Approval V1.4.4



--- END OF FILE ---
