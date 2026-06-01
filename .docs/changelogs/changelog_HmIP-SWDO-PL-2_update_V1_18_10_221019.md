## [HmIP-SWDO-PL-2_update_V1_18_10_221019.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-SWDO-PL-2_update_V1_18_10_221019.tgz)
Required CCU firmware version: &#8805; 3.65.11<br/>
<sub>sha256: 72d108398ab3362402961e3ff279bdab2477bacc442152529b7ae3969fb94532</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HMIP-SWDO-PL-2 - Homematic IP Window / Door Contact - optical, plus

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany

Version 1.18.10 2022-10-19
--------------------------------------------------------------
** Bugfix
   * The current consumption is too high if the sampling time 
     is more than 2 s and the battery cover is closed.


Version 1.18.8 2022-10-05
--------------------------------------------------------------
** Bugfix
   * Boot flag now get reseted correctly after receiving APP ACK. This also solves [HMIP_SWDO_2-10]


Version 1.18.6 2022-09-12
--------------------------------------------------------------
** New Feature
   * Hotfix for high current consumption with open housing.


Version 1.18.4 2022-06-28
--------------------------------------------------------------
** New Feature
   * Add parameter CYCLIC_BIDI_INFO_MSG_DISCARD
   * enable CYCLIC_BIDI_INFO_MSG_DISCARD parameter for all devices
   * default value is 30 (every hour)


Version 1.18.0 - 2022-04-28
--------------------------------------------------------------
** New Feature
   * Add pairing support (HmIP-SWDO-PL/HmIP-SWDO-PL-2)
   * Add support for HmIP-SWDO-2


Version 1.16.10 - 20190227
--------------------------------------------------------------
** Bugfix
   * [YOU_CTS_OPT_SMI_BN-52][HMIP_SWDO_I-20]Fixed a bug that
     caused setting of alarmworthy event flag with unidirectional
     or cyclic status frames.

** New Feature
   * Added new device type for HmIP-SWDO-PL.


Version 1.16.8 - 20180302
--------------------------------------------------------------

** Related Hardware
   * 1343958I / 1454161C

** Bugfix
   * Fixed a bug with receiving answers of conditional switch commands.
   * Also had to correct the counting of sequence counters if
     they are the same as the sequence counter of the status frame.


Version 1.16.6 - 20180221
--------------------------------------------------------------
** Modifications
   * Changed counting of event_counter to new mechanism
     (boot:0; other:[1..252]).
   * Reworked the mechanism of receiving answers.


Version 1.16.4 - 20180209
--------------------------------------------------------------
** Bugfix
   * Added separate keypress counter for window and backup.
   * All pending flags are now handled after boot process is
     finished. Otherwise it is possible to miss an acknowledgment
	   frame of a frame at boot.


Version 1.16.2 - 20180207
--------------------------------------------------------------
** Bugfix
   * Added first statusinfo to the backup mechanism.



Version 1.16.0 - 201802015
--------------------------------------------------------------
** Bugfix
   * Added mechanism to prevent overwriting of a alarmworthy
     event with a not alarmworthy one.
   * Fast window open and close now also causes a backup.
   * Fixed a bug with missing MAC_ACKs after blinking.
** New Feature
   * Added new parameter DISABLE_MSG_TO_AC.
   * Added alarm-channel and depending functionality for
     security solution.
** Comments
   * Excluded cyclic bidi statusinfo from backup mechanism.
   * 'ifdef'-ed some unnecessary parts for contact sensors
     without optical detection.


Version 1.14.1 - 20170803
--------------------------------------------------------------
** Bugfix
   * Fixed bug in sleep behaviour.


Version 1.14.0 - 20170315
--------------------------------------------------------------
** Bugfix
   * Report link partner problem frame now includes the
      address of the link partner
   * device turn of rx and go to sleep if status info to shc
      was ok but at least one link partner hasn't answered
** Modification
   * add separate sequence counter for status infos
** Comments
   * relevant changes in HMOS:
   * Device is 5 seconds awake after sending a Multicast (AllDevices)
   * Communication problems with burst receivers when sending multiple
     data packets one after the other


Version 1.12.2 - 20170208
--------------------------------------------------------------
** Comments
   * Did a actualisation of the firmware converter.
     To be sure to be able to differentiate between the old
     and the new update file the version was increased.


Version 1.12.1 - 20160425
--------------------------------------------------------------
** Bugfix
   * Fixed a bug with ACKs to config update request frames.


Version 1.12.0 - 20160413
--------------------------------------------------------------
** Comments
   * Increased version due to change from SVN to GIT
     and to new library version.

