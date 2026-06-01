## [HmIPW-DRD3_update_V2_0_6_230412.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-DRD3_update_V2_0_6_230412.tgz)
Required CCU firmware version: &#8805; 3.43.15<br/>
<sub>sha256: 5dc13e8576fdf6f6a16954445bb639e00615d69c37c22055a06443749c7c646c</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIPW-DRD3 - Homematic IP Wired Dimming Actuator - 3 channels

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 2.0.6 - 2023-03-27
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * Channelstates are not set to off on copro overtemp event



Version 1.4.8 - 2022-03-23
--------------------------------------------------------------

** Bugfix
   * General improvements - Code optimisation



Version 1.4.6 - 2021-07-23
--------------------------------------------------------------

** Improvement
   * Rework of update process



Version 1.4.4 - 2021-05-06
--------------------------------------------------------------

** Bugfix
   * Dimming direction change if other input is press
   * Wrong lock timeout handling for event counter
   * Wrong order in the list 1 parameters of the real channel in dimmer actuators
   * DEC ExecutionStart with level 0 is set channel to 100%
   * HMIPW_DRD3-58 - Error if one or more channels are switching
   * Error in the dst handling (changeover) if dst is given by SHC



Version 1.4.2 - 2021-03-11
--------------------------------------------------------------

** Improvement
   * Adjustment behavior at "Channel inactive"



Version 1.4.0 - 2021-02-18
--------------------------------------------------------------

** Bugfix
   * After a long button press, one channel will sporadically remain permanently supplied with 230 volts.
   * A long keypress release leads to longer run time than the previous ones if the driving time is shorter than the long keypress repetition time
   * Wrong handling in the update module if channels are not active 
   * In a switching group, only the first channels are switched on
   * After a long button press, one channel will sporadically remain permanently supplied with 230 volts.
   * No status frame if a level change (not 0) is done and the start level is != 0

** New Feature
   * Implement channel parameter for setting the Dimm-Min-Level.
   * Implement channel parameter for setting the Dimm-Min-Level.
   * Switch-off ramp via central programs or automation.

** Improvement
   * The time information telegram does not contain a note about the sommer / winter time change.
   * Error on the display and in the status frame if mains power is missing, although the channel state is inactive



Version 1.0.0 - 2019-03-01
--------------------------------------------------------------

** Bugfix
   * Weekprogram configuration lists are not working properly 
   * Event counter timeout isn't reset if within the triggered profile the multiexecution flag isn't set
   * Short key press of key visual leads to a restart, if a factory reset was aborted before
   * Answer-Frames are sometimes sent to the wrong IP destination
   * Weekprogram doesn't work correctly if several virtual channels shall be triggered by one switching point
   * Homematic IP actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover.
   * Divide maximum number of partners for virtual channels into individual values for virtual A, B and C

** Improvement
   * Modify event counter check to meet current specification
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.
   * Add new parameter for Contrast



--- END OF FILE ---
