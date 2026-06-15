## [HmIPW_FAL24_C6_update_2_4_6_230815.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW_FAL24_C6_update_2_4_6_230815.tgz)
Required CCU firmware version: &#8805; 3.73.4<br/>
<sub>sha256: 743ce7770ae988149ea6a825bd6cb75c376430a6a5f158c5705e96455fec6118</sub>

C H A N G E L O G
-----------------

Version 2.4.006 - 2023-08-04
--------------------------------------------------------------
  Application:      2.4.006
  Bootloader:       1.14.000
  BootloaderWired:  1.6.000
  Library:          1.64.000

** Bugfix
   * In stand-alone mode, the heat pump was not switched off 15 minutes before the last
     valves were closed.
   * Change from summer to winter time was not working.
   * Activation of pump function via select button in FW 2.2.6 not possible
   * After a communication error with the wall thermostat has been resolved, the
     channel LED may display an incorrect status for up to 15 minutes.

** New Feature
   * Added new parameter DEVICE_OPERATION_MODE to enable calculation of improved on times
     and post processing planner (for operation with heat pumps).
   * Added new parameter HEATING_PWM_CYLCE_TIME.


Version 2.2.006 - 2022-05-30
--------------------------------------------------------------
  Application:      2.2.006
  Bootloader:       1.14.000
  BootloaderWired:  1.6.000
  Library:          1.64.000

** Bugfix
   * DEC Identify: Time for display illumination was wrong.
      The lighting duration of the backlight and the system button by sending the DEC
      "Identify" does not correspond to the specification.
   * The channel 10 cannot be controlled above 17°C in pairing mode.
      After pairing, the device transmits the information to the wall thermostat
      whether External Clock is active or inactive. In this case, it is erroneously
      transmitted actively, so that the setting of the target temperature on the wall
      thermostat is limited.
   * Dew point sensor alarm from the MIOB was not forwarded to the MIOB switching
    output (dehumidification control).
     If dew point alarm was reported by the MIOB, this information was only forwarded to
     the wall thermostats but not back to the MIOB to the switching output (dehumidifier
     control).
   * WTH-2 "%" symbol is not removed when the humidity and dew alarm are cancelled.
   * In the case of NormallyOpen, the LED states are not displayed correctly when the
     channels are switched on manually on the device.
** Improvement
   * The time information telegram does not contain a note about the summer / winter
     time change.
      So it was possible that a time request to the access point in the period where the
      changeover from summer to winter time takes place could lead to a double
      changeover.
   * Perform valve protection function on all channels
      The valve protection function was previously only executed for channels that were
      also linked to a wall thermostat. This has changed, the function is now also
      executed for channels that do not have a link partner. However, the channels with
      a link partner are decisive for the execution.
** New Feature
   * Extension of the humidity limit by a pre-limit.
      Humidity Monitoring has been extended by a threshold. With the help of this
      threshold, a first alarm can be triggered even before the current threshold. The
      first alarm activates a dehumidifier in connection with a MIOB, when the second
      threshold is triggered, cooling is also stopped, and the corresponding valve is
      closed.


Version 2.0.002 - 2019-02-15
--------------------------------------------------------------

First Release.

--- END OF FILE ---

