## [HmIP-MIOB_update_V2_2_0_231109.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-MIOB_update_V2_2_0_231109.tgz)
Required CCU firmware version: &#8805; 3.65.3<br/>
<sub>sha256: e6694249088cb94c3e041b72569117b5ce78b4f87b53e0ee1f673304e9c1dc12</sub>

C H A N G E L O G
-----------------

Version 2.2.000 - 2023-11-09
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * Channel 11 does not pay attention to the event counter
   * For heat demand control on the VirtB channels, a level command should also be taken into account in addition to a conditional switch command.
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   
Version 2.0.010 - 2022-05-23
--------------------------------------------------------------

** Bugfix
   * Status info cannot request from virtuel channels
   * No CSC Frame to linkpartner from ch 9/10 at changeover input
   * Sorting of status info container wrong

Version 2.0.008 - 2022-05-10
--------------------------------------------------------------

** Bugfix
   * Direct Execution Command to FAL is not assembled correctly when inputs are configured as "Normally Open".

Version 2.0.006 - 2022-04-27
--------------------------------------------------------------

** Bugfix
   * Due to the default settings of the link parameters, a conditional switch command is not handled according to specification
   
Version 2.0.004 - 2022-03-31
--------------------------------------------------------------

** Bugfix
   * Weekprogram-Status(-with Ack) is not triggered in case of Mode-Change
   * MIOB "Normally Closed"-Input: Cooling is not activated

Version 2.0.000 - 2022-02-07
--------------------------------------------------------------

** Bugfix
   * Direct link CO input to FALx deactivates internal channel A
   * MIOB sends many status messages during inclusion process
   * If the switch-on and switch-off times in the Easy Profile are set to "Not active" at the same time, the device hangs up.
   * Rocker switch no longer responds after frequent operation
   * CCU2 MIOB LED confirms red if internal button has been linked to more than 2 other actuators
   * MIOB fails sporadically and can only be operated again after the 230 volt supply has been interrupted

** New Feature
   * Use of the HmIP-MIOB in connection with the HmIP-BWTH wall thermostat

** Improvement
   * The time information telegram does not contain a note about the sommer / winter time change.
   * If possible, send multicasts only to PARTNER_ALL_WIRED_DEVICES instead of to PARTNER_ALL_DEVICES.
   * Improve switch command functionality by new implementation of local loopback, adding command cancelation and using node sending functionality

Version 1.8.004 - 2019-01-29
--------------------------------------------------------------

** Bugfix
	* Level Command at analog output fixed
	* Behaviour of event counter fixed

** Improvement
	* Split up event counter for digital input channels in case of conditional switch command
   
** Modification
	* Change to Version 1.8.004.

Version 1.8.002 - 2019-01-24
--------------------------------------------------------------

** Bugfix
	* Long keypress behaviour at digital input channels corrected (last long keypress is sent with arr)
	* Fixed wrong behaviour of application sequence counter	

** Improvement
	* Sending of config request frames in case of no linkpartner at digital input channels
	
** Modification
	* Change to Version 1.8.002.

Version 1.8.000 - 2018-12-19
--------------------------------------------------------------

** Bugfix
	* Weekprogram under certain circumstances does switch all actuator channels if switched all at the same time 

** Improvement
	* Weekprogram implemented
	* Pairing with FALMOT
	* All PowerUp parameters, that are listed in list 3 of the device, must be supported.
	* Disable MSG to AC parameter implemented
	* Application Sequence Counter handling adapted
	* Configuration parameter for pushbutton channel (long presstime, double presstime, repeated long press timeout) added
   
** Modification
	* Change to Version 1.8.000.

Version 1.6.004 - 2017-11-23
--------------------------------------------------------------

** Improvement
	* MIOB behaviour in case of system restart improved. Now sends DEC-Logic to FAL in any case.
   
** Modification
	* Change to Version 1.6.004.

	
Version 1.6.002 - 2017-02-09
--------------------------------------------------------------

** Bugfix
	* In case of multiple FAL, linked to different acutator channels of the MIOB, in some configurations not all FALs got DEC Logic command (eg. for changeover).
   
** Modification
	* Change to Version 1.6.002.

	
Version 1.6.001 - 2017-02-08
--------------------------------------------------------------

** Bugfix
	* Fixed Issue: Direct execution command was sent to FAL on wrong Channel. If no Link between Out0 and FAL created, no DEC was sent from MIOB 
   
** Modification
	* Change to Version 1.6.001.

	
Version 1.6.000 - 2017-01-30
--------------------------------------------------------------

** Bugfix
	* Error in heat demand function (VIRT B-Channels of both actuators) fixed. 
   
** Modification
	* Change to Version 1.6.000.

	
Version 1.4.000 - 2016-09-20
--------------------------------------------------------------

** Bugfix
	* Issue with global pump protection function (in conjunction with the FAL) fixed.
   
** Modification
	* Change to Version 1.4.000.

Version 1.2.000 - 2016-09-08
--------------------------------------------------------------

** Bugfix

	* Fixed issue with powerup ontime and powerup ondelay at actuator channels.
	* Fixed issue with event delaytime and event randomtime for statusinfo 
	  transmission in case of statuschange at actuator channels.
	* Fixed issue with log keypress timer at application startup.
   
** Modification
	* Change to Version 1.2.000.

	
Version 1.0.012 - 2016-08-25
--------------------------------------------------------------

** Bugfix

	* Bugfix at internal link between input and output channels (CO-Pilot).
   
** Modification
	* Change to Version 1.0.012.

	
Version 1.0.011 - 2016-07-28
--------------------------------------------------------------

** Bugfix
	* Double ack at csc and usc fixed.
	* Application sequence counter error fixed.
   
** Modification
	* Change to Version 1.0.011.
	* Changed Lib to 1.16.1

	
Version 1.0.010 - 2016-07-28
--------------------------------------------------------------

** Bugfix
	* Bug with DEC of second relay output fixed
   
** Modification
	* Change to Version 1.0.010.
	* Unconditional switch command added for switching actuator channels
	

Version 1.0.009 - 2016-07-27
--------------------------------------------------------------

** Bugfix

	* Application ACK is now sent in case of set ARR Bit.  
	* Logic Combination fixed.
	* Powerupactions fixed.
	* Edit Parameterlist fixed.
   
** Modification
	* Change to Version 1.0.009.
	* Send Statusinfo subsequent to levelcommand or dec with level on channel for analog output.
	* Statusinfo is only sent in case of "significant" changes.
	

Version 1.0.008 - 2016-06-21
--------------------------------------------------------------

** Modification
	* Change to Version 1.0.008.
	* Minor changes in pairing routines.
	* Device Functions IDs adapted.

Version 1.0.007 - 2016-06-15
--------------------------------------------------------------

** Bugfix
	* Bugfix in SNC Command
   
** Modification
	* Change to Version 1.0.007.
	* Internal Links implemented (eg. Link between C/O input and CO-Pilot Output).
	* Tactile Switch functionality implemented for digital Inputs (sends 
	  Unconditional Switch Command with short (<400 ms) or long (>400 ms every 250 ms) keypress).
	* Statusinfo implemented.

Version 1.0.006 - 2016-06-01
--------------------------------------------------------------

** Bugfix
	* Bugfix in pairing routines. 
   
** Modification
	* Change to Version 1.0.006.
	* Heatdemand relay functions on Virt B channels implemented.
	* DEC send to FAL if FAL reset has been detected (sequence counter = 0x01).

Version 1.0.005 - earlier - 2016-05-23
--------------------------------------------------------------

** Bugfix
	* Bugfix in pairing routines.

--- END OF FILE ---