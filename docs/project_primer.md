# Project primer (Steuerung3D Remake)

## 1) Purpose and scope

This repo is a small, test-driven "walking skeleton" for the Steuerung3D control stack, with a deterministic core, clear device boundary, and explicit transport and logging seams. The goal is to keep the real system boundaries visible while the protocol and UI evolve (see [README.md](../README.md) and [ARCHITECTURE.md](ARCHITECTURE.md)).

What this primer covers:
- Core loop and invariants, key data types, and transport/logging seams.
- Legacy PLC wire protocol sources and the current contract.
- How the boot/profile system and demos are wired.
- The tests that freeze critical semantics.

## 2) Architecture at a glance

Core flow (simplified):
- Inputs (HiP/joystick/clients) publish intents to a transport.
- Core consumes intents, updates `MachineState`, builds a `CommandFrame`, steps a device adapter, then publishes a `TelemetrySnapshot` ([src/steuerung3d/core/engine.py](../src/steuerung3d/core/engine.py)).
- Device adapters provide the boundary: SIM, toy UDP, or TwinCAT legacy UDP (see [ARCHITECTURE.md](ARCHITECTURE.md) and [README.md](../README.md)).

Key boundaries:
- Core is deterministic and transport-agnostic.
- The CommandFrame seam keeps device adapters replaceable and testable ([ARCHITECTURE.md](ARCHITECTURE.md)).
- PLC wire protocol is treated as frozen; the edge adapter translates to/from the core seam ([PLC_TWINCAT_LEGACY.md](PLC_TWINCAT_LEGACY.md)).

## 3) Core loop and invariants

Core loop order (single tick):
1) Drain intents and apply them to `MachineState`.
2) Enforce rig and mode invariants.
3) Advance tick/time.
4) Build `CommandFrame` and call device adapter.
5) Emit `TelemetrySnapshot` and clear one-shot state.

Source: [src/steuerung3d/core/engine.py](../src/steuerung3d/core/engine.py).

Mode/safety invariants:
- `ESTOP > FAULT > IDLE/LIVE` ordering; ESTOP forces `enable=False` and `vel=0`. FAULT/IDLE force `vel=0` ([src/steuerung3d/core/state_machine.py](../src/steuerung3d/core/state_machine.py)).

Legacy PLC contract invariants (core assumptions):
- Lifetick comes from `CommandFrame.tick & 0xFFFF` ([PLC_TWINCAT_LEGACY.md](PLC_TWINCAT_LEGACY.md)).
- On enable edge, the PLC setpoint integrator is rebased to last measured position (no `vel*dt` in that edge frame) ([PLC_TWINCAT_LEGACY.md](PLC_TWINCAT_LEGACY.md)).
- Enabled is measured truth (derived from PLC status), not commanded intent ([PLC_TWINCAT_LEGACY.md](PLC_TWINCAT_LEGACY.md)).

## 4) Data model and intents (core seam)

`MachineState` is the single source of truth and contains measured state, command state, safety flags, and per-axis workflow data ([src/steuerung3d/core/state.py](../src/steuerung3d/core/state.py)).

Command side:
- `CommandFrame` carries per-axis setpoints plus legacy knobs, param ops, and LifeTick echo values ([src/steuerung3d/core/command_frame.py](../src/steuerung3d/core/command_frame.py)).
- Param ops (`param_edit_begin`, `param_write`, `param_cancel`) are axis-agnostic and designed to stay on the CommandFrame seam.

Telemetry side:
- `TelemetrySnapshot` publishes measured axis state plus diagnostic fields, params, and raw PLC uplink fields ([src/steuerung3d/core/telemetry.py](../src/steuerung3d/core/telemetry.py)).
- `estop_status_word` is carried through untouched for UI bit decoding ([src/steuerung3d/core/telemetry.py](../src/steuerung3d/core/telemetry.py)) and decoded using the canonical map in [src/steuerung3d/protocol/estop_bits.py](../src/steuerung3d/protocol/estop_bits.py).

Intents (examples):
- Motion/control: `EnableAxis`, `JogAxis`, `SetEstop`.
- Parameter flow: `ParamEditBegin`, `ParamWrite`, `ParamCancel`.
- LifeTick echo: `EchoLifeTick` mirrors device tick back to the device path ([src/steuerung3d/core/intents.py](../src/steuerung3d/core/intents.py)).

## 5) Transport, logging, and replay

Transport is the seam between producers (UI/joystick) and the core. It is not inherently "networking"; the default is an in-process transport to keep tests deterministic ([docs/transport.md](transport.md)).

Logging streams:
- Session logs (per process) from the supervisor (`python -m steuerung3d up ...`).
- JSONL event logs (intents, telemetry, command frames) written by the recorder ([docs/logging.md](logging.md)).

Replay and regression:
- JSONL records are used to compare command-frame sequences and replay deterministic runs ([docs/logging.md](logging.md)).
- The CommandFrame regression hash is enforced in tests (see section 8).

## 6) PLC legacy protocol sources and mapping

Authoritative sources:
- ST program `KommAnton__MAIN.st` (canonical), referenced by [docs/protocols/legacy_plc_anton.md](protocols/legacy_plc_anton.md).
- Contract and invariants: [docs/PLC_TWINCAT_LEGACY.md](PLC_TWINCAT_LEGACY.md).
- PLC-wire end-to-end behavior (DenSi/Core/HiP): [docs/protocol_plc_wire.md](protocol_plc_wire.md).

Wire format basics:
- ASCII, semicolon-delimited fields; uplink has `EOD` marker + tail fields.
- Downlink field ordering and required token count are strict (see [docs/protocols/legacy_plc_anton.md](protocols/legacy_plc_anton.md) and codec tests).
- `Intent` is the string `"True"`/`"False"` (not boolean) and parsing is order-sensitive ([docs/protocols/legacy_plc_anton.md](protocols/legacy_plc_anton.md)).

Codec reference:
- The project also ships a minimal parser/encoder for the legacy uplink format to keep the mapping explicit ([src/steuerung3d/protocol/legacy_plc.py](../src/steuerung3d/protocol/legacy_plc.py)).

## 7) Stack boot and operational workflow

Recommended boot path:
- `python -m steuerung3d up --profile <profile>` with profile-driven supervisor and session logs ([docs/DEV_STACK.md](DEV_STACK.md), [docs/STACK_BOOT_STATUS.md](STACK_BOOT_STATUS.md)).

Operational expectations:
- Per-run session logs under `.run/<stack>/sessions/<timestamp>/`.
- Structured birds-eye status via a UDP JSON heartbeat channel (see [docs/STACK_BOOT_STATUS.md](STACK_BOOT_STATUS.md)).

Legacy compatibility:
- `setup_stack` still exists as a thin wrapper over the same runtime (see [docs/STACK_BOOT_STATUS.md](STACK_BOOT_STATUS.md)).

## 8) Regression tests that freeze semantics

These tests are the contract for behavior that should not change silently:

- PLC downlink field order and `Intent` string; `Modus=='w'` token count; uplink EOD split ([tests/test_plc_twincat_legacy_codec.py](../tests/test_plc_twincat_legacy_codec.py)).
- Device adapter invariants: send every frame, lifetick echo, enable-edge rebase, measured-enabled truth ([tests/test_plc_twincat_legacy_device_udp.py](../tests/test_plc_twincat_legacy_device_udp.py)).
- LifeTick echo pipeline and 16-bit wrap semantics ([tests/test_livetick_echo_pipeline.py](../tests/test_livetick_echo_pipeline.py), [tests/unit/test_livetick_roundtrip.py](../tests/unit/test_livetick_roundtrip.py)).
- LifeTick UI view model delta and wrap behavior ([tests/unit/test_densi_lifetick_vm.py](../tests/unit/test_densi_lifetick_vm.py)).
- Axis router slicing and device-scoped fields (estop word, params, commit status) ([tests/test_axis_router.py](../tests/test_axis_router.py)).
- CommandFrame sequence regression hash (deterministic SIM) ([tests/unit/test_command_frame_regression.py](../tests/unit/test_command_frame_regression.py)).
- Stack profile loading and expansion (ports, per-axis processes) ([tests/test_stack_boot_profiles.py](../tests/test_stack_boot_profiles.py)).
- Integration: Core + DenSi PLC-wire param write roundtrip ([tests/integration/test_roundtrip_core_densi_plc.py](../tests/integration/test_roundtrip_core_densi_plc.py)).
- Integration: Core + HiP LifeTick echo roundtrip over PLC-wire ([tests/integration/test_roundtrip_core_hip_plc.py](../tests/integration/test_roundtrip_core_hip_plc.py)).
- E-Stop word decoding behavior used by UI banner state ([tests/test_ui_banner_helpers.py](../tests/test_ui_banner_helpers.py), [tests/unit/test_densi_banner_vm.py](../tests/unit/test_densi_banner_vm.py)).

If a change is intentional, update the tests and document the reason in the commit message (especially the CommandFrame regression hash).

## 9) Glossary and refactor direction

Glossary (internal terms):
- Core: deterministic engine that consumes intents and emits telemetry.
- HiP: Human Intent Parser (operator UI).
- DenSi: device endpoint simulator (PLC-wire boundary on dev stacks).
- CommandFrame: per-tick command setpoint sent to device adapters.
- TelemetrySnapshot: per-tick measured state sent to clients.
- LifeTick: device-origin tick looped through UI for freshness/health.

Refactor direction (current intent):
- Converge transports on `InMemTransport` and keep the "shim" for older bus APIs until removed ([docs/transport.md](transport.md)).
- Keep CommandFrame as the stable seam to minimize churn across adapters and tests ([docs/ARCHITECTURE.md](ARCHITECTURE.md)).
- Continue migrating boot flows toward the profile-driven supervisor; `setup_stack` remains a compatibility wrapper until fully retired ([docs/STACK_BOOT_STATUS.md](STACK_BOOT_STATUS.md)).
- Treat the PLC wire format as frozen; evolve the stack by improving adapters and tests, not by mutating on-wire order or semantics without synchronized updates ([docs/PLC_TWINCAT_LEGACY.md](PLC_TWINCAT_LEGACY.md)).
