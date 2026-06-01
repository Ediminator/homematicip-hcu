## [HmIP-RGBW_update_V1_0_62_230711.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-RGBW_update_V1_0_62_230711.tgz)
Required CCU firmware version: &#8805; 3.69.7<br/>
<sub>sha256: ef23ac0e4a341637e6b94d57900610152ecabc856fb2b30589ef5d2e655483d0</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-RGBW - Homematic IP RGBW Dimmer fÃ¼r LED Strips

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.0.62 - 2023-07-11
--------------------------------------------------------------

** Bugfix
   * StatusInfo at channel 2 wrong if effect is started
   * After set config sometimes a statusinfo is send with wrong frametype
   * The ON_MIN_LEVEL parameter is evaluated inconsistently for a DEC and a direct link.
   * Effect colour with level 0 is not set



Version 1.0.54 - 2023-04-03
--------------------------------------------------------------

** Bugfix
   * Effect rendering at brightness = 0%
   * Effect / scene with random sequence and endless repetitions stops
   * Take over rainbow effect from DALI gateway as default setting



Version 1.0.52 - 2022-12-13
--------------------------------------------------------------

** New Feature
   * Frist Release



--- END OF FILE ---
