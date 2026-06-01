## [HmIP-BROLL-2_update_V1_10_16_230626.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-BROLL-2_update_V1_10_16_230626.tgz)
Required CCU firmware version: &#8805; 3.69.5<br/>
<sub>sha256: 0defd5628cd526db8c958070f8956a1a2c4876faa8d0bb10fa15a5f5b11783fa</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-BROLL-2 - Homematic IP Shutter Actuator for brand switches

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.10.16 - 2023-06-16
--------------------------------------------------------------

** Improvement
   * Execute function "Enable operation within one end position to manually solve any error" only by a long button press



Version 1.10.8 - 2022-11-15
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator

** Improvement
   * Relay should remain switched on for 2 seconds when reaching the end position, so that the motor can remove the tension



Version 1.10.4 - 2022-06-22
--------------------------------------------------------------

** Bugfix
   * LED sequence timings while Background OTAU are wrong
   * Number of send attemps to link partner is wrong
   * Only one switch command is sent while long button press if the link partner cannot be reached



Version 1.10.2 - 2022-05-24
--------------------------------------------------------------

** Bugfix
   * After automatic measurement of driving times the device doesn't send a statusinfo



Version 1.10.0 - 2022-05-06
--------------------------------------------------------------

** New Feature
   * First Release



--- END OF FILE ---
