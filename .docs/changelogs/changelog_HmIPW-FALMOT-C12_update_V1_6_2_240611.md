## [HmIPW-FALMOT-C12_update_V1_6_2_240611.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-FALMOT-C12_update_V1_6_2_240611.tgz)
Required CCU firmware version: &#8805; 3.75.6<br/>
<sub>sha256: 0465289cea4a5c67e666faa58b4e833d83921b1c92bce55dff73483a3f277a33</sub>

C H A N G E L O G
-----------------

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

First Release.


--- END OF FILE ---

