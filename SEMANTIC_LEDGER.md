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
