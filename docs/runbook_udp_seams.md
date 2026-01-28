# UDP Seams Runbook (Patch2)

This repo currently runs the system as 3 processes connected via UDP:

- **HI-P** (Human Intent Parser): UI → Intents
- **core_udp_service**: CoreEngine + UDP bridge
- **Den-Si** (Device Endpoint Simulator): CommandFrame → simulated plant → Telemetry

## Ports (localhost)

Operator side:
- HI-P → Core (Intents):        `127.0.0.1:51001`  (HI-P sends, core binds)
- Core → HI-P (Telemetry):      `127.0.0.1:51002`  (core sends, HI-P binds)

Device side:
- Core → Den-Si (CommandFrame): `127.0.0.1:52001`  (core sends, Den-Si binds)
- Den-Si → Core (Telemetry):    `127.0.0.1:52002`  (Den-Si sends, core binds)

## Quickstart (3 terminals)

Terminal A (device simulator):
```bash
python -m steuerung3d.apps.den_si --axis X --dt 0.1 --log-level info
Terminal B (core bridge):

bash
Copy code
python -m steuerung3d.apps.core_udp_service --dt 0.1 --log-level info
Terminal C (UI intent parser):

bash
Copy code
python -m steuerung3d.apps.hi_p --log-level info
Use --log-level debug when diagnosing seams.

Expected logs (sanity)
HI-P should log telemetry reception:

rx first telemetry: tick=... estop=... fault=...

core_udp_service should show heartbeat about once per second:

HB t=... intents=... dev_telem=... cmd_out=... ui_telem_out=...

Den-Si should log telemetry TX, and (when core is running) command RX:

rx cmd: tick=... estop=... mode=...

tx telem: tick=... estop=...

Stopping
core_udp_service supports Ctrl+C clean shutdown (KeyboardInterrupt handling).

yaml
Copy code

---

## 2) `docs/logging.md` (update or new)

```md
# Logging Convention

All CLI apps accept:

- `--log-level {debug|info|warning|error}`

and use the same logging format:
`%(asctime)s %(levelname)s %(name)s: %(message)s`

## Debug level expectations

- HI-P:
  - logs `rx telemetry` at DEBUG
  - logs `tx intent` at INFO when sending a user action intent

- Den-Si:
  - logs `rx cmd` at DEBUG
  - logs `tx telem` at DEBUG
  - logs injected diagnostic actions at INFO (e.g. `inject estop=True`)

- core_udp_service:
  - logs `rx dev telem` / `tx cmd frame` / `tx ui telem` at DEBUG
  - logs a once-per-second `HB ...` line at INFO

## Dependencies note
Some apps require:
- `more_itertools`
- `arrow`

Install in the active env if missing.