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

