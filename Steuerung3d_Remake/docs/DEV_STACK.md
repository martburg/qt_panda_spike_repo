# Dev stack

`python -m steuerung3d.apps.dev_stack --config <file.toml>` runs a small end-to-end demo.

What it does:

- runs `CoreEngine` in a real-time loop (`CoreRunner`)
- drains intents from a transport, applies them to `MachineState`
- calls the configured device adapter (`device.step(...)`) every frame
- publishes telemetry snapshots back to the transport
- prints snapshots periodically and toggles ESTOP once during the run

## Run it

Run from the **repo root**:

```powershell
python -m steuerung3d.apps.dev_stack --config config\dev_plc.toml
```

If you run from `src/` you must adjust the path:

```powershell
python -m steuerung3d.apps.dev_stack --config ..\config\dev_plc.toml
```

## Device selection

The device adapter is selected by `device.kind` in TOML:

- `sim` (default): local plant simulation
- `udp_plc_toy`: early semicolon UDP adapter (`adapters/plc/udp_device.py`)
- `plc_twincat_legacy_fleet`: legacy TwinCAT UDP adapter (Anton/Burt/Cecil/Debby…)

See `docs/CONFIG_TOML.md` for the schema and examples.

## UDP SIM fallback (off-network development)

When `device.kind = "plc_twincat_legacy_fleet"`, the dev stack checks whether it can bind to
`controller_ip` (e.g. `172.16.17.5`).

- If the IP exists on the current machine, it uses the real legacy device fleet.
- If the IP is *not* present (common on a laptop/off the PLC network), it automatically starts
  loopback “PLC simulators” and talks to those instead.

This allows you to test:

- lifetick per frame
- encoding/decoding
- device/fleet wiring
- telemetry integration

…without requiring real PLCs.

## Output

The demo prints one line every ~0.5 seconds at 100 Hz, for all configured axes, e.g.:

```
[dev_stack] controller_ip=172.16.17.5 not present on this host -> using UDP SIM fallback for plc_twincat_legacy_fleet
tick=   50 t=  0.50s mode=LIVE estop=False Anton(...) Burt(...) Cecil(...) Debby(...)
```

Logs are written to `logs/session.jsonl` (JSON Lines) via the recorder.

## Notes

- Windows does not ship `curses` by default; the dev stack is plain stdout for portability.
- UDP on Windows may raise `WinError 10054` (ICMP Port Unreachable mapped to a socket error). The UDP
  device adapters treat this like a dropped packet (best effort receive).

