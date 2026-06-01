## [HmIP-HAP2_1_0_44_250924.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-HAP2_1_0_44_250924.tgz)
Required CCU firmware version: &#8805; 3.83.6<br/>
<sub>sha256: b467854fc56cbd114c3badf8ee0168684deaea64ca43ac1e016c5b3e6ba68120</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-HAP - Access Point 2

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.0.44 - 2025-09-24
--------------------------------------------------------------

** Bugfix
   * Background OTAU stops in a deadlock after it was paused



Version 1.0.42 - 2025-09-11
--------------------------------------------------------------

** Bugfix
   * Support new server certificate



Version 1.0.40 - 2025-08-12
--------------------------------------------------------------

** Bugfix
   * Other access point as next hop in rm response
   * Wrong data in route request for a special address.
   * Close connection with websocket connection delay always 14s
   * Timeout for device routes learnd over backbone

** New Feature
   * Add another root CA from Amazon.



Version 1.0.38 - 2025-08-04
--------------------------------------------------------------

** Bugfix
   * GatewayToken set with netfinder not readable at configuration
   * Time interval for the lookup request is not increased
   * Send priority
   * Answer at rm request without data
   * Device op mode in rm response is not updated
   * Not reachable device is not set to distance 7
   * Distance at answer for RM request wrong
   * Missing data in ICMP destiantion unreachable 

** New Feature
   * Add multicast to MAC Filter



Version 1.0.36 - 2025-07-11
--------------------------------------------------------------

** Bugfix
   * The HAP2 sends ICMP destination unreachable with the wrong IP source address.
   * The HAP2 does not send its cyclic status info frames.
   * First signal of the boot sequence is not visible 



Version 1.0.34 - 2025-07-10
--------------------------------------------------------------

** Bugfix
   * The access point determines routes from radio frames that are not directly addressed to it.
   * HAP2 blinkt nach Neustart der HCU
   * Keine Verbindung zu den GerÃ¤ten, wenn HAP2 die Verbindung Ã¼bernimmt
   * Wrong entry in Routing Table
   * HAP2 bursted Tripple Burst EmpfÃ¤nger nicht an
   * No answer for frame from sim device send to crrfd



Version 1.0.32 - 2025-07-07
--------------------------------------------------------------

** Bugfix
   * Heating Controller Mode Frames to Multicast are not filtered.Â 
   * The AccessPoint does not respond to the cloud address if it is not directly connected.



Version 1.0.30 - 2025-07-03
--------------------------------------------------------------

** Bugfix
   * All routes learned over backbone send in rm response
   * Age counter not reset after icmp neighbor advertisement
   * No answer to Status Request frames
   * RSSI with 0x80 for rf device entry
   * Network table entry with distance 0



Version 1.0.28 - 2025-06-20
--------------------------------------------------------------

** New Feature
   * FirstRelease



--- END OF FILE ---

