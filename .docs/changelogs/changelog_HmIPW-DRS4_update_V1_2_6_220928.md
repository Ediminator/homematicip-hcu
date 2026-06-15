## [HmIPW-DRS4_update_V1_2_6_220928.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-DRS4_update_V1_2_6_220928.tgz)
Required CCU firmware version: &#8805; 3.43.15<br/>
<sub>sha256: 0865ce0ec6d2e6f0c4de2f518b0cce0f840b6f746efebd3b4c85de5dba2d8e90</sub>

C H A N G E L O G
-----------------

Version 1.2.6 - 2022-09-28
--------------------------------------------------------------

** Improvement
   * General improvements - Code optimisation



Version 1.2.4 - 2018-08-27
--------------------------------------------------------------

** Bugfix
   * If more than one status ACK frame is within the answer queue only the first one is send. Afterwards every new status ACK only triggers the last one
   * Statusinfo module creates status ACK telegrams with set ACK, ARR and Boot bits if this is the first status to be sent after startup
   * HmIP_APP: Send node confusion when using external send nodes
   * Sometimes Statusinfo uses old ApplicationSequenceNumber and Statusinfo with ACK get lost
   * Answer-Frames are sometimes sent to the wrong IP destination
   * Weekprogram doesn't work correctly if several virtual channels shall be triggered by one switching point



Version 1.2.2 - 2018-07-05
--------------------------------------------------------------

** Bugfix
   * Profile: Buffer for learned links can overflow



Version 1.2.0 - 2018-07-03
--------------------------------------------------------------

** Bugfix
   * If the link partner is known, an NAK is sent on ("invalid") frames without ARR bit
   * If "Disable Message to AC" is activated and only one channel is addressed, no App-Ack is sent.
   * Direct Execution Commands without ARR bit are answered at application level
   * Homematic IP actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover.
   * Divide maximum number of partners for virtual channels into individual values for virtual A, B and C
   * Fix CCM flags according to RFC3610

** Improvement
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.
   * Add new parameter for Contrast
   * Unify values for undervoltage
   * Increase interval for switching actuator channels after power up



--- END OF FILE ---
