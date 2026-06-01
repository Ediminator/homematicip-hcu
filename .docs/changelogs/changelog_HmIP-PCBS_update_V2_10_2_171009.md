## [HmIP-PCBS_update_V2_10_2_171009.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-PCBS_update_V2_10_2_171009.tgz)
Required CCU firmware version: &#8805; 3.47.10 / 2.47.10<br/>
<sub>sha256: eab8e2f7ec94505f60f9d84986f182cb40f49808837dfb53891b92f513df73bb</sub>

R E L E A S E   N O T E S
-------------------------


Device:		HmIP-BSM
Component:	Application of the Homematic IP switch actuator with power metering for brand switch systems, flush mount

Company:	eQ-3 Entwicklung GmbH, Maiburger Str. 36, 26789 Leer, Germany
Author:		M. Battermann


Version 1 (2 for pluggable).10.2 - 20171009
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
   * 1754501B
   * 1854630A

** Bugfix
	 
** Improvement
   
** Comments 
   * Increased version of HMOS to 1.20.4.
   
   
Version 1 (2 for pluggable).10.0 - 20171006
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
   * 1754501B
   * 1854630A

** Bugfix
	 
** Improvement
   
** Comments 
   * Created Tag 1(2 for pluggable).10.0


Version 1 (2 for pluggable).9.2 - 20171006
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
   * 1754501B
   * 1854630A

** Bugfix
   * Corrected behaviour of weekprogrammm for neagtive coordiantes.
     [HMIP_BSM-43][HMIP_FSM-14][HMIP_FSM16-10]
	 [YOU_SWA_PAI-32][YOU_SWA_POM_PAI-46]
   * Changed behaviour of init routines in powermeter- and switch-task.
     [HMIP_BSM-40]
   * [GRASS] Fixed behaviour of sending statusmessages 
     for multichannel devices. 
	 
** Improvement
   
** Comments 
   
   
Version 1 (2 for pluggable).9.1 - 20170908
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B
   * 1454104F
   * 1764508B 
   * 1754501B
   * 1854630A

** Bugfix

** Improvement
   * new parameter for suppressing messages to Access Controller
   
** Comments 
   * First release version for HmIP-PCBS2


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
   
   
Version 0.5.25 - 20160407
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed another bug with loading and accepting new parameter.

** Comments 
   * 
   
   
Version 0.5.24 - 20160407
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed a bug with eventdelay of the switch channels. 
    (wrong channel "group" was read)
   * Fixed a bug with reading out configuration parameters 
     for the switch channel(s).

** Comments 
   * 
   
   
Version 0.5.23 - 20160405
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Added forgotten initialisation of of reset pin for FSM16.

** Comments 
   * Added / Corrected Power fail detection for bistable relais.
   
   
Version 0.5.22 - 20160401
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Redesign of sending ACKs.
   * Added marker for rx options.

** Comments 
   * 
	 
	 
Version 0.5.21 - 20160331
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed a bug with keypress counter in simulated keypresses.
   * fixed problem that the internal ACK frame is send to the 
     address of the link partner, which has received while 
	 waiting for tx callback.
   * fixed problem hat the rx is not restarted while waiting 
     for tx callback
   * Fixed a bug with sequence counter handling for statusinfo.

** Comments 
   * Exchanged KEY_1 and KEY_2 to uniform channel layout of 
     HmIP priducts. 
     Now Channel 2 is the upper button but upper butten holds 
	 its old function.
   
   
Version 0.5.20 - 20160330
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed a bug with checking the sender address 
     (Mistake in version 0.5.17 checked not on receiving 
	  switch commands but in direct execution case)

** Comments 
   * 
   
   
Version 0.5.19 - 20160329
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * 

** Comments 
   * Added answering of time information frames.
	 
	 
Version 0.5.18 - 20160329
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * 

** Comments 
   * Changed behaviour of longkeypress in the internal link 
     from toggle to the same behaviour as the short one.
   
   
Version 0.5.17 - 20160324
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed handling of seq-counter of different sender.
   * Fixed executing of internal send commands.

** Comments 
   * Corrected some typos, comments and style.
   * Removed unnecessary saving of sequence counter.
   * Reverted change of powerUp-jumptarget enumeration.
   
   
Version 0.5.16 - 20160322
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed setting and sending of binary state from the real channel.
   * Fixed powerup behaviour. 
     NOTE: PowerUp action is triggert 2s after boot due 
	 to settle time of the measurement IC!
   * Fixed some typos and style.

** Comments 
   * 
   
Version 0.5.15 - 20160304
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed a bug with receiving new configuration for the
     powermeter channel.

** Comments 
   * 
   
   
Version 0.5.14 - 20160303
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed a bug with numbering of parameters for powermeter 
     channel.

** Comments 
   * 
   
   
Version 0.5.13 - 20160301
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Smaller cleanup and correction of typos.

** Comments 
   * Added channel information to the statusinfo frame.
   * Actualisations of information in the LevelInfo frame
   
   
Version 0.5.12 - 20160224
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Fixed two small logic bugs in application.c.
   * Fixed a bug with sending long keypresses.

** Comments 
   * Added support for bistable relays.
   
   
Version 0.5.11 - 20160218
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * Corrected a bug with long keypress.

** Comments 
   * Corrected number of possible partners for the powermeter channel.
   * Removed the small delay that was inserted in version 0.5.10.
	 
	 
Version 0.5.10 - 20160210
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305B
   * 1554267B

** Bugfix
   * 

** Comments 
   * Added a small delay between receiving a "force statusinfo" 
     telegramm trom testrunner and sending it because testrunner 
	 has a bug and/or is to slow to send the command and start 
	 the receive step.
   
   
Version 0.5.9 - 20160205
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * 

** Comments 
   * Added "force statusinfo" to the testmode.
   * Added saving of calibration gain values.
   
   
   
Version 0.5.8 - 20160203
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * Corrected teh handling of channel numbers with direct 
     executions.
   * Corrected some size conflicts NUMBER_OF_ACT_CHANNELS and 
     NUMBER_OF_SWITCH_CHANNELS in combination with virtual 
	 channels.
   * Fixed a bug in the order of calibration steps.

** Comments 
   * 
   
   
Version 0.5.7 - 20151218
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * 

** Comments 
   * Moved handling of Request Time Service frame from testmode 
     to application receive callback.
   * Added handling of timeinfo request frames.
   
   
Version 0.5.6 - 20151217
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * Added MAX_PARTNERS_CHANNEL_POWERMETER to the maximal 
     number of partner.
   * Fixed some minor bugs in getter functions for the 
     device flags of LIST0

** Comments 
   * Implemented requesting and receiving time information.
   * Implemented sending of own time information.
   * Implemented handling of new LIST0 parameters.
   * Implemented handling of new LIST12 parameters.
	 
	 
Version 0.5.5 - 20151210
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * 

** Comments 
   * Added files an functions for the weekprogramm 
     (first time compiling, not ready implemented).
   
   
Version 0.5.4 - 20151127
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * 

** Comments 
   * Implemented virtual Channels also to PowerUpAction.
   
   
Version 0.5.3 - 20151126
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * Corrected size of persist data in the linker options.
   * Corrected some comments.

** Comments 
   * Implemented virtual channels.
   
   
Version 0.5.2 - 20151120
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   *

** Comments 
   * Corrected handling of sequence counter.
   
   
Version 0.5.1 - 20151113
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   *

** Comments 
   * Corrected some default values for the parameter.
   
   
Version 0.5.0 - 20151111
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * 

** Comments 
   * Increased the version number due to creation of a tag.
   * Added sending of NAK_INVALID_CHANNEL.
   
   
Version 0.3.14 - 20151109
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * Fixed a small bug in the powerUp action.
   * Corrected type of second parameter ("permanent") of 
     PROFILE_timercalc-function (uint8_t -> bool_t).

** Comments 
   * Resorted the order of writing the CS5490 registers on calibration.
	 
	 
Version 0.3.13 - 20151105
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A
   * 1554267B

** Bugfix
   * Added m_useTmp to the switch module to be able to do 
     correct configuration.
   * Corrected a bug in the factory reset routines 
     regarding the key number.

** Comments 
   * Added parameter CURRENTDETECTION_BEHAVIOR.
   * Added case SERVICE_ID_FORCE_STATUSTEL in preparation 
     for the calibration by the testtool.
   * Added calibration routines.
   * Removed obsolete application_dummy files.
   * Removed some obsolete pin definitions because these 
     were unified across BSM and FSM.
   
   
Version 0.3.12 - 20151028
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added routines to save and read out the release delay time.
   
   
Version 0.3.11 - 20151028
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added routines for measuring the delay times of the relay.
   * Added routines to save and read out the operate delay time.
   
   
Version 0.3.10 - 20151023
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added testroutines for LEDs and KEYs.
	 
	 
Version 0.3.9 - 20151023
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Fixed a bug with sending error frames.
   * Removed division by two at the calculation of the switching 
     times because the worst possible switch time of the relais 
	 is longer as half a period and would cause negative switching 
	 times.

** Comments 
   * Removed unnecessary parameter for zc-delay.
   * Removed some warnings.
   * Small change with sending NACKs.
   * Added a trigger for sending an ACK after direct executon 
     frame with FRAMES_SNC_ACTION_CODE_RAMP_START was received.
   * Instead of three groups of one-dimensional arrays for power-up action 
     now one groups of two-dimensional arrays is used.
   
   
Version 0.3.8 - 20151019
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Fixed a bug in the key routines regarding inclusion 
     requests and simultan switch commands.
   * Corrected location of GDO2 (transceiver IO) 
     in the hardware config.

** Comments 
   * Added Task for internal temperatur measurement.
   * Added sending of error frames.
   * Moved or deleted some functions from application_dummy.c
   * Corrected default relay delays for better accuracy.
   * Did some code clean-up and corrections of comments.
	 
	 
Version 0.3.7 - 20151009
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Added initial configuration of the relay pin in the 
     switch module.

** Comments 
   * Added zero-crossing-switching 
     (functionality without HMOS -> directly with the emlib).
   * Changed the return values of APPLICATION_KEY_key_evaluation 
     to a bitarray to be able to handle a switch command of 
	 a not included device and sending out inclusion requests.
   
   
Version 0.3.6 - 20150930
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Small change if the reset procedure gets aborted with a 
     short keypress.

** Comments 
   * Implemented report link partner problem.
	 
	 
Version 0.3.5 - 20150929
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Switched read out of FUP and DRDY flags to be able to 
     read the frequency with faster data interval.
   * Corrected ome wrong coments.

** Comments 
   * Changed the reset procedure to fit for mains powered devices.
     -> added Error state and removed state for inital keypress.
	 
	 
Version 0.3.4 - 20150928
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added sending of StatusInfo frames after entering 
     a new profile section.
   * Now the powermeter and the switch module can cancel a 
     pending statusinfo from the other module if the own 
	 (delay) timeout is reached.
	 
	 
Version 0.3.3 - 20150924
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Added sending of a StatusInfo telegramm after inclusion.

** Comments 
   * Added sending of StatusInfo frames in the powermeter task.
   * Added sending of Powermeter-values in the statusinfo.
   * Added LevelInfo as ACK (Just a dummy, channel is still wrong).
   * Did some optimisations with sending frames in the 
     application module.
   * Commented sending of ACKs in the switch module 
     (this seems to be done in the profile module already).
   * Commented sending of StatusInfos in the switch module 
     (this seems to be done in the profile module already).
	 
	 
Version 0.3.2 - 20150915
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Changed sample number from 500 to 400.
   * Corrected the device type.

** Comments 
   * Now the value of m_pavg (the last measured power value) is 
     taken to sense the network status. This can be done because 
	 the value does not to be very accurate (average).
	 
	 
Version 0.3.1 - 20150911
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Changed the function header of SWITCH_get_state

** Comments 
   * Implemented functionality that the powermeter channel 
     simulates a keypress on button one or two to trigger the 
	 profile if someone presses another switch in the bridge 
	 network.
   * Implemented features to just switch the relay on if 
     the chennel is off and vise versa.
   * Implemented further init step of the CS5490 to change 
     the sample count (not the sample rate!).
   
   
Version 0.3.0 - 20150904
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Removed some parts to added some HmIP-FSM functionality.
	 
	 
Version 0.1.10 - 20150903
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Did some code cleanup and commentation.
   * Added powerstatus mechanism that changes DO of CS5490 
     and stores the value to a module variable.
   
   
Version 0.1.9 - 20150706
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added files for powermeter functionality.
   
	 
Version 0.1.8 - 20150702
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added delays to the tasks if they try to call the 
     parameter module and get a BUSY.
   
   
Version 0.1.7 - 20150630
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Correted some behavior with sending and receiving ACKs.
   * Corrected default behaviour of long keypress.

** Comments 
   * 
   

Version 0.1.6 - 20150626
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Simplified parameter lists.

** Comments 
   * Removed some of my own warnings.
   * Removed triggering of "NACK peer unknown" because this 
     is handled in the STACK / HMOS.
   * Further process in multi channel functionality.
   * Added functionality to send NACKs and statusinfo frames 
     with set ACK bit.
   
   
Version 0.1.5 - 20150624
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * Fixed some parameter issues.

** Comments 
   * 
   
   
Version 0.1.4 - 20150623
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Added switch module.
   * First steps of multi channel functionality added.
   
   
Version 0.1.3 - 20150618
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A
   * 1564305A

** Bugfix
   * 

** Comments 
   * Further implementing of the profile task.
   * Made some changes to the creation of the internal link.
   * Added dummy-functionality as output.
	 
	 
Version 0.1.2 - 20150617
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A

** Bugfix
   * 

** Comments 
   * Implemented creation of internal link.
   * Added profile task. (not tested yet!)
   * Added application_dummy for missiong (SWITCH-) functions 
     to make the profile task compile. 
   
   
   
Version 0.1.1 - 20150615
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A

** Bugfix
   * 

** Comments 
   * Changes in the LED callbacks due to changes in HMOS.
   * Renaming of the functions in the application key module.
   
   
Version 0.1.0 - 20150611
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A

** Bugfix
   * Corrected DEVICE_INFO_OPERATION_MODES.

** Comments 
   * Added Button-task.
   * Added creating and handling of config request frames.
   * Added creating and sending of unconditional switch command
     frames.
   * Added define for relay port / pin.


Version 0.0.1 - 20150605
--------------------------------------------------------------

** Related Hardware
   * 1424102A + 1434181A

** Bugfix
   * 

** Comments 
   * Initial commit with template as new start of the project.
	 
	 
--- END OF FILE ---



Version <Versionsnummer> - <Releasedatum im Format YYYYMMDD>
--------------------------------------------------------------

** Bugfix
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung des allgemeinen Fehlers bzw. Programmabsturzes>
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung des allgemeinen Fehlers bzw. Programmabsturzes>

** New Feature
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung der neuen Funktion>
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung der neuen Funktion>

** Modification
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung der Modifikation>
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung der Modifikation>

** Improvement
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung der Verbesserung>
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung der Verbesserung>

** Bugs
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung des offenen Fehlers>
   * <JIRA Vorgangsnummer (optional)> - <Beschreibung des offenen Fehlers>

** Related Hardware
   * <Platinennummer> - <zusätzliche Hinweise, Modifikationen usw.>

** Comments
   * <Allgemeiner Kommentar>
   * <Allgemeiner Kommentar>

