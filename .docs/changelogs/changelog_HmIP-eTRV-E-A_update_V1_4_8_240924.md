## [HmIP-eTRV-E-A_update_V1_4_8_240924.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-eTRV-E-A_update_V1_4_8_240924.tgz)
Required CCU firmware version: &#8805; 3.73.4<br/>
<sub>sha256: 7c34947f457ac7f3119b07f46e3783b150764a0cce48bfa9b92984377a8aa4af</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-eTRV-E - Homematic IP HeizkÃ¶rperthermostat â Evo

alte Bezeichnung:
Homematic IP HeizkÃ¶rperthermostat
HmIP-eTRV-E


Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version V1.4.8 - 2024-09-23
--------------------------------------------------------------

** Bugfix
   * Changed define LOW_BAT_BOOT from 2.5V to 2.3V



Version V1.4.006 - 2023-10-17
--------------------------------------------------------------

** Bugfix
   * ARR Bit in CYCLIC_BIDI_INFO_MSG nicht gesetzt						
   * Low Bat Meldung kommt nicht bei Spannungseinbruch durch Motorfahrt / Display an
   * ARR Bit of Status Info Frame set False after Inclusion
   * Device sends ACK and NAK after Reboot command
   * Device reacts delayed after a window action with the motor drive



Version V1.4.004 - 2023-10-06
--------------------------------------------------------------

** Bugfix
   * ARR Bit of Status Info Frame set False after Inclusion

** Improvement
   * Status Info nach Ãnderung der Ventilposition wird spÃ¤t gesendet



Version V1.4.002 - 2023-09-19
--------------------------------------------------------------

** Bugfix
   * Valve-adapt: Device first sends Status "wait-state" before "adaption in progress"
   * Device sends ACK and NAK after Reboot command
   * Device sends Status Info to Multicast with ARR
   * Status info after window open has wrong valve level

** Improvement
   * Status Info nach Ãnderung der Ventilposition wird spÃ¤t gesendet



Version V1.4.000 - 2023-09-10
--------------------------------------------------------------

** Bugfix
   * When adaption is aborted via button press, the adaption is automatically restarted after installation drive
   * Device reacts delayed after a window action with the motor drive

** Improvement
   * Increase Low Batt Threshold



Version V1.2.002 - 2022-10-04
--------------------------------------------------------------

** Bugfix
   * Beleuchtungsdauer > 50 Sekunden stimmt nicht



Version V1.2.000 - 2022-02-10
--------------------------------------------------------------

** Bugfix
   * Setting vacation/party mode not possible
   * Valve remains closed after decalcification
   * eTRV kehrt nicht auf eingestellte Temperatur zurÃ¼ck nach Abschaltung des Eco-Modus



Version V1.0.012 - 2022-01-27
--------------------------------------------------------------

** Bugfix
   * Week program 3 not usable



Version V1.0.010 - 2021-03-01
--------------------------------------------------------------

** Improvement
   * Default value for display contrast must be adjusted



Version V1.0.000 - 2019-08-19
--------------------------------------------------------------

** Improvement
   * The time information telegram does not contain a note about the sommer / winter time change.



--- END OF FILE ---
