## [HmIP-eTRV-B-2_R4M_update_V1_4_0_250616.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-eTRV-B-2_R4M_update_V1_4_0_250616.tgz)
Required CCU firmware version: &#8805; 3.83.6<br/>
<sub>sha256: 65f051a9013564a97ebd036e5ade71b66a0f1c4d29a384bafc349b4ac4abbb7c</sub>

C H A N G E L O G
-----------------

Version 1.4.0 - 2025-06-06
--------------------------------------------------------------

** Bugfix
   * Missing valve is not detected after decalcification run
   * After a reinclusion, the device sometimes only reacts to a window contact after deleting and reintegrating. 
   * The device does not report an error if the decalcification run is performed without a valve
   * Correction for MANU set point temperature update after window open.
     If window open is detected (extern/intern) and during this time the device get the command "Eco-Mode", the device updated the set point temperature after window close and "Eco-Mode" off to the window open temperature.

** Improvement
   * Unnecessary valve movements with several window contacts.
     If several window contacts are linked to the device, an unwanted valve movement occurred from the second window open message.
   * The automatic switchover from manu-mode to auto-mode after a restart following receipt of the first time-info telegram should be deactivated.



Version 1.2.28 - 2024-10-14
--------------------------------------------------------------

** Improvement
   * Optimization of temperature control properties in conjunction with a wall thermostat



Version 1.2.26 - 2022-09-12
--------------------------------------------------------------

** Bugfix
   * Race condition during lcd port test
   * SWDCLK Pin on LCD Coprocessor causes some LCD segments to light up on boot



Version 1.2.24 - 2022-09-05
--------------------------------------------------------------

** Bugfix
   * The second bar for the weekly program is never shown in the display.



Version 1.2.22 - 2022-08-15
--------------------------------------------------------------

** New Feature
   * First Release



--- END OF FILE ---
