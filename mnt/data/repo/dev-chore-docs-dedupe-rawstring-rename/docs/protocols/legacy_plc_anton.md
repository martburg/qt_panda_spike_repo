# Legacy PLC UDP Protocol — Anton

Shared guarantees: `legacy_plc_common.md` (172.16.17.2)

Canonical source: Beckhoff ST program `KommAnton__MAIN.st`.

Endpoints (as coded in the PLC):

- PLC bind: `172.16.17.2:15001`
- Controller bind (receiver of PLC status): `172.16.17.5:15002`

Payload is **ASCII** text with `;` as delimiter.

## Framing rules

- Delimiter: `;`
- Frames typically end with a trailing `;` (so `.split(';')` yields an empty last token).
- Decimal separator: `.`
- Boolean intent is transported as the string **`"True"`** / **`"False"`**.
- Parsing is **order-sensitive**: the PLC peels fields sequentially using `FIND`, `LEFT`, `RIGHT`.

---

## Downlink (Controller → PLC)

Source: `KommAnton__MAIN.st` parsing of `DownMessage1`.

### Base downlink fields (always required)

| # | Field | PLC type | Example | Notes |
|---:|---|---|---|---|
| 0 | `LifetickUIrx` | `WORD` | `1234` | Watchdog tick value. |
| 1 | `Modus` | `STRING` | `E` / `w` / `xx` | `w` enables write-parameters extension. |
| 2 | `OwnPID` | `STRING` | `4711` | Sender identity (legacy “owner”). |
| 3 | `ControlPIDTx` | `UINT` | `0` | Parsed legacy field. |
| 4 | `Intent` | `STRING` | `True` | If `Intent == 'True'` PLC sets `ControlPID := OwnPID`. |
| 5 | `ControlIN` | `UINT` | `0` | Legacy control word. |
| 6 | `GuideControlUI` | `UINT` | `0` | Copied into `GuideControl`. |
| 7 | `SpeedSollIN` | `REAL` | `1.25000` | Commanded speed. |
| 8 | `GuideSollSpeedUI` | `REAL` | `0.00000` | Commanded guide speed. |
| 9 | `PosSoll` | `REAL` | `12.34000` | Commanded position. |
| 10 | `EStopReset` | `DWORD` | `0` | Reset request / bitfield. |
| 11 | `ReSync` | `REAL` | `0` / `1` | Resync request. |
| 12 | `GUINotHaltIN` | `INT` | `0` / `1` | GUI “Not-Halt” input. |

**Minimum tokens**: 13

### Write-parameters extension (`Modus == 'w'`)

When `Modus == 'w'`, the controller must append the following fields in-order:

| # | Field | PLC type | Example |
|---:|---|---|---|
| 13 | `AccIN` | `REAL` | `5` |
| 14 | `DccIN` | `REAL` | `4` |
| 15 | `PosMaxHardUI` | `REAL` | `300.0` |
| 16 | `PosMaxUserUI` | `REAL` | `300.0` |
| 17 | `PosMinUserUI` | `REAL` | `0.0` |
| 18 | `PosMinHardUI` | `REAL` | `0.0` |
| 19 | `SpeedMaxUI` | `REAL` | `2.5` |
| 20 | `AccMaxUI` | `REAL` | `5` |
| 21 | `DccMaxUI` | `REAL` | `5` |
| 22 | `AmpMaxUI` | `REAL` | `100` |
| 23 | `FilterP` | `REAL` | `1.0` |
| 24 | `FilterI` | `REAL` | `0.0` |
| 25 | `FilterD` | `REAL` | `0.0` |
| 26 | `FilterIL` | `REAL` | `1.0` |
| 27 | `GuidePitchUI` | `REAL` | `-6.3` |
| 28 | `GuidePosMaxUI` | `REAL` | `0.096` |
| 29 | `GuidePosMinUI` | `REAL` | `0.000` |
| 30 | `VelOrPos` | `STRING` | `VEL` / `POS` |
| 31 | `PosWinUI` | `REAL` | `0.5` |
| 32 | `VelWinUI` | `REAL` | `0.5` |
| 33 | `AccTotUI` | `REAL` | `5.0` |

**Total tokens when `Modus == 'w'`**: 34

### Example downlink (base)

1234;E;4711;0;True;0;0;1.25000;0.00000;12.34000;0;0;0;

### Example downlink (`Modus == 'w'`)

1234;w;4711;0;True;0;0;1.25000;0.00000;12.34000;0;0;0;5;4;300;300;0;0;2.5;5;5;100;1;0;0;1;-6.3;0.096;0;VEL;0.5;0.5;5;

## Uplink (PLC → Controller)

Source: `KommAnton__MAIN.st` construction of `UpMessage` plus appended tail fields.

### `EOD` marker

The ST literal is `EOD\`, but the PLC copies bytes only until it hits the backslash (`\` = ASCII 92),
so the transmitted marker token is effectively **`EOD`**.

### Base uplink fields (0–37)

| # | Field | PLC type / formatting | Example |
|---:|---|---|---|
| 0 | `OwnPID` | `STRING` | `4711` |
| 1 | `LifetickUItx` | `REAL_TO_STRING(UINT)` | `1235` |
| 2 | `Status` | `WORD_TO_STRING` | `0` |
| 3 | `GuideStatus` | `WORD_TO_STRING` | `0` |
| 4 | `PosIst` | `LREAL_TO_FMTSTR(...,5)` | `12.34000` |
| 5 | `SpeedIstUI` | `LREAL_TO_FMTSTR(...,5)` | `1.25000` |
| 6 | `MasterMomentUI` | `LREAL_TO_FMTSTR(...,5)` | `0.00000` |
| 7 | `CabTemperatureUI` | `LREAL_TO_FMTSTR(...,1)` | `34.2` |
| 8 | `Name` | `STRING` | `Anton` |
| 9 | `GearToUI` | `LREAL_TO_FMTSTR(...,3)` | `1.000` |
| 10 | `PosMaxHardUI` | `...,(3)` | `300.000` |
| 11 | `PosMaxUserUI` | `...,(3)` | `300.000` |
| 12 | `PosMinUserUI` | `...,(3)` | `0.000` |
| 13 | `PosMinHardUI` | `...,(3)` | `0.000` |
| 14 | `SpeedMaxUI` | `...,(2)` | `2.50` |
| 15 | `AccMaxUI` | `...,(2)` | `5.00` |
| 16 | `DccMaxUI` | `...,(2)` | `5.00` |
| 17 | `AmpMaxUI` | `...,(2)` | `100.00` |
| 18 | `FilterP` | `...,(6)` | `1.000000` |
| 19 | `FilterI` | `...,(6)` | `0.000000` |
| 20 | `FilterD` | `...,(6)` | `0.000000` |
| 21 | `FilterIL` | `...,(6)` | `1.000000` |
| 22 | `RopeSWLL` | `...,(1)` | `2000.0` |
| 23 | `RopeDiameter` | `...,(1)` | `6.0` |
| 24 | `RopeType` | `STRING` | `d` |
| 25 | `RopeNumber` | `STRING` | `d` |
| 26 | `RopeLength` | `...,(2)` | `300.00` |
| 27 | `GuidePitchUI` | `...,(1)` | `-6.3` |
| 28 | `GuidePosMaxUI` | `...,(4)` | `0.0960` |
| 29 | `GuidePosMinUI` | `...,(4)` | `0.0000` |
| 30 | `GuidePosIstUI` | `...,(4)` | `0.0123` |
| 31 | `GuideIstSpeedUI` | `...,(2)` | `0.00` |
| 32 | `MotAuslastUI` | `...,(1)` | `12.3` |
| 33 | `ActCurUI` | `...,(1)` | `4.2` |
| 34 | `SpeedMaxforUI` | `...,(2)` | `2.50` |
| 35 | `PosDiffForUI` | `...,(5)` | `0.00000` |
| 36 | `RampenformUI` | `DWORD_TO_STRING` | `8` |
| 37 | `EStopStatus` | `DWORD_TO_STRING` | `0` |

### Tail fields appended after `EOD`

| Tail # | Field | PLC formatting | Example | Notes |
|---:|---|---|---|---|
| 0 | `SystemTime` | `SYSTEMTIME_TO_STRING` prefixed with `N_` / `L_` | `N_2026-01-12-09:20:31.123` | `N_` = SafetyPLC time valid, `L_` = local time. |
| 1 | `sCutPos` | `LREAL_TO_FMTSTR(...,5)` | `12.34000` | Only updated when not E-stopped; otherwise repeats old value. |
| 2 | `sCutVel` | `LREAL_TO_FMTSTR(...,5)` | `1.25000` | Same. |
| 3 | `PosWinUI` | `LREAL_TO_FMTSTR(...,5)` | `0.50000` | |
| 4 | `VelWinUI` | `LREAL_TO_FMTSTR(...,5)` | `0.50000` | |
| 5 | `AccTotUI` | `LREAL_TO_FMTSTR(...,3)` | `5.000` | |
| 6 | `GuidePosManualMaxUI` | `LREAL_TO_FMTSTR(...,3)` | `0.096` | |

### Example uplink (structure)

<0..37 base fields>;EOD;<system_time>;<cut_pos>;<cut_vel>;<pos_win>;<vel_win>;<acc_tot>;<guide_pos_manual_max>;

