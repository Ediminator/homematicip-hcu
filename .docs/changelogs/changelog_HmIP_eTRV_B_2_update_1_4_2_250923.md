## [HmIP_eTRV_B_2_update_1_4_2_250923.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP_eTRV_B_2_update_1_4_2_250923.tgz)
Required CCU firmware version: &#8805; 3.63.3<br/>
<sub>sha256: f5fe0d2295bf02c0db567f289382bf854f83f9395ea7a674b3f1fe62cc722772</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device: HmIP-eTRV-B-2 - Homematic IP Radiator Thermostat - basic

Company: eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.4.2 - 2025-09-23
--------------------------------------------------------------

** Bugfix
   * Correction for MANU set point temperature update after window open.
      If window open is detected (extern/intern) and during this time the device
      get the command "Eco-Mode", the device updated the set point temperature
      after window close and "Eco-Mode" off to the window open temperature.
   * The device did not report an error after the decalcification run is performed
     without a valve.
   * Unnecessary valve movements with several window contacts.
      If several window contacts are linked to the device, an unwanted valve movement
      occurred from the second window open message.
   * After a reinclusion, the device sometimes only reacts to a window contact after
     deleting and reintegrating.
   * Missing valve was not detected after decalcification run.

** Improvement
   * The automatic switchover from manu-mode to auto-mode after a restart following
     receipt of the first time-info telegram should be deactivated.


Version 1.2.014 - 2024-10-12
--------------------------------------------------------------

** Bugfix
   * Optimization of temperature control properties in conjunction with a wall
     thermostat.


Version 1.2.012 - 2022-03-17
--------------------------------------------------------------

** First release


--- END OF FILE ---