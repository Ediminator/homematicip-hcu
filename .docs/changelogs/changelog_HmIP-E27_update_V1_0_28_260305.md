## [HmIP-E27_update_V1_0_28_260305.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-E27_update_V1_0_28_260305.tgz)
Required CCU firmware version: &#8805; 3.0.0<br/>
<sub>sha256: fe055058ceaf002ee0535d44466c694bde6cdac0011899c876c13a601381d4df</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-E27 - HmIP-E27

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.0.28 - 2026-03-05
--------------------------------------------------------------

** Improvement
   * Improve WLAN performance



Version 1.0.26 - 2026-02-20
--------------------------------------------------------------

** Improvement
   * Error handling while WLAN setup



Version 1.0.24 - 2026-02-13
--------------------------------------------------------------

** Improvement
   * Set USE_PARTNER_RAM_LOOKUP 



Version 1.0.22 - 2026-02-10
--------------------------------------------------------------

** Bugfix
   * ICMP Destination Unreachable isn't handled correctly



Version 1.0.20 - 2026-02-09
--------------------------------------------------------------

** Bugfix
   * Device sometimes uses incorrect route
   * Device repeatedly sends sequence number validations even though it has already been validated previously



Version 1.0.18 - 2026-02-06
--------------------------------------------------------------

** Improvement
   * Use actual version of HmIPW-lib
   * Use actual version of BBDC



Version 1.0.16 - 2026-02-04
--------------------------------------------------------------

** Improvement
   * Use actual version of BBDC



Version 1.0.14 - 2026-02-04
--------------------------------------------------------------

** Improvement
   * Don't handle frames addressed to Any* / handle only some All* frames



Version 1.0.12 - 2026-01-30
--------------------------------------------------------------

** Improvement
   * Change gesture for factory reset



Version 1.0.10 - 2026-01-29
--------------------------------------------------------------

** Bugfix
   * DEC UniversalLight - Hue&Sat: rapid color change during dimming
   * PowerUP - HCL without function
   * InclusionAccept is not send over router



Version 1.0.8 - 2026-01-23
--------------------------------------------------------------

** Bugfix
   * Device sends sometimes TimeInformationRequest to the AllAC address at boot

** Improvement
   * Optimize WLAN scan
   * Optimize LED handling at boot



Version 1.0.6 - 2026-01-21
--------------------------------------------------------------

** Bugfix
   * Retrigger Inclusion Request does not check SGTIN
   * BT module does not switch off after 5 minutes
   * After DEC-STOP, the color of the light bulb changes from TC to HSV mode.

** Improvement
   * Adjust orange flashing slightly during power-up
   * Add gamma correction



Version 1.0.4 - 2025-12-01
--------------------------------------------------------------

** Improvement
   * Add RSSI to status frames



Version 1.0.2 - 2025-11-25
--------------------------------------------------------------

** Improvement
   * BluFi: Disable setting WLAN data without security



Version 1.0.0 - 2025-11-17
--------------------------------------------------------------

** Bugfix
   * Factory-Reset is done after 5th restart
   * DEC with Hue and SAT is not handled, if HCL or Dim2Warm is active
   * after restart frames repeatedly send

** Improvement
   * Adjust dimming curve for TW



--- END OF FILE ---
