## [HmIP-FROLL_update_V1_10_16_230616.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-FROLL_update_V1_10_16_230616.tgz)
Required CCU firmware version: &#8805; 3.69.5<br/>
<sub>sha256: 4c2ae03e84add793926e392ffd470ece72cb813925972ef5378e9257f11afa13</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:		HmIP-FROLL - Homematic IP Shutter Actuator for flush mount

Company:	eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.10.16 - 2023-05-04
--------------------------------------------------------------

** Improvement
   * Execute function "Enable operation within one end position to manually solve any error" only by a long button press


Version 1.10.12 - 2022-12-05
--------------------------------------------------------------

** Bugfix
   * If the device is restarted while overtemperature error the first statusinfo after restart doesn't signalize an error
   * A long keypress release leads to longer run time than the previous ones if the driving time is shorter than the long keypress repetition time
   * After a long keypress the actor runs longer than the set driving time
   * Section of virtual channels remains in "Move up/down reference run" if all three virtual channels are triggered by Direct Execution Command at startup
   * A command triggered by weekprogram or internal link is handled by the virtual channels although an error is active
   * Wrong evaluation of the event counter with multiple links between sensor and actuator

** Improvement
   * The level values 201 (last value) and 202 (don't care) to a virtual channel shall be directly passed through to the real channel
   * Changing driving directions with HmIP UP actuators via parameters
   * HmIP actuators with default links as button pair, should also have ABORT_EVENT_SENDING_CHANNELS as default in pairs
   * The time information telegram does not contain a note about the sommer / winter time change
   * Enable operation within one end position to manually solve any error
   * Switch from external to internal oscillator


Version 1.8.12 - 2019-09-03
--------------------------------------------------------------

** Bugfix
   * negative coordinates are not handled correctly
   * incorrect data type order for error status info message
   * default profile for long keypresses is useless
   * missing rf connection leads to stop of local operation at long key presses
   * bug in the creation of direct execution command for the weekprogram
   * actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover
   * HmIP radio shutter and blind actuators can be made to send DeviceInclusions again by a RetriggerDeviceInclusion Request, although this function was only intended for Wired devices
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up
   * Shutters and blinds with longer driving times do not reach end position by short movements (very small values for MAX_TIME_FIRST_DIR)
   * Device does not work correctly after overtemperature was detected

** Improvement
   * added parameter DELAY_COMPENSATION to give the user the opportunity to use motors 
     with greater delay time between switching the relay and start of motor movement.
   * new parameter to disable messages to the AC
   * new operation mode for wired devices
   * event counter validation expanded to range
   * all powerup parameters are supported now
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality
   * Modify event counter check to meet current specification
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES
   

Version 1.2.0 - 2017-05-18
--------------------------------------------------------------

** First release


--- END OF FILE ---
