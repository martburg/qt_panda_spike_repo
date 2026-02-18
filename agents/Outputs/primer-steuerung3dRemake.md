# Steuerung3d_Remake Primer

## What this project is
- A small, test-driven "walking skeleton" for the Steuerung3D control stack with explicit device boundaries and deterministic stepping, centered on `MachineState` and a `Timebase` tick loop. See [README.md](README.md) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- A multi-process control stack that connects UI (HiP), core (core engine + UDP bridge), and device endpoints (DenSi or PLC adapters) over UDP with clear intent/telemetry seams. See [docs/DEV_STACK.md](docs/DEV_STACK.md) and [docs/runbook_udp_seams.md](docs/runbook_udp_seams.md).
- A protocol-focused remake that keeps the legacy TwinCAT UDP contract explicit, testable, and preserved. See [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md) and [docs/protocol_plc_wire.md](docs/protocol_plc_wire.md).
- A system that logs intents, telemetry, and command frames in JSONL for deep debugging, replay, and regression checks. See [docs/logging.md](docs/logging.md) and [docs/logging_and_replay.md](docs/logging_and_replay.md).
- A repo structured around `src/steuerung3d` runtime code, `tests/`, `configs/`, and `docs/` with TOML-driven boot profiles. See [docs/REPO_STRUCTURE.md](docs/REPO_STRUCTURE.md) and [docs/STACK_BOOT_STATUS.md](docs/STACK_BOOT_STATUS.md).

## Why the rewrite exists
- Make the legacy TwinCAT PLC UDP protocol explicit, testable, and regression-guarded while modernizing the stack. See [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md).
- Establish a deterministic core tick loop and a single source of truth (`MachineState`) to enable predictable behavior and reliable tests. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- Keep a clear command/measurement seam using a full-state `CommandFrame` each tick to tolerate loss/duplication on UDP. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/plc_integration.md](docs/plc_integration.md).
- Enable record/replay and "commanded vs measured" analysis with JSONL logging and a log viewer. See [docs/logging.md](docs/logging.md).
- Provide a profile-driven supervisor (`python -m steuerung3d up --profile ...`) with per-session logs and birds-eye status for real-world ops hygiene. See [docs/STACK_BOOT_STATUS.md](docs/STACK_BOOT_STATUS.md).

## Architecture map
- **Core**: `CoreEngine` drains intents, updates `MachineState`, emits `CommandFrame`, calls device adapters, and publishes `TelemetrySnapshot`. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **Protocol/Transport**: `InMemTransport` baseline plus JSONL logging wrappers; UDP bridges for multi-process runs. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/logging.md](docs/logging.md), and [docs/runbook_udp_seams.md](docs/runbook_udp_seams.md).
- **Device adapters**:
  - SIM device for local dev. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
  - Legacy PLC adapter (`plc_twincat_legacy`) including codec, device, and fleet; loopback UDP sims for off-network development. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md).
- **Apps / processes**:
  - `core_udp_service` (core + UDP bridge).
  - `hi_p` (operator UI; intents out, telemetry in).
  - `den_si` (device endpoint simulator; command in, telemetry out).
  - `plc_stack` (real rig edge adapter + core wiring).
  - `dev_stack` and profile-driven supervisor (`steuerung3d up`). See [README.md](README.md), [docs/DEV_STACK.md](docs/DEV_STACK.md), and [docs/plc_stack.md](docs/plc_stack.md).
- **Data flow (UDP seams)**:
  - IntentIn (HiP/joy2intent → Core), UI telemetry (Core → HiP), Device command (Core → DenSi/PLC), Device telemetry (DenSi/PLC → Core). See [docs/protocol_plc_wire.md](docs/protocol_plc_wire.md) and [docs/runbook_udp_seams.md](docs/runbook_udp_seams.md).

## Source of truth
- **Canonical PLC UDP contract (required)**: [docs/protocols/legacy_plc_anton.md](docs/protocols/legacy_plc_anton.md) is the explicit, axis-specific ground truth derived from the PLC ST program.
- **Protocol semantics and invariants**: [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md) and [docs/protocol_plc_wire.md](docs/protocol_plc_wire.md).
- **ST sources for archaeology**: [ST-Code/INDEX.md](ST-Code/INDEX.md) and [ST-Code/KommAnton__MAIN.st](ST-Code/KommAnton__MAIN.st).
- **Protocol index**: [docs/protocols/legacy_plc_protocols.md](docs/protocols/legacy_plc_protocols.md).

## Semantics contracts (no regression)
- **E-Stop truth is device-owned**: `TelemetrySnapshot.estop` is authoritative; UI cannot assert safety state. See [docs/safety_estop_policy.md](docs/safety_estop_policy.md).
- **Command frame is full-state and deterministic**: core must emit a complete `CommandFrame` every tick. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/plc_integration.md](docs/plc_integration.md).
- **Legacy PLC invariants**:
  - Send a downlink every frame (watchdog).
  - `lifetick = CommandFrame.tick & 0xFFFF`.
  - On enable edge, rebase `PosSoll` to last `PosIst` (no `vel*dt` integration on that frame).
  - `AxisState.enabled` is measured truth derived from uplink, not commanded intent.
  See [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md).
- **LifeTick roundtrip semantics**: device tick from uplink must be echoed back via `EchoLifeTick` and appear as `LifetickUIrx` on downlink; HiP shows delta ticks. See [docs/protocol_plc_wire.md](docs/protocol_plc_wire.md) and [docs/livetick.md](docs/livetick.md).
- **Per-axis routing (no broadcast)**: one datagram per axis per tick; no broadcast fallback in multi-axis mode. See [docs/decisions.md](docs/decisions.md).
- **UI telemetry slicing**: each HiP should only see its axis telemetry to avoid cross-talk. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/decisions.md](docs/decisions.md).

## How to run
- **Profile-driven supervisor (recommended)**:
  - `python -m steuerung3d up --profile dev_sim`
  - Companion commands: `plan`, `doctor`, `status`, `logs`, `down`
  See [README.md](README.md) and [docs/STACK_BOOT_STATUS.md](docs/STACK_BOOT_STATUS.md).
- **HiP ↔ Core ↔ DenSi demo (Yellow UI)**:
  - `python -m steuerung3d.apps.core_udp_service --dt 0.1`
  - `python -m steuerung3d.apps.den_si`
  - `python -m steuerung3d.apps.hi_p`
  See [README.md](README.md) and [docs/DEV_STACK.md](docs/DEV_STACK.md).
- **Legacy single-process dev runner**:
  - `python -m steuerung3d.apps.dev_stack --config configs/dev_plc.toml`
  See [docs/DEV_STACK.md](docs/DEV_STACK.md).
- **Logs and sessions**:
  - Per-process session logs live under `.run/<stack>/sessions/<timestamp>/`.
  See [README.md](README.md) and [docs/logging.md](docs/logging.md).

## How to test efficiently
- **Fast lane**: `pytest -q`. See [docs/testing.md](docs/testing.md).
- **Integration subset**: `pytest -q -m integration`. See [docs/testing.md](docs/testing.md).
- **Golden regression tests**:
  - Core ⇄ HiP livetick echo roundtrip PLC test. See [docs/testing.md](docs/testing.md).
  - Core ⇄ DenSi param write roundtrip PLC test. See [docs/testing.md](docs/testing.md).

## Current state & near-term milestones
- **Stabilized**:
  - Deterministic core tick + `CommandFrame` seam. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
  - JSONL logging for intents/telemetry/command frames. See [docs/logging.md](docs/logging.md).
  - Profile-driven boot supervisor with birds-eye status. See [docs/STACK_BOOT_STATUS.md](docs/STACK_BOOT_STATUS.md).
  - TwinCAT legacy UDP adapter + fleet support + loopback UDP sims. See [README.md](README.md) and [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md).
  - Per-axis routing and UI telemetry slicing. See [docs/decisions.md](docs/decisions.md).
- **Next milestones** (from repo plan):
  - Real transport stream beyond in-mem (UDP and beyond). See [docs/milestones.md](docs/milestones.md).
  - Harden multi-axis runtime behavior (timeouts, diagnostics). See [docs/milestones.md](docs/milestones.md).
  - Minimal PLC simulator for integration tests without real PLCs. See [docs/milestones.md](docs/milestones.md).
  - Prod PLC targets + axis→endpoint mapping refinements. See [docs/milestones.md](docs/milestones.md).
  - Joystick/setup-stack ergonomics and selection semantics. See [docs/milestones.md](docs/milestones.md).

## Glossary
- **HiP**: operator UI ("Human Intent Parser") that emits intents and renders UI telemetry. See [docs/DEV_STACK.md](docs/DEV_STACK.md).
- **DenSi**: device endpoint simulator UI (device-side) that consumes command frames and emits telemetry. See [docs/DEV_STACK.md](docs/DEV_STACK.md).
- **CommandFrame**: full-state commanded setpoints emitted by core each tick; device adapters consume it. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **TelemetrySnapshot**: core-published system state snapshot (measured truth). See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- **LifeTick / TimeTick**: 16-bit device tick loopback used to confirm end-to-end freshness and compute UI delta. See [docs/livetick.md](docs/livetick.md) and [docs/protocol_plc_wire.md](docs/protocol_plc_wire.md).
- **Profile**: stack boot configuration in TOML under `configs/stacks/*.toml`. See [docs/STACK_BOOT_STATUS.md](docs/STACK_BOOT_STATUS.md).
- **Edge adapter**: PLC bridge that translates `CommandFrame` to PLC wire and telemetry back. See [docs/PLC_TWINCAT_LEGACY.md](docs/PLC_TWINCAT_LEGACY.md).
