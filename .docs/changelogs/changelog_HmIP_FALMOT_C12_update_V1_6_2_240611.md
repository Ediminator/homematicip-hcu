## [HmIP_FALMOT_C12_update_V1_6_2_240611.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP_FALMOT_C12_update_V1_6_2_240611.tgz)
Required CCU firmware version: &#8805; 3.75.6<br/>
<sub>sha256: 53ae19ca1dc1f2b8ab4148ec6ed36b80b6b424db71a6126fd67e1e9631da14f5</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:   HmIP-FALMOT-C12 - Homematic IP Floor Heating Actuator - 12 channels, motorised

Company:  eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.6.2 - 2024-06-11
--------------------------------------------------------------
** Bugfix
   * The device opened the valve in heating mode when the actual temperature is
     permanently higher than 32 degrees.
   * DST in TimeInfoResponse is not observed, i.e. a time transfer during the
     changeover to winter time may temporarily result in an incorrect time.
   * Communication test with wall thermostat does not work as expected.
     When the test is started, the valve is opened completely. However, if the valve is
     already fully open, nothing happens except for the green confirmation flash on the
     wall thermostat. The function has been changed as follows: If the valve position
     is < 50, 100% is approached, otherwise 0%.
   * Bar graph display during adaptation drive does not meet expectations. If the valves
     have moved to the end position and the adpation run has not yet been started, all
     bars of the valves should be displayed to indicate that they are fully open.
   * Pairing from FALMOT-C12 to FALMOT-C12 was acknowledged by red LED

** Improvement
   * Valve adaptation was carried out more frequently than necessary during operation.
   * Decalcification as the cause of heat pump malfunction
      Due to the weekly adaptation run, all valves were closed for a short period of
      time, which meant that no more heat was taken and some heat pumps ran into an
      error.


Version 1.4.010 - 2023-09-29
--------------------------------------------------------------
** Improvement
   * optimization of the valve control


Version 1.4.008 - 2022-09-27
--------------------------------------------------------------
** Modification
   * new HMOS Version


Version 1.4.006 - 2021-02-09
--------------------------------------------------------------
** Bugfix
   * FALMOT reports disconnection to WTH if "Window open" is reported by WTH for longer
     than 3 hours.
      As soon as window open was signaled by the WTH, the cyclic telegram set/actual
      temperature from the WTH was no longer processed by the device, i.e. set and
      actual temperature were not updated until window close.
   * When the time request changes to the WTH partner, it does not change back to the
     Access Point
      If the Access Point is not reachable, the time request is sent to a known WTH. The
      time request was then sent permanently to this partner. This led to increased data
      communication if routers in the field.


Version 1.4.002 - 2020-11-30
--------------------------------------------------------------
** Bugfix
   * The channel 12 cannot be controlled above 17 C in pairing mode.
      After pairing, the device transmits the information to the wall thermostat whether
      External Clock is active or inactive. In this case, it is erroneously transmitted
      actively, so that the setting of the target temperature on the wall thermostat is
      limited.
   * In cooling mode, the valves are closed at temperatures above 30  C.
   * DEC Identify: Time for display and system key illumination was wrong.
      The lighting duration of the backlight and the system button by sending the DEC
      "Identify" does not correspond to the specification.
   * The device sends invalid status frame.
      If additional configuration is transmitted during the status transmission, wrong
      values could be transmitted in the status.
   * The time information telegram does not contain a note about the summer / winter
     time change.
      So it was possible that a time request to the access point in the period where the
      changeover from summer to winter time takes place could lead to a double
      changeover.
   * Device crash in connection with a router.
      If commands from the AP could not be sent directly to the device and reached the
      device through a router, a device crash could occur.
   * Failure if WTH link partner is additionally linked to an eTRV and Optimum-Start-
     Stop is active at the WTH.
      The device did not distinguish between the HeatingControlMode frames sent to the
      eTRV or directly to the FALMOT. As long as Optimum-Start-Stop was not activated,
      this was not a problem, because the same info (set and actual temperature) was
      transmitted in both frames. However, if Optimum-Start-Stop is active, the
      telegrams are temporarily different and this led to a valve opening and closing on
      the device.


Version 1.2.002 - 2020-02-24
--------------------------------------------------------------
** Bugfix
   * Individual status changes on channel 1 were not transmitted.
      Status changes that only affect channel 1 were not transmitted. Only if further
      channels had status changes, the change of channel 1 was transmitted.

** New Feature
   * Implementation of automatic hydraulic adjustment.
      In order not to have to carry out a manual hydraulic adjustment, this is
      automatically do by the device.


Version 1.0.010 - 2019-08-12
--------------------------------------------------------------
** Improvement
   * Extension by valve PWM control at valve position < 15%.
      In order to prevent in rooms with several heating circuits being operated with the
      same room thermostat from maintaining different floor surface temperatures, a PWM
      control is switched on for small valve positions.


Version 1.0.008 - 2019-03-18
--------------------------------------------------------------

First Release.


--- END OF FILE ---

