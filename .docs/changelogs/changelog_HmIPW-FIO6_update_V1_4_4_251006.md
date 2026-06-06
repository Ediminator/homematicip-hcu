## [HmIPW-FIO6_update_V1_4_4_251006.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-FIO6_update_V1_4_4_251006.tgz)
Required CCU firmware version: &#8805; 3.87.6<br/>
<sub>sha256: bfbaaff13bf75295f81ec7fdd67cffa871c9106c94de0e23e9a7c50c052add6e</sub>

C H A N G E L O G
-----------------

Version 1.4.4 - 2025-10-06
--------------------------------------------------------------

** Bugfix
   * Alarm backup is not send if the initiating input channel has link partners in addition to the SHC



Version 1.4.2 - 2025-06-11
--------------------------------------------------------------

** Bugfix
   * ApplSeqNo remains at 1 if OperationMode 0x3 (binary behaviour) is activ
   * Offline alarming from Wired to Radio and Radio to Wired does not work



Version 1.4.0 - 2025-02-04
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * Piggyback ACKs are not evaluated accurately enough.
   * Offline alarming from Wired to Radio and Radio to Wired does not work
   * Output channels might be set to a wrong state after a long keypress command has received
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.
   * If there is no AppAck on a CSC from the CCU, the backup channel is triggered
   * HmIP_APP: Send node confusion when using external send nodes
   * Answer-Frames are sometimes sent to the wrong IP destination

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.
   * The time information telegram does not contain a note about the sommer / winter time change.
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES.
   * Modify event counter check to meet current specification



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
