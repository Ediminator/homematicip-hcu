## [HmIP-FWI_update_V1_0_14_220428.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-FWI_update_V1_0_14_220428.tgz)
Required CCU firmware version: &#8805; 3.61.5 / 2.61.7<br/>
<sub>sha256: 72b30c467f60caff9faad8d8b562bd794080218354944831bc6fa2694ba183b7</sub>

C H A N G E L O G
-----------------

Version 1.0.014 - 2022-04-28
--------------------------------------------------------------
** Improvement
    In connection with dnt fingerprint code lock BioAccess PRO:
     Use of 4-Bit or 8-Bit Mode recommended, 10-Bit Mode must not be used.


Version 1.0.012 - 2021-12-10
--------------------------------------------------------------
** Improvement
    Device does not communicate code inputs and bell contact actuation via status.
     If an code or a bell operation was detected during normal operation, this was not
     reported as a status. With the improvement, program actions via the status message
     are now also possible in addition to the direct link actions.
    After a firmware update the learned Wiegand codes are still available.
     After a FW update, the learned codes were no longer available and the customer has
     to teach them in again. The implementation was extended so that the codes are still
     known after a FW update.
    Time duration for the state update at restart of the central unit.
     When the control panel is restarted, the user channel authorizations are not known
     and are therefore initially set to "not authorized". The authorization is only
     correctly stored again when this has been communicated by the device via the
     corresponding status message. Means: Up to this point, the central program does not
     function. To solve this problem, this information is always sent when a status is
     sent due to a Wiegand code detection.


Version 1.0.006 - 2021-07-21
--------------------------------------------------------------
First Release.

--- END OF FILE ---

