# Semantic Ledger

This file records *declared* semantic changes (RefOS Lane 2) made during stabilization.

## 2026-02-24

- **Change:** Exclude transitions-based FSM tests from automated runs by default.
  - **Why:** The optional third-party dependency `transitions` is not required for core functionality and is not available in some CI/dev environments.
  - **How:** Introduced marker `requires_transitions` and opt-in environment gate `RUN_TRANSITIONS_TESTS=1`.
  - **Files:** `conftest.py`, `pytest.ini`, `tests/test_axis_fsm.py` (plus removal of redundant `tests/conftest.py`).
  - **Expected impact:** `pytest` default run skips those tests; developers can opt-in locally.

- **Change:** Switch PLC edge codec adapter to the canonical PLC protocol implementation.
  - **Why:** The placeholder `adapters/plc/plc_codec.py` was a scaffold with a non-canonical token layout; the source-of-truth is `KommAnton__MAIN.st` mirrored by `protocol/plc_codec.py`.
  - **How:** Replaced `adapters.plc.PlcCodec` to delegate encoding/decoding to `protocol.plc_codec`.
  - **Files:** `src/steuerung3d/adapters/plc/plc_codec.py`, `src/steuerung3d/adapters/plc/validate.py`.
  - **Expected impact:** PLC UDP payloads now follow the canonical token ordering; endpoint configs are required to be single-axis.

- **Change:** Consolidate runtime TOML configs under `/configs` only.
  - **Why:** Duplicate dev TOMLs under `src/steuerung3d/config/` created drift and ambiguity.
  - **How:** Removed `dev_*.toml` from the Python package directory; updated README to point to `/configs`.
  - **Files:** `src/steuerung3d/config/README.md` (and removed `src/steuerung3d/config/dev_*.toml`).
  - **Expected impact:** All tooling and documentation should reference `/configs/*` paths for runtime configuration.

## 2026-02-28 — One-shot derived invariants + core-mode contract tightening

**Lane:** 2 (Declared Semantic Fix)

### Change
1) One-shot signals (`estop_reset`, `resync`, `param_ops`) are now treated as **derived outputs**
   from per-axis state maps (canonical):
   - `estop_reset_req_by_axis`
   - `resync_req_by_axis`
   - `pending_param_ops_by_axis`

   Legacy globals remain as compatibility fallbacks, but the system’s source of truth is the per-axis maps.

2) `aggregate_core_mode` contract is tightened:
   - `motion_allowed` may only be true in `core_mode == LIVE` (existing invariant)
   - When `core_mode == LIVE`, `blocked_by` must not contain hard safety reasons.
     Currently allowed LIVE-only code: `NO_SELECT_FOR_MOTION`

### Motivation
- Prevent invariant drift caused by dual tracking (global bool/list + per-axis maps)
- Make mode aggregation semantics explicit and enforceable in tests
- Reduce “heisenbugs” from stale one-shot flags surviving beyond a tick

### Tests
- Added LIVE+Select motion_allowed=true test
- Existing aggregation tests continue to cover the main state ladder

### Notes
- Multi-axis routing in core_udp_service continues to route per-axis param ops and reset pulses strictly.
- `MachineState.clear_one_shots()` centralizes one-shot clearing to keep the tick loop clean.
- Bugfix/tightening: `clear_one_shots` is now a real `MachineState` method (was accidentally module-level in one snapshot), and the engine uses `state.clear_transients()` for end-of-tick cleanup.


## 2026-03-01 — HiP axis picker starts unattached and lists live DenSi devices only

**Lane:** 2 (Declared Semantic Fix)

### Change
- The HiP axis picker (`cmbAxis`) now **starts in `NotAttached`** on cold boot.
- The picker list now contains **live DenSi devices only**, based on `TelemetrySnapshot.densis[...].online`.
  (Previously it was derived from `snap.axes` keys, which can include configured axes even when no DenSi is running.)
- If the operator is already attached to an axis and it goes offline, that axis remains visible in the picker
  so the operator can intentionally release it.

### Motivation
- Avoid accidental implicit attachment caused by a Qt default combobox selection.
- Present the operator with the correct mental model: *"pick a running DenSi to connect"*.
- Fix a smoke-test failure where the picker listed all configured axes (Anton/Burt/Cecil/Debby/SIMUL) but none were reachable.

### Files
- `src/steuerung3d/apps/yellow/engines/hip/step_context.py`
- `src/steuerung3d/apps/yellow/binders/hip_qt_binder_apply_impl.py` (dedupe NotAttached; follow VM selection)
- `src/steuerung3d/apps/yellow/binders/hip_qt_binder_init_impl.py` (force cold-boot NotAttached in combobox)

### Tests
- Updated `tests/unit/test_hip_runtime.py` fixture to include `TelemetrySnapshot.densis` so Hip runtime unit tests continue to model discovery.

## 2026-03-03 — JogCartesian gated by RigMode.SYNC_ACTIVE

**Change:** `JogCartesian` is now accepted only when the rig workflow is in `RigMode.SYNC_ACTIVE` (in addition to the existing requirements: LIVE core_mode, no ESTOP/FAULT, and matching rig lease).

**Why:** Cartesian motion is defined as “rig/kinematics active” only during SYNC_ACTIVE; this prevents accidental cartesian motion during manual setup modes.

**Tests:** `tests/test_jog_cartesian_gate.py`


## 2026-03-03 — DenSi E-Stop adds STOPPING state and records coastdown distance

**Lane:** 2 (Declared Semantic Fix)

### Change
- DenSi E-Stop ladder now includes an explicit `EStopState.STOPPING` state.
  - On trip/OK-chain fault, if the axis is still moving, the ladder enters `STOPPING`.
  - Once the simulated axis speed falls below a small epsilon, the ladder transitions to `ESTOP` (fully stopped).
- During E-Stop, commanded speed is still dropped to `0` immediately, but the DenSi sim no longer hard-zeros the *actual* speed.
  Instead, the plant ramps down with `DccMax` so we can compute a realistic stop distance.
- Cut markers now latch **before** the deceleration step so `CutVel` reflects the actual speed at the moment E-Stop is entered.
- Cut markers now latch **before** the deceleration step so `CutVel` reflects the actual speed at the moment E-Stop is entered.
- Cut marker latch trigger tightened: latch on **cause-edge** (trip bits / OK-chain fault became active),
  not merely on the `state.estop` edge. This avoids false-zero latches when the device is already in
  a non-ready ESTOP-like state at startup.
- New parameter `PosDiffStop` is published once the axis stops (and `PosDiffFor` is aligned to the same value for UI compatibility):
  - `PosDiffStop = pos_stop - CutPos`

### Motivation
- Match real-world “commanded=0, actual decelerates with Dcc” behavior.
- Provide a deterministic, inspectable “distance traveled after E-Stop” metric for diagnostics.

### Files
- `src/steuerung3d/apps/yellow/engines/densi/types.py`
- `src/steuerung3d/apps/yellow/engines/densi/estop_fsm.py`
- `src/steuerung3d/apps/yellow/engines/densi/engine.py`
- `src/steuerung3d/apps/yellow/engines/densi/step_impl.py`
- `src/steuerung3d/apps/yellow/engines/densi/plc_anton_vel_cmd.py`
- `src/steuerung3d/apps/yellow/engines/densi/motion_clamp.py`
- `src/steuerung3d/apps/yellow/engines/densi/cut_markers.py`
- `src/steuerung3d/apps/yellow/engines/densi/param_defaults.py`

## 2026-03-03 — ReSync arms live Cut baseline; show cut markers in IDLE/ESTOP (hide in SYNC)

**Lane:** 2 (Declared Semantic Fix)

### Change
- `btnDiagResync` (HiP) now enables whenever attached, not modal-locked, and `last_mode == IDLE` (no longer depends on banner `estate`).
- DenSi `ReSync` no longer clears Cut markers to `0`. Instead it **arms live baseline tracking**:
  - while armed, DenSi updates `CutPos/CutVel/CutTime` to the current actual position/velocity every tick
  - when an E-Stop *cause* becomes active (trip bit set or OK-chain fault), the Cut markers **freeze** at that moment
- `PosDiffFor` is reserved for the Cut-marker distance (`pos - CutPos`) and is no longer overwritten by the PLC-faithful loop.
  The setpoint-based diagnostic is now published as `PosDiffSoll`.
- HiP Cut markers are now **visible in IDLE and ESTOP**, but hidden while in `SYNC_*` modes.

### Motivation
- Match operator workflow: baseline starts at 0 on boot, Resync “follows” until the next E-Stop, then freezes so coastdown distance is meaningful.
- Avoid “PosDiff == Pos” artifacts caused by `CutPos` staying at 0 and by `PosDiffFor` being clobbered by unrelated diagnostics.

### Files
- `src/steuerung3d/apps/yellow/engines/hip/attach_state.py`
- `src/steuerung3d/apps/yellow/engines/hip/step_impl.py`
- `src/steuerung3d/apps/yellow/engines/hip/presentation.py`
- `src/steuerung3d/apps/yellow/engines/densi/engine.py`
- `src/steuerung3d/apps/yellow/engines/densi/step_impl.py`
- `src/steuerung3d/apps/yellow/engines/densi/resync.py`
- `src/steuerung3d/apps/yellow/engines/densi/cut_markers.py`
- `src/steuerung3d/apps/yellow/engines/densi/plc_anton_vel_cmd.py`
- `src/steuerung3d/apps/yellow/engines/densi/param_defaults.py`

## 2026-03-06 — Stable HiP device telemetry projection in multi-HiP fanout

**Lane:** 2 (Declared Semantic Fix)

### Change
- In fanout mode, shared pool telemetry continues to be broadcast to all HiPs, but the top-level device-scoped surface (`params`, PLC uplink fields/tail, estop word, param commit state) is now projected per HiP from its attached axis only.
- If a HiP is unattached, the device-scoped top-level telemetry surface is cleared instead of drifting between whichever DenSi updated last.
- HiP presentation and parameter/session UI now consume the axis-scoped view rather than the raw shared fanout snapshot.

### Motivation
- Fix manual smoke-test bug where HiP readouts switched unpredictably between DenSis, including while unattached.
- Keep shared discovery/global pool visibility while making the main device panel stable and authoritative per HiP.

### Files
- `src/steuerung3d/core/telemetry_axis_view.py`
- `src/steuerung3d/apps/yellow/engines/hip/step_impl.py`
- `tests/test_telemetry_axis_view.py`
- `tests/test_hip_fanout_presentation.py`

- 2026-03-06 Lane 2: separate attachment from live console lane selection. JoyState/JoyStateUpdate now carry selected_axes; joy2intent emits global lane selection only (no auto-claim/direct jog). HiP motion resolves through current HiP↔DenSi attachment, deselect/deadman force zero velocity, and birds-eye reports attached lanes, selected lanes, deadman, and resolved moving targets.


- Lane 2 compat refinement: command-frame motion resolution keeps new lane semantics for explicit `selected_axes` + deadman, but preserves legacy `select_hip=True` pass-through for older tests/stacks that do not yet emit explicit lane selections.
