## [HmIPW_STH_update_3_0_2_240503.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW_STH_update_3_0_2_240503.tgz)
Required CCU firmware version: &#8805; 3.81.5<br/>
<sub>sha256: 60ea3fec600bd235e86ad9da0121d373c6b1d3cd1f5561da979ed4359e3a7f4d</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version
of the CCUx!

Device: HmIPW-STH - Homematic IP Wired Temperature and Humidity Sensor - indoor

Company: eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 3.0.2 - 2024-04-08
--------------------------------------------------------------

** Bugfix
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


Version 2.8.010 - 2022-10-10
--------------------------------------------------------------

** Bugfix
   * After reinclusion, partly cyclic data telegrams for eTRV, actuator and FAL are not
     sent.


Version 2.8.002 - 2021-12-08
--------------------------------------------------------------

** Bugfix
   * Device does not respond to ALL_TRIPLE_BURST_LISTENING_DEVICES.
      A generally valid message to the address ALL_TRIPLE_BURST_LISTENING_DEVICES is
      supported now.
   * DRIx window contacts of a room cannot form the necessary AND connection.
      If a window contact with several channels is linked as partner, window-closed was
      already detected if only one channel of the window contact reported window-closed.

** New Feature
   * Switchover for use either as thermostat or as hygrometer (2-point control) with
     effect on the actor channel and/or internal switching actuator.
      Via the parameter setting it is now possible to switch the actuator channel 5
      depending on the humidity.

** Improvement
   * Whenever connection to link partner FAL is checked, the led is blinking.
      If the wall thermostat is linked to a FAL or FALMOT, the link connection is
      checked every 50 minutes as standard. This results in a flashing LED on the
      thermostat. Especially if the connection is made via a router, this flashing could
      take longer. This should not be the case as it will cause confusion for customers.
      The LED should only be triggered when the customer makes manual changes.
   * The time information telegram does not contain a note about the summer / winter
     time change.
      So it was possible that a time request to the access point in the period where the
      changeover from summer to winter time takes place could lead to a double
      changeover.
   * Automatic switching between heating and cooling at the two-point control for
     actuator channel 5.
      Up to now, the parameter "Art der Zweipunktregelung" was used to specify whether
      the two-point control for the actuator channel 5 should heat or cool. This
      parameter has now been extended by the value heating and cooling. If this value is
      now selected, the two-point control is automatically changed to heating or
      cooling.
   * Smart RX FAL cyclic packet reduction
      To reduce the radio load, a check is made before each cyclic data telegram is sent
      to the FAL or FALMOT to determine whether it actually has to be sent. If there has
      been no change in the mode, the actual temperature, the humidity and the set
      temperature, the packet does not have to be sent every cycle.


Version 2.6.000 - 2019-09-04
--------------------------------------------------------------

** Bugfix
   * DEC Identify: Time for display illumination was wrong.
      The lighting duration of the backlight and the system button by sending the DEC
      "Identify" does not correspond to the specification.

** New Feature
   * Improvement for data communication.
      If possible the device send multicasts only to PARTNER_ALL_WIRED_DEVICES instead
      of to PARTNER_ALL_DEVICES.

** Improvement
   * Immediate evaluation of temperature change for the two-point-control.
      Temperature changes triggered by the central unit or a window contact, are
      forwarded directly to the switching actuators for the two-point-control.


Version 2.4.008 - 2019-03-07
--------------------------------------------------------------

** First release


--- END OF FILE ---