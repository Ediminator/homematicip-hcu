## [HM-LC-Bl1PBU-FM_update_V2_11_1_161212.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/HM-LC-Bl1PBU-FM_update_V2_11_1_161212.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.11.0<br/>
<sub>sha256: f5e2bfa47a5348026d3a73aee9c55e09e2a48b45bbed44fa11afe97a1a1dc8c4</sub>

Achtung! Bitte verwenden Sie die Firmware-Datei nur in Verbindung mit dem Firmware Update Tool ab Version 1.1 sowie der CCU2 ab Version 2.11.0.
Die aktuellste Version des Firmware Update Tools finden Sie im Downloadbereich der Website www.eQ-3.de.

Please note: Only use the firmware file in connection with the Firmware Update Tool from version 1.1 as well as version 2.11.0 or higher of the CCU2.
You will find the latest version of the Firmware Update Tool in the download area of the website www.eQ-3.de.


In Verbindung mit der CCU2 wird das Gerät automatisch in den Updatemodus versetzt. 
Für ein Firmware-Update mit dem Firmware Update Tool, gehen Sie wie folgt vor:
1. Netzspannung des Gerätes ausschalten / vom Gerät trennen (Ggfs. Sicherheitshinweise der Installation beachten!),
2. den Aus/runter-Taster (UP-Markenschalter) bzw. den Bedientaster von Kanal 1 (sonstige Aktoren) drücken und festhalten,
3. bei immer noch gedrückt gehaltener Taste den Aktor wieder mit Netzspannung versorgen.
4. Sobald die LED schnell blinkt, kann die Taste losgelassen werden. Das Update wird jetzt durchgeführt.


Version 2.11.1 - 20161209
--------------------------------------------------------------
** Improvement
	 * Optimization of internal EEPROM handling

	 
Version 2.10.0 - 20160810
--------------------------------------------------------------
** Modification
   * Support for HM-LC-JaPBU-FM
	 
** Improvement
	 * Increased accuracy of internal level at blind actuators
	 

Version 2.9.0 - 20160111
--------------------------------------------------------------
** Modification
   * Support for HM-LC-Sw2PBU-FM


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