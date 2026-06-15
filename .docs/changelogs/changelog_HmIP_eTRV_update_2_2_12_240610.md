## [HmIP_eTRV_update_2_2_12_240610.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP_eTRV_update_2_2_12_240610.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.35.10<br/>
<sub>sha256: 38cfa10ce3a8661ce26297b0b83c060af4413992e01541eef12c7142ad1bb39e</sub>

C H A N G E L O G
-----------------

Version 2.2.012 - 2024-05-03
--------------------------------------------------------------
Version:
  Application:  2.2.012
  Bootloader:   1.14.000
  Library:      1.64.000

** Bugfix
   * Communication problems with link partners if there is no cloud connection.
      If the cloud connection is lost, the Access Point reports this to the device with
      a "Destination unreachable". This message causes a longer processing time in the
      device. during this time, the device cannot be reached by link partners. This can
      lead, for example, to window open/close messages not being received.


Version 2.2.010 - 2022-01-05
--------------------------------------------------------------

** Modification
   * new HMOS Version


Version 2.2.008 - 2019-02-25
--------------------------------------------------------------

** Bugfix
   * eTRV sometimes responds delayed on window close.
      In cooperation with a WTH, a window-closing was not recognized again until the
      window-closing was signalled by the window contact and the next cyclic data tele-
      gram was received by the WTH.
   * Error when changing from winter to summer time.
      On the day of the time change, the time is increased by one hour every full hour
      after 2 o'clock.
   * Moving to the window open valve position happens twice.
      After opening the window, a new valve position is calculated. From time to time it
      happens that after moving to the new valve position, the valve move to the old
      valve position again for a short time.
   * Wrong set manu temperature after new start after reset.
      After a restart after a reset, the parameter values of the minimum and maximum
      setpoint temperature are queried too early, which erroneously sets manu setpoint
      temperature to 0 °C.

** Modification
   * In "Duration" replace the unit "days" by "10ms".
      Revision of the current "Duration", since days are not needed as a unit for a 16
      bit value anyway.
   * Adjustment of the LCD start display
      In the future only the application version major minor will be shown in the LCD
      start display. All further information can be found in the APP or the CCU.
   * No status info directly after inclusion
      To make the status visible faster, it is now sent to the access point directly
      after inclusion

** New Feature
   * Motor whisper mode
     The motor speed can be reduced by the parameter CHANNEL_OPERATION_MODE to minimize
     running noise.


Version 2.0.000 - 2017-09-25
--------------------------------------------------------------

** Bugfix
   * Correction in Paging-Module HMOS-Library
      Catched erros which could occure after an OTAU update to a newer paging module.
   * Correction for the Optimum Start Stop function
      After activating the optimum start stop function it is now executed correctly.

** Modification
   * Parameter extension for installer solution.
      With the help of the new parameter "DISABLE_MSG_TO_AC" all transmissions to the
      central address are suppressed. Also to the status receiver address if this is
      the same as the central address.


Version 1.8.000 - 2017-07-19
--------------------------------------------------------------

** Bugfix
   * Correction in temperature week program.
      If one daily temperature profiles consist of only one switch time point, the
      switch time point is skipped by midnight of the next day.
   * Correction for set point temperature update after window open.
      If window open is detected (extern/intern) and during this time the device get the
      command "Eco-Mode", the device updated the set point temperature after window
      close and "Eco-Mode" off to the old set point temperature.
   * Correction for set point temperature update after weekprogram configuration.
      If window open is detected (extern/intern) and during this time a new week program
      is transmitted to the device, the device updated the set point temperature after
      window close by using the new week program set point temperature.
   * Extension for the Quick Veto Function.
      If the quick veto function is active, the remaining time is transferred in the
      status telegram.
   * Behavior after aborting the factory reset.
      If the factory reset is aborted or not executed until the end, the device performs
      a reboot after the termination or after the timeout.
   * Abort of Quick Veto by "Duration = 0".
      If Quick Veto is active, Quick Veto can be aborted by the radio command
      "Duration = 0". The device answers the radio telegram with an "Ack".


Version 1.6.003 - 2017-02-02
--------------------------------------------------------------

** Bugfix
   * If more than two radiator thermostats are linked to each other, now the temperature
     fall detection is properly deactivated on all devices.
   * The Application_Sequence_Number for TIME_INFO_REQUEST is increment after sending.
   * If the device wait for incoming data, it don't responce to other requests.
   * New data packages will not be sent until the current data transmission has
     finished.

** Modification
   * Implementation of Quick-Veto-Function


Version 1.4.002 - 2016-06-08
--------------------------------------------------------------

** Bugfix
   * If the device is linked with a Remote-Control-Unit and the Parameter "ON_TIME" is
     set, the temperature "TEMPERATURE_RC" is hold minimum for this time (also the time
     is > 1 Minute).


Version 1.2.012 - 2015-12-09
--------------------------------------------------------------

** Bugfix
   *  Window open temperature isn't overwritten, when activating the party function.
   * In combination with multiple routers the device is reached via radio all the time.
   * If a DEC is send with "actual temperature" and "4.5°C" as setpoint the device
     performs nothing.
   * At window-open, a manually change on the device, is now transferred correctly from
     TRV link partners.
   * Window status of SWD link partner is reset when the link partner is deleted.
   * If the party mode is abort from the HAP, the party mode is immediately leave.

** Modification
   * Heating-Control in connection with a WTH shows occasionally two-point behavior.
   * Change in library m_rx_options.header.header.bidi to m_rx_options.header.header.arr
   * Modification of full-rx-timeout in the application for router functionality.
   * Modification holiday period (start and end) must be transmitted as a status for
     CCU2 integration.
   * Changeover the project to the hmos library


Version 1.0.018 - 2015-06-24
--------------------------------------------------------------

First Release.

--- END OF FILE ---