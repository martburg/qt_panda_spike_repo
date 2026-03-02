# Steuerung3D Remake (v0.x)

A small, test-driven “walking skeleton” for the Steuerung3D control stack.

The repo intentionally starts simple:

- **Core**: deterministic tick loop (`Timebase`), single source of truth (`MachineState`), intent handling, snapshot publishing.
- **Protocol**: in-memory transport + optional JSONL recording/replay.
- **Devices**:
  - `sim`: a minimal plant + device adapter for local development.
  - `plc (toy)`: a tiny semicolon-separated UDP device adapter (`UdpPlcDevice`) used as an early boundary.
  - `plc_twincat_legacy`: TwinCAT/Beckhoff legacy UDP protocol adapter (Anton/Burt/Cecil/Debby …) with **fleet** support.

If you only read one doc, start here:

- `docs/DEV_STACK.md` – how to run the demo app (SIM, legacy PLC, and UDP-sim fallback)
- `docs/PLC_TWINCAT_LEGACY.md` – protocol notes + field mapping + design constraints

---

## Quick start

### Create an environment

**Windows (venv)**

```powershell
cd <repo-root>
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -e .
pip install pytest
```

**Conda**

```powershell
conda create -n steuerung3d python=3.11 -y
conda activate steuerung3d
pip install -e .
pip install pytest
```

### Run tests

```powershell
pytest -q
```

Recommended local gate (lint + format + optional typecheck + tests):

```powershell
python tools/check.py
```

Manual runbook:

- `docs/MANUAL_TESTING.md` (recommended after `pytest -q` stays green)

---

## Boot a stack (profile-driven)

The current recommended entry point is the **profile-driven supervisor**:

```powershell
python -m steuerung3d up --profile dev_sim
```

Companion tools:

```powershell
python -m steuerung3d plan   --profile dev_sim
python -m steuerung3d doctor --profile dev_sim
python -m steuerung3d status --profile dev_sim
python -m steuerung3d logs core --profile dev_sim --follow
python -m steuerung3d down   --profile dev_sim
```

Profiles live in `configs/profiles/*.toml` and own the **rig axes + wiring** (ports, services enabled, per-axis expansion).

Legacy note: `configs/stacks/` remains as a compatibility mirror for older docs/scripts; edit `configs/profiles/` as the source of truth.

### Session logging (per run, per process)

Each `up` creates a fresh session directory:

```
.run/<stack>/sessions/<timestamp>/
  core.log
  densi-Anton.log
  hip-Debby.log
  ...
  meta.json
```

- keeps the last **5** sessions by default (older sessions are deleted)
- `.run/<stack>/LATEST` points to the newest session (portable, no symlink)

### Structured birds-eye status

Stacks can enable a UDP JSON heartbeat side-channel (does **not** touch PLC UDP formats).
When enabled, the supervisor prints a compact “birds-eye” table and can still fall back to a log tail on crash.

See: `docs/STACK_BOOT_STATUS.md`

### Run the HiP ↔ Core ↔ DenSi UDP demo (Yellow UI)

Open three terminals:

**Windows Terminal tip:** open in repo folder (`wt`), then split panes (`Alt+Shift+D`) to get 3 terminals in the right folder.

```powershell
python -m steuerung3d.apps.core_udp_service --dt 0.1
```

```powershell
python -m steuerung3d.apps.den_si
```

```powershell
python -m steuerung3d.apps.hi_p
```

This demo exercises the intent/telemetry seam over UDP and supports axis-agnostic parameter editing
(Edit → Write → Cancel) from HiP.

Notes:

- Editing is **modal** in HiP: once you press Edit for a group, other Edit buttons and tab switching are disabled until Write/Cancel.
- HiP↔Core delivery is guarded with `req_id` acks; device-side acceptance is confirmed by observing DenSi’s reported `params` in telemetry.
- After Write, HiP shows a **modal dialog** once the device is observed as applied (or after a timeout if not confirmed).
- If **pos limits** are auto-adjusted to satisfy `HardMax ≥ UserMax ≥ UserMin ≥ HardMin`, HiP shows an info dialog listing the adjusted values.
- For **Guider** limits, `PosMin` is **clamped** to ensure `PosMin ≤ PosMax` (no swapping).

> Note: the above “3 terminals” demo still works, but most local development is now done via
> `python -m steuerung3d up --profile ...`.

### Run the dev stack

From the **repo root**:

```powershell
python -m steuerung3d.apps.dev_stack --config configs\dev_plc.toml
```

- If the configured `controller_ip` (e.g. `172.16.17.5`) is **not present** on this host, the dev stack automatically falls back to **loopback UDP PLC simulators** and still exercises the real legacy codec/device.

---

## Repo map

- `src/steuerung3d/core/…` – tick loop, state, intents, engine.
- `src/steuerung3d/protocol/…` – runner thread, transport, JSONL logging.
- `src/steuerung3d/adapters/sim/…` – local simulation.
- `src/steuerung3d/adapters/plc/udp_device.py` – early “toy” UDP boundary.
- `src/steuerung3d/adapters/plc_twincat_legacy/…` – **real legacy TwinCAT UDP** (fleet + config + UDP simulators).

---

## Status

This is a foundation for incremental expansion:

- ✅ deterministic core tick & snapshots
- ✅ in-memory transport + JSONL recorder
- ✅ command vs measured separation in `MachineState`
- ✅ TwinCAT legacy UDP codec/device/fleet + Windows-safe UDP behavior
- ✅ config-driven selection in `apps/dev_stack`
- ✅ profile-driven boot supervisor + per-session logs + structured birds-eye status

Next milestones typically include:

- real PLC endpoint construction + integration tests
- richer axis commands (position setpoints, limits, fault handling)
- CLI log viewer / regression guards

