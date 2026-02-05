# Boot + structured birds-eye status (current state)

This document describes the current **profile-driven boot system** and the **structured birds-eye status** channel.

Goals:
- Start a stack with one command.
- Keep logs per run, per process.
- Make a compact, structured “is it alive / stale / faulted” view the default.

---

## Unified boot entry point

Start a stack from the repo root:

```powershell
python -m steuerung3d up --profile <profile>
```

Companion tools:

```powershell
python -m steuerung3d plan   --profile <profile>
python -m steuerung3d doctor --profile <profile>
python -m steuerung3d status --profile <profile>
python -m steuerung3d logs <service> --profile <profile> --follow
python -m steuerung3d down   --profile <profile>
```

`setup_stack` still exists, but it is now a **thin wrapper** over the same runtime (so we only maintain one supervisor implementation).

---

## Session logging (per run, per process)

Each `up` run creates its own session directory:

```
.run/<stack>/sessions/<timestamp>/
  meta.json
  core.log
  densi-Anton.log
  hip-Anton.log
  inputd.log
  joy2intent.log
  ...
```

Behavior:
- One logfile per process (stdout/stderr combined).
- Keep last **N** sessions (default: 5); older sessions are deleted.
- `.run/<stack>/LATEST` points to the newest session (portable, no symlink).

---

## Structured birds-eye status (UDP JSON heartbeat)

We added a side-channel heartbeat mechanism that **does not touch PLC UDP packet formats**.

### Supervisor side

- The supervisor binds `net.status_in` (example: `127.0.0.1:51200`).
- The supervisor injects these env vars into each child process:
  - `ST3D_STATUS_OUT`
  - `ST3D_STACK_NAME`
  - `ST3D_SERVICE_NAME`
  - `ST3D_INSTANCE`

### Service side

Services emit JSON heartbeats via:

- `StatusEmitter.from_env()` (see `src/steuerung3d/core/status.py`)

Current emitters:
- `core_udp_service` (derived ages/mode/estop/fault)
- `joy2intent` (mode, age_ms, stale_stop, winches, endpoints)
- `inputd` (connected flag, out addr, tx count)
- `HiP controller` (axis, mode, age/stale, estop/fault)
- `DenSi controller` (axis, mode, online, tick, age/stale, estop/fault)

When status is enabled, the supervisor prints a compact birds-eye view based on structured status. If a child dies, it still falls back to a short log tail so you immediately see the crash context.

---

## Config notes

Profiles live in `configs/stacks/*.toml`.

- Profiles own the **rig axes + wiring**.
- The `dev_sim` profile includes the status channel:

```toml
[net]
status_in = "127.0.0.1:51200"
```

Joy2intent config is now bindings-only (axes live in the stack profile):
- `configs/joy2intent_bindings_gamepad.toml`

---

## SIM vs REAL boot: device provisioning

We support two boot semantics via `[rig].device_source`.

### SIM (`device_source = "sim"`)

- The profile provides `[rig].axes = [...]`.
- The supervisor spawns one DenSi simulator per axis.
- HiP can be provisioned as a *pool* by setting:

```toml
[services.hip]
count = "auto"  # one HiP window per configured axis
```

By default the HiP windows start **unattached**; the operator picks which device each HiP controls.

### REAL (`device_source = "real"`)

- PLCs/DenSis are already running and emitting telemetry.
- The supervisor starts core + tooling first.
- It listens for core status heartbeats for `[rig].discovery_ms` and reads discovered `devices` from core.
- Then it starts a HiP pool sized to the discovered devices (`count = "auto"`, min 1).
- DenSi sims are suppressed automatically in REAL mode.

See example profile: `configs/stacks/dev_real.toml`.

---

## Tests

`pytest -q` is green (last seen: 71 passed, 1 skipped).

Regression tests cover stack expansion + wrapper behavior. The status module is currently exercised by integration runs (unit tests can be added later if needed).

---

## Validation checklist (next step)

### Plan/doctor

- `python -m steuerung3d plan --profile dev_sim` shows correct argv/ports per axis
- `python -m steuerung3d doctor --profile dev_sim` passes

### Up/run

- `python -m steuerung3d up --profile dev_sim`
  - birds-eye prints structured lines for: core / inputd / joy2intent / hip / densi
  - session logs created under `.run/.../sessions/...`

### Crash path

- Kill one child process
  - supervisor prints last ~40 log lines
  - supervisor shuts down cleanly

### Post-mortem helpers

- `python -m steuerung3d status --profile dev_sim` works against latest session metadata
- `python -m steuerung3d logs core --profile dev_sim --follow` works
- `python -m steuerung3d down --profile dev_sim` terminates latest session processes
