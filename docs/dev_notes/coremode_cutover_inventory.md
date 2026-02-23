# CoreMode Cutover Inventory

Date: 2026-02-23
Branch: coremode-cutover

## Legacy mode concepts

### Mode enum/state machine
- [src/steuerung3d/core/mode.py](src/steuerung3d/core/mode.py): `Mode` enum (ESTOP/FAULT/IDLE/LIVE).
- [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py): `MachineState.mode`.
- [src/steuerung3d/core/state_machine.py](src/steuerung3d/core/state_machine.py): `_coerce_mode()`, `normalize_mode()`, `enforce_mode_actions()`.

### Mode propagation / usage
- [src/steuerung3d/core/telemetry.py](src/steuerung3d/core/telemetry.py): `TelemetrySnapshot.mode`, `TelemetrySnapshot.from_state()` uses `state.mode`.
- [src/steuerung3d/core/command_frame.py](src/steuerung3d/core/command_frame.py): `CommandFrame.mode` field.
- [src/steuerung3d/core/executor.py](src/steuerung3d/core/executor.py): `CommandFrame(mode=state.mode.value)`.
- [src/steuerung3d/apps/log_viewer/__main__.py](src/steuerung3d/apps/log_viewer/__main__.py): uses `snap.mode` or `cf.mode` when rendering.
- [src/steuerung3d/apps/dev_stack/__main__.py](src/steuerung3d/apps/dev_stack/__main__.py): prints `snap.mode`.
- [src/steuerung3d/apps/plc_stack/__main__.py](src/steuerung3d/apps/plc_stack/__main__.py): prints `snap.mode`.

### Intent-based mode toggles
- [src/steuerung3d/core/intents.py](src/steuerung3d/core/intents.py): `ArmLiveMode`, `DisarmToIdle`.
- [src/steuerung3d/core/intent_handler.py](src/steuerung3d/core/intent_handler.py): handles `ArmLiveMode`/`DisarmToIdle` and motion gating.
- [src/steuerung3d/protocol/codec.py](src/steuerung3d/protocol/codec.py): intent type map includes `arm_live_mode`, `disarm_to_idle`.
- [src/steuerung3d/apps/cli_client/__main__.py](src/steuerung3d/apps/cli_client/__main__.py): publishes `ArmLiveMode`/`DisarmToIdle`.
- [src/steuerung3d/apps/dev_stack/__main__.py](src/steuerung3d/apps/dev_stack/__main__.py): publishes `ArmLiveMode`.
- [src/steuerung3d/apps/plc_stack/__main__.py](src/steuerung3d/apps/plc_stack/__main__.py): publishes `ArmLiveMode`.
- [src/steuerung3d/apps/core_service/__main__.py](src/steuerung3d/apps/core_service/__main__.py): publishes `ArmLiveMode`.

### live_request tracking
- [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py): `core_live_request`, `core_live_request_seen`.
- [src/steuerung3d/core/intent_handler.py](src/steuerung3d/core/intent_handler.py): sets `core_live_request` on `ArmLiveMode` / clears on `DisarmToIdle`.
- [src/steuerung3d/apps/core_udp_service/__main__.py](src/steuerung3d/apps/core_udp_service/__main__.py): consumes `core_live_request`, stores `core_live_request_seen`.

## Stage-2 CoreMode aggregation

### Core aggregator
- [src/steuerung3d/core/mode_aggregate.py](src/steuerung3d/core/mode_aggregate.py):
  - `AxisSafetyFacts`, `AggregateInputs`, `aggregate_core_mode()`, `aggregate_and_store()`.
  - `axis_gate` includes `owner` + `age_ms`.

### Aggregator wiring / storage
- [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py): `core_mode`, `core_blocked_by`, `core_axis_gate`.
- [src/steuerung3d/apps/core_udp_service/__main__.py](src/steuerung3d/apps/core_udp_service/__main__.py):
  - builds `AxisSafetyFacts` per axis.
  - calls `aggregate_and_store()`.
  - emits Frederik birds-eye fields (`core_mode`, `blocked_by`, per-axis facts).
- [src/steuerung3d/core/stack_runtime.py](src/steuerung3d/core/stack_runtime.py): Frederik panel rendering in birds-eye output.

### AxisSafetyFacts inputs
- [src/steuerung3d/apps/core_udp_service/__main__.py](src/steuerung3d/apps/core_udp_service/__main__.py):
  - estop/armed/ready derived from `derive_banner_estate_from_word()`.
  - started derived from command state.
  - age from `densi_registry.last_seen_core_tick`.
  - owner from `axis_claims` or `lease_axis_holders`.

### Key bits (chkEsKey1/chkEsKey2) in DenSi telemetry
- [src/steuerung3d/protocol/estop_bits.py](src/steuerung3d/protocol/estop_bits.py):
  - `schluessel1` bit 30 -> `chkEsKey1`.
  - `schluessel2` bit 31 -> `chkEsKey2`.
- [src/steuerung3d/apps/yellow/panels/densi/densi_estop_checkboxes_render.py](src/steuerung3d/apps/yellow/panels/densi/densi_estop_checkboxes_render.py):
  - checkbox discovery/sync via `iter_specs()` + `decode_estop_word()`.
- [src/steuerung3d/apps/yellow/runtimes/densi_runtime.py](src/steuerung3d/apps/yellow/runtimes/densi_runtime.py):
  - consumes `tick_result.estop_bits`/`estop_word` and updates estop dot/checkbox VMs.
- [src/steuerung3d/apps/yellow/assets/yellow3_merged.ui](src/steuerung3d/apps/yellow/assets/yellow3_merged.ui):
  - checkbox widgets `chkEsKey1`, `chkEsKey2`.
- [src/steuerung3d/apps/yellow/domain/ui_estop.py](src/steuerung3d/apps/yellow/domain/ui_estop.py):
  - profile inference uses `schluessel1`/`schluessel2` bits.

## Grep hits to revisit during cutover

- `Mode.` / `MachineState.mode` / `state.mode` usage.
- `TelemetrySnapshot.mode` / `snap.mode` / `cf.mode` output formatting.
- `ArmLiveMode` / `DisarmToIdle` call sites in apps and CLI.
- `core_mode` / `core_blocked_by` / `core_axis_gate` consumers.
- `core_live_request` / `core_live_request_seen`.
- `AxisSafetyFacts` and `aggregate_core_mode()` usage.

## Risks / test touchpoints

### Risks
- Mixed legacy `state.mode` vs new `core_mode` signals can diverge (telemetry vs birds-eye).
- CLI/dev/plc demo flows still publish `ArmLiveMode`, which now maps to live request gating.
- UI continues to show `snap.mode` (telemetry) in log viewers; potential confusion post-cutover.

### Tests to watch
- [tests/test_core_mode_aggregate.py](tests/test_core_mode_aggregate.py)
- [tests/test_core_mode_runtime.py](tests/test_core_mode_runtime.py)
- [tests/test_state_machine_modes.py](tests/test_state_machine_modes.py)
- [tests/test_core_reset_policy.py](tests/test_core_reset_policy.py)
- [tests/test_joy_motion_pipeline.py](tests/test_joy_motion_pipeline.py)
- [tests/unit/test_frederik_panel.py](tests/unit/test_frederik_panel.py)
- [tests/unit/test_birdseye_format.py](tests/unit/test_birdseye_format.py)
