## [HmIP-PDT-UK_update_V2_2_4_231123.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-PDT-UK_update_V2_2_4_231123.tgz)
Required CCU firmware version: &#8805; 3.73.9<br/>
<sub>sha256: bbd7f42100fffece86c39c3562c943fc0ad6876bde7ec265b3919ccfc5bb3f8e</sub>

C H A N G E L O G
-----------------

Version 2.2.4 - 2023-11-10
--------------------------------------------------------------

** Bugfix
   * Fixed error which leads to an boot failure under some special conditions. 



Version 2.2.2 - 2023-09-11
--------------------------------------------------------------

** Bugfix
   * No signaling of the switching status on the system LED



Version 2.2.0 - 2023-06-08
--------------------------------------------------------------

** Bugfix
   * The ON_MIN_LEVEL parameter is evaluated inconsistently for a DEC and a direct link.

** Improvement
   * Add 2 configuration parameters for better dimming of LED lamps



Version 2.0.0 - 2022-12-07
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * Device sends answers-frame on a TimeInfo from AC to "any-router"-address 
   * Device does a reboot if factory reset is aborted
   * In a switching group, only the first channels are switched on
   * With the settings "Anzahl der auszulassenden Statusmeldungen = 0" and "Anzahl der auszulassenden, unverÃ¤nderten Statusmeldungen = 0" the status is not transmitted in 2 to 3 minute intervals
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.
   * Wrong behaviour if a link partner is answering late
   * A TimeInfo frame with ARR-Bit will not be answered
   * Homematic IP actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover.
   * Factory-Reset timing not correct
   * device uses OFF_LEVEL of a direct link for direct execution command if level of direct execution is 0
   * After an OTAU reboot the inclusion requests are send to address 0x000000 sometimes

** New Feature
   * Implement channel parameter for setting the Dimm-Min-Level.
   * Switch-off ramp via central programs or automation.
   * Rework AppSequenceCounter validation to a counter range check

** Improvement
   * Switch from external to internal oscillator
   * The time information telegram does not contain a note about the sommer / winter time change.
   * Modify event counter check to meet current specification
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.



Version 1.6.0 - 2017-11-21
--------------------------------------------------------------

** Bugfix
   * Device does a reboot if factory reset is aborted
   * A TimeInfo frame with ARR-Bit will not be answered
   * Homematic IP actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover.
   * device uses OFF_LEVEL of a direct link for direct execution command if level of direct execution is 0
   * After an OTAU reboot the inclusion requests are send to address 0x000000 sometimes

** New Feature
   * Rework AppSequenceCounter validation to a counter range check

** Improvement
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.



--- END OF FILE ---
