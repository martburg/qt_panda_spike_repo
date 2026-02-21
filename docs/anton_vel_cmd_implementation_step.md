# Anton vel_cmd implementation step

## Purpose
Implement a PLC-faithful DenSi reaction to legacy downlink fields `SpeedSollIN` and `PosSoll`, matching the
legacy Anton PLC semantics for gating, ramping, soft-limit braking, and position-trim overlay.

## Conditions and goals
- DenSi must remain a device-side simulator (Seam E in, Seam D out).
- Behavior must be deterministic: use tick-based staleness, no wall-clock control logic.
- No new seam categories; core remains authoritative.
- Match `legacy_plc_anton.md` wire semantics and field meanings.

## In scope
- Control gating (ownership/intent + enable + lifetick stale + safety ready).
- Speed clamp to `SpeedMaxUI` (`VelMax`).
- Soft-limit braking using sqrt law with `DccMaxUI`.
- Acceleration ramp using `AccTotUI` (`AccMove`) or `AccMaxUI`.
- Position-trim PID overlay using `FilterP/I/D/IL`.
- Guide fields minimal storage/echo (GuidePosIstUI, GuideIstSpeedUI).

## Out of scope
- New kinematics models.
- New core ownership/lease policies.
- Guide mechanics beyond basic storage/echo.

## Deterministic assumptions
- `dt_s` comes from the DenSi timebase and is constant in tests.
- Lifetick staleness uses tick counters, not wall clock.
- Integrators advance only on ticks.

## Mapping: Core CommandFrame -> legacy downlink fields

| Legacy field | Source in modern stack | Notes |
|---|---|---|
| LifetickUIrx | `CommandFrame.lifetick_echo[axis_id]` else `CommandFrame.tick & 0xFFFF` | Echo tick for watchdog |
| Modus | `"w"` if ParamWrite ops present else `"E"` | Write extension when params are sent |
| OwnPID | not in CommandFrame | DenSi sim uses a constant (device-side only) |
| ControlPIDTx | not in CommandFrame | default 0 |
| Intent | `CommandFrame.intent` | ownership/lease gate proxy |
| ControlIN | `AxisSetpoint.enable` | used for enable intent |
| GuideControlUI | not in CommandFrame | stored/echoed (defaults to 0) |
| SpeedSollIN | `AxisSetpoint.vel` | base commanded speed |
| GuideSollSpeedUI | not in CommandFrame | stored/echoed (defaults to 0) |
| PosSoll | `AxisSetpoint.pos` if present else `state.params["PosSoll"]` else current `PosIst` | used by PID trim |
| EStopReset | `CommandFrame.estop_reset` | legacy reset |
| ReSync | `CommandFrame.resync` | legacy resync |
| GUINotHaltIN | `CommandFrame.gui_not_halt` | legacy flag |
| write extension | `CommandFrame.param_ops` -> `state.params` | key map per `protocol/plc_codec.py` |

## Mapping: DenSi telemetry -> legacy uplink fields

DenSi writes to `TelemetrySnapshot` and `state.params`. The PLC wire encoder
(`protocol/plc_wire.py`) maps these to legacy uplink fields. Key params:

- `PosMaxHardUI` <- `state.params["HardMax"]`
- `PosMaxUserUI` <- `state.params["UserMax"]`
- `PosMinUserUI` <- `state.params["UserMin"]`
- `PosMinHardUI` <- `state.params["HardMin"]`
- `SpeedMaxUI`   <- `state.params["VelMax"]`
- `AccMaxUI`     <- `state.params["AccMax"]`
- `DccMaxUI`     <- `state.params["DccMax"]`
- `FilterP/I/D/IL` <- `state.params["P"/"I"/"D"/"IL"]`
- `GuidePosIstUI` <- `state.params["GuidePosIst"]`
- `GuideIstSpeedUI` <- `state.params["GuideIstSpeed"]`
- `AccTotUI`     <- `state.params["AccMove"]`

## How to test without joystick

- Unit tests for motion law and PLC parsing:
  - `pytest -q tests/unit/test_plc_codec_anton.py`
  - `pytest -q tests/unit/test_densi_plc_anton_motion.py`

- Integration-ish tick stepping:
  - `pytest -q tests/integration/test_densi_plc_anton_loop.py`

These tests inject synthetic CommandFrame inputs and step the DenSi engine deterministically.
