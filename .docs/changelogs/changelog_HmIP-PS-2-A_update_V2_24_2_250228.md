## [HmIP-PS-2-A_update_V2_24_2_250228.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-PS-2-A_update_V2_24_2_250228.tgz)
Required CCU firmware version: &#8805; 3.81.1<br/>
<sub>sha256: 961943d7f222ea896644b09682ef31908fa3e1b637162177bd281c28cbdbb6e9</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HMIP-PS-2-A - Homematic IP Pluggable Switch, anthracite

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany

Version 1 (2 for pluggable).24.2 - 2023-01-12
--------------------------------------------------------------
** Bugfix
   * Corrected error int the zero crossing switching module (timing is wrong if controller clock is changed)
   

Version 1 (2 for pluggable).24.0 - 2022-10-07
--------------------------------------------------------------
** New Feature
   * Support for new microcontroller type

** Modification
   * Device uses random times relay switching times if production values are damaged or are missing
   

Version 1 (2 for pluggable).22.16 - 2022-06-20/2022-07-07
--------------------------------------------------------------
** Bugfix
   * Changed emergency shutoff timeout for first threshold to 20 minutes (only HmIP-FSM16)
   * Changed overtemperature shutoff threshold temperature to 80 Â°C (only HmIP-FSM16)
   * Switch from external to internal oscillator( HmIP-PS(M)(-2)/HmIP-BSM)


Version 1 (2 for pluggable).22.14 - 2022-05-30
--------------------------------------------------------------
** Bugfix
   * Changed emergency shutoff thresholds for HmIP-PSM-2 and HmIP-PS-2


Version 1 (2 for pluggable).22.10/22.12 - 2022-04-27/2022-05-04
--------------------------------------------------------------
** Bugfix
   * Fixed error in the powermeter calibration for HmIP-BSM-I


Version 1 (2 for pluggable).22.8 - 2022-01-25
--------------------------------------------------------------
** Bugfix
   * Incorrect output switching under some unfavourable timing and profile conditions


Version 1 (2 for pluggable).22.6 - 2022-01-24
-------------------------------------------------------------- 
** Improvement
   * Improved calibration of the internal rc oscillator (HmIP-FSM/HmIP-FSM16)
   
   
Version 1 (2 for pluggable).22.4 - 2022-01-14
--------------------------------------------------------------
** Bugfix
   * Error in emergency shutoff functionality

** Modification
   * activate power failure detection for all devices with powermeter, zero crossing switching or bistable relays


Version 1 (2 for pluggable).22.2 - 2021-12-09
--------------------------------------------------------------
** Bugfix
   * add separate handling of overcurrent shutoff to ensure that output is switched off
   * fixed error in emergency shutoff handling for devices with more than one channel
   
** Modification
   * update HMOS to 1.64.0
   
   
Version 1 (2 for pluggable).22.0 - 2021-10-08
--------------------------------------------------------------
** Bugfix
   * The time information telegram does not contain a note about the sommer / winter time change.
   * Timeout for first factory reset step is too long
   * Device sends RequestConfigUpdate if received a MacAck from a LinkPartner
   
** New Feature
   * Transmitting negative power from switching measuring actuators.
   * Overcurrent detection and shutoff (HmIP-PSM-2/HmIP-PS-2)
   
     
Version 1 (2 for pluggable).20.6 - 2021-10-13
--------------------------------------------------------------
** Bugfix
   * Fixed Wrong definition of overload error flag
   * Fixed error if current is to big (e.g. 26 A -> if power is to big the power meter chip generates an power overflow, this caused a reset of power and current to 0)
   
** New Feature
   * Overcurrent detection and shutoff for switch actuators with metering (HmIP-PSM/HmIP-BSM/HmIP-FSM/HmIP-FSM16)


Version 1 (2 for pluggable).20.4 - 2021-09-16
--------------------------------------------------------------
** Bugfix
   * The daylight saving time information is now taken from time information telegram, if included.
      
** Modification
   * Device sends RequestConfigUpdate if received a MacAck from a LinkPartner


Version 1 (2 for pluggable).20.2 - 2021-08-25
--------------------------------------------------------------
** Bugfix
   * Update UART communication lib to fix a bug in power meter communication. 


Version 1 (2 for pluggable).20.0 - 2021-07-22
--------------------------------------------------------------
** Bugfix

** New Feature
   * Support of HmIP-BSM-I
   * Reset of power meter chip if the communication is broken.
   * Add parameter MOUNTING_ORIENTATION


Version 1 (2 for pluggable).18.22 - 2021-04-12
--------------------------------------------------------------
** Bugfix
   * Device responds on multicast frames without ARR bit
   * Device sends Status-Frames with Ack-Flag on SwichCommands without ARR-Flag


Version 1 (2 for pluggable).18.20 - 2021-01-15
--------------------------------------------------------------
** Bugfix
   * Fixed a bug that with not removing calibration task.
   
   
Version 1 (2 for pluggable).18.18 - 2021-01-06
--------------------------------------------------------------
** Improvement
   * Switched to usage of internal OSC with permanent calibraton 
     from the HFXO due to problems when switching non omic loads.
     
   
Version 1 (2 for pluggable).18.16 - 2020-08-03
--------------------------------------------------------------
** Bugfix
   * Added missing defines for the new statusinfo module in PS, 
     thus also in PCBS.

 
Version 1 (2 for pluggable).18.14 - 2020-07-15/2020-07-10
--------------------------------------------------------------
** Bugfix
   * Move some routines for testing the relay to ram functions. 
   * Device send status continuously and leads CCU and device running into duty cycle


Version 1 (2 for pluggable).18.12 - 2020-06-22
--------------------------------------------------------------
** Bugfix
   * After inclusion, device sends bidirectional status telegrams
     to the CCU after approx. 120s


Version 1 (2 for pluggable).18.10 - 2020-05-27
--------------------------------------------------------------
** Bugfix
   * BSM sends Statusframes with ARR every 3 minutes in case that SHC did not acknowlegeded
   * RSSI-value in AnswerFrame always 0dBm
   * BSM does not respond to a keystroke if a switching command was previously
     received on the actuator channel from an unknown link partner
     
** Modification
   * Update to HMOS 1.46.1


Version 1 (2 for pluggable).18.6 - 2020-03-09
--------------------------------------------------------------
** Bugfix
   * Device sends answers-frame on a TimeInfo from AC to "any-router"-address
   * Device sends ack frames if ARR bit is not set


Version 1 (2 for pluggable).18.4 - 2020-02-26
--------------------------------------------------------------
** Bugfix
   * Channel keys without function if external link partner could not be reached and DisableMSGToAC = true
   * Device sends status info with "Level with profile Information" instead of "Binary with profile Information"
   * Parameter DisableMSGtoAC without function if multicast address is set as system partner
   * If the button is pressed to fast after restart, the device does not switch permanently any more.	
     
     
Version 1 (2 for pluggable).18.2 - 2020-02-12
--------------------------------------------------------------
** Bugfix
   * Device running into duty cycle if CCU or HAP is not available
   * Update status info sending rules
   * Configuration is not longer shown on LED, if a key is pressed while getting config data

** New Feature
   * Using status info module
   
   
Version 1 (2 for pluggable).16.0 - 2019-11-21
--------------------------------------------------------------
** Bugfix
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES.
   * Device reboots if relay has to be switched
   * fixed bug in device behavior, if message to ac is disabled
   * fixed bug if factory reset is aborted
   * Fixed a bug in the zero crossing module due to new version of emlib

** Modification
   * Update HMOS to 1.44.2
   * Update Bootloader to 1.14 (Fixed inverted LEDs in bootloader in V1.14.2)
   * Modify emlib makro calls due to changes in updated emlib

** New Feature
   * Support of HmIP-FSI16
   * Add support for switch inputs
   * Add relay count feature


Version 1 (2 for pluggable).14.4 -2019-04-24 (Hotfix)
--------------------------------------------------------------
** Bugfix
   * PowerUpAction is executed although the parameters are not yet loaded.
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.
   * Modify event counter check to meet current specification


Version 1 (2 for pluggable).14.2 -2019-03-11
--------------------------------------------------------------
** Bugfix
   * Modify event counter check to meet current specification
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up. 
   * FSI16 switches relay to fast if mains power fails (not waiting min 200 ms) as the the ZCD detection without measuring IC produces IRQs
     only for positive half waves. Timer now has an interval of 20 ms, so the relay is switch only if 220 ms has elapsed. 


Version 1 (2 for pluggable).14.0 - 2018-12-12
--------------------------------------------------------------
** Bugfix
   * PSMR/PSM doesn't switch if the key visual is pressed directly after the boot process is finished (green led signal)
   * Corrected sending of Status-Info frames if the recipent (central or statusinfo receiver) is not available.
   * Stopped sending inclusion request on each long keypress repetition
   * Fixed another potentially deadlock.
   * Race condition may cause deadlock
   * Corrected bug with weekprogramm at the day of daylight changeover.
   * Corrected bug with creating direct execution frames in the weekprogramm.

** Improvement
   * check of keypress counter and application sequence counter updated   
   

Version 1 (2 for pluggable).12.6 - 2018-11-19 (Hotfix)
--------------------------------------------------------------
** Bugfix
   * Corrected sending of Status-Info frames if the recipent (central or statusinfo receiver) is not available.   
   * Stopped sending inclusion request on each long keypress repetition.   
   * Race condition may cause deadlock 
   * Fixed another potentially deadlock.
	 
** Improvement
   * check of keypress counter and application sequence counter updated
   
** Comments 
   * Update HMOS to 1.36.0
   
   
Version 1 (2 for pluggable).12.4 - 2018-06-28 (Hotfix)
--------------------------------------------------------------
** Bugfix
   * Corrected bug with weekprogramm at the day of daylight changeover.
   
   
Version 1 (2 for pluggable).12.2 - 2018-06-22 (Hotfix)
--------------------------------------------------------------
** Bugfix
   * Corrected bug with creating direct execution frames in the weekprogramm.
   
   
Version 1 (2 for pluggable).12.0 - 2018-06-05
--------------------------------------------------------------
** Bugfix
   * Increased HMOS version to 1.30.0 to be able to route inclusion frames (with routing actuators).
	 
** Improvement
   * Added functionality and configuration parameters to do "OFF-Actions" at powerup.

     
** Comments
   

Version 1 (2 for pluggable).10.14 - 2018-03-13
--------------------------------------------------------------
** Comments 
   * Changed default value for the long keypress from 4s to 0,4s. Necessary modifications to leave the pairing function as it is.
   
   
Version 1 (2 for pluggable).10.12 - 2018-02-26
--------------------------------------------------------------
** Bugfix
   * Added reset of measurement array after switching to prevent next measurement to be outdated. An outdated array may cause wrong switching!


Version 1 (2 for pluggable).10.10 - 2018-02-20
--------------------------------------------------------------
** Bugfix
   * Fixed wrong reset of a pending flag if disable_msg_to_ac was set.
   * Added sending of unknown RSSI value in two cases.
   * Corrected switching direction if switching with current detection is disabled.
   * Corrected timeout for sequence counter (from 10 to 2 minutes).
   
** Comments 
   * Changed default value for POWERUP_ONTIME from 0x00 to 0xFF.
   * Added new operation mode (minimum HMOS 1.24.0 necessary)
   * Changed counting of event_counter to new mechanism (boot:0; other:[1..252])
   * Changed checking of event_counter to new mechanism.
   
   
Version 1 (2 for pluggable).10.8 - 2017-12-22
--------------------------------------------------------------
** Bugfix
   * Fixed bug with fast switching
   
   
Version 1 (2 for pluggable).10.6 - 2017-11-06
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with sending statusframes with ACK and ARR bit


Version 1 (2 for pluggable).10.4 - 2017-10-20
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with sending statusframes at actuartors
     with powermeter function.
   
   
Version 1 (2 for pluggable).10.2 - 2017-10-09
--------------------------------------------------------------
** Comments 
   * Increased version of HMOS to 1.20.4.
   
   
Version 1 (2 for pluggable).10.0 - 2017-10-06
--------------------------------------------------------------
** Bugfix
   * Corrected behaviour of weekprogrammm for neagtive coordiantes.
   * Changed behaviour of init routines in powermeter- and switch-task.
   * Fixed behaviour of sending statusmessages for multichannel devices. 
   
** Improvement
   * new parameter for suppressing messages to Access Controller


Version 1 (2 for pluggable).8.12 - 2017-07-19
--------------------------------------------------------------
** Bugfix
   * Statusmessage handling corrected

** Improvement
   * Statusmessage handling optimized for multichannel devices
   * No reboot after aborded factory reset
   * new telegrams are only send if previous telegram is acked or timed out
   
** Comments 
   * First release version for HmIP-MOD-OC8
   * Use of bootloader 1.10.0

   
Version 1 (2 for pluggable).6.2 - 2017-04-27
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with not acting device if the 
     channel key was pressed at a included device.
   
   
Version 1 (2 for pluggable).6.1 - 2017-04-26
--------------------------------------------------------------
** Bugfix
   * Increased the power to trigger a simulated 
     keypress from 0.1W to 1 W.
   * Value for the new powerstatus is saved after 
     being stable for two measurements.
   * Corrected default duration of weekprogramm to 0xFF.
   * Corrected / Optimised sending of a normal ACK/NACK.

   
Version 1 (2 for pluggable).6.0 - 2017-04-25
--------------------------------------------------------------
** Bugfix
   * Increased the pulse for switching the relais
     from 30 ms to 75 ms
   * In auto inclusion mode, the triple burst listener device is not a permanent listener.
   * Fixed a bug with the sequence counter in the unicast frame 
     (for collecting ACKs) after sending multicast frames due to a long keypress.
     
** Comments 
   * Added lock feature to weekprogramm channel.
   * Added delayed weekprogram status info to status info
      receiver after change of lock channels.
   * Removed ramp time from the weekprogram.
   * Added sending of statusframes for the weekprogram.
     (After inclusion, cyclic and on request)
   * Corrected a bug with inhibit channels. 
   * Added new weekprogramm.
   
   
Version 1 (2 for pluggable).4.3 - 2017-05-27
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with not acting device if the 
     channel key was pressed at a included device.

** Comments 
   *
   
   
Version 1 (2 for pluggable).4.2 - 2017-05-26
--------------------------------------------------------------
** Bugfix
   * Increased the power to trigger a simulated 
     keypress from 0.1W to 1 W.
   * Value for the new powerstatus is saved after 
     being stable for two measurements.

** Comments 
   * 
   
   
Version 1 (2 for pluggable).4.1 - 2017-03-08
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with the sequence counter in the unicast frame 
     (for collecting ACKs) after sending multicast frames due to a long keypress.
   
   
Version 1 (2 for pluggable).4.0 - 2017-02-08
--------------------------------------------------------------
** Bugfix
   * Corrected a bug with RSSI calculation in statusInfo.
   * Fixed a bug that caused errors with one partner linked 
     to more channels.
   * Fixed a bug with sending unrequested ACKs.

** Comments 
   * Added switching the relay as EMC action.
   
   
Version 1 (2 for pluggable).2.4 - 2016-09-27
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with the simulated keypress generated from 
     the powermeter task.
   * Added IDLE state to switch task.
   * Corrected behaviour of the powerfailure function.
   * Corrected behaviour of the overhead function.
   * Suppressed sending of StatusInfoFrames if the device is 
     not included.
   * Corrected behaviour of factory reset if the keyVisual is 
     pressed during powerUp.
   
   
Version 1 (2 for pluggable).2.2 - 2016-09-01
--------------------------------------------------------------
** Bugfix
   * Included hmos 1.16.2 which fixed a bug with exlusion after inclusion


Version 1 (2 for pluggable).2.1 - 2016-08-25
--------------------------------------------------------------
** Bugfix
   * Corrected size of action type.
   * Fixed a bug that caused not spawning conditional switch 
     channel task.
   * Fixed setting of the decision value for falling direction 
     in the conditional switch channel.


Version 1 (2 for pluggable).2.0 - 2016-07-19
--------------------------------------------------------------
** Bugfix
   * StutusInfo frames from the switch module can now be send 
     with ARR-Bit. 
     StatusInfo frames from the powermeter are still 
     unidirectional all the time.
   * Fixed bug that first reset step is ready before 
     the timeout of 4 seconds occur.
   * Suppress boot blinking if reset is in progress.
   * Fixed a bug with index of parameter arrays if the key 
     visual is used as channel key.
   * Conditional switch channel gets now removed in idle state.
   * Fixed a bug in evaluation of long keypresses 
     for the pairing mode.
   * Fixed a bug with setting parameters for the 
     input channel.
   * Added routines for HmIP-PS.
   * Reduced number of partners for HmIP-PSx to 20. 
     With this all switch actuators act the same.
   * Corrected a bug with the switching direction.
   * Corrected calculation of energycount.
   * Fixed a bug with ACKs to config update request frames.
   
** Comments 
   * Removed sending of config update requests on buttonpress 
     of the keyvisual for all permanent powered actuators.
   * Set the default values for event delay of output1, 
     meter and conditional channel from 1 to 3 seconds.
   * Powermeter arrays for averaging now always get resetted 
     if SWITCH_set_level_real() is called.
   * Set default value for the longpress time in the 
     HmIP-PSx devices to 4s.
   * Added conditional switch channel.
   *  Added pairing functionality.
   *  Added routing functionality.
   * Some optimisations on startup.
   *  Added parameter LED_DISABLE in list1 of the 
     real channel.
   *  Added default link between key visual and 
     the switch channel.
   *  Added routines to do visialisation of the 
     channel state with the key visual.
   *  Corrected factory reset gesture 
     (only valid at power up).
   *  Added key routines for switching with the key visual.




