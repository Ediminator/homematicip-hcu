## [HmIPW-DRI32_update_V1_4_6_250526.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-DRI32_update_V1_4_6_250526.tgz)
Required CCU firmware version: &#8805; 3.43.15<br/>
<sub>sha256: f3d8e42a912185c76a1279d15a576913ab4eb47d593fceb208bf33b4393d858c</sub>

C H A N G E L O G
-----------------

Version 1.4.6 - 2025-05-26
--------------------------------------------------------------

** Bugfix
   * Wrong default value for parameter CYCLIC_INFO_MSG



Version 1.4.4 - 2025-05-20
--------------------------------------------------------------

** Bugfix
   * Status info cyclic time is roundabout 60s



Version 1.4.2 - 2025-05-15
--------------------------------------------------------------

** Bugfix
   * Device sends no dec identify by system button
   * Eventcounter at send usc always 0
   * Short button press is not always recognized correctly
   * AppSeqNo is 0 after LongButtonPress

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.



Version 1.4.0 - 2025-01-31
--------------------------------------------------------------

** Bugfix
   * Short key press of key visual leads to a restart, if a factory reset was aborted before
   * Boot-Flag will not be set in a Status-Answer-Telegram  
   * Short button press is not always recognized correctly
   * Offline alarming from Wired to Radio and Radio to Wired does not work
   * Display is not updated after voltage reset.
   * AppSeqNo is 0 after LongButtonPress
   * Short key press of key visual leads to a restart, if a factory reset was aborted before

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality.
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES.



Version 1.2.4 - 2022-12-05
--------------------------------------------------------------

** Improvement
   * General improvements - Code optimisation
   * General improvements - Code optimisation



Version 1.2.2 - 2018-09-10
--------------------------------------------------------------

** Bugfix
   * If more than one status ACK frame is within the answer queue only the first one is send. Afterwards every new status ACK only triggers the last one
   * Statusinfo module creates status ACK telegrams with set ACK, ARR and Boot bits if this is the first status to be sent after startup
   * HmIP_APP: Send node confusion when using external send nodes
   * Sometimes Statusinfo uses old ApplicationSequenceNumber and Statusinfo with ACK get lost
   * Answer-Frames are sometimes sent to the wrong IP destination



Version 1.2.0 - 2018-07-06
--------------------------------------------------------------

** Bugfix
   * If an input is configured as a switch, a long keystroke is sent when the input is opened.
   * Fix CCM flags according to RFC3610

** Improvement
   * Add new parameter for Contrast
   * Unify values for undervoltage



--- END OF FILE ---
