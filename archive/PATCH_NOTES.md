# Drop-in Docs Overlay

This zip contains:

- docs/boot_to_recover.md  (canonical boot→sync→recover/resync process description)

Extract into repo root to place the doc under ./docs/.

## JoyStateUpdate -> DenSi motion wiring (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Motion intent and handler chain (canonical):
- JoyStateUpdate is accepted in core/intent_handler.py and stored on state.joy (JoyState.soll_speed).
- Hip UI engine (apps/yellow/engines/hip/engine.py) uses JoyState + deadman + claim to emit JogWinch intents via apps/yellow/domain/joy_motion_map.py::map_soll_speed_to_jog_winch().
- Core intent handler applies JogWinch in core/intent_handler.py: sets axis_cmd.vel for the axis (winch_id).

DenSi command frame build + velocity field:
- core/executor.py::build_command_frame builds CommandFrame with AxisSetpoint(enable, vel).
- AxisSetpoint.vel is the velocity setpoint (units/s placeholder) used downstream as SpeedSollIN.
- DenSi engine step_plant_with_clamp() passes CommandFrame to plc_anton_vel_cmd.py, which reads AxisSetpoint.vel as commanded speed (SpeedSollIN).

VelMax location and read path:
- Core param registry: core/param_registry.py defines VelMax in the "vel" group.
- DenSi motion law reads params["VelMax"] (or SpeedMaxUI) inside plc_anton_vel_cmd.py to clamp speed.
- DenSi engine sets a default VelMax in state.params (apps/yellow/engines/densi/engine.py).

Additional JoyStateUpdate source:
- apps/joy2intent/mapping.py synthesizes JoyStateUpdate from joystick inputs (soll_speed clamped in core/joy_state.py).

## JoyStateUpdate -> DenSi motion wiring (implementation)

Summary:
- JoyStateUpdate now emits a JogWinch intent in core/intent_handler.py, scaled by VelMax and forced to 0 when deadman is released.
- New tests cover JoyStateUpdate scaling and command frame flow in tests/test_joy_motion_pipeline.py.
- PLC boolean token tests and UDP PLC command decode tests were added/updated to enforce True/False tokens and fallbacks.
- Manual smoke steps added to docs/MANUAL_TESTING.md for 1dev_sim deadman/velocity verification.

TODO:
- Consider multi-axis selection policy for JoyStateUpdate (currently single-axis only).

## HipJoySollSpeedMotionClean Phase 0 (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Core JoyStateUpdate handling:
- core/intent_handler.py::apply_intent() handles JoyStateUpdate by updating state.joy and (currently) emitting JogWinch with VelMax scaling.

HiP JoyState + motion intent emission:
- apps/yellow/engines/hip/engine.py::HipEngine.step() stores JoyState on self.state.joy (clamped), then emits JogWinch via map_soll_speed_to_jog_winch() when deadman + LIVE + claim owner match.
- HiP engine does not emit EnableAxis; EnableAxis/ReleaseAxis are emitted in apps/joy2intent/mapping.py (non-HiP path) and claim/release in HipEngine.step().

VelMax access in HiP:
- apps/yellow/engines/hip/presentation.py::compute_readouts_state() reads params.get("VelMax") for slider scaling.
- params are delivered via TelemetrySnapshot.params (from core), so HipEngine.step() can read snap.params for VelMax.

Before flow:
- JoyStateUpdate -> core stores state.joy; HiP emits JogWinch with normalized speed (no scaling) -> core applies JogWinch (lease/claim gated) -> CommandFrame AxisSetpoint.vel -> DenSi SpeedSollIN.

Target flow:
- JoyStateUpdate remains input only; HiP scales soll_speed by VelMax from params and emits EnableAxis/JogWinch (m/s) into core; core should not derive motion directly from JoyStateUpdate.

Planned scaling location in HiP:
- apps/yellow/engines/hip/engine.py (inside JogWinch emission block) or apps/yellow/domain/joy_motion_map.py (extend to accept vel_max from snap.params).

## HipJoySollSpeedMotionClean Phase 1-4 (implementation)

Summary:
- Core no longer derives motion from JoyStateUpdate; it stores joystick input only.
- HiP scales normalized soll_speed by VelMax and emits EnableAxis + JogWinch (m/s), with deadman release forcing JogWinch(0) + EnableAxis(False).
- HiP avoids spamming repeated EnableAxis and JogWinch intents.
- Tests updated to assert HiP scaling, EnableAxis/JogWinch emission, and command-frame velocity flow from HiP intents.
- Manual testing steps added for HiP joystick scaling and deadman gating.

Follow-ups:
- Ensure pytest environment includes the transitions dependency or vendor it in dev setup.

## BirdsEyeMotionDiagnostics Phase 0 (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Birds-eye/status transport:
- Structured status heartbeat lives in core/status.py (StatusEmitter.emit_every).
- Yellow runtimes use apps/yellow/runtimes/runtime_utils.py::emit_status to send heartbeats.
- Supervisor collects in core/stack_runtime.py (StatusCollector + format_birds_eye).

Hook points for motion diagnostics:
- HiP: apps/yellow/runtimes/hip_runtime.py::_emit_status() builds summary/fields and already includes joy fields. If needed, hip_controller.py::poll_once() has rt_result.intents + snap access just before intents are published.
- Core: apps/core_udp_service/__main__.py::on_snapshot() emits status via status.emit_every with tick/mode/estop/fault and age metrics; this is the place to add intent/cmd diagnostics per tick.
- DenSi: apps/yellow/runtimes/densi_runtime.py::_emit_status() emits status based on last_cmd and engine state; this is the stable place to add cmd rx/apply diagnostics. den_si/__main__.py wires DenSiController which owns DensiRuntime.

## HipModeTruthFix Phase 0 (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Where UI shows EStop/Armed/Ready:
- HiP banner estate is computed from the Safety PLC estop word via derive_banner_estate_from_word in apps/yellow/domain/banner_facts.py and wired into the banner VM in apps/yellow/panels/hip/hip_banner_vm.py.
- The banner label reads ESTOP/IDLE/ARMED/READY and is rendered in apps/yellow/panels/hip/hip_banner_render.py via HipViewModel.banner.estate.

Where birds-eye hip "mode" is sourced:
- hip_runtime.py::_emit_status() uses self._last_mode (from TelemetrySnapshot.mode) for the status summary/fields.
- _last_mode is updated per tick from snap.mode in hip_runtime.py::tick().

Mismatch:
- UI estate reflects Safety PLC estop ladder state (estop word bits), while birds-eye hip "mode" reflects controller mode (snap.mode). When the PLC ladder shows ARMED/READY/ESTOP but snap.mode is IDLE, birds-eye reports mode=IDLE even though UI shows ARMED/READY/ESTOP.

Target source-of-truth (candidate):
- Use the same banner estate used by HiP UI (banner.estate from hip_banner_vm) or the underlying estop word decode (banner_facts.derive_banner_estate_from_word) as the hip status "mode".

## HipModeTruthFix Phase 3 (tests)

Summary:
- Added unit tests to lock banner estate mapping and ensure HiP status mode uses the UI estate.

## ResetPolicyAndCoreBirdsEye Phase 0 (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Reset intent type(s) and routing:
- Intent: RequestEstopReset in core/intents.py (fields: axis_id, hip_id).
- Emitted from HiP UI path: apps/yellow/engines/hip/engine.py when btnEStopReset is clicked.
- Core handling in core/intent_handler.py: RequestEstopReset sets state.estop_reset_req_by_axis[axis_id] (or legacy estop_reset_req) with owner check against state.axis_claims.
- Core -> DenSi routing: core/executor.py builds CommandFrame.estop_reset from state.estop_reset_req (legacy), then core_udp_service device_step maps estop_reset_req_by_axis into per-axis frames via AxisRouter.publish_command_frames (estop_reset field in per-axis CommandFrame).
- Device-side consumption: DenSi engine reads CommandFrame.estop_reset in apps/yellow/engines/densi/engine.py::handle_estop_reset_cmd.

hip_id origin and transport:
- hip_id generated in apps/yellow/controllers/hip_controller.py and passed into HipRuntime/HipEngine; attached to RequestEstopReset intent in HipEngine.
- Protocol codec passes hip_id through intent encode/decode (protocol/codec.py).

Axis ownership/attachment state:
- Core owns exclusive claims: state.axis_claims (axis_id -> hip_id) in core/state.py.
- Lease holders: state.lease_axis_holders (axis_id -> list[hip_id]) used by _axis_lease_allows in core/intent_handler.py.
- Telemetry exposes lease_axis / lease_axis_holders via core/telemetry.py; AxisRouter slices per-axis in protocol/axis_router.py.

Draft design (phase 1+) notes:
- Enforce RequestEstopReset axis scoping: only allow if hip_id matches claim owner or lease holder for axis.
- Safe default: deny if owner/hip_id missing.
- Emit birds-eye policy fields from Core with per-axis ownership, estop/reset eligibility, and last reset request details.

Proposed birds-eye field list (Core line):
- core_mode, blocked_by, last_reset_request{axis_id, hip_id, allowed, reason}
- per-axis list: axis_id, in_scope, estop/fault/ready/armed, owner_hip_id, reset_allowed, reset_denied_count

## CoreModeAggregatorFromScratch Phase 0 (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Telemetry facts (estop/fault/started/taster/armed/ready/age) and where they come from:
- Estop + fault are exported in TelemetrySnapshot from MachineState: [src/steuerung3d/core/telemetry.py](src/steuerung3d/core/telemetry.py#L37-L151). PLC uplink decode sets estop based on EStopStatus cause bits: [src/steuerung3d/protocol/plc_codec.py](src/steuerung3d/protocol/plc_codec.py#L246-L341).
- EStopStatus word is carried through as estop_status_word in TelemetrySnapshot and used to decode logical bits (taster/ready/etc.): [src/steuerung3d/core/telemetry.py](src/steuerung3d/core/telemetry.py#L60-L151), [src/steuerung3d/protocol/estop_bits.py](src/steuerung3d/protocol/estop_bits.py#L6-L121).
- READY bit is the logical "ready" bit in EStopStatus (bit 29) and is set by the DenSi ladder when the estate reaches READY: [src/steuerung3d/apps/yellow/engines/densi/estop_fsm.py](src/steuerung3d/apps/yellow/engines/densi/estop_fsm.py#L130-L159).
- Ladder estate (ESTOP/IDLE/ARMED/READY) is derived from the estop word using taster/schuetz/brake bits: [src/steuerung3d/apps/yellow/domain/banner_facts.py](src/steuerung3d/apps/yellow/domain/banner_facts.py#L35-L96).
- Taster state is the estop bit "taster" (bit 27). DenSi view model uses it directly for dots and banner grace handling: [src/steuerung3d/apps/yellow/runtimes/densi_runtime.py](src/steuerung3d/apps/yellow/runtimes/densi_runtime.py#L454-L496).
- Started (post-ESStart) is not a first-class telemetry field; in core birds-eye it is inferred from axis_cmd enable/velocity in core state: [src/steuerung3d/apps/core_udp_service/__main__.py](src/steuerung3d/apps/core_udp_service/__main__.py#L623-L655).
- Armed/ready in birds-eye are derived from banner estate decoded from the estop word: [src/steuerung3d/apps/core_udp_service/__main__.py](src/steuerung3d/apps/core_udp_service/__main__.py#L612-L655).
- Age/staleness is tracked per runtime: hip/densi use stale_after_ms with compute_age_ms/compute_stale; core uses densi_offline_after_ticks for device registry aging. See [src/steuerung3d/apps/yellow/runtimes/hip_runtime.py](src/steuerung3d/apps/yellow/runtimes/hip_runtime.py#L58-L189), [src/steuerung3d/apps/yellow/runtimes/densi_runtime.py](src/steuerung3d/apps/yellow/runtimes/densi_runtime.py#L68-L120), [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py#L16-L64), [src/steuerung3d/core/telemetry.py](src/steuerung3d/core/telemetry.py#L92-L138).

Keyswitch scope (key1/key2) findings:
- Keyswitch bits are defined only as EStopStatus bits schluessel1/schluessel2 (bit 30/31) with UI profile helpers; no explicit axis in_scope policy was found in core. See [src/steuerung3d/protocol/estop_bits.py](src/steuerung3d/protocol/estop_bits.py#L58-L66) and [src/steuerung3d/apps/yellow/domain/ui_estop.py](src/steuerung3d/apps/yellow/domain/ui_estop.py#L162-L214).

DenSi READY meaning (for birds-eye):
- The READY bit is driven by the DenSi ladder: when no trip and schuetz=1, taster=1, and brake OK, estate becomes READY and inj_bits["ready"] is set. See [src/steuerung3d/apps/yellow/engines/densi/estop_fsm.py](src/steuerung3d/apps/yellow/engines/densi/estop_fsm.py#L130-L159).

Birds-eye panels/emitters (status heartbeats):
- Core "Frederik" panel: status.emit_every with core_mode, blocked_by, per-axis fields in [src/steuerung3d/apps/core_udp_service/__main__.py](src/steuerung3d/apps/core_udp_service/__main__.py#L580-L709).
- HiP runtime status: [src/steuerung3d/apps/yellow/runtimes/hip_runtime.py](src/steuerung3d/apps/yellow/runtimes/hip_runtime.py#L350-L392) and controller emission hook for motion intents in [src/steuerung3d/apps/yellow/controllers/hip_controller.py](src/steuerung3d/apps/yellow/controllers/hip_controller.py#L108-L190).
- DenSi runtime status: [src/steuerung3d/apps/yellow/runtimes/densi_runtime.py](src/steuerung3d/apps/yellow/runtimes/densi_runtime.py#L239-L309).

Staleness thresholds found:
- HiP/Densi controllers default stale_after_ms=500. See [src/steuerung3d/apps/yellow/controllers/hip_controller.py](src/steuerung3d/apps/yellow/controllers/hip_controller.py#L35-L76) and [src/steuerung3d/apps/yellow/controllers/densi_controller.py](src/steuerung3d/apps/yellow/controllers/densi_controller.py#L35-L75).
- Core device offline: densi_offline_after_ticks=200 (approx 2s at 10ms ticks). See [src/steuerung3d/core/state.py](src/steuerung3d/core/state.py#L19-L28) and [src/steuerung3d/core/telemetry.py](src/steuerung3d/core/telemetry.py#L92-L138).
- DenSi lifetick stale thresholds: active=50 ticks, idle=500 ticks. See [src/steuerung3d/apps/yellow/engines/densi/engine.py](src/steuerung3d/apps/yellow/engines/densi/engine.py#L136-L176) and [src/steuerung3d/apps/yellow/engines/densi/plc_anton_vel_cmd.py](src/steuerung3d/apps/yellow/engines/densi/plc_anton_vel_cmd.py#L19-L146).
- joy2intent stale_after_ms default 200 in config. See [src/steuerung3d/apps/joy2intent/config.py](src/steuerung3d/apps/joy2intent/config.py#L54-L66).

## CoreModeAggregatorFromScratch Phase 5 (tests)

Edge-case policy clarifications:
- If all axes are out-of-scope, core_mode is ESTOP and blocked_by includes MISSING (detail: no_in_scope_axes).
- Precedence order: stale/missing overrides estop/fault; estop overrides fault.
- Mixed scope is stable: out-of-scope axes do not block in-scope aggregates.

Tests added:
- tests/test_core_mode_aggregate.py: all out-of-scope ESTOP, stale overrides, estop precedence, multi-axis idle/armed.
