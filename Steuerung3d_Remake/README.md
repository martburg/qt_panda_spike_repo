# Steuerung3D Remake (v0.1 walking skeleton)

This repository is a **minimal but structurally correct** foundation for the Steuerung3D remake.

The goal of v0.1 is not feature completeness — it is to lock in the **right seams** early so we don’t pay refactor-tax later.

Key choices in this skeleton:

- **Deterministic fixed-timestep core** (`CoreEngine`) driven by `Timebase(dt_s=...)`.
- A strict split between **commanded** state (what we want the machine/device to do) and **measured** state (what the device reports back).
- A device boundary expressed as a per-tick **`CommandFrame` → `device_step(...)`** seam.
- A transport boundary expressed as a **`Transport` interface** (in-mem today, UDP/WebSocket later).
- JSONL **record/replay hooks** to make debugging deterministic and shareable.

---

## Quick start

### Requirements

- Python **3.11+**

### Install options

**Option A — Editable install (recommended for day-to-day dev)**

```bash
python -m pip install -e .
```

This makes `import steuerung3d` resolve to your working tree (no copying), so edits take effect immediately.

**Option B — No install (quick try-out)**

```bash
PYTHONPATH=src python -m steuerung3d.apps.cli_client
```

### Run the CLI client (Bone “CLI”)

```bash
python -m steuerung3d.apps.cli_client
```

Try:

```
live
enable X on
jog X 0.5
estop on
estop off
idle
quit
```

### Run tests

```bash
pytest -q
```

---

## Mental model

There are three kinds of messages in this system:

### 1) Intents (client → core)
High-level requests: “enable axis X”, “jog X at 0.5”, “set e-stop”.

- Represented by dataclasses in `core/intents.py`
- Applied to state by `core/intent_handler.py`
- Typically sparse, event-driven, and not guaranteed to be “every tick”.

### 2) CommandFrame (core → device)
Per-tick *complete* setpoints for the device layer.

- Built by `core/executor.py` from `state.axis_cmd`
- Consumed by `device_step(state, cmd_frame, dt)` (sim adapter now; real fieldbus adapter later)
- This is the “hard seam” that prevents architecture drift.

### 3) TelemetrySnapshot (core → client)
A read-only snapshot of what the machine *currently is doing*.

- Built by `core/telemetry.py` from **measured** `state.axes`
- Published through `Transport` to clients/UIs
- Recorded to JSONL for replay/debugging.

---

## Tick lifecycle (what happens in `CoreEngine.step_once()`)

Each tick is executed in a fixed order:

1. **Drain intents** from `Transport` (or bus) and apply them to `MachineState`.
2. Enforce **mode/safety invariants** (ESTOP/FAULT/IDLE clamp rules).
3. Advance deterministic time: `tick += 1`, `t_s = tick * dt`.
4. Build a **CommandFrame** from `axis_cmd` and call **`device_step(...)`**.
5. Emit a **TelemetrySnapshot** derived from measured state.

This strict order is what makes record/replay and testing reliable.

---

## Layering / architecture

Think of the repository in 4 layers:

```
apps/                Human-facing entry points (CLI, dev stack, replay)
protocol/            Transport, runner thread, codec, record/replay utilities
core/                Deterministic logic: state, intents, mode clamp, command frame
adapters/            Device/IO boundary: sim today, real PLC/fieldbus later
```

Data flows “down” and “up” like this:

```
   (user / UI / joystick)
            |
         Intent
            v
+------------------------+
|        CORE            |
|  MachineState          |
|  mode/safety clamps    |
|  builds CommandFrame   |
+------------------------+
            |
       CommandFrame
            v
+------------------------+
|      DEVICE ADAPTER    |  (SimAxisPlant now; EtherCAT/PLC later)
|  updates measured state|
+------------------------+
            |
     TelemetrySnapshot
            v
   (UI / logger / replay)
```

---

## Commanded vs Measured split (the seam)

`MachineState` holds both:

- `state.axis_cmd[axis_id]` → **commanded**: what the core wants
- `state.axes[axis_id]` → **measured**: what the device reports

This prevents subtle bugs where “we think we’re enabled” because we set a flag, but the device never actually enabled (or faulted). In v0.1 the sim device updates measured state; later the real adapter will.

---

## Record / replay

### Recording

`LoggedTransport` wraps any `Transport` and writes JSONL records:

- `kind="intent"`: every intent published by a client
- `kind="telemetry"`: every telemetry snapshot published by core

File format is line-oriented JSON with schema `steuerung3d.log/v1`.

### Replay

The replay app (`apps/replay_player`) loads a JSONL log, injects intents at their recorded ticks, runs a new core instance, and compares telemetry snapshots for mismatches.

This is the foundation for “share a log and reproduce my bug”.

---

## File-by-file guide

Below is the purpose of each file currently in the repo.

### Repository root

- `pyproject.toml`  
  Project metadata and packaging. Uses a `src/` layout and setuptools. Also configures pytest `testpaths`.

- `conftest.py`  
  Pytest helper: adds `./src` to `sys.path` so you can run tests without `pip install -e .`.

- `.gitignore`  
  Standard ignores; adjust as log/artifact folders grow.

- `.pytest_cache/*`  
  Pytest internal cache (not part of the system design).

### `src/steuerung3d/`

- `__init__.py`  
  Marks `steuerung3d` as a package (v0.1: no public API exported yet).

#### `src/steuerung3d/common/`

- `common/__init__.py`  
  Package marker.

- `common/timebase.py`  
  Defines `Timebase(dt_s)` used by the core for deterministic tick timing and diagnostic timestamps.

#### `src/steuerung3d/core/` (the deterministic heart)

- `core/__init__.py`  
  Package marker.

- `core/state.py`  
  Defines the **single source of truth**:
  - `MachineState` (tick, time, mode, estop/fault flags)
  - `AxisState` (measured)
  - `AxisCommandState` (commanded)

- `core/mode.py`  
  `Mode` enum: `ESTOP`, `FAULT`, `IDLE`, `LIVE`.

- `core/state_machine.py`  
  Mode normalization + per-mode clamping rules:
  - `ESTOP` disables and zeroes commands
  - `FAULT` clamps motion
  - `IDLE` clamps motion
  - `LIVE` allows control

- `core/intents.py`  
  Intent dataclasses (the control vocabulary). Designed to be easy to encode/decode and match on.

- `core/intent_handler.py`  
  `apply_intent(state, intent)` — policy layer that applies intents into `MachineState`.  
  v0.1 policy: only `LIVE` accepts motion intents; safety/mode intents always apply.

- `core/command_frame.py`  
  Defines:
  - `AxisSetpoint` (per-axis desired enable/velocity)
  - `CommandFrame` (per-tick device payload)

- `core/executor.py`  
  `build_command_frame(state)` — converts commanded state into a `CommandFrame`.  
  This is the canonical “core → device” seam.

- `core/engine.py`  
  `CoreEngine` — runs the tick lifecycle:
  drain intents → enforce mode actions → time forward → build command frame → device_step → snapshot.

- `core/telemetry.py`  
  `TelemetrySnapshot` and `AxisTelemetry` — immutable “view” objects produced from measured state.

- `core/commands.py` *(legacy / placeholder)*  
  Earlier “command” dataclasses (pre-CommandFrame seam). Kept as a placeholder for future expansions or removal once vocabulary is finalized.

- `core/inmem_bus.py` *(legacy / non-threadsafe)*  
  Deque-based bus for intents/telemetry. Useful for single-thread demos but **not thread-safe**.  
  For threaded apps prefer `protocol/transport.py` (`InMemTransport`).

#### `src/steuerung3d/protocol/` (how components talk)

- `protocol/__init__.py`  
  Package marker.

- `protocol/transport.py`  
  Defines:
  - `Transport` Protocol (publish/drain intents and telemetry)
  - `InMemTransport` thread-safe Queue-based implementation  
  Seam for UDP/WebSocket/ZMQ transports later.

- `protocol/core_runner.py`  
  `CoreRunner` — runs a `CoreEngine` in a background thread with optional real-time pacing to match `dt_s`.

- `protocol/codec.py`  
  JSON-friendly encoding/decoding for:
  - `Intent` (type-discriminated)
  - `TelemetrySnapshot`  
  Used by logging and future network transports.

- `protocol/recording.py`  
  JSONL logging utilities:
  - `JsonlRecorder` (write intent/telemetry records)
  - `JsonlReader` (iterate and decode records)
  - `LoggedTransport` (wrap a Transport and auto-log)

- `protocol/inmem_bus.py` *(legacy / duplicate)*  
  Same idea as `core/inmem_bus.py` (deque-based). Kept for backwards compatibility with older demos; direction is to converge on `InMemTransport`.

#### `src/steuerung3d/adapters/` (device boundary)

- `adapters/__init__.py`  
  Package marker.

##### `src/steuerung3d/adapters/sim/`

- `adapters/sim/__init__.py`  
  Package marker.

- `adapters/sim/axis_plant.py`  
  `SimAxisPlant` — simple simulation that:
  - consumes `CommandFrame` setpoints
  - updates **measured** `AxisState` (pos/vel/enabled)  
  Includes max-vel and max-acc limiting.

- `adapters/sim/device.py`  
  `SimDevice` — thin wrapper that exposes `step(state, cmd, dt)` matching `CoreEngine.device_step`.

#### `src/steuerung3d/apps/` (entry points)

- `apps/__init__.py`  
  Package marker.

##### `apps/cli_client/`

- `apps/cli_client/__init__.py`  
  Package marker.

- `apps/cli_client/__main__.py`  
  Interactive CLI:
  - starts core in a background thread (`CoreRunner`)
  - reads commands from stdin and publishes intents
  - prints periodic telemetry

##### `apps/dev_stack/`

- `apps/dev_stack/__init__.py`  
  Package marker.

- `apps/dev_stack/__main__.py`  
  Local dev stack:
  - core + sim device + in-mem transport
  - logs everything to `logs/session.jsonl` via `LoggedTransport`
  - prints telemetry and triggers a demo e-stop  
  (Convenient smoke-test and log generator.)

##### `apps/replay_player/`

- `apps/replay_player/__init__.py`  
  Package marker.

- `apps/replay_player/__main__.py`  
  Replay tool:
  - loads a JSONL session log
  - injects intents at recorded ticks
  - runs a fresh core and compares telemetry against recorded reference

##### `apps/core_service/` *(older demo / transitional)*

- `apps/core_service/__init__.py`  
  Package marker.

- `apps/core_service/__main__.py`  
  Earlier demo using `protocol/inmem_bus` and the legacy `on_step` hook.  
  Still useful as a “hello core”, but newer work should prefer `device_step` + adapters.

#### `src/steuerung3d/tests/` (executable specs)

- `tests/__init__.py`  
  Package marker.

- `tests/test_intents.py`  
  Checks intent application rules (LIVE gating + safety overrides).

- `tests/test_state_machine_modes.py`  
  Checks mode normalization and clamping invariants.

- `tests/unit/test_engine_tick.py`  
  Validates tick progression and timebase behavior.

- `tests/unit/test_transport_inmem.py`  
  Validates `InMemTransport` queue semantics.

- `tests/unit/test_sim_axis_plant.py`  
  Validates `SimAxisPlant` respects setpoints and limits.

- `tests/unit/test_record_replay_smoke.py`  
  Smoke test for JSONL recording: record → read → basic assertions about final telemetry.

### `tools/` (workflow helpers, not core runtime)

These scripts support the broader Obsidian/ChatGPT-assisted workflow and are not required to run the core.

- `tools/chatgpt_active_to_obsidian.py`  
  Helper to export/capture into an Obsidian vault.

- `tools/Obsidian Saver (Chat + Web)-2.0.0.user.js`  
  Browser userscript related to the Obsidian saver workflow.

- `tools/open_steuerung3d_prompt_with_saver.cmd`  
  Windows helper to open the prompt + saver.

- `tools/start_obsidian_saver.cmd`  
  Windows helper to start the saver process.

---

## Where we go next (practical roadmap)

- Replace/deprecate the duplicate deque-based `InMemBus` modules in favor of `InMemTransport`.
- (Optional next bone) Log **CommandFrames** alongside intents/telemetry for deeper debugging.
- Introduce a real transport (UDP) while keeping the same core interfaces.
- Grow `MachineState` to multiple axes and richer safety/limits while preserving the same tick lifecycle.
