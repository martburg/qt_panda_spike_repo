# CoreMode Cutover Inventory

Date: 2026-02-23
Branch: coremode-cutover

## Removed legacy mode concepts

### Deleted in cutover
- [src/steuerung3d/core/mode.py](src/steuerung3d/core/mode.py): legacy `Mode` enum removed.
- [src/steuerung3d/core/state_machine.py](src/steuerung3d/core/state_machine.py): legacy normalize/enforce helpers removed.
- [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py): `MachineState.mode` removed.

### CoreMode propagation / usage
- [src/steuerung3d/core/core_mode.py](src/steuerung3d/core/core_mode.py): `CoreMode` enum + `core_mode_value()`.
- [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py): `MachineState.core_mode` (authoritative).
- [src/steuerung3d/core/telemetry.py](src/steuerung3d/core/telemetry.py): `TelemetrySnapshot.core_mode`.
- [src/steuerung3d/core/command_frame.py](src/steuerung3d/core/command_frame.py): `CommandFrame.core_mode` field.
- [src/steuerung3d/core/executor.py](src/steuerung3d/core/executor.py): clamps motion when `core_mode != LIVE` or `joy.select_hip` is false.

### Intent-based mode toggles (removed)
- `ArmLiveMode` / `DisarmToIdle` intents removed from core and protocol codec.
- `core_live_request` / `core_live_request_seen` removed from state + core UDP service.

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

## Grep hits to keep tidy

- `core_mode` / `core_blocked_by` / `core_axis_gate` consumers.
- `AxisSafetyFacts` and `aggregate_core_mode()` usage.

## Risks / test touchpoints

### Risks
- `core_mode` is derived from safety facts; ensure any UI components still referencing mode strings read `core_mode`.
- Select gating (`joy.select_hip`) is authoritative in core; tests that assume motion without select must set it explicitly.

### Tests to watch
- [tests/test_core_mode_aggregate.py](tests/test_core_mode_aggregate.py)
- [tests/test_core_mode_runtime.py](tests/test_core_mode_runtime.py)
- [tests/test_state_machine_modes.py](tests/test_state_machine_modes.py)
- [tests/test_core_reset_policy.py](tests/test_core_reset_policy.py)
- [tests/test_joy_motion_pipeline.py](tests/test_joy_motion_pipeline.py)
- [tests/unit/test_frederik_panel.py](tests/unit/test_frederik_panel.py)
- [tests/unit/test_birdseye_format.py](tests/unit/test_birdseye_format.py)
