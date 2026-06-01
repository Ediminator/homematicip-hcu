## [HM-Sen-MDIR-WM55_update_V1_2_0_160825.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/HM-Sen-MDIR-WM55_update_V1_2_0_160825.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.11.9<br/>
<sub>sha256: 92846022dde3a010c3dcbdf514ccd029614c7fce4b753048c48e90b42016a940</sub>

Achtung! Bitte verwenden Sie die Firmware-Datei nur in Verbindung mit dem Firmware Update Tool ab Version 1.1 sowie der CCU2 Version 2.11.9.
Die aktuellste Version des Firmware Update Tools finden Sie im Downloadbereich der Website www.eQ-3.de.

Please note: Only use the firmware file in connection with the Firmware Update Tool from version 1.1 as well as version 2.11.9 of the CCU2.
You will find the latest version of the Firmware Update Tool in the download area of the website www.eQ-3.de.


In Verbindung mit der CCU2 wird das Geraet automatisch in den Updatemodus versetzt. 
Fuer ein Firmware-Update mit dem Firmware Update Tool, gehen Sie wie folgt vor:
1. Entnehmen sie die Battieren aus dem Geraet,
2. den Anlerntasters des Geraetes drÃ¼cken und festhalten,
3. bei immer noch gedrueckt gehaltener Anlerntaster die Batterien wieder einsetzen.
4. Sobald die LED schnell blinkt, kann die Taste losgelassen werden. Das Update wird jetzt durchgefuehrt.




Changelog:

Version 1.2.0 - 20160825
--------------------------------------------------------------

** Bugfix
   * wrong brightness calculation for values over 190
   
** Improvement
   * changed brightness calculation of values below 80 (approx 1 Lux)
     from logarithm to linaer for better utilization.
     Caution: If values below 80 are used in programs or links, 
              this programs or links must be adjusted.


Version 1.1.2 - 20150413
--------------------------------------------------------------

** Bugfix
   * sending conditional switch command all 6 min. fixed
   * wrong blinking during direct teach-in fixed
   * inverted key channel functions in direct teach-in fixed
   
** Improvement
   * removed delay in brightness measurment


Application Version 1.0.1 - 20150115
--------------------------------------------------------------

** Comments
   * First Release