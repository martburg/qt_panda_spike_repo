# Architecture overview

This repo is a deliberately small “walking skeleton” that keeps the boundaries of the final system
visible early.

Canonical architecture references:
- `docs/Architectural_Primer_v4_full.md` (full spec)
- `docs/Architectural_Primer.md` (summary)

## Core principles

- **Single source of truth:** `MachineState` owns the system state.
- **Deterministic stepping:** a `Timebase` defines `dt` and produces ticks.
- **Device boundary:** the core talks to hardware (real PLCs or sims) through `device.step(state, cmd, dt)`.
- **Intent/telemetry transport:** clients publish intents; the core publishes snapshots.
- **Record/replay:** transports can be wrapped to log traffic (JSONL).

## Key modules

- `steuerung3d/core/state.py`
  - `MachineState`: global tick/time, mode, safety flags
  - `AxisState`: measured state (pos/vel/enabled/fault)
  - `AxisCommandState`: commanded state (enable/vel) stored separately

- `steuerung3d/core/param_registry.py`
  - Canonical parameter registry (groups, tolerances, normalization)

- `steuerung3d/core/command_frame.py`
  - `CommandFrame`: one “frame” of commanded values produced by the core

- `steuerung3d/core/engine.py`
  - `CoreEngine.step_once()`
    - drain intents
    - update state
    - build a command frame
    - call the device adapter
    - publish a snapshot

- `steuerung3d/protocol/transport.py`
  - `InMemTransport`: in-process intent + telemetry queues

- `steuerung3d/protocol/recording.py`
  - `JsonlRecorder`: writes JSON lines
  - `LoggedTransport`: wraps a transport and records in/out messages

- `steuerung3d/protocol/core_runner.py`
  - `CoreRunner`: runs `CoreEngine` in its own thread (real-time-ish)

## Device adapters

- `steuerung3d/adapters/sim/*`
  - simulation device + plant (local development)

- `steuerung3d/adapters/plc/udp_device.py`
  - early minimal UDP adapter (toy protocol)

- `steuerung3d/adapters/plc_twincat_legacy/*`
  - real TwinCAT legacy UDP protocol:
    - codec (`codec.py`)
    - single-axis UDP device (`device.py`)
    - fleet device (`fleet.py`)
    - TOML loader (`config.py`)
    - loopback UDP simulators for off-network development (`udp_sim.py`)

## Why the command frame seam matters

The core produces a `CommandFrame` that is independent of transport and device details. This keeps:

- the core deterministic and testable
- device adapters replaceable (SIM, legacy PLC, future protocols)
- logging and regression testing straightforward

## HiP ↔ DenSi parameter editing (axis-agnostic)

In addition to motion / mode intents, the system supports an **axis-agnostic parameter edit flow**
between:

- **HiP** (Human Intent Parser / operator UI)
- **DenSi** (Device Endpoint Simulator)

The flow is deliberately simple and mirrors the UI buttons:

- **Edit** → prime DenSi to accept new values for a parameter group
- **Write** → commit new values to DenSi
- **Cancel** → abort the edit session (no changes applied)

This is modeled as a small state machine per edit group (e.g. `pos`, `vel`, `filter`, `guider`).

### Intents

HiP emits intents (over UDP or in-memory transport):

- `BeginParamEdit(group)`
- `CommitParamEdit(group, values)`
- `CancelParamEdit(group)`

The **core** applies these to `MachineState` and emits the corresponding operations in the
next `CommandFrame`.

### CommandFrame

`CommandFrame` carries a list of parameter operations (axis-agnostic):

- `param_ops: [ {op: begin|commit|cancel, group, values?, session_id?, req_id?} ... ]`

This keeps parameter traffic on the same deterministic “frame seam” as motion commands.

### Telemetry

DenSi reports parameter edit state and applied values in telemetry so HiP can:

- enable/disable fields and buttons correctly
- show the effective values after a write

In practice the DenSi/PLC side is treated as semi-frozen: we avoid adding new protocol obligations there.
So the system uses a two-layer guarantee:

- **HiP ↔ Core**: guarded delivery via `req_id` acks (dedupe + retry).
- **Core ↔ DenSi**: *observed confirmation* by comparing the requested values to DenSi’s reported `params` in telemetry.
  Core publishes `param_commit_status` (`pending/applied/timeout`) so the UI can present a clear result.

Important UI detail:

- While a group is in **active edit mode**, HiP must **not** overwrite in-progress user typing
  with periodic telemetry refresh. Only non-active groups should be refreshed.

### UI gating policy

- **HiP**: parameter text fields are disabled (grey) until Edit is pressed; active fields become enabled (white).
  Editing is **modal**: once a group is in edit mode, other Edit buttons and tab switching are disabled until Write/Cancel.
  After Write, HiP shows a **modal dialog** once Core observes the device as applied (or a timeout if not confirmed).
  If HiP auto-adjusts **pos** limits to satisfy `HardMax ≥ UserMax ≥ UserMin ≥ HardMin`, it shows an info dialog listing the adjustments before sending.
- **DenSi**: Edit/Write/Cancel controls are disabled (greyed). DenSi acts as a “device endpoint”, not an operator.

### Safety / startup

DenSi starts in a **stopped / not-OK** state by default so the safe state is visible immediately.
Diagnostic buttons “Set All” / “Clear All” remain purely diagnostic and keep their semantics.

Axis FSM (controller-side)

Each axis has a controller-side FSM that governs mode, safety gating, and recovery.

The FSM is implemented using the transitions library.

It consumes events derived from:

operator intents (enable/disable, request recover)

safety/estop status from uplink

watchdog / comm health

It outputs “allowed actions” and state, which downstream code uses to:

accept or reject commands

force safe command defaults (e.g., zero velocity)

trigger recover procedures

Why this exists

Legacy PLC protocol is order-sensitive and permissive.

Without an explicit FSM, safety & recover logic leaks into UI and transport.

A test-driven FSM makes the system deterministic and regression-safe.

Key states

IDLE: safe, not driving motion.

ENABLED (or ACTIVE): normal running state (whatever you named it).

ESTOP: safety stop asserted → commands must be gated.

RECOVER: explicit recovery sequence before returning to idle/ready.

Key transitions

enable: IDLE → ENABLED

estop: * → ESTOP

recover_request: ESTOP → RECOVER

recover_done: RECOVER → IDLE

disable: ENABLED → IDLE



## Axis-scoped UDP routing (no broadcast)

For real PLC integration (and to avoid surprising cross-talk in sim), the device command path is **strictly per-axis**:

- Core builds one device command payload **per axis**
- The UDP service sends it to exactly one target (host:port) for that axis
- Broadcast fallback is **not allowed** in multi-axis mode

This matches the frozen PLC contract: each PLC endpoint must receive only the data it expects.

### Port overlap guard

A common Windows pitfall is overlapping ports when running local sims:

- DenSi `cmd-in` uses a contiguous range (e.g. `52001..52004`)
- Core `dev_telem_in` must not be within that range

Launchers enforce this and refuse to start if an overlap is detected.

## Per-axis UI telemetry slicing

Device telemetry arrives multiplexed (all DenSi instances send to a single `dev_telem_in` port).
The core maintains per-axis caches for device-specific fields and publishes **one telemetry stream per HiP**:

- each HiP receives a snapshot containing only its axis (`axes={Anton: ...}`)
- per-axis fields such as `params`, `estop_status_word`, and param-commit status are taken from the correct axis cache

This prevents the “last-writer wins” effect where HiPs appear to show the telemetry of different DenSis.

## Transaction acks (HiP)

Ack signals (`core_acks`) are one-shot fields in telemetry snapshots. The receiver may drain multiple snapshots per poll.
Therefore, the HiP must process acks across **all** drained snapshots before deciding to resend or time out.
