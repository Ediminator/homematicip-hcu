## [hm-ou-cfm-tw_update_V1_3_160620.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/hm-ou-cfm-tw_update_V1_3_160620.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.17.9<br/>
<sub>sha256: 387c263491b6532558ab08fa49e40bbe164f8b89b59e0e3bd71fe10278a32c2e</sub>

Achtung! Bitte verwenden Sie die Firmware-Datei nur in Verbindung mit dem Firmware Update Tool ab Version 1.1 sowie der CCU2 ab Version 2.15.2.
Die aktuellste Version des Firmware Update Tools finden Sie im Downloadbereich der Website www.eQ-3.de.

Please note: Only use the firmware file in connection with the Firmware Update Tool from version 1.1 as well as from version 2.15.2 of the CCU2.
You will find the latest version of the Firmware Update Tool in the download area of the website www.eQ-3.de.

In Verbindung mit der CCU2 wird das Gerät automatisch in den Updatemodus versetzt.

Für ein Firmware-Update mit dem Firmware Update Tool, gehen Sie wie folgt vor:
1. Trennen Sie das Gerät von der angeschlossenen Versorgungsspannung,
2. den Anlerntaster (Kanal 1) des Gerätes drücken und festhalten,
3. bei gedrücktem Anlerntaster die Versorgungsspannung wiederherstellen.
4. Sobald die LED schnell blinkt, kann die Taste losgelassen werden. Das Update wird jetzt durchgeführt.

-----------------------------------------------------------------------------------------------------------------------------------
| Wichtiger Hinweis für ein Update per CCU2:                                                                        
|
| Der Start des Firmupdates von der Version 1.1 kann nach dem Start des Updatevorganges eine Fehlermeldung in der Zentrale
| auslösen, obwohl die Geräte-LED korrekt blinkt.
|
| Bitte bestätigen Sie in diesem Fall die Fehlermeldung in der WebUI. Entnehmen Sie die Batterien aus dem Gerät, um diese dann 
| bei gedrücktem Taster wieder einzusetzen. Das Update startet unmittelbar, erkennbar an dem schnellen Blinken der LED. 
| Nach etwa 2 - 3 Minuten ist das Update angeschlossen.
|
| Wurde die neue Firmware erfolgreich Übertragen, wird von dem Gerät das Initialisierungsblinken durchgeführt. 
| Unter "Einstellungen -> Geräte" in der WebUI wird nach aktualisieren der Ansicht die neue Firmwareversion angezeigt. 	                                                                                                
------------------------------------------------------------------------------------------------------------------------------------

Changelog:

Version 1.3.001 - 201600620
--------------------------------------------------------------
** Bug fixes
  * Handling of voltage comparator improved
  
Version 1.2.003 - 20160418
--------------------------------------------------------------
** Bug fixes
  * Handling of MP3 files in a playlist
  * Handling of blink signals in a playlist
  * Start of firmware update via central 
** Improvement
  * Changes for production reasons

Version 1.1.001 - 20160211
--------------------------------------------------------------
** Bug fixes
  
Version 1.0.001 - 20151110
--------------------------------------------------------------
** Release
	* Initial version