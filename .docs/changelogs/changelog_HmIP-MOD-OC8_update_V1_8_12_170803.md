## [HmIP-MOD-OC8_update_V1_8_12_170803.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-MOD-OC8_update_V1_8_12_170803.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.29.18<br/>
<sub>sha256: 5fbc686ba4b72c8cfdb69f94d2a0c4fab812f2f076470f52b6c587a4b622c76c</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version
of the CCUx!

Device: HmIP-MOD-OC8 - Homematic IP Module Board Open Collector - 8 channels

Company: eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1 (2 for pluggable).8.12 - 20170719
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
   * 1754501B

** Bugfix
   * Statusmessage handling corrected

** Improvement
   * Statusmessage handling optimized for multichannel devices
   * No reboot after aborded factory reset
   * new telegrams are only send if previous telegram is acked or timed out
   
** Comments 
   * First release version for HmIP-MOD-OC8
   * Use of bootloader 1.10.0
   
   
Version 1 (2 for pluggable).7.6 - 20170530
--------------------------------------------------------------
 
** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
 
** Bugfix
   * [HMIP_PCBS_BAT-14] ARR timeout is not observed 
      with the Info and TimeInformation frames
   * [HMIP_PCBS_BAT-15] LowBat Bit is not set in the status Info
      
** Improvement
   * [HMIP_PCBS_BAT-16] DataType Operating Voltage send with StatusInfo
   
** Comments 
   * 
    
    
Version 1 (2 for pluggable).7.5 - 20170519
--------------------------------------------------------------
 
** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
 
** Bugfix
   * [HMIP_PCBS_BAT-12] The device reacts with the same 
     event counter for an unconditional switch command.
   * [HMIP_PCBS_BAT-13] Device is permanently awake.
   
** Comments 
   * 

   
Version 1 (2 for pluggable).7.4 - 20170427
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix
   * [HMIP_BSM-33] Fixed a bug with not acting device if the 
     channel key was pressed at a included device.

** Comments 
   *
   
   
Version 1 (2 for pluggable).7.3 - 20170426
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix
   * [HOTFIX] Increased the power to trigger a simulated 
     keypress from 0.1W to 1 W. [HMIP_BSM-32]
   * [HOTFIX] Value for the new powerstatus is saved after 
     being stable for two measurements. [HMIP_BSM-32]
   * Corrected default duration of weekprogramm to 0xFF.
   * Corrected / Optimised sending of a normal ACK/NACK. [CHANGEMANAGEMENT-25]

** Comments 
   *
   
   
Version 1 (2 for pluggable).7.2 - 20170425
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix

** Comments 
   * Removed ramp time from the weekprogram.
   * Added sending of statusframes for the weekprogram.
     (After inclusion, cyclic and on request)
   * Corrected a bug with inhibit channels. [CHANGEMANAGEMENT-51]
	  
	  
Version 1 (2 for pluggable).7.1 - 20170413
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix

** Comments 
   * Added lock feature to weekprogramm channel.
   * Added delayed weekprogram status info to status info
      receiver after change of lock channels.
   
   
Version 1 (2 for pluggable).7.0 - 20170405
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix
   * Increased the pulse for switching the relais 
     from 30 ms to 75 ms.

** Comments 
   * Increased version due to creation of a tag.


Version 1 (2 for pluggable).5.9 - 20170405
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix
   * 

** Comments 
   * Added new weekprogramm.
   
   
Version 1 (2 for pluggable).5.8 - 20170328
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix
   * In auto inclusion mode, the triple burst listener device is not a permanent listener.

** Comments 
   * 
   
   
Version 1 (2 for pluggable).5.7 - 20170308
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 

** Bugfix
   * Fixed a bug with the sequence counter in the unicast frame 
     (for collecting ACKs) after sending multicast frames due 
	 to a long keypress.

** Comments 
   * 
   
   
Version 1 (2 for pluggable).5.0 - 20161209
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B

** Bugfix
   * 

** Comments 
   * Increased version number due to creation of a tag.
   
   
Version 1 (2 for pluggable).3.8 - 20161128
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * [GRASS] Corrected a bug with RSSI calculation in statusInfo.

** Comments 
   * 
   
   
Version 1 (2 for pluggable).3.7 - 20161114
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * [GRASS] Fixed a bug that caused errors with one partner linked 
     to more channels.

** Comments 
   * 
   
   
Version 1 (2 for pluggable).3.6 - 20161104
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Fixed a bug with sending unrequested ACKs.

** Comments 
   * 
   
   
Version 1 (2 for pluggable).3.5 - 20161021
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * Added switching the relay as EMC action.
   
   
Version 1 (2 for pluggable).3.4 - 20160926
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Fixed a bug with the simulated keypress generated from 
     the powermeter task.

** Comments 
   *


Version 1 (2 for pluggable).3.3 - 20160913
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Added IDLE state to switch task.
   * Corrected behaviour of the powerfailure function.
   * Corrected behaviour of the overhead function.
   * Suppressed sending of StatusInfoFrames if the device is 
     not included.
   * Corrected behaviour of factory reset if the keyVisual is 
     pressed during powerUp.

** Comments 
   *
   
   
Version 1 (2 for pluggable).3.2 - 20160901
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Included hmos 1.16.2 which fixed a bug with exlusion after inclusion

** Comments 
   *
   

Version 1 (2 for pluggable).3.1 - 20160721
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Corrected size of action type.
   * Fixed a bug that caused not spawning conditional switch 
     channel task.
   * Fixed setting of the decision value for falling direction 
     in the conditional switch channel.

** Comments 
   *
   
   
Version 1 (2 for pluggable).3.0 - 20160719
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * Increased version number due to creation of a tag.
   
   
Version 1 (2 for pluggable).1.17 - 20160718
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * StutusInfo frames from the switch module can now be send 
     with ARR-Bit. 
     StatusInfo frames from the powermeter are still 
     unidirectional all the time.

** Comments 
   * 
	 
	 
Version 1 (2 for pluggable).1.16 - 20160714
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * Removed sending of config update requests on buttonpress 
     of the keyvisual for all permanent powered actuators.
   
   
Version 1 (2 for pluggable).1.15 - 20160708
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * [HmIP-PSM]Fixed bug that first reset step is ready before 
     the timeout of 4 seconds occur.
   * Suppress boot blinking if reset is in progress.
   * Fixed a bug with index of parameter arrays if the key 
     visual is used as channel key. 

** Comments 
   * 
	 
	 
Version 1 (2 for pluggable).1.14 - 20160704
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Conditional switch channel gets now removed in idle state.

** Comments 
   * Set the default values for event delay of output1, 
     meter and conditional channel from 1 to 3 seconds.
   * Powermeter arrays for averaging now always get resetted 
     if SWITCH_set_level_real() is called.
	 
	 
Version 1 (2 for pluggable).1.13 - 20160616
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * [HmIP-PSM]Fixed a bug in evaluation of long keypresses 
     for the pairing mode.
   * [HmIP-PSM] Fixed a bug with setting parameters for the 
     input channel.

** Comments 
   * [HmIP-PSM] Set default value for the longpress time in the 
     HmIP-PSx devices to 4s.
   
   
Version 1 (2 for pluggable).1.12 - 20160613
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Corrected some typos.

** Comments 
   * Added conditional switch channel.
	 
	 
Version 1 (2 for pluggable).1.11 - 20160531
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Reset ACCEPT_ANY_DEVICE to 0.

** Comments 
   * [HmIP-PSM] Major version increased to 2.
     Minor and Path number will run parallel for all devices.
	 
	 
Version 1.1.10 - 20160518
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * [HmIP-PS] Added routines for HmIP-PS.
   * Renamed CS5490_zc.c /.h to zerocrossing_interrupt.c / .h 
     to be more general.
   * Smaller changes to the DUMMY_SGTIN.
   * Reduced number of partners for HmIP-PSx to 20. 
     With this all switch actuators act the same.
	 
	 
Version 1.1.9 - 20160512
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * [HmIP-FSM16] Corrected a bug with the switching direction.

** Comments 
   * Added visualisation of the channelstate with the key 
     visual (Including the parameter) to all actuators. 
   
   
Version 1.1.8 - 20160510
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * [HmIP-PSM] Added pairing functionality.
   
   
Version 1.1.7 - 20160509
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * [HmIP-PSM] Added routing functionality.
   
   
Version 1.1.6 - 20160509
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * Some style changes.
   * Corrected calculation of energycount.

** Comments 
   * Some optimisations on startup.
	 
	 
Version 1.1.5 - 20160503
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * Corrected some comments and function headers.
   * Corrected parameter for energy threshold. It was one byte 
     but has to be two byte.
   * [HmIP-PSM] Added parameter LED_DISABLE in list1 of the 
     real channel.
	 
	 
Version 1.1.4 - 20160502
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * [HmIP-PSM] Added default link between key visual and 
     the switch channel.
   * [HmIP-PSM] Added routines to do visialisation of the 
     channel state with the key visual.
   * [HmIP-PSM] Corrected factory reset gesture 
     (only valid at power up).
   
   
Version 1.1.3 - 20160428
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F

** Bugfix
   * 

** Comments 
   * [HmIP-PSM] Added key routines for switching with the key visual.
   
   
Version 1.1.2 - 20160426
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed to which multicast addresses the device listens.

** Comments 
   * Startet porting code to the PSM hardware.
   
   
Version 1.1.1 - 20160425
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed a bug with ACKs to config update request frames.

** Comments 
   *
   
   
Version 1.1.0 - 20160413
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * 

** Comments 
   * Increased version number due to creation of a tag.
   
   

--- END OF FILE ---
