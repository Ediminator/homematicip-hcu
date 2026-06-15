## [HmIPW-DRAP_3_0_20_231208.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-DRAP_3_0_20_231208.tgz)
Required CCU firmware version: &#8805; 3.73.9<br/>
<sub>sha256: fb866367a12cc1bc54484425e7b373e538c410b46a10da6d89b5f99d0abbee2f</sub>

C H A N G E L O G
-----------------

Version 3.0.20 - 2023-12-08
--------------------------------------------------------------

** Bugfix
   * Bus power somtimes switch off at update



Version 3.0.18 - 2023-09-29
--------------------------------------------------------------

** Bugfix
   * LEDs flash blue and after some time the communication to the cloud is disrupted.
   * The bus supply voltage is switched on and off several times during booting. 



Version 3.0.16 - 2023-06-14
--------------------------------------------------------------

** Bugfix
   * Multicast routing problems
   * LED sequence wrong after get data from lookup server



Version 3.0.12 - 2023-05-31
--------------------------------------------------------------

** Bugfix
   * Problems at Update



Version 3.0.10 - 2023-04-21
--------------------------------------------------------------

** Bugfix
   * After reboot (power) sometimes both APs connected to cloud
   * No lookup request after get a crrfd url that is too long
   * Time at close connection with 0xffff wrong



Version 3.0.4 - 2023-03-22
--------------------------------------------------------------

** Bugfix
   * Encrypted frames not send to cloud
   * The coprocessor crashes if a load is connected to the bus during operation.
   * Backbone frames payload length wrong

** New Feature
   * Use return code when closing the WebSocket to the AP for indication if the route is still valid.

** Improvement
   * send destination unreach with LHL = 7-x



Version 2.4.28 - 2022-09-16
--------------------------------------------------------------

** Bugfix
   * Replies to frames from the server are lost. 
   * The access point sends frames to the server that are too long. 

** Improvement
   * Set different timeouts for backbone Routers and backbone devices 



Version 2.4.22 - 2022-05-09
--------------------------------------------------------------

** Bugfix
   * BUS is not switched on after Power UP



Version 2.4.20 - 2022-04-07
--------------------------------------------------------------

** Bugfix
   * The DRAP will reboot if it does not receive a response to an Inclusion Accept. 



Version 2.4.18 - 2022-03-29
--------------------------------------------------------------

** Bugfix
   * The DRAP sends a route management frame with its own address marked as Unreachable. 
   * The display switches off and communication with the bus is disturbed. 



Version 2.4.16 - 2022-01-26
--------------------------------------------------------------

** Bugfix
   * The access points (HAP/DRAP) always send the Manufacturer Code 0x01 (EQ3) in the Inclusion Request, even with OEM variants.

** New Feature
   * Forward backbone route management frames to the cloud server



Version 2.4.14 - 2021-08-16
--------------------------------------------------------------

** Bugfix
   * Error flag Bus overload in StatusInfo is not reset
   * Carrier sense always 0
   * The DRAP tries to start a sequence number validation on all frames and takes the destination address of the receiving frame as the source address.
   * HTTP client hangs if the previous connection was not closed.
   * The access point interrupts the connection to the cloud server if the lookup server has delivered an incorrect URL.
   * Sends to MulticastAllWiredDevices over Backbone with wrong CRRFD Address
   * Error with updateURL not accessible.
   * Websocket connection delay is only applied after restart.
   * DRAP after firmwareupdate over CCU3 not reachable
   * Full support for DEC Identify.
   * DRAP power supply rated current exceeded: DRAP display goes off, nothing else happens.
   * DRAP do not respond to IGMPv3 Membership Queries

** New Feature
   * Request Route to device for Live OTAU support

** Improvement
   * The web bootloader should prohibit a downgrade to a smaller major version.
   * If a DRAP is operated with 2 separate strings, multicast frames are sent to bus 1 and bus 2 one after the other - this could also happen simultaneously.



Version 2.2.24 - 2020-12-16
--------------------------------------------------------------

** Bugfix
   * Frames can no longer be sent. The stack remains in the busy state. 



Version 2.2.16 - 2020-09-23
--------------------------------------------------------------

** Bugfix
   * Download of update files will not start, if FIN,ACK from checkversion is not acked.



Version 2.2.12 - 2020-08-26
--------------------------------------------------------------

** Bugfix
   * Multicast Readressing is also applied to INTERFACE_LOCAL/CLOUD



Version 2.2.10 - 2020-08-24
--------------------------------------------------------------

** Bugfix
   * If the application is defective, an incorrect application version is reported to the update server.



Version 2.2.4 - 2020-08-07
--------------------------------------------------------------

** Bugfix
   * The device-specific configuration can no longer be retrieved with Netfinder.



Version 2.2.2 - 2020-07-24
--------------------------------------------------------------

** Bugfix
   * Wrong app sequence counter in status response frame.
   * In loop mode, inclusion request frames are discarded in the coprocessor.

** Improvement
   * Do not accept frames to AnyRouter if it is known that it is not routed.



Version 2.2.0 - 2020-07-16
--------------------------------------------------------------

** Bugfix
   * With the custom lookup address, the path is not processed correctly. 

** New Feature
   * Advanced Routing

** Improvement
   * change default update URL
   * Block duplicate multicast frames when routing.
   * Accept CCU SGTIN within Update Server URL
   * Changing from switching to routing between the two buses of the DRAP



Version 2.0.28 - 2020-02-24
--------------------------------------------------------------

** Bugfix
   * With the custom lookup address, the path is not processed correctly. 



Version 2.0.26 - 2020-10-13
--------------------------------------------------------------

** Bugfix
   * Download of update files will not start, if FIN,ACK from checkversion is not acked.



Version 2.0.22 - 2019-06-17
--------------------------------------------------------------

** Bugfix
   * No communication between RF and wired components 



Version 2.0.18 - 2019-04-08
--------------------------------------------------------------

** Bugfix
   * DRAP lights up orange after update.



Version 2.0.16 - 2019-02-05
--------------------------------------------------------------

** Bugfix
   * LED sequence for factory reset is to slow
   * Wrong DHCP Vendor ID. DRAP reports as HAP 

** New Feature
   * OTAU multicast frames have to be routed 



Version 2.0.12 - 2018-10-19
--------------------------------------------------------------

** Bugfix
   * If the DRAP is configured as a router and it sends a validation request before it gets an IP address from the DHCP server, the DRAP restarts. 
   * sometimes the watchdog is triggered while Bus is powering up 



Version 2.0.6 - 2018-08-27
--------------------------------------------------------------

** Improvement
   * Only evaluate the HTTP response code, not the response phrase. 



--- END OF FILE ---

