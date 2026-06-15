## [HmIP-ESI_update_V1_6_6_250228.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-ESI_update_V1_6_6_250228.tgz)
Required CCU firmware version: &#8805; 3.73.9<br/>
<sub>sha256: 52d7ba00cb476ecc6464db1cd4e0f2caec74ffea7fc918ccbb18248855939a5e</sub>

C H A N G E L O G
-----------------

Version 1.6.6 - 2024-12-18
--------------------------------------------------------------

** Bugfix
   * No counting with ES-LED
   * Changed parameter only applied after reboot
   * HmIP ESI-GAS counting too much
   * After sensor change from iec to gas or led the error code is not reset
   * After sensor change from iec to gas or led the meter constant is 0



Version 1.4.0 - 2024-03-08
--------------------------------------------------------------

** Bugfix
   * Incorrect error message if IEC protocol not recognized
   * SML status word of length 1 byte not taken into account
   * no protocol detection of D0-D energy counter with 8-N-1 (LOGAREX)

** Improvement
   * Statusword under Obis 96.05.05 is not supported
   * fix DZG sign workaround
   * Error flashing if device is started without sensor
   * add OBIS 36.7.0 for single phase power meter
   * add workaround for Pafal EA5: take 'F' as 15 into OBIS C
   * Improved error handling for configuration change notification on the device to the AP
   * An ES-IEC without a recognized protocol should be reported



Version 1.2.2 - 2023-12-14
--------------------------------------------------------------

** Bugfix
   * Power consumption too high with ES-LED and ES-Gas
   * error code 1 on cloud inclusion

** Improvement
   * increase D0-C handshake timeout for LuG



Version 1.0.6 - 2023-11-02
--------------------------------------------------------------

** New Feature
   * First Release



--- END OF FILE ---
