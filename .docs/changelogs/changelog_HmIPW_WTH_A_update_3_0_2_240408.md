## [HmIPW_WTH_A_update_3_0_2_240408.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW_WTH_A_update_3_0_2_240408.tgz)
Required CCU firmware version: &#8805; 3.79.6<br/>
<sub>sha256: 2746ff8d6094ba4499996fba35f79d7c388e226af3fe14ccb4b677177f5818e3</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version
of the CCUx!

Device: HmIPW-WTH-A - Homematic IP Wired Wall Thermostat with Humidity Sensor

Company: eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 3.0.2 - 2024-04-08
--------------------------------------------------------------

** Bugfix
   * Symbol display for heating / cooling is missing if an actuator link exists.
      With the new FW version it is now possible to operate the two-point control
      depending on the operating mode (heating / cooling). Here, the symbol should also
      be shown on the display accordingly.
   * The Encoder-Button response without backlight "Off", only worked every second time.
   * The "Heating Controller Mode" frame was sent several times.
      The "Heating Controller Mode" telegram was sent cyclically to each channel of the
      FAL. It is sufficient if the telegram is sent to the FAL only once.
   * Boosttime was set in Party-Status-Info-Frame even if boost was not active.
   * Boot flag is reset prematurely.
      If a time info request is sent after a restart, the boot flag must not be missing
      in the regular status frame. If no response is sent from the access point to the
      time info request after a restart, the boot flag must not be reset in the status
      until the status frame has been acknowledged.
   * The device send no DEC telegram to link partners if a new link partner was
      previously added or removed.
   *  Instead of a conditional switch command the device should send a level command to
      linked switch actuators. This allows the actuator to be deactivated directly by
      the wall thermostat
   * Emergency shutdown at 30°C during cooling.
      Cooling is also active when the set temperature is greater than 30.0°C
   * Hysteresis for 2-point control with switching actuator does not work as specified.
      The hysteresis was not evaluated correctly for the humidity. The resolution
      should be 1%. However, it actually had a resolution of 2%.

** Improvement
   * The automatic switchover from manu-mode to auto-mode after a restart following
     receipt of the first time-info telegram should be deactivated.
   * The "Heating Controller Mode" frame was sent several times.
      The "Heating Controller Mode" telegram was sent cyclically to each channel of the
      FAL. It is sufficient if the telegram is sent to the FAL only once.
   * Instead of a conditional switch command the device should send a level command to
     linked switch actuators. This allows the actuator to be deactivated directly by the
     wall thermostat.
   * The cooling profile factory setting is set to 28°C.

** New Feature
    * Implementation of the "Heating controller 2 bit field" parameter in list 1 for
      channel 5
       The parameter values COOLING_ENABLE and HEATING_ENABLE were added for channel 5
       (Actuator link partner). This makes it possible to deactivate cooling or heating
       in the respective mode.


Version 2.8.010 - 2023-03-17
--------------------------------------------------------------

** First release


--- END OF FILE ---