## [HmIP-MOD-WD-VK_update_V1_2_14_260223.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-MOD-WD-VK_update_V1_2_14_260223.tgz)
Required CCU firmware version: &#8805; 3.65.6<br/>
<sub>sha256: 40d616faaeefabdc98bbe1384d2396024726d5a2bc4f4369dc54bb5285f271b4</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-MOD-WD-VK - Homematic IP Module for VEKA window drives

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.2.14 - 2026-02-23
--------------------------------------------------------------

** Bugfix
   * Powerup action doesn't work reliably
   * Missing status info after direct execution command



Version 1.2.12 - 2026-01-08
--------------------------------------------------------------

** Bugfix
   * Corrected communication timing with different VEKA firmware versions
   * Backup-Channel not triggered
   * Powerup action doesn't work reliably
   * Error code Communication not set when bus line is interrupted
   * No ErrorCode for ErrorDrive in status frame
   * No ErrorCodes for LowVoltage in status frame
   * Actor profile freezes after communication with LinkPartner
   * After receiving "driving" command a sporadic communication error occurs and is reported by status frame und LED
   * Wrong Parametervalue Channel2 List1: PowerUp_Jumptarget



Version 1.2.10 - 2025-10-09
--------------------------------------------------------------

** Bugfix
   * Operating mode "Pole Change" does not work any more since V1.2.2



Version 1.2.8 - 2025-09-29
--------------------------------------------------------------

** Bugfix
   * FactoryReset only possible with PowerUp



Version 1.2.6 - 2025-09-22
--------------------------------------------------------------

** New Feature
   * Support of new VEKA Drives with changed status handling

** Improvement
   * Changed interval for status request to the veka drive from 5s to 2s 



Version 1.2.2 - 2025-09-18
--------------------------------------------------------------

** New Feature
   * Support of new VEKA Drives with changed status handling

** Improvement
   * Changed interval for status request to the veka drive from 5s to 2s 



Version 1.0.6 - 2022-07-27
--------------------------------------------------------------

** Bugfix
   * Stop-Command ends a reference run after timeout
   * Wrong status info if VEKA drive is disconnected (bus or supply voltage)
   * Missing stop command after repeated key presses on local keys



Version 1.0.4 - 2022-07-21
--------------------------------------------------------------

** Bugfix
   * Stop-Command ends a reference run after timeout
   * Wrong status info if VEKA drive is disconnected (bus or supply voltage)
   * Missing stop command after repeated key presses on local keys



Version 1.0.2 - 2022-07-08
--------------------------------------------------------------

** Bugfix
   * Missing stop command after repeated key presses on local keys
   * At off/on delay the drive run to the other direction



Version 1.0.0 - 2022-06-30
--------------------------------------------------------------

** Bugfix
   * Green LED feedback although App-Ack is missing
   * Device keys not working correctly
   * Drive Error State is read from wrong register

** New Feature
   * Add level for a tilted window to actuator channel status



--- END OF FILE ---
