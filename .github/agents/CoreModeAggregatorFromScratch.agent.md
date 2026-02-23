---
name: CoreModeAggregatorFromScratch
description: Build a new Core mode aggregator from scratch implementing the full safety ladder ESTOP→IDLE→ARMED→READY→LIVE based on per-axis DenSi safety state (incl. key1/key2 scope + chkbTaster) plus operator (JoyStateUpdate) and explicit live request. Upgrade birds-eye into a “Frederik panel”. Keep HiP thin: Core is the source of truth for LIVE. Add tests.
argument-hint: "Start with profile 1dev_sim (single axis Anton). Then extend to multi-axis. Must keep pytest green."
---

# CoreModeAggregatorFromScratch Agent

## Mission
Implement **Core mode** as a deterministic aggregation over per-axis safety states, emulating the real global SafetyPLC (“Frederik”) behavior, with these modes:

- `ESTOP`
- `IDLE`
- `ARMED`
- `READY`
- `LIVE`

Core mode must be the **single source of truth** used by Yellow UI/birds-eye. HiP remains minimal: it may **request** transitions (reset/live), but Core decides based on the aggregate safety facts.

Deliver a robust birds-eye “Frederik panel” and unit tests locking the ladder.

---

## Ground Rules / Non-goals
- **No env vars**. Configuration only.
- Do not implement full physical SafetyPLC; implement the **state reduction** faithfully from DenSi telemetry facts.
- Avoid touching motion logic except where it must be gated by `core_mode==LIVE` (likely already).
- Reset policy stays: **only the attached/lease-owner HiP may reset its axis**.
- Deterministic: the same inputs yield the same core_mode each tick.
- Emit “why” diagnostics (blocked_by) to birds-eye.

---

## Definitions (Source of Truth)
### Inputs to aggregation (per tick)
For each axis `a` in `rig.axes`:
- `in_scope[a]` : bool  (key1/key2 inclusion logic)
- `axis_estop[a]` : bool
- `axis_started[a]` : bool   (post ESStart)
- `axis_fault[a]` : bool
- `axis_taster_enabled[a]` : bool (chkbTaster / arming enabled)
- `axis_armed[a]` : bool  (arming completed / armed state)
- `axis_ready[a]` : bool  (ready state)
- `axis_age_ms[a]` : int (staleness)
- `axis_owner[a]` : str|None (lease/claim owner hip_id)

Global/operator inputs:
- `joy_deadman` : bool (from JoyStateUpdate)
- `joy_select` : bool
- `live_request` : bool (explicit intent, rate-limited)
- `estop_reset_requests` : list of axis-scoped reset intents (already policy-checked)
- `disarm_request` : optional (if exists; otherwise ignore)

### Outputs
- `core_mode` ∈ {ESTOP, IDLE, ARMED, READY, LIVE}
- `blocked_by` list of reasons (axis-scoped and global)
- `axis_gate[a]` : derived per-axis gating summary for birds-eye (optional but helpful)

---

## Ladder Semantics (Implement Exactly)
Compute the aggregate state based on **in-scope axes only**.

1) **ESTOP**
Core is `ESTOP` if any in-scope axis:
- is stale beyond a threshold OR missing telemetry
- or `axis_estop == True`
- or `axis_fault == True` (if fault implies estop; otherwise treat separately but still blocking)

2) **IDLE**
Core is `IDLE` if not ESTOP and any in-scope axis is not “started”:
- `axis_started == False`
This mirrors: after reset attempt, operator presses **ESStart** on each axis.

3) **ARMED**
Core is `ARMED` if:
- not ESTOP
- all in-scope axes are started
- and at least one in-scope axis is in an “arming flow” OR all axes are past “idle”
- but not all required axes are READY yet

Interpretation with `axis_taster_enabled`:
- If `axis_taster_enabled == False` for an axis, that axis should not block ARMED→READY on “armed” but may still block READY depending on your current DenSi ladder truth (see Phase 0).

4) **READY**
Core is `READY` if:
- not ESTOP
- all in-scope axes started
- and all in-scope axes satisfy the readiness requirement:
  - If `axis_taster_enabled[a] == True` → require `axis_ready[a] == True`
  - If `axis_taster_enabled[a] == False` → define requirement via existing DenSi ladder:
    - either `axis_started[a]==True` is sufficient
    - or require `axis_armed[a]==True`
  Use Phase 0 to confirm which rule matches existing DenSi truth.

5) **LIVE**
Core enters `LIVE` only if:
- Core is READY (as computed above)
- and there is an explicit **live request** (intent), AND
- `joy_deadman == True` and `joy_select == True` (operator gating)

Core exits LIVE when:
- READY no longer holds (any axis regresses) → drop to appropriate state
- or `joy_deadman` becomes False → drop back to READY (preferred)
- or an explicit disarm/stop intent exists (optional)

---

## Phase 0 — Discovery & Mapping (Stop after this phase)
1) `pytest -q`
2) Identify where DenSi telemetry exposes:
- `estop`, `fault`, `started/ESStart`, `taster enabled`, `armed`, `ready`
3) Identify how key1/key2 scope is represented now (per-axis config/telemetry).
4) Determine current “READY” meaning in DenSi birds-eye (`ready=1`) and what prereqs it implies.
5) Document in `archive/PATCH_NOTES.md`:
- exact field names and modules
- definitive rule for ARMED/READY when `taster_enabled` is false
- staleness threshold constants (if any) used elsewhere

**STOP** after writing Patch Notes.

---

## Phase 1 — New core aggregation module (pure + testable)
Create `src/steuerung3d/core/mode_aggregate.py`:

- dataclasses:
  - `AxisSafetyFacts`
  - `AggregateInputs`
  - `AggregateResult` (mode, blocked_by, optional per-axis gates)
- function:
  - `aggregate_core_mode(inputs: AggregateInputs) -> AggregateResult`

The function must:
- ignore out-of-scope axes
- treat missing/stale as blocking ESTOP
- compute `blocked_by` reasons with clear codes:
  - `STALE`, `ESTOP`, `FAULT`, `NOT_STARTED`, `NOT_READY`, `NO_SCOPE`, `NO_LIVE_REQUEST`, `NO_DEADMAN`, `NO_SELECT`

---

## Phase 2 — Wire into Core runtime
In the core service tick loop (e.g. `src/steuerung3d/apps/core_udp_service.py`):
- Build `AxisSafetyFacts` list from the latest per-axis telemetry snapshots.
- Compute `in_scope` based on key1/key2 rules.
- Get `joy_deadman`, `joy_select` from latest JoyStateUpdate held in core state.
- Define `live_request` as presence of `RequestLive`/`ArmLiveMode` intent in this tick (see Phase 3).
- Call `aggregate_core_mode(...)` each tick and set `state.mode` accordingly.
- Ensure existing mode-gated intent handling still works (LIVE only).

---

## Phase 3 — Explicit live request intent + policy
Add/confirm an explicit intent type:
- `RequestLive()` or reuse `ArmLiveMode()` if already present.

Rules:
- HiP may emit `RequestLive` only when its local ladder is READY and operator holds dm+select.
- Core accepts `RequestLive` only when aggregate READY is true and dm+select are true.

Also implement live exit:
- if dm goes false, core falls back to READY.

Do NOT make live implicit from dm+select alone.

---

## Phase 4 — Birds-eye “Frederik panel”
Upgrade core birds-eye to show:
- `core_mode=<...>`
- `blocked_by=[...]` (top reasons)
- `joy_dm`, `joy_sel`, `live_req_seen`
- Per-axis list (compact):
  - `axis estop fault started taster armed ready in_scope owner age_ms`
- Include counters:
  - `reset_denied`
  - `live_denied` (if request rejected) with last reason

This panel must make it obvious why the system is not READY or LIVE.

---

## Phase 5 — Tests
Add unit tests for the pure aggregator:
- out-of-scope axis does not block
- any stale/missing blocks ESTOP
- estop blocks
- not-started => IDLE
- readiness rules for taster enabled/disabled
- LIVE requires READY + live_request + dm + sel
- LIVE drops to READY when dm false

Add integration-level tests (light):
- core accepts/denies RequestLive appropriately (policy)
- reset policy remains intact

`pytest -q` must remain green.

---
## Acceptance Criteria
With `1dev_sim` (single axis Anton):
1) Boot: core shows `ESTOP` until DenSi reset/start clears it.
2) After ESStart: core transitions to `IDLE`.
3) After arming path: core transitions to `ARMED` then `READY` consistent with DenSi.
4) When operator holds dm+select and requests live: core becomes `LIVE`.
5) On deadman release: core returns to `READY`.

Birds-eye must clearly show reasons for any blocked transition.
