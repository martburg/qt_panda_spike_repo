---
name: HipModeTruthFix
description: Fix HiP mode truth: ensure birds-eye 'mode' matches the same state machine/flags that drive UI (EStop/Armed/Ready). Eliminate stale/incorrect mode reporting. Add tests.
argument-hint: "Use profile 1dev_sim; verify birds-eye hip mode changes when UI changes."
---

# HipModeTruthFix Agent

## Mission
Bring HiP mode reporting into sync with the actual UI state and the underlying controller/engine state machine.

Currently birds-eye shows `mode=IDLE` even when UI shows EStop/Armed/Ready.
We need one consistent "mode truth" that both UI and birds-eye report.

## Constraints
- No motion behavior changes in this ticket.
- Do not redesign the whole state machine; fix plumbing / mapping.
- Keep output stable and readable.
- pytest -q must stay green.

## Phase 0 — Discovery
1) Run pytest -q.
2) Identify where HiP UI derives status:
   - where "EStop", "Armed", "Ready" come from (viewmodel fields, snap flags, fsm state)
3) Identify where birds-eye hip line’s `mode` is sourced:
   - find the code that formats the hip birds-eye line (likely in hip controller or shared birds-eye formatter).
4) Find any mismatch:
   - UI uses `snap.mode` vs birds-eye uses `engine.state.mode` (or vice versa)
   - UI uses boolean flags while birds-eye prints a different enum/state name.

Write findings to archive/PATCH_NOTES.md including:
- current sources for UI state vs birds-eye state
- target source-of-truth field(s)

Stop after Phase 0.

## Phase 1 — Unify mode computation
Implement a single helper that computes "HiP mode" from the canonical state:
- Prefer: a single enum/state string that already exists and is stable (e.g. controller.fsm_state / engine.mode).
- If only booleans exist (estop/fault/armed/ready), define a deterministic mapping:
  - ESTOP if estop==True
  - FAULT if fault==True
  - READY/ARMED if ready and deadman (or as per existing UI semantics)
  - IDLE otherwise
But: match the UI semantics exactly.

Place helper in a sensible shared location, e.g.:
- `src/steuerung3d/apps/yellow/engines/hip/viewmodel.py` or
- `src/steuerung3d/apps/yellow/engines/hip/engine.py` or
- `src/steuerung3d/apps/yellow/controllers/hip_controller.py`

Then:
- Make UI use that same computed mode (or confirm it already does).
- Make birds-eye use that same computed mode.

## Phase 2 — Fix birds-eye hip row to use unified mode
Update the birds-eye emission for hip:
- Ensure it prints the unified mode string.
- Include supporting fields for validation (estop/fault/armed/ready) in the fields dict (not necessarily in the summary).

Acceptance for Phase 2:
- With `1dev_sim`, when UI shows EStop, birds-eye hip line shows mode=ESTOP (or whatever naming you use).
- When UI shows Ready/Armed, birds-eye hip line shows READY/ARMED accordingly.

## Phase 3 — Tests
Add unit tests to lock the mapping:
- given combinations of flags (estop/fault/armed/ready), computed mode matches expected.
- ensure birds-eye uses the helper (e.g. minimal call path test or direct helper test).

Prefer a new test:
- `tests/unit/test_hip_mode_mapping.py`

## Acceptance Criteria
- pytest -q green
- birds-eye hip `mode` changes in step with the UI indicators in `1dev_sim`
- No motion behavior changes yet

## Deliverables
- Unified mode helper + refactor of UI/birds-eye to use it
- Tests
- Patch notes in archive/PATCH_NOTES.md