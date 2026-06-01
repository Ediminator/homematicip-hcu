## [HmIP-RC8_update_V2_6_2_241028.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-RC8_update_V2_6_2_241028.tgz)
Required CCU firmware version: &#8805; 3.83.6<br/>
<sub>sha256: 6abd9f973d9c3ca56e62b76a08f17b8277f2c7adebb9097146defefbf96b9982</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-RC8 - Homematic IP Remote Control - 8 Buttons

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 2.4.0 - 2021-12-09
--------------------------------------------------------------

** Bugfix
   * LED sequence at live otau wrong
   * Device does not send MAC ACK if the application response comes after an application retry
   * Transmission behaviour incorrect on long keystroke
   * Error in transmission behaviour if link partner answers late

** New Feature
   * Support of "Security Plus" - Disable active alarm system although the cloud is offline
   * Support of HmIPW operation mode
   *  Support of systems and solutions without a central unit (installer solution)
   * Support of routing between Homemativ IP and Homematic IP Wired

** Improvement
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality.
   * If all link partners are Homematic IP wired devices send multicast frames to the wired-multicast address and not to all-devices-multicast-address.



Version 2.6.2 - 2024-09-04
--------------------------------------------------------------

** Bugfix
   * No led sequence SNC Error
   * Device hangs when factory reset is aborted
   * No red led if device is in dutycycle
   * No red led if factoryreset is aborted
   * No red LED if no AppAck for USC

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.



--- END OF FILE ---

