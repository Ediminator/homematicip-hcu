## [HMIP-HAP_3_0_18_230929.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HMIP-HAP_3_0_18_230929.tgz)
Required CCU firmware version: &#8805; 3.73.9<br/>
<sub>sha256: 95a994f191dd537809820d31f049ecf12699b76fc6dcb1984934ba9fd447bb34</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-HAP - Access Point
alte Bezeichnung: YOU-HAP-TTU

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 3.0.18 - 2023-09-29
--------------------------------------------------------------

** Bugfix
   * LEDs flash blue and after some time the communication to the cloud is disrupted.
   * The update is interrupted after the web bootloader is downloaded.



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
   * Times between lookup requests become too large
   * After reboot (power) sometimes both APs connected to cloud
   * No lookup request after get a crrfd url that is too long
   * Time at close connection with 0xffff wrong



Version 3.0.4 - 2023-03-22
--------------------------------------------------------------

** Bugfix
   * Encrypted frames not send to cloud
   * The access point gets stuck in an endless loop when an update is triggered by Netfinder, but no different version is available on the update server.
   * Backbone frames payload length wrong

** New Feature
   * New parameters for multicast filter
   * Connection to the Cludserver, LockupServer and Updateserver via IPv6 possible
   * Use return code when closing the WebSocket to the AP for indication if the route is still valid.

** Improvement
   * send destination unreach with LHL = 7-x



Version 2.4.28 - 2022-09-16
--------------------------------------------------------------

** Bugfix
   * The access point sends frames to the server that are too long. 
   * Replies to frames from the server are lost. 

** Improvement
   * Set different timeouts for backbone Routers and backbone devices 



Version 2.4.24 - 2022-05-12
--------------------------------------------------------------

** Bugfix
   * The HAP treis to send a frame to all wired devices via any router 



Version 2.4.20 - 2022-04-06
--------------------------------------------------------------

** Bugfix
   * The HAP will reboot if it does not receive a response to an Inclusion Accept. 



Version 2.4.18 - 2022-03-29
--------------------------------------------------------------

** Bugfix
   * The HAP sends a route management frame with its own address marked as unreachable. 



Version 2.4.16 - 2022-01-26
--------------------------------------------------------------

** Bugfix
   * The access points (HAP/DRAP) always send the Manufacturer Code 0x01 (EQ3) in the Inclusion Request, even with OEM variants.
   * Device becomes continuous BURST transmitter in case of cloud failure
   * HAP answers status frames (ARR) with burst frames.

** New Feature
   * Forward backbone route management frames to the cloud server



Version 2.4.12 - 2021-07-27
--------------------------------------------------------------

** Bugfix
   * The HAP tries to start a sequence number validation on all frames and takes the destination address of the receiving frame as the source address.



Version 2.4.10 - 2021-07-15
--------------------------------------------------------------

** Bugfix
   * FactoryReset first button press duration too long



Version 2.4.8 - 2021-06-29
--------------------------------------------------------------

** Bugfix
   * KeyVisual key press data for long button press wrong

** Improvement
   * Stronger evaluation of the RSSI value during routing 



Version 2.4.4 - 2021-04-28
--------------------------------------------------------------

** Bugfix
   * HTTP client hangs, if the previous connection was not closed.
   * The access point interrupts the connection to the cloud server if the lookup server has delivered an incorrect URL.
   * Incorrect KeyVisual signal when the AP disconnects from the cloud server.
   * Wrong priority for frames to event listener  
   * The AccessPoint sends a response to an empty RM V1 request.
   * HAP glows permanently turquoise in a Singel HAP installation 
   * Factory reset is also possible during operation. 
   * Fehler bei nicht erreichbarer UpdateURL
   * Invalid Tcp/IP packet in the web bootloader.
   * Websocket connection delay is only applied after restart.
   * HAP do not respond to IGMPv3 Membership Queries

** New Feature
   * Request routing information over HAP protocol
   * Live OTAU Service

** Improvement
   * Improve system behavior when HmIP-HAP has no internet connection.



Version 2.2.24 - 2020-12-16
--------------------------------------------------------------

** Bugfix
   * Frames can no longer be sent. The stack remains in the busy state. 



Version 2.2.18 - 2020-10-07
--------------------------------------------------------------

** Bugfix
   * OTAU: "Update Data" frames are send with burst.



Version 2.2.16 - 2020-09-23
--------------------------------------------------------------

** Bugfix
   * Web-Bootloader cancels download of CoProzessor update.
   * Download of update files will not start, if FIN,ACK from checkversion is not acked.



Version 2.2.12 - 2020-08-26
--------------------------------------------------------------

** Bugfix
   * Multicast Readressing is also applied to INTERFACE_LOCAL/CLOUD



Version 2.2.10 - 2020-08-24
--------------------------------------------------------------

** Bugfix
   * If the application is defective, an incorrect application version is reported to the update server.

** Improvement
   * No longer route cyclic multicast frames.
   * Flashing behaviour when the centre is not accessible (flashing turquoise)



Version 2.2.4 - 2020-08-07
--------------------------------------------------------------

** Bugfix
   * The device-specific configuration can no longer be retrieved with Netfinder.



Version 2.2.0 - 2020-07-16
--------------------------------------------------------------

** Bugfix
   * With the custom lookup address, the path is not processed correctly. 

** New Feature
   * Advanced Routing

** Improvement
   * Change the default update URL
   * Improve the connection to the cloud server. 



Version 2.2.2 - 2020-07-24
--------------------------------------------------------------

** Bugfix
   * Wrong app sequence counter in status response frame.

** Improvement
   * Do not accept frames to AnyRouter if it is known that it is not routed.



Version 2.0.40 - 2020-10-05
--------------------------------------------------------------

** Bugfix
   * Download of update files will not start, if FIN,ACK from checkversion is not acked.



Version 2.0.36 - 2019-10-16
--------------------------------------------------------------

** Bugfix
   * The HAP crashes and restarts when DHCP is switched off. 



Version 2.0.34 - 2019-10-11
--------------------------------------------------------------

** Bugfix
   * If the ICMP ping fails, but the lookup server query succeeds, the KeyVisual color is not updated. 
   * The local bootloader returns a wrong value during the update. 



Version 2.0.32 - 2019-10-08
--------------------------------------------------------------

** Bugfix
   * No connection to the server is established and the KeyVisual lights up yellow permanently. 

** Improvement
   * To test the Internet connection, an attempt is made to send a ping to the lookup server; if the ping fails, an attempt is made to establish a connection anyway. 



Version 2.0.26 - 2019-07-23
--------------------------------------------------------------

** Bugfix
   * With the custom lookup address, the path is not processed correctly. 
   * HAP firmware stops after a FactoryReset is cancelled.
   * FactoryReset has no timeout.



Version 1.2.26 - 2020-10-06
--------------------------------------------------------------

** Bugfix
   * Download of update files will not start, if FIN,ACK from checkversion is not acked.



Version 1.2.12 - 2018-04-19
--------------------------------------------------------------

** Bugfix
   * the configuration data will sometimes be corrupted during the update, causing a factory reset
   * Look up server is requested just one time after startup 



--- END OF FILE ---

