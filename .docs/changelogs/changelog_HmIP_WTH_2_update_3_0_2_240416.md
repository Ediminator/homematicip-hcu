## [HmIP_WTH_2_update_3_0_2_240416.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP_WTH_2_update_3_0_2_240416.tgz)
Required CCU firmware version: &#8805; 3.75.6<br/>
<sub>sha256: 1e23a94b20f9ea095aa468fb4c756a8e039ff3b0393c46212f0c8202f4207144</sub>

C H A N G E L O G
-----------------

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

** Modification
    Parameter extension for installer solution.
     With the help of the new parameter "DISABLE_MSG_TO_AC" all transmissions to the
     central address are suppressed. Also to the status receiver address if this is
     the same as the central address.
    In "Duration" replace the unit "Days" by "10ms".
     Revision of the current duration, becaues a 16 bit value are not needed as unit
     "Days" anyway.

** Improvement
    Adjustment of the LCD start display.
     In the future only the application version major minor will be shown in the LCD
     start display. All further information can be found in the app or the ccu.


Version 2.0.002 - 2018-04-06
--------------------------------------------------------------

** Bugfix
   * Logic "Window open temperature" corrected in cooling mode
      In cooling mode, it is not advisable to change to the window open temperature, as
      a result, more cooling would have to be used.
   * Error during window open in cooling mode
      While window open in cool mode a new set temperature sent from the access point is
      not taken over.
   * Error when changing from winter to summer time.
      On the day of the time change, the time is increased by one hour every full hour
      after 2 o'clock.

** Modification
   * Function modification of Optimum-Start-Stop
      Change to Optimum Start, means that the comfort temperature should be reached at
      the desired point in time, the lowering temperature not.
   * Extension for pairing with a FALMOT


Version 1.8.000 - 2017-09-15
--------------------------------------------------------------

** Bugfix
   * Correction in Paging-Module HMOS-Library
      Catched erros which could occure after an OTAU update to a newer paging module.
   * Correction for the Optimum Start Stop function
      After activating the optimum start stop function it is now executed correctly.
 
** Modification
   * Parameter extension for installer solution.
      With the help of the new parameter "DISABLE_MSG_TO_AC" all transmissions to the
      central address are suppressed. Also to the status receiver address if this is the
      same as the central address.


Version 1.6.000 - 2017-07-21
--------------------------------------------------------------

** Bugfix
   * Expansion for inclusion condition.
      If parameter changes have been made to the device before the inclusion, the device
      can only be included if a factory reset has been performed on the device before.
   * Correction for set point temperature update after weekprogram configuration.
      If window open is detected (extern/intern) and during this time a new week program
      is transmitted to the device, the device updated the set point temperature after
      window close by using the new week program set point temperature.
   * Correction when changing from auto mode to manu mode.
      When changing from auto mode to manu mode and boost is active, boost is abort.
   * The date and time are cyclically synchronized with the access point.
      In order that  date and time are be synchron in system, the data is retrieved
      every 6 hours at Access point.
   * Behavior after aborting the factory reset.
      If the factory reset is aborted or not executed until the end, the device performs
      a reboot after the termination or after the timeout.

** Improvement
   * If the quick veto function is active, the remaining time is transferred in the
     status telegram.
   * Abort of Quick Veto by "Duration = 0".
      If Quick Veto is active, Quick Veto can be aborted by the radio command
      "Duration = 0". The device answers the radio telegram with an "Ack".


Version 1.4.004 - 2017-02-14
--------------------------------------------------------------

** Bugfix
   * Bug fixing in temperature week program
     If one daily temperature profiles consist of only one switch time point, the switch
     time point is skipped by midnight of the next day.
   * The Application_Sequence_Number for TIME_INFO_REQUEST is increment after sending.
   * If the device wait for incoming data, it don't responce to other requests.
   * "Sa" and "Su" symbols are displayed during the weekend profile setting.
   * Time profile "Sunday" is accepted.
   * Time profile can be read out.
   * RF-Data-Communication Improvement:
     New data packages will not be sent until the current data transmission has
     finished.

** New Feature
   * Implementation of Quick-Veto-Function (Default: inactive)


Version 1.2.002 - 2016-08-31
--------------------------------------------------------------

** Bugfix
   * The antenna symbol is not flashing when the communication does take place
     indirectly via a router.
   * If Party-Mode active, the device send in Pairing-Mode no Status-Messages to address
     0x000000.
   * If the FAL send a Direct Execution Command with Humidity limiter state "True", the
     device is not change from cooling mode to heating mode ( if cooling is activ ).
   * After troubleshooting with fix V1.2.001 it was no longer recognized that a MIOB is
     in the system.

** Modification
   * Party/Holiday function is distributed by FAL to link partner.


Version 1.0.013 - 2016-06-30
--------------------------------------------------------------

** First release


--- END OF FILE ---