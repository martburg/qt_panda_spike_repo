# Manual testing runbook

This runbook complements the automated pytest suite with a **repeatable, observable** manual routine.

## Preflight (always)

From repo root (env active):

```powershell
pytest -q
```

Optional: clear previous logs

```powershell
if (Test-Path .\logs) { Remove-Item .\logs\* -Force }
```

Optional: clear previous supervisor run sessions

```powershell
if (Test-Path .\.run) { Remove-Item .\.run\* -Recurse -Force }
```

## Environment sanity (Windows)

The apps are meant to be imported as `steuerung3d.*` (not `src.steuerung3d.*`).

From repo root, do an editable install once per environment:

```powershell
python -m pip install -e .
```

Quick check:

```powershell
python -c "import importlib.util as u; print(u.find_spec('steuerung3d'))"
```

## Test 0 — Profile-driven boot (recommended)

Preflight the profile (no processes started):

```powershell
python -m steuerung3d plan   --profile dev_sim
python -m steuerung3d doctor --profile dev_sim
```

Start the stack:

```powershell
python -m steuerung3d up --profile dev_sim
```

What to look for:
- birds-eye prints structured lines for core / inputd / joy2intent / hip / densi
- session logs created under `.run/dev_sim/sessions/<timestamp>/`

Crash behavior:
- kill one child -> supervisor prints a short log tail and shuts down cleanly

Post-mortem helpers (new terminal):

```powershell
python -m steuerung3d status --profile dev_sim
python -m steuerung3d logs core --profile dev_sim --follow
python -m steuerung3d down --profile dev_sim
```

## Test A — Core + SIM via CLI client (fast sanity)

Run:

```powershell
python -m steuerung3d.apps.cli_client
```

Suggested interaction:

```
show
enable X on
jog X 0.6
show
estop on
show
estop off
clearfault
quit
```

What to look for:
- after `enable` + `jog`, X telemetry should show motion (when core_mode is LIVE)
- after `estop on`, commanded motion stops and state reflects ESTOP
- select gating: motion requires select_hip in the core joystick state

## Test B — Dev stack end-to-end + JSONL log

Run:

```powershell
python -m steuerung3d.apps.dev_stack --config configs\dev_plc.toml
```

What to look for:
- periodic status lines (tick/t/core_mode/estop)
- if not on the PLC network, a message about **UDP SIM fallback** is expected

Then inspect the run:

```powershell
python -m steuerung3d.apps.log_viewer .\logs\session.jsonl --show-intents
```

## Test C — Yellow UDP seam: HiP ↔ Core ↔ DenSi (3 processes)

### Open 3 terminals in the repo root

**Windows Terminal**
- Open in repo folder (Explorer address bar → type `wt` → Enter)
- Split panes: `Alt+Shift+D` twice (3 panes)
- In each pane:

```powershell
conda activate steuerung3d
cd C:\Users\Martin\Documents\Steuerung3d_Remake\dev
```

(Or use your venv activation instead of conda.)

### Start the three processes

Pane 1 (Core UDP service):

```powershell
python -m steuerung3d.apps.core_udp_service --dt 0.1 --log-level debug
```

Pane 2 (DenSi):

```powershell
python -m steuerung3d.apps.den_si
```

Pane 3 (HiP):

```powershell
python -m steuerung3d.apps.hi_p
```

### What to try in HiP

**C1 — Edit / Cancel**
- Press **Pos Edit** (fields unlock; other edits/tabs lock = modal edit)
- Change a value
- Press **Pos Cancel** (revert and exit edit mode)

**C2 — Edit / Write**
- Press **Pos Edit**, change values, press **Pos Write**
- Expect: HiP waits for confirmation (by observing DenSi telemetry) and shows an “applied” dialog

**C3 — Constraints**
- Enter invalid limit combinations
- Expect: HiP auto-adjusts to satisfy:
  - `HardMax ≥ UserMax ≥ UserMin ≥ HardMin`
  - Guider clamps to ensure `PosMin ≤ PosMax`
- HiP shows an info dialog listing corrections before sending

## Test D — PLC legacy fleet wiring (real vs UDP SIM fallback)

Run the dev stack with `device.kind = "plc_twincat_legacy_fleet"`.

- Off-network: it should automatically use loopback UDP PLC simulators.
- On-network: it should bind to the configured `controller_ip` and use the real adapter.

## Test F — Joy deadman -> DenSi vel_cmd (SIM)

Run profile:

```powershell
python -m steuerung3d up --profile 1dev_sim
```

Steps:
- Enable deadman.
- Move joystick to command motion.
- Verify DenSi cmd velocity changes (Wireshark or telemetry log).
- Release deadman -> velocity returns to 0.

## Test G — HiP joystick scaling + deadman gate (SIM)

Run profile:

```powershell
python -m steuerung3d up --profile 1dev_sim
```

Steps:
- Move joystick and confirm the HiP UI shows the motion input changing.
- Hold deadman and move joystick: DenSi cmd velocity should be non-zero.
- Release deadman: DenSi cmd velocity returns to 0 and axis disables.
- Full deflection should yield approximately $\pm VelMax$ (from HiP params/telemetry).

## Regression guard added (why Test C won’t silently break again)

`udp_channels.py` imports helpers from `protocol.codec`. A refactor can accidentally remove them and only break the apps at runtime.

We keep a small pytest tripwire:

- `tests/test_protocol_imports.py` imports `udp_channels` and round-trips `RawControls`.

---

## Test E — Profile-driven boot + birds-eye status (recommended path)

This validates the **current supervisor** (sessions, structured status, metadata helpers).

### E1 — Plan/doctor

```powershell
python -m steuerung3d plan   --profile dev_sim
python -m steuerung3d doctor --profile dev_sim
```

What to look for:
- argv and port expansions make sense per axis
- doctor reports OK and no port collisions

### E2 — Up/run

```powershell
python -m steuerung3d up --profile dev_sim
```

What to look for:
- birds-eye prints structured lines for core / inputd / joy2intent / hip / densi
- a new session directory exists under `.run/dev_sim/sessions/<timestamp>/`

### E3 — Crash path

- kill one child (Task Manager on Windows is fine)
- expect: supervisor prints a short tail of the child log, then shuts down cleanly

### E4 — Post-mortem helpers

```powershell
python -m steuerung3d status --profile dev_sim
python -m steuerung3d logs core --profile dev_sim --follow
python -m steuerung3d down   --profile dev_sim
```
