## [HmIP-BDT_update_V2_2_4_231110.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-BDT_update_V2_2_4_231110.tgz)
Required CCU firmware version: &#8805; 3.73.9<br/>
<sub>sha256: 5f0809fd42120793daaeaf4e7c29e6e3ba9649ed6d4c528f6fe5a42c25eca90f</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-BDT - Homematic  IP 
Dimmer mit Phasenabschnittsteuerung fÃ¼r Markenschalterserien

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 2.2.4 - 2023-11-10
--------------------------------------------------------------

** Bugfix
   * Fixed error which leads to an boot failure under some special conditions. 



Version 2.2.0 - 2023-06-08
--------------------------------------------------------------

** Bugfix
   * The ON_MIN_LEVEL parameter is evaluated inconsistently for a DEC and a direct link.

** New Feature
   * Add separate LED mode with additional configuration parameters for a better dimming behaviour



Version 2.0.0 - 2022-12-06
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * In a switching group, only the first channels are switched on
   * With the settings "Anzahl der auszulassenden Statusmeldungen = 0" and "Anzahl der auszulassenden,unverÃ¤nderten Statusmeldungen = 0" the status is not transmitted in 2 to 3 minute intervals
   * Device sends answers-frame on a TimeInfo from AC to "any-router"-address 
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.
   * Rocker switch no longer responds after frequent operation
   * System LED signals error (red) if rocker switch is linked to internal channel and 2 or more external channels
   * Homematic IP actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover.
   * A TimeInfo frame with ARR-Bit will not be answered
   * Wrong behaviour if a link partner is answering late
   * Device does a reboot if factory reset is aborted
   * device uses OFF_LEVEL of a direct link for        direct execution command if level of direct execution is 0 
   * Wrong order of datatypes in the statusinfo frame
   * The Weekprogram astro times doesn't work correctly with negative latitude or longitude
   * After an OTAU reboot the inclusion requests are send to address 0x000000 sometimes

** New Feature
   * Implement channel parameter for setting the Dimm-Min-Level.
   * Switch-off ramp via central programs or automation.
   * Rework AppSequenceCounter validation to a counter range check
   * Support of HmIPW operation mode
   * Support of systems and solutions without a central unit (installer solution)

** Improvement
   * Switch from external to internal oscillator
   * The time information telegram does not contain a note about the sommer / winter time change.
   * HmIP actuators with default links as button pair, should also have ABORT_EVENT_SENDING_CHANNELS as default in pairs.
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES.
   * Changing driving directions with HmIP UP actuators via parameters.
   * Modify event counter check to meet current specification
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.
   * Changed default values for Powerup action parameters



Version 1.6.0 - 2017-11-21
--------------------------------------------------------------

** Bugfix
   * Homematic IP actuators trigger, due to the astro function, one hour delayed or prematurely on the day of the time changeover.
   * A TimeInfo frame with ARR-Bit will not be answered
   * Device does a reboot if factory reset is aborted
   * device uses OFF_LEVEL of a direct link for        direct execution command if level of direct execution is 0 
   * Wrong order of datatypes in the statusinfo frame
   * The Weekprogram astro times doesn't work correctly with negative latitude or longitude
   * After an OTAU reboot the inclusion requests are send to address 0x000000 sometimes

** New Feature
   * Rework AppSequenceCounter validation to a counter range check
   * Support of HmIPW operation mode
   * Support of systems and solutions without a central unit (installer solution)

** Improvement
   * All PowerUp parameters, that are listed in list 3 of the device, must be supported.
   * Changed default values for Powerup action parameters



Version 1.4.8 - 2017-08-01
--------------------------------------------------------------

** Bugfix
   * Implement missing support of the direct execution commands LOCK and UNLOCK
     
   * After the first time NACK answer, all answers are NACK
   * Device hangs up while installing update V1.2.2
   * Wrong applications sequence number after a long keypress
   * If not included, a long keypress triggers an inclusion request all 250 ms
   * Direct execution commands with speciale value level "old value" is not handled correctly
   * Device sends answers on multicast commandand on commands without arr bit in generally
     
   * If a sending device (RC etc. ) is connected to more than one virtual channel, only the first channel is switching.
     
   * Modify power up jump targets to match the power up jump targets of the switch actuators
   * Na answer on a configuration commit frame



--- END OF FILE ---
