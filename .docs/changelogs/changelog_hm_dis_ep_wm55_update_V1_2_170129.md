## [hm_dis_ep_wm55_update_V1_2_170129.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HM/hm_dis_ep_wm55_update_V1_2_170129.tgz)
Required CCU firmware version: &#8805; 3.37.8 / 2.19.1<br/>
<sub>sha256: 36f8edf125e63ce548ca7c59cb82029ef8cbc9b323b11782cf67df5c733a810a</sub>

ï»¿Achtung! Bitte verwenden Sie die Firmware-Datei nur in Verbindung mit der CCU2 ab Version 2.19.1.
Die jeweils aktuellste Version finden Sie im Downloadbereich unter www.eQ-3.de.

Please note: Only use the firmware file in connection with the with the CCU2 from version 2.19.1.
In each case you will find the latest version in the download area of www.eQ-3.de.

In Verbindung mit der CCU2 wird das Geraet automatisch in den Updatemodus versetzt.


-----------------------------------------------------------------------------------------------------------------------------------
Wichtiger Hinweis fuer die Zeilenverwaltung:                                                                        

Ab der Firmwareversion 1.1 koennen die Statuszeilen bei einer Textuebertragung entweder ueberschrieben, oder mit der Zeichenkette 
"XXX" bzw. "xxx" geloescht werden.                                                                                         
------------------------------------------------------------------------------------------------------------------------------------

Changelog:

Version 1.2.001 - 20170126
--------------------------------------------------------------
** Bug fix
  * Device ignores central command if it is received directly after sending a SwitchCmd
  * Sporadically no correct processing of the long button press
  * Link options are incorrectly stored for wor receivers
  * Central program links on the channels 1 & 2 can lead to incorrect LED feedback

Version 1.1.002 - 20160927
--------------------------------------------------------------

** Improvement
  * Lines can now be preserved and are individually erasable
  * Changes for production reasons

Version 1.0.004 - 20160428
--------------------------------------------------------------
** Release
	* Initial version