## [HM-ES-PMSw1-Pl-DN-R2_update_V2_6_0000_150812.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/HM-ES-PMSw1-Pl-DN-R2_update_V2_6_0000_150812.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.9.0<br/>
<sub>sha256: 9f64e38d0d674c9aca53f79055ad721f20695aaff7e131dbb76d11967c24ed07</sub>

C H A N G E L O G
-----------------

Version 2.6 - 20150812
----------------------
** Bugfix
   * timeouts during aes-keychange fixed


Version 2.5 - 20150217
--------------------------------------------------------------
** Bugfix
   * before jump to bootloader, IRQs are disabled
   * problem with simulated telegrams fixed
   * toggle to counter was not correct
   * counter of internal buttonpress fixed
   * decode of transmitted time at conditional switch command fixed
   * ontime-mode minimum fixed

** Improvement
   * blinking enhanced to new definitions
   * ZC detection support
   * long buttonpress of device-button not only for config
   * power-up-action available
   * support for new devices
   * status messages with rising random interval 
   
   
Version 1.6 - 20140417
--------------------------------------------------------------
** Bugfix
   * fix delay for statusinfo when random time is set to zero

** Improvement
   * measured power sometimes not zero when relais is turned off


Version 1.5 - 20140204
--------------------------------------------------------------
** Modification
   * modification of TRX settings


Version 1.4 - 20131218
--------------------------------------------------------------
** Bugfix
   * energy counter goes wrong when power is above 300 W
   * device can be operated with its button, when device is locked by CCU