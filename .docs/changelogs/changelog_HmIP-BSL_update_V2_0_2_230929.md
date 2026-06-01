## [HmIP-BSL_update_V2_0_2_230929.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-BSL_update_V2_0_2_230929.tgz)
Required CCU firmware version: &#8805; 3.75.6<br/>
<sub>sha256: d3c95f739cb5cfb5772002621979c93449d8602fd65ec9f7da08245f470e7ce7</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-BSL - Homematic IP Switch Actuator with Signal Lamp â for brand switches

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 2.0.2 - 2023-09-29
--------------------------------------------------------------

** Bugfix
   * Changelog only entry for Version 2.0.0
   * LinkProfile optical signal and optical signal off special values wrong
   * LinkProfil with OnOffLevel old value and dont care wrong
   * OnMinLevel at RealChannels not used with DEC
   * Only status info at error overtemp
   * DEC with duration ontime 0s is set as infinity
   * OpticalSignal in Linkparameter is used one time when OnOffTime is set
   * LED sequence 'Unused Button' is not used
   * No status info after OutputBehaviour use last selection which was != 0x00
   * Level is set from 0% to 5% if dec 0x8d with only enum is send
   * OutputBehaviour is always set to 0 if level is set to 0%
   * Level old value is not used at DEC 0x8d
   * PowerUpOpticalSignal is not used
   * Weekprogram with level on to old value not set the old value
   * At powerup jumptarget OffDelay output not switch on



Version 2.0.0 - 2023-08-01
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * In a switching group, only the first channels are switched on
   * System led shows also actions on channel 7 & 11 instead of only channel 3
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.
   * HmIP-BSL: Rocker switch no longer responds after frequent operation
   * System LED signals error (red) if rocker switch is linked to internal channel and 2 or more external channels
   * race condition may cause deadlock
   * False handling with two internal direct links
   * False function of ToggleDimLastDir in combination with ToggleDimToCounter
   * Reserved bit is set in StatusInfo Level Group
   * Output colour white when creating link partner

** New Feature
   * Switch-off ramp via central programs or automation.

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.
   * Extension of LED modes analog to HmIPW-WRC6
   * New profile parameter SHORT_OFF_OUTPUT_BEHAVIOUR for selecting an additional LED colour/behaviour
   * The time information telegram does not contain a note about the sommer / winter time change.
   * HmIP actuators with default links as button pair, should also have ABORT_EVENT_SENDING_CHANNELS as default in pairs.
   * Changing driving directions with HmIP UP actuators via parameters.
   * Modify event counter check to meet current specification
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality



Version 1.0.2 - 2018-08-30
--------------------------------------------------------------

** New Feature
   * First Release



--- END OF FILE ---
