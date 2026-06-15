## [HmIPW-DRBL4_update_V1_10_18_230728.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-DRBL4_update_V1_10_18_230728.tgz)
Required CCU firmware version: &#8805; 3.75.1<br/>
<sub>sha256: 0284a2a1d3daae056bd857b7fe6ee2246bf4f200ae25e2a955556c9b3312f719</sub>

C H A N G E L O G
-----------------

Version 1.10.18 - 2023-07-28
--------------------------------------------------------------

** Bugfix
   * Configuration parameters cannot be saved



Version 1.10.16 - 2023-06-16
--------------------------------------------------------------

** Improvement
   * Execute function "Enable operation within one end position to manually solve any error" only by a long button press



Version 1.10.8 - 2022-11-15
--------------------------------------------------------------

** Bugfix
   * Error in slat adjustment, slats move in the wrong direction
   * Wrong evaluation of the event counter with multiple links between sensor and actuator



Version 1.10.0 - 2022-06-05
--------------------------------------------------------------

** Bugfix
   *  Error when the same position is called up several times
   * A command triggered by weekprogram is handled by the virtual channels although an error is active

** New Feature
   * Add possibilty to increase the time between two slats movements

** Improvement
   * Change of driving time while long button press if the end position of the slats is reached
   * Enable operation within one end position to manually solve any error
   * The time information telegram does not contain a note about the sommer / winter time change.



Version 1.8.4 - 2022-10-19
--------------------------------------------------------------

** Improvement
   * General improvements - Code optimisation



Version 1.8.2 - 2021-02-15
--------------------------------------------------------------

** Bugfix
   * Section of virtual channels remains in "Move up/down reference run" if all three virtual channels are triggered by Direct Execution Command at startup



Version 1.8.0 - 2021-01-15
--------------------------------------------------------------

** Bugfix
   * After a long button press, one channel will sporadically remain permanently supplied with 230 volts.
   * After a long keypress the actor runs longer than the set driving time



Version 1.6.0 - 2020-06-26
--------------------------------------------------------------

** Improvement
   * Add CHANNEL_OPERATION_MODE to switch between blind and shutter mode



Version 1.4.0 - 2019-09-24
--------------------------------------------------------------

** Bugfix
   * Shutters and blinds with longer driving times do not reach end position by short movements (very small values for MAX_TIME_FIRST_DIR)
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.

** Improvement
   * Modify event counter check to meet current specification



Version 1.2.10 - 2018-11-07
--------------------------------------------------------------

** Bugfix
   * Device doesn't show the supply voltage on display, instead an error is shown



Version 1.2.8 - 2018-11-06
--------------------------------------------------------------

** Bugfix
   * Short key press of key visual leads to a restart, if a factory reset was aborted before
   * Event counter timeout isn't reset if within the triggered profile the multiexecution flag isn't set



Version 1.2.6 - 2018-09-28
--------------------------------------------------------------

** Bugfix
   * Weekprogram sometimes does not trigger all channels



Version 1.2.4 - 2018-08-27
--------------------------------------------------------------

** Bugfix
   * If more than one status ACK frame is within the answer queue only the first one is send. Afterwards every new status ACK only triggers the last one
   * Statusinfo module creates status ACK telegrams with set ACK, ARR and Boot bits if this is the first status to be sent after startup
   * HmIP_APP: Send node confusion when using external send nodes
   * Sometimes Statusinfo uses old ApplicationSequenceNumber and Statusinfo with ACK get lost
   * Answer-Frames are sometimes sent to the wrong IP destination



Version 1.2.2 - 2018-08-14
--------------------------------------------------------------

** Bugfix
   * Real channel does not reach correct final slats position if more than one virtual channel is triggered at same time
   *  Weekprogram doesn't work correctly if several virtual channels shall be triggered by one switching point



Version 1.2.0 - 2018-08-01
--------------------------------------------------------------

** Bugfix
   * configuration of weekprogram channel does not work
   * First drive of channel 5, 9 and 13 always takes 90 seconds although the driving time was modified
   * Device sends no status info at local operation
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



--- END OF FILE ---
