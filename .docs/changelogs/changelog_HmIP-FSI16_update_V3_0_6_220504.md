## [HmIP-FSI16_update_V3_0_6_220504.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-FSI16_update_V3_0_6_220504.tgz)
Required CCU firmware version: &#8805; 3.61.7 / 2.61.7<br/>
<sub>sha256: 44439929da91841bf7b0e166974476eec659852c774912d84ddca9edfe25b229</sub>

C H A N G E L O G
-----------------

Version 3.0.6 - 2022-05-04
--------------------------------------------------------------
** New Feature
   * Add pairing to HmIP-FSI16
   
** Modification
   * Changed to new firmware platform


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


Version 1 (2 for pluggable).18.22 - 2021-04-12
--------------------------------------------------------------
** Bugfix
   * Device responds on multicast frames without ARR bit
   * Device sends Status-Frames with Ack-Flag on SwichCommands without ARR-Flag


--- END OF FILE ---