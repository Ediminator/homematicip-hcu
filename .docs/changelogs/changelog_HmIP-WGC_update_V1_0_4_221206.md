## [HmIP-WGC_update_V1_0_4_221206.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-WGC_update_V1_0_4_221206.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.31.23<br/>
<sub>sha256: 7ad624454a844409546d01de773b4cc2d3f0aa20228fca9b3a003dfcdf81a0fd</sub>

 R E L E A S E   N O T E S
-------------------------


Device:   HmIP-WGC
Component:  Application of the Homematic IP Wallmount Garage Controller 

Company:  eQ-3 Electronics Co.,Ltd , Zhuhai,Guangdong, China
Author:   Karsten Loof

Version 1.0.4 - 2022-12-05
--------------------------------------------------------------
** Improvement
   * General improvements - Code optimisation

Version 1.0.2 - 2017-9-1
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
 
** Improvement
   System turn off on voltage 2.0V
   Send the status frame with error bit to receiver once battery voltage under 2.4V
   Send the status frame with bad battery bit to receiver once battery voltage under 2.6V
   Once power by battery and the battery voltage is under 2.4V, no action on relay and send out an NAK frame.
   
Version 1.0.1
--------------------------------------------------------------

** Related Hardware
   * 150948B
   
** Comments
   * Updated to HMOS V1.20.3

Version 1.0.0 - 2017-8-14
--------------------------------------------------------------

** Related Hardware
   * 150948B

Release the version to V1.0.0

Version 0.0.21 - 2017-8-2
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *Fixed [Jira] (HMIP_WGC-18) If the device is powered with 2.4V at start, the device current is at 4mA
    Problem is turn on the relay boost circuit in initialise    
** Improvement
   * Turn on the relay boost circuit early 10ms before turn on the relay. This way helpfully for low battery voltage.
   * Battery low bat redefine
     #define VERY_LOW_BAT_LIMIT_BOOT_TWOCELL   2400
     #define VERY_LOW_BAT_LIMIT_TX_TWOCELL     2450

Version 0.0.20 - 2017-7-28
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *Fixed [Jira] (HMIP_WGC-17) Device is blinking if low bat and intern button is pressed
        
** Improvement


Version 0.0.19 - 2017-7-14
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *Fixed [JIRA] (HMIP_WGC-16) Switching more than one channel over one transmitter is not possible
      
   Add code:  if( m_linked_channels == 0) in line 555
   
** Improvement



Version 0.0.18 - 2017-7-10
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *Fixed [JIRA] (HMIP_WGC-14) If one linkpartner was not reached 
          a Report Linkpartner Problem frame will be sent after 10 seconds
      
    Set rx_timeout to zero once need to report linkpartner problem.
   
** Improvement


Version 0.0.17 - 2017-7-5
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *Fixed [JIRA] (HMIP_WGC-14) If one linkpartner was not reached 
          a Report Linkpartner Problem frame will be sent after 10 seconds
      
    Set rx_timeout to zero once need to report linkpartner problem.
   
** Improvement

Version 0.0.16 - 2017-7-5
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *Fixed <HMIP_WGC-10 > - <Cyclic status info have not the the RSSI value 0x80> 
    Changed the APPLICATION_STATE_SEND_STATUS with 0x80 
   
** Improvement

Version 0.0.15 - 2017-6-20
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   * Try fixed the bug of HMIP_WGC-12 [If the button is pressed long, the next short button press is send with long key pressed ]
     No sure as can not test the bug in Zhuhai, changed the code that may affect the bug.
   
** Improvement
 

Version 0.0.14 - 2017-6-12
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   * Fixed the bug of HMIP_WGC-11 [Device send multicast if just one linkpartner is added to channel 1 ]
   
** Improvement
 

Version 0.0.13 - 2017-6-8
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   * Fixed the bug of HMIP_WGC-13 [Ontime with Direct Execution Command and Jumptarget is not longer than 1 second]
     The output relay shall have the function like the HmIP protocol. The device shall function like a normal actor 
   device. So no limitation in the firmware. Only the limitation over the configuration parameters are allowed. 
   
** Improvement
 

Version 0.0.12 - 2017-4-10
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   * Disable system LED invisible function. DON NOT have invisible function after few mins.
   * Device will been able to switch the relay before inclusion.
   * Relay on time, Min value set to 300ms, Max value set to 1,000ms.Stand value set to 400ms. Step is 100ms.
     Change the LIST3_ON_TIME for different duration.
** Improvement
   * Battery voltage measurement while relay on function NOT implement at this version.


Version 0.0.11 - 2017-4-5
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix

** Improvement
   * Improvement the test mode function. Had test with test runner software.

Version 0.0.10 - 2017-3-6
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
    *[JIRA] (HMIP_WGC-5) Long keypress does not work correct
  *[JIRA] (HMIP_WGC-8) No address in LinkPartnerPRoblem telegramm
  *[JIRA] (HMIP_WGC-9) Wrong send behaviour
  
 
waiting feedback from Leer for LED on time.

** Improvement
   * 
   
Version 0.0.7 - 2017-1-20
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *

** Improvement
   * Changed the resotring factory reset to main power supply way. Don't need remove the battery / extern power for restoreing factory mode.

Version 0.0.6 - 2017-1-19
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *

** Improvement
   * If power up by extern power supply, turn the RX mode to TRANSCEIVER_MODE_RX. Device don't go to sleep and leave FULL RX all the time.

Version 0.0.5 - 2017-1-10
--------------------------------------------------------------

** Related Hardware
   * 150948B

** Bugfix
   *

** Comments 
    Comment or delete some unused code. that code only support in ASIR.

Version 0.0.4 - 2017-1-5
--------------------------------------------------------------

** Related Hardware
   * 150948A(It should be B in face), boost for relay.

** Bugfix
   * Fixed the bug of battery current consumption on standby. 

** Comments 
   * Add relay opraiton time recode for debug the battery lifetime.


Version 0.0.3 - 2016-12-6
--------------------------------------------------------------

** Related Hardware
   * 150948A(It should be B in face), boost for relay.

** Bugfix
   * Relay no work some time.   

** Comments 
   * improvment the LED function, LED will on only 6 minutes after power on.

   
Version 0.0.2 - 2016-10-19
--------------------------------------------------------------

** Related Hardware
   * 150948A

** Bugfix
   * 

** Comments 
   * Finished first test with PCBA. 
   * Including
   * Internal internal link 
   * LED indicate
   

Version 0.0.1 - 2016-9-14
--------------------------------------------------------------

** Related Hardware
   * NONE

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

