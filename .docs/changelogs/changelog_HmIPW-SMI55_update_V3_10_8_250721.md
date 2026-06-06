## [HmIPW-SMI55_update_V3_10_8_250721.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIPW/HmIPW-SMI55_update_V3_10_8_250721.tgz)
Required CCU firmware version: &#8805; 3.69.7<br/>
<sub>sha256: 775792cc9402ef20fac6dcf6e28f1ba7546eaf52c170c6b38ddc4356ef409d76</sub>

C H A N G E L O G
-----------------

Version V3.10.8 - 2025-07-07
--------------------------------------------------------------

** Bugfix
   * After a long key stroke (2min-timer has expired) Device do not send to extLP on a new key stroke
   * Timer for long keystroke is not considered
   * AppSeqNr wird nicht korrekt erhÃ¶ht
   * SMO230 geht auf unreach
   * ErhÃ¶hte Stromaufnahme nach Bedienung der Remote-KanÃ¤le
   * Flashing behavior not correct during transmission

** Improvement
   * Long button press cannot dim in conjunction with a motion detector.



Version V3.10.6 - 2025-05-23
--------------------------------------------------------------

** Bugfix
   * Mit einem WRCx Tastenpaar in der Schaltgruppe des SMO230 kann man zwar ein- aber nicht ausschalten
   * Interner Aktor schaltet nicht bei DV von externen Aktoren mit MOTION_VIRTUAL
   * Backup-Channel - DecisionValue in BAckup-CSC is unlike ParameterValue 0xB3 
   * Aktuator-Channel w/o Function after adding LP to BlockingChannel 
   * Device does not send any status info to the HAP if the actuator status has changed
   * RetriggerDeviceInclusion Command will be ignored
   * Device use wrong AppSeqNr after "Abort Sending" with Buttonpress
   * Sending Order while sending to burst and perm Listener not correct
   * Device sends configUpdateReq if internal LP linked to BlockingChannel 
   * Device does not acknowledge with a response to a reset on Channel 2

** Improvement
   * Send Answer "NAK, old Event" if Event-counter is not valid



Version V3.10.4 - 2024-06-21
--------------------------------------------------------------

** Bugfix
   * Tastendruckroutine fÃ¼r langen Tastendruck fehlerhaft



Version V3.8.104 - 2024-01-26
--------------------------------------------------------------

** Bugfix
   * The changeover from summer time to winter time takes place 1 hour too early
   * Actuator channels: Process State is not output correctly
   * Timeprofile: not all virtual channels will be triggered 
   * DaylightSavingTime changeover does not take place
   * Wrong Parameter values for UTC and DST
   * Device should send a TimeInfoRequest after configuration of list 0
   * Weekprogram profile: Real and virtual states don't match
   * The device sporadically does not switch according to the time profile
   * Parameter Liste1 0x4d ... "RemoteAbortEventSendingChannels" nicht vorhanden



Version V3.8.102 - 2024-01-11
--------------------------------------------------------------

** Bugfix
   * ParameterList 3 - wrong Defaultvalues short/long for parameter ONTIME  
   * PowerUP-Paramter: Switch-on delay for VirA (CH10) is ignored
   * Switching status of the real channel is not consistent for various "LogicCombination" with Vir channel A
   * Parameter "EventDelayTime" delays the actuator state change

** Improvement
   * Customizing the Function of the System Button
   * Clarification: Customizing the Function of the System Button



Version V3.8.98 - 2023-12-13
--------------------------------------------------------------

** Bugfix
   * Parameter 0x18 und 0x 1a in Liste 0 haben falschen default-wert



Version V3.6.82 - 2023-10-05
--------------------------------------------------------------

** Improvement
   * Parameter x4D und x4C Default-Wert anpassen



Version V3.6.80 - 2023-09-28
--------------------------------------------------------------

** Bugfix
   * Parameter Liste1 0x4d ... "RemoteAbortEventSendingChannels" nicht vorhanden



Version V3.6.78 - 2023-09-27
--------------------------------------------------------------

** Bugfix
   * RequestConfigUpdate not send on buttonpress (push buttons)



Version V3.6.72 - 2023-05-04
--------------------------------------------------------------

** Bugfix
   * Keine Statusmeldung, wenn Bewegungserkennung mit DEC reaktiviert wird



Version 3.2.28 - 2022-05-13
--------------------------------------------------------------

** Modification
   * Ungefilterter Helligkeitswert ist immer gleich dem gefilterten Wert 



Version V3.2.22 - 2021-10-14
--------------------------------------------------------------

** Modification
   * GerÃ¤t ignoriert Antworten der Zentrale bei mehr als einem Link auf dem BM-Kanal
   * GerÃ¤t ignoriert Antworten der Zentrale bei mehr als einem Link auf dem BM-Kanal
   * GerÃ¤t ignoriert Answer-Frames von Zentrale und zeigt dann ein falsches Sendeverhalten



Version V3.2.20 - 2021-07-22
--------------------------------------------------------------

** Modification
   * CLONE - BrightnessFilterTime - Status mit gefiltertem Wert wird zu spÃ¤t gesendet  
   * BrightnessFilterTime - Status mit gefiltertem Wert wird zu spÃ¤t gesendet  



Version V3.2.18 - 2021-07-21
--------------------------------------------------------------

** Modification
   * CLONE - GerÃ¤t antwortet nicht immer auf ein StatusRequest 
   * GerÃ¤t antwortet nicht immer auf ein StatusRequest 
   * CLONE - GerÃ¤t sendet auf ein ConfigStart ein Answer mit NAK-Old Event
   * GerÃ¤t sendet auf ein ConfigStart ein Answer mit NAK-Old Event



Version V3.2.16 - 2021-07-14
--------------------------------------------------------------

** Modification
   * CLONE - GerÃ¤t sendet kein AppAck/Status wenn ein Schaltbefehl mit langem Tastendruck  auf dem BlockingChannel  empfangen wird
   * GerÃ¤t sendet kein AppAck/Status wenn ein Schaltbefehl mit langem Tastendruck  auf dem BlockingChannel  empfangen wird
   * CLONE - SPI sendet kein Status nach timeout der Blocking Period, wenn zuvor Konfig.parameter Ã¼bertragen wurden



--- END OF FILE ---
