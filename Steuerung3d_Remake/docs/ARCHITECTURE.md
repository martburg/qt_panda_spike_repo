# Architecture overview

This repo is a deliberately small “walking skeleton” that keeps the boundaries of the final system
visible early.

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

## Axis types + controller-side FSM wiring (Legacy TwinCAT)

We support **multiple axis kinds**. The core state (`MachineState.axes[axis_id]`) is generic, but an axis can carry a `kind` and an optional typed telemetry blob (`AxisState.tel`) for adapter/controller-specific needs.

### Design rule: multi axis types

- `AxisState` is the common surface: `pos`, `vel`, `enabled`, `fault`, `meta`, plus:
  - `kind: str` (e.g. `"legacy_twincat"`, `"sim"`, …)
  - `tel: Optional[Any]` (typed, axis-kind specific)
- `AxisCommandState` remains the common commanded surface for v0.1: `enable`, `vel`
- The controller/FSM layer must **only** touch axes it owns:
  - Legacy TwinCAT FSM is applied only if `ax.kind == "legacy_twincat"`
  - Non-legacy axes keep their existing semantics (e.g. SIM plant)

### Wiring: engine → executor → device

Per tick:

1. `CoreEngine.step_once()` processes intents (if configured) and enforces mode/safety invariants.
2. `drive_legacy_axis_fsms(state)` runs **before** building the command frame:
   - lazily creates `state.axis_fsm[axis_id]`
   - reads typed `ax.tel` (`LegacyAxisTelemetry`) or uses a default placeholder
   - runs the FSM (`LegacyTwinCATAxisFSM.step(tel, req)`)
   - maps FSM state → `AxisCommandState` (`enable`, `vel`)
3. `build_command_frame(state)` emits `CommandFrame` based on `state.axis_cmd`
4. `device_step(state, cmd_frame, dt)` (SIM or real PLC adapter) updates measured state and (for legacy) updates `ax.tel`

### READY/ENABLING/ACTIVE semantics

For legacy TwinCAT:
- `READY` means “claimed and permitted to enable”
- `ENABLING` and `ACTIVE` keep enable asserted

So the minimal mapping is:

- allow enable if FSM state ∈ `{ST_READY, ST_ENABLING, ST_ACTIVE}`
- `cmd_state.enable = req.want_enable and allow_enable`
- `cmd_state.vel` passes through only when enabled (currently 0.0 in the no-intents placeholder)
