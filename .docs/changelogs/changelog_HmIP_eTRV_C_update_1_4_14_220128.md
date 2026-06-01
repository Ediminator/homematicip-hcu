## [HmIP_eTRV_C_update_1_4_14_220128.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP_eTRV_C_update_1_4_14_220128.tgz)
Required CCU firmware version: &#8805; 3.45.5 / 2.45.5<br/>
<sub>sha256: f31087c4465466994f345db39acb1a41239c25e3ba912880632232c37e2ed9e4</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device: HmIP-eTRV-C - Homematic IP Radiator Thermostat Compact

Company: Q-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.4.014 - 2022-01-28
--------------------------------------------------------------

* Bugfix
   * The device no longer heats correctly after a link to the WTH has been created.
      If the link between eTRV and WTH was deleted and then a new link was created, the
      devices only synchronized again after a restart (battery change) at the eTRV.
   * The time information telegram does not contain a note about the summer / winter
     time change.
      So it was possible that a time request to the access point in the period where the
      changeover from summer to winter time takes place could lead to a double
      changeover.
   * DRIx window contacts of a room cannot form the necessary AND connection.
      If a window contact with several channels is linked as partner, window-closed was
      already detected if only one channel of the window contact reported window-closed.
   * Correction for MANU set point temperature update after window open.
      If window open is detected (extern/intern) and during this time the device get the
      command "Eco-Mode", the device updated the set point temperature after window
      close and "Eco-Mode" off to the old set point temperature.
   * If the adaptation drive is faulty, it will not be repeated automatically.
      If the adaptation drive fails, it is first repeated automatically before being
      aborted with the corresponding error message


Version 1.2.004 - 2019-02-26
--------------------------------------------------------------

** Bugfix
   * Moving to the window open valve position happens twice.
      After opening the window, a new valve position is calculated. From time to time it
      happens that after moving to the new valve position, the valve move to the old
      valve position again for a short time.
   * Unconditional switch command to Multicast to wrong channel is answered.
      When receiving a unconditional switch command to the multicast address with wrong
      channel number, a nak was answered
   * Device does not respond to multicast AllTripleBurstListeningDevices.
      Frames with multicast address AllTrippleBurstListeningDevices was not responded.

** Modification
   * In "Duration" replace the unit "days" by "10ms".
      Revision of the current "Duration", since days are not needed as a unit for a
      16 bit value anyway.

** New Feature
   * Motor whisper mode
      The motor speed can be reduced by the parameter CHANNEL_OPERATION_MODE to minimize
      running noise.


Version 1.0.006 - earlier
--------------------------------------------------------------

First Release.

--- END OF FILE ---