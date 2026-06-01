## [HmIP-WTH-B-A_update_V1_4_2_240418.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-WTH-B-A_update_V1_4_2_240418.tgz)
Required CCU firmware version: &#8805; 3.73.9<br/>
<sub>sha256: 9eb4da2ee142f531a610ce431ee6deeb8812215e4f34a59b7516c12990395e6a</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device: HmIP-WTH-B-A - Homematic IP Wall Thermostat - basic

Company: eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.4.2 - 2024-04-18
--------------------------------------------------------------
** Bugfix
   * The "Heating Controller Mode" frame was sent several times.
      The "Heating Controller Mode" telegram was sent cyclically to each channel of the
      FAL. It is sufficient if the telegram is sent to the FAL only once.
   * The device send no DEC telegram to link partners if a new link partner was
     previously added or removed.
   * Instead of a conditional switch command the device should send a level command to
     linked switch actuators. This allows the actuator to be deactivated directly by the
     wall thermostat.
   * Hysteresis for 2-point control with switching actuator does not work as specified.
     The hysteresis was not evaluated correctly for the humidity. The resolution should
     be 1%. However, it actually had a resolution of 2%.
   * Emergency shutdown at 30Â°C during cooling.
      Cooling is also active when the set temperature is greater than 30.0Â°C
** Modification
   * Default Value of TEMPERATURE_LOWERING_COOLING to 30.0Â°C
   * Cooling Weekprogram to Flatline 28Â°C
   * The automatic switchover from manu-mode to auto-mode after a restart following
     receipt of the first time-info telegram should be deactivated.
** New Feature
   * New Parameter TEMPERATURE_WINDOW_OPEN_COOLING for set point temperature in cooling
     mode.
   * Implementation of the "Heating controller 2 bit field" parameter in list 1 for
     channel 5. The parameter values COOLING_ENABLE and HEATING_ENABLE were added for
     channel 5 (Actuator link partner). This makes it possible to deactivate cooling or
     heating in the respective mode.


Version 1.2.020 - 2023-04-20
--------------------------------------------------------------
** Version
   * Application: 1.2.018
   * Bootloader:  1.16.002
   * Library:     1.64.000

** Bugfix
   * After reinclusion, partly cyclic data telegrams for eTRV, actuator and FAL are not
     sent.
   * Device cannot be paired with channel 11 and 12 of FALMOT in pairing mode.


Version 1.2.016 - 2022-03-25
--------------------------------------------------------------

** First release


--- END OF FILE ---

