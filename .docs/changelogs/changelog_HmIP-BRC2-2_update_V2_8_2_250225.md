## [HmIP-BRC2-2_update_V2_8_2_250225.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-BRC2-2_update_V2_8_2_250225.tgz)
Required CCU firmware version: &#8805; 3.83.6<br/>
<sub>sha256: e3df7fe0bcb1b09b9825cc5e66e2dc8c5cd750a2f824f245d1ffdf023ad53f85</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-BRC2-2 - Homematic IP Remote Control for brand switches - 2 channels 

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 2.8.2 - 2025-02-25
--------------------------------------------------------------

** Bugfix
   * Device Parameters are different to Device Specific documentation 



Version 2.8.0 - 2025-01-30
--------------------------------------------------------------

** New Feature
   * Version 1.8.6 20180308
     --------------------------------------------------------------
     ** Bugfix
        * Transmission behaviour incorrect on long keystroke
        * Error in transmission behaviour if link partner answers late
        * Wrong channel number in "report linkpartner problem" frame
     
     ** New Feature      
        * Support of systems and solutions without a central unit (installer solution)
     
     ** Improvement
        * update HMOS to V1.26.0
     
     Version 1.6.0 20170823
     --------------------------------------------------------------
     ** Bugfix
        * if one link partne is unreachable the device goes to
          sleep directly and is not waiting for app answers of 
          other link partners
     
     ** Improvement
        * update HMOS to V1.20.3
     
     Version 1.4.2 20161216
     --------------------------------------------------------------
     ** Bugfix
        * HMOS now ignore stay awake bit for frames that are 
          looped back internal
        * statusinfo frames are send with the "normal"sequence
          number -> 
          after every status info frame the status info sequence
          counter is incremented, but the normal counter is put in
          the status frame. so every status info is send with the
          same sequence number as long no "normal" frame is send.
          The ACKs of the status info frames are not accepted as
          the sequence number of the ACK frame and the internal
          status info sequence number doesn't match
     
     ** Improvement
        * update HMOS to V1.18.2
     
     Version 1.4.1 20160422
     --------------------------------------------------------------
     ** Bugfix
        * Fixed bug that device waits arr timeout before 
          signaling tx status (red or green)
     	 * Device now accepts answers from SNC/HAP for switch commands



--- END OF FILE ---

