## [HmIPW-FIO6_update_V1_2_10_230822.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-FIO6_update_V1_2_10_230822.tgz)
Required CCU firmware version: &#8805; 3.43.15<br/>
<sub>sha256: d8bcc7b4c20b9afe1d9afb11ac6a67e5fba2412a9adc500b4d1e7a3555cd4ea5</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIPW-FIO6 - Homematic IP Wired IO Module flush-mount - 6 channels

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.2.10 - 2023-06-28
--------------------------------------------------------------

** Improvement
   * General improvements - Code optimisation



Version 1.2.8 - 2021-10-26
--------------------------------------------------------------

** Bugfix
   * Piggyback ACKs are not evaluated accurately enough.



Version 1.2.6 - 2018-10-15
--------------------------------------------------------------

** Bugfix
   * If ResetDisable is set the device hang in abort reset



Version 1.2.4 - 2018-10-08
--------------------------------------------------------------

** Bugfix
   * Short key press of key visual leads to a restart, if a factory reset was aborted before



Version 1.2.2 - 2018-09-25
--------------------------------------------------------------

** Bugfix
   * If more than one status ACK frame is within the answer queue only the first one is send. Afterwards every new status ACK only triggers the last one
   * Statusinfo module creates status ACK telegrams with set ACK, ARR and Boot bits if this is the first status to be sent after startup
   * HmIP_APP: Send node confusion when using external send nodes
   * Sometimes Statusinfo uses old ApplicationSequenceNumber and Statusinfo with ACK get lost
   * Answer-Frames are sometimes sent to the wrong IP destination
   * Weekprogram doesn't work correctly if several virtual channels shall be triggered by one switching point
   * Profile: Buffer for learned links can overflow
   * If the link partner is known, an NAK is sent on ("invalid") frames without ARR bit
   * If "Disable Message to AC" is activated and only one channel is addressed, no App-Ack is sent.



Version 1.2.0 - 2018-07-06
--------------------------------------------------------------

** Bugfix
   * If an input is configured as a switch, a long keystroke is sent when the input is opened.
   * Direct Execution Commands without ARR bit are answered at application level
   * Divide maximum number of partners for virtual channels into individual values for virtual A, B and C

** Improvement
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.



--- END OF FILE ---
