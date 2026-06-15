## [HMIP-WRC6_update_V2_2_14_220324.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HMIP-WRC6_update_V2_2_14_220324.tgz)
Required CCU firmware version: &#8805; 3.59.6 / 2.59.7<br/>
<sub>sha256: e41349f09a7f51bbeea1e9477792a24df677af6a5be57de6296e7602645a8da5</sub>

C H A N G E L O G
-----------------

Version 2.2.14 - 2022-03-24
--------------------------------------------------------------

** Bugfix
   * General improvements - Code optimisation



Version 2.2.12 - 2021-10-04
--------------------------------------------------------------

** Bugfix
   * LED Sequence for LiveUpdate wrong
   * First button press time at factory reset to long



Version 2.2.8 - 2020-08-07
--------------------------------------------------------------

** Bugfix
   * Device freezes, if undefined number of keypresses have been done



Version 2.2.6 - 2020-03-09
--------------------------------------------------------------

** Bugfix
   * No optical feedback on button press if there are no link partners
   * Low-Bat bit is not set in status frames and switch commands



Version 2.0.2 - 2019-11-05
--------------------------------------------------------------

** Bugfix
   * Device does not send MAC ACK if the application response comes after an application retry
   * Transmission behaviour incorrect on long keystroke
   * Error in transmission behaviour if link partner answers late

** New Feature
   * Support of HmIPW operation mode
   * Update routing support

** Improvement
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality.
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES.



--- END OF FILE ---
