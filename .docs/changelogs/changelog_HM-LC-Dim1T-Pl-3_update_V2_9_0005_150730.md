## [HM-LC-Dim1T-Pl-3_update_V2_9_0005_150730.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/HM-LC-Dim1T-Pl-3_update_V2_9_0005_150730.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.13.0<br/>
<sub>sha256: 6436c613b09b60a650e0e3772adb14871f58a82d374504d60c8da672d1e3b082</sub>

Um den Aktor in den Update-Mode zu versetzen, ist wie folgt vorzugehen:
1. Netzspannung ausschalten / vom Gerät trennen (Ggfs. Sicherheitshinweise der Installation beachten!),
2. den Aus/runter-Taster (UP-Markenschalter) bzw. den Bedientaster von Kanal 1 (sonstige Aktoren) drücken und festhalten,
3. bei immer noch gedrückt gehaltener Taste den Aktor wieder mit Netzspannung versorgen.
4. Sobald die LED schnell blinkt, kann die Taste losgelassen werden. Das Update wird jetzt durchgeführt.

Version 2.9.5 - 20150729
--------------------------------------------------------------
** Bugfix
   * simulation of internal buttons fixed
** Modification
   * add support for HM-LC-Dim1T-FM-LF
   

Version 2.8.3 - 20140508
--------------------------------------------------------------
** Bugfix
   * statusinfo random value = 0 was not proper
   * ACK for ramp-stop was always on CH1
** Modification
   * patable moved to fixed flash adress
   
   
Version 2.7.1 - 20140210
--------------------------------------------------------------
** Bugfix
   * LEVEL_REAL in ACK telegrams of devices with virtual channels was wrong
** Improvement
   * increased immunity of load error detection of leading edge dimmers


Version 2.6.1 - 20131204
--------------------------------------------------------------
** Bugfix
   * reset at devices with separate config button was reachable by 1x short + 1x long buttonpress
   * configuration process interrupted when AES was active
      
   
Version 2.5.5 - 20131126
--------------------------------------------------------------
** Bugfix
   * error in load appear behaviour at HM-LC-Dim1L-Pl-3
   * config start telegram was accepted from foreign CCUs
   * LED signal for usererr modified to 2s
   * LED signal for device defect modified
** New Feature
   * AES support
   * local reset disable added
   

Version 2.4.0 - 20130712
--------------------------------------------------------------
** Modification
   * 50Hz tolerance increased


Version 2.3.2 - 20130417
--------------------------------------------------------------
** Bugfix
   * teach-in corrupted when partner sends 2x 0xff as additional info
   * special value for statusinfo inactive modified (from 0xff to 0)
   * parameter list 3 info telegram had wrong index at ELSE_ACTION parameters


Version 2.2.0 - 20120315
--------------------------------------------------------------
** New Feature
   * bootloader can be accessed by rf telegram
   

Version 2.1.0 - 20120113
--------------------------------------------------------------
** Bugfix
   * reduced flicker on dirty mains
** Modification
   * new LED signals
   * powerup action modified
   * internal buttons and links per default visible
** Improvement
   * softdim at manuel dimming instead of visible steps
   * statusinfo timer with new calculation method 