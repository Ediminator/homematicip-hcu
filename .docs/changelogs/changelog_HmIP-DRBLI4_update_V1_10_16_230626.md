## [HmIP-DRBLI4_update_V1_10_16_230626.tgz](https://raw.githubusercontent.com/ediminator/homematicip-hcu/main/HmIP/HmIP-DRBLI4_update_V1_10_16_230626.tgz)
Required CCU firmware version: &#8805; 3.69.5<br/>
<sub>sha256: 52fed059ea0cd92e73f07d8d123580c8ddc740c3fac68ab5b63479d4dced29e9</sub>

C H A N G E L O G
-----------------

Please note: Only use the firmware file in connection with the current software-version of the CCUx!

Device:      HmIP-DRBLI4 - Homematic IP Jalousieaktor fÃ¼r Hutschienenmontage  â 4-fach

Company:     eQ-3, Maiburger Str. 29, 26789 Leer, Germany



Version 1.10.16 - 2023-06-16
--------------------------------------------------------------

** Improvement
   * Funktion "Enable operation within one end position to manually solve any error" execute only with a long button press.



Version 1.10.14 - 2023-02-10
--------------------------------------------------------------

** Bugfix
   * Reduced maximum number of partners to 4 for virtual channel B



Version 1.10.10 - 2022-12-02
--------------------------------------------------------------

** Bugfix
   * Incorrect display visualization while local operation



Version 1.10.8 - 2022-11-15
--------------------------------------------------------------

** Bugfix
   * Wrong evaluation of the event counter with multiple links between sensor and actuator
   * Error in slat adjustment, slats move in the wrong direction



Version 1.10.0 - 2022-06-05
--------------------------------------------------------------

** Bugfix
   *  Error when the same position is called up several times
   * A command triggered by weekprogram or internal link is handled by the virtual channels although an error is active

** New Feature
   * Add possibilty to increase the time between two slats movements

** Improvement
   * Switch from external to internal oscillator
   * Change of driving time while long button press if the end position of the slats is reached
   * Enable operation within one end position to manually solve any error



Version 1.8.2 - 2021-02-15
--------------------------------------------------------------

** Bugfix
   * Section of virtual channels remains in "Move up/down reference run" if all three virtual channels are triggered by Direct Execution Command at startup



Version 1.8.0 - 2021-01-15
--------------------------------------------------------------

** Bugfix
   * A long keypress release leads to longer run time than the previous ones if the driving time is shorter than the long keypress repetition time
   * After a long button press, one channel will sporadically remain permanently supplied with 230 volts.
   * After a long keypress the actor runs longer than the set driving time
   * Device freezes, if undefined number of keypresses have been done



Version 1.6.0 - 2020-06-09
--------------------------------------------------------------

** Bugfix
   * Device sends RequestConfigUpdate if received a MacAck from a LinkPartner
   * The symbol for slat or shutter position remains in the display when switching to the input channels

** Improvement
   * Changing driving directions with HmIP UP actuators via parameters.
   * Add CHANNEL_OPERATION_MODE to switch between blind and shutter mode



Version 1.4.0 - 2019-09-24
--------------------------------------------------------------

** New Feature
   * Initial Release



--- END OF FILE ---
