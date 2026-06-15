## [HM-LC-Sw1PBU-FM_update_V2_8_2_150713.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/HM-LC-Sw1PBU-FM_update_V2_8_2_150713.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.11.0<br/>
<sub>sha256: f03e9a54bea00cb0dbfea5953e1a645b95b89bd3e96d86de32dba31e3ede3f0e</sub>

Achtung! Bitte verwenden Sie die Firmware-Datei nur in Verbindung mit der aktuellsten CCU2/3 Version.

Version 2.8.2 - 20150713
--------------------------------------------------------------
** Bugfix
   * Simulation of internal buttons fixed


Version 2.7.1 - 20150427
--------------------------------------------------------------
** Improvement
   * ZC-Switching on HM-LC-Sw1-DR
   
   
Version 2.6.3 - 20150202
--------------------------------------------------------------
** Bugfix
   * timing for repeated transmissions fixed

** Improvement
   * detection of buttonpress improved on flush-mount-devices


Version 2.6.1 - 20141210
--------------------------------------------------------------
** New Feature
   * support for TRX1-TIF


Version 2.5.1 - 20140321
--------------------------------------------------------------
** Bugfix
   * info telegram random timer value fixed

** Improvement
   * only linkable to one central unit


Version 2.4.4 - 20140206
--------------------------------------------------------------
** Bugfix
   * with aes active, no links for channel 2 and 4 could be created   

** New Feature
   * powerup-action for switches
   * long press of internal buttons usable after configurable timeout

** Improvement
   * behaviour of internal buttons made equally for several different devices
   * blink code for errors simplified


Version 2.3.2 - 20131204
--------------------------------------------------------------
** Bugfix
   * Reset can be entered from teach-in-mode  
   * info telegram delay was initialised with wrong values
   * config problems with aes active
      
	  
Version 2.2.4 - 20130417
--------------------------------------------------------------
** Bugfix
   * configuration handling problems removed
   * special value for info telegramm inactive changed (from 0xff to 0)
   * telegram counter problems while configuration  

** New Feature
   * local reset disable
   * info telegrams with random und offset

** Improvement
   * medium busy check for info telegrams


Version 2.1.3 - 20120315
--------------------------------------------------------------
** Bugfix
   * telegram counter at info telegrams to CCU was wrong
   * up/down link profile for internal button not correct