## [hm_tc_it_wm_w_eu_update_V1_4_002_171018.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/hm_tc_it_wm_w_eu_update_V1_4_002_171018.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.9.0<br/>
<sub>sha256: 387c669fa61db800b63aa7ad7d26ba78d1f77a89c1550e0be36696ce0463fd26</sub>

Achtung! Bitte verwenden Sie die Firmware-Datei nur in Verbindung mit dem Firmware Update Tool ab Version 1.1 sowie der CCU2 ab Version 2.9.0.

Die aktuellste Version des Firmware Update Tools finden Sie im Downloadbereich der Website www.eQ-3.de.

Version 1.4.002 - 17/02/13
--------------------------------------------------------------
** Bug
  * Jira HMTCIT-29 -> Improvement of radio communication: After the incoming Data "FRAME_CONTROL_MODE", 
					  "FRAME_LIMITED_SWITCHING" and "FRAME_UNLIMITED_SWITCHING" the Device change for 5 s from WOR to RX-Mode.

					  
Version 1.4.001 - 16/10/11
--------------------------------------------------------------
** Bug
  * Jira HMTCIT-25 -> After several changes of the temperature offset, no incorrect actual temperature is shown in the LCD.
  

Version 1.4.000 - 16/09/20
--------------------------------------------------------------
** Modification / Improvement
  * After the incoming Data "CCU-Command" and "Configuration" the Device change for 5 s from WOR to RX-Mode.
  

Version 1.3.002 - 15/08/27
--------------------------------------------------------------
** Bug
  * Fixed incorrect display at mode-lock.

  
Version 1.3.001 - 15/05/06
--------------------------------------------------------------
** Bug
  * Bugfix at direkt pairing. Sometimes the parameter configuration after pairing goes wrong.
** Change Request
  * The conditional data message for the two-point-regulation is send now cyclical.
  * If the button lock is active, the behaves of the lock symbol is simular to the HM-CC-RT-DN.

  
Version 1.2.001 - 14/10/20
--------------------------------------------------------------
** Bug
  * Modification the radio data interpretation function, if check for CONFIG_SERIALNUMBER it is also necessary to 
    check the frame typ for FRAME_CONFIGURATION.
  * Modification the direct link button-switch profile. 


Version 1.1.000 - 14/04/24
--------------------------------------------------------------

** Bug
  * Change in config_rt(...,...), parameter configuration is start at parameterposition 20.
    The weekly program transfer to the partner was incorrect if the first timestep > 21:15 o'clock
  * If party-mode bring into action, always the long status-message is send out instead of the 
    short status-message. The party-temperature is add as last byte at the long status-message.
** Change Request
  * Make direct pairing with HM-ES-PM-Sw1-Pl (Actor-Switch) possible.
  

Version 1.0.007 - 13/11/26
--------------------------------------------------------------

** Bug
  * If boost is activ, actual temp. and humidity are not show to display.
