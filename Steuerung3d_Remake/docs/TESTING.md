# Testing

The project uses `pytest`.

## Run all tests

From the repo root:

```powershell
pytest -q
```

## What is covered (v0.x)

- Core engine stepping and state updates
- Transport behavior and logging wrappers
- TwinCAT legacy codec field mapping (including `EOD` handling)
- TwinCAT legacy UDP devices:
  - lifetick is sent every frame
  - Windows-safe socket behavior (`WinError 10054` treated as dropped packet)

## Writing new tests

A good test in this repo is:

- deterministic (no sleeps if possible)
- minimal (one concern per test)
- asserts behavior at boundaries (codec ↔ device ↔ core)

Examples to follow:

- `test_plc_twincat_legacy_codec.py` – pure parsing/encoding
- `test_plc_twincat_legacy_device_udp.py` – UDP behavior with a small in-test server

## Windows notes

- `curses` is not available by default on Windows.
- UDP may raise `WinError 10054` when the remote port is unreachable.
- UDP bind may raise `WinError 10049` when trying to bind to an IP not configured on this host.
  The dev stack can fall back to loopback PLC simulators in that case.

## Verifying legacy FSM wiring

Use the probe script to confirm the control loop wiring:

```bash
python src/steuerung3d/tools/verify_fsm_wiring.py
Expected output shape:

tick 1: claiming, cmd_enable=False

tick 2: ready, cmd_enable=True

tick 3: enabling, telemetry reflects enabled feedback

tick 4+: active

This script is a deterministic "fake device" loop that proves:
engine -> drive_legacy_axis_fsms -> build_command_frame -> device_step -> telemetry -> (next tick FSM)

yaml
Copy code
