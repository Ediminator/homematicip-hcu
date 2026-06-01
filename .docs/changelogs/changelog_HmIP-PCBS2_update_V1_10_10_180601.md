## [HmIP-PCBS2_update_V1_10_10_180601.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-PCBS2_update_V1_10_10_180601.tgz)
Required CCU firmware version: &#8805; 3.45.5 / 2.45.6<br/>
<sub>sha256: e7fd35671aa9697a93c105f6327cc558fea30bc24f43872c23e194f38864273b</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device: HmIP-PCBS2 - Homematic IP Printed Circuit Board Switch 2 Channels

Company: eQ-3, Maiburger Str. 29, 26789 Leer, Germany


Version 1.10.10 - 20180220
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
   * Fixed wrong reset of a pending flag if disable_msg_to_ac was set.
   * Added sending of unknown RSSI value in two cases.
   * Corrected switching direction if switching with current 
     detection is disabled.
   * Corrected timeout for sequence counter (from 10 to 2 minutes).
	 
** Improvement
   * Corrected some comments.
   
** Comments 
   * Changed default value for POWERUP_ONTIME from 0x00 to 0xFF.
   * Added new operation mode (minimum HMOS 1.24.0 necessary)
   * Changed counting of event_counter to new mechanism
     (boot:0; other:[1..252]).
   * Changed checking of event_counter to new mechanism.

   
   
Version 1.10.8 - 20171222
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
   * Fixed bug with fast switching
	 
** Improvement
   *
   
** Comments 
   * 
   
   
Version 1.10.6 - 20171106
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
   * Fixed a bug with sending statusframes with ACK and ARR bit
	 
** Improvement
   *
   
** Comments 
   * 


Version 1.10.4 - 20171020
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
   * Fixed a bug with sending statusframes at actuartors
     with powermeter function.
	 
** Improvement
   *
   
** Comments 
   * 
   
   
Version 1.10.2 - 20171009
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
   *
	 
** Improvement
   *
   
** Comments 
   * Increased version of HMOS to 1.20.4.
   
   
Version 1.10.0 - 20171006
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
   *
	 
** Improvement
   *
   
** Comments 
   * Created Tag 1.10.0


Version 1.9.2 - 20171006
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
   * Changed behaviour of init routines in powermeter- and switch-task.

   * Fixed behaviour of sending statusmessages 
     for multichannel devices. 
	 
** Improvement
   
** Comments 
   
   
Version 1.9.1 - 20170908
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

	 
--- END OF FILE ---
