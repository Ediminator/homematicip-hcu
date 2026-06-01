## [HmIP-eTRV-C-2_update_V1_4_14_220128.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-eTRV-C-2_update_V1_4_14_220128.tgz)
Required CCU firmware version: &#8805; 3.53.34 / 2.53.34<br/>
<sub>sha256: ee3632fd683cb6d53b1c189447d37b438987c2ce845d5c202edad7e10e80205d</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:   HmIP-eTRV-C-2 - Homematic IP Radiator Thermostat - Compact

Company:  Q-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.4.014 - 2022-01-28
--------------------------------------------------------------

* Bugfix
   * The time information telegram does not contain a note about the summer / winter
     time change.
      So it was possible that a time request to the access point in the period where the
      changeover from summer to winter time takes place could lead to a double
      changeover.
   * The device no longer heats correctly after a link to the WTH has been created.
      If the link between eTRV and WTH was deleted and then a new link was created, the
      devices only synchronized again after a restart (battery change) at the eTRV.
   * Correction for MANU set point temperature update after window open.
      If window open is detected (extern/intern) and during this time the device get the
      command "Eco-Mode", the device updated the set point temperature after window
      close and "Eco-Mode" off to the old set point temperature.
   * If the adaptation drive is faulty, it will not be repeated automatically.
      If the adaptation drive fails, it is first repeated automatically before being
      aborted with the corresponding error message
   * Stabilization of the adaptation drive.
      The adaptation drive failed by some valves, this was corrected.


Version 1.4.006 - 2020-10-20
--------------------------------------------------------------

First Release.


--- END OF FILE ---

