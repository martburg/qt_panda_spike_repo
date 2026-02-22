---
name: HipJoySollSpeedMotionClean
description: Clean architecture: JoyStateUpdate remains normalized input state; Core stops mapping it to motion; HiP scales normalized soll_speed to m/s using VelMax (param truth from DenSi mirrored into HiP) and emits EnableAxis + JogWinch into Core. Add tests.
argument-hint: "Run from repo root. Use profile 1dev_sim for smoke."
---

# HipJoySollSpeedMotionClean Agent

You are a VSCode/Codex implementation agent working inside this repository.

## Mission
Refactor the joystick-to-motion architecture to match the intended layering:

- `JoyStateUpdate(deadman, select_hip, soll_speed)` remains **input state** (normalized speed).
- **Core** must NOT derive motion directly from `JoyStateUpdate`.
- **HiP** is the place where normalized `soll_speed` is scaled to **m/s** using **VelMax from parameters** (truth originates in DenSi; HiP mirrors it and uses it once connected).
- HiP emits canonical motion intents into Core:
  - `EnableAxis(axis_id, enable=True/False)` driven by deadman/select gating
  - `JogWinch(winch_id=axis_id, rate=<m/s>)` driven by scaled joystick speed
- Existing safety policy and lease/selection gates must remain enforced (do not bypass).
- All tests must remain green; add new tests where necessary.

## Context / Key design notes
- Joy speed is normalized in [-1, 1] upstream (joy2intent).
- VelMax is a parameter: canonical truth lives in DenSi; when HiP has contact it shows/mirrors those params.
- Scaling must therefore happen in HiP, not DenSi, and not Core.
- Multi-axis support: do NOT hardcode "Anton" unless the current architecture already does for 1-axis; prefer using the selected axis / known rig axes.

## Non-goals
- No Bird’s Eye DenSi debug UX in this ticket
- No transport/protocol redesign
- No new dependencies

---

## Phase 0 — Baseline & Discovery (no behavior changes)
1) Run: `pytest -q`
2) Locate:
   - Where HiP receives/maintains `JoyState` (JoyStateUpdate)
   - Where HiP emits intents into Core (existing pipeline)
   - Existing joy-motion mapping in HiP (`apps/yellow/domain/joy_motion_map.py`, Hip engine)
   - Where VelMax is accessible in HiP (params/telemetry snapshot/viewmodel)
3) Document findings in `archive/PATCH_NOTES.md`:
   - "Before" flow and "Target" flow
   - Exact place in HiP to apply scaling and emit intents

Stop after documenting Phase 0 findings.

---

## Phase 1 — Remove Core bridge (JoyStateUpdate → motion)
If Core currently converts `JoyStateUpdate` into `JogWinch`/velocity changes, remove that behavior.

Requirements:
- Core should still store the latest `JoyState` if needed for UI/telemetry
- Core should NOT set axis velocity from `JoyStateUpdate`
- Ensure existing tests updated accordingly (some tests added for Option A may need to move)

---

## Phase 2 — Implement scaling + motion emission in HiP
Implement in HiP engine (not Core, not DenSi):

- When HiP has valid joystick state:
  - Determine selected axis (prefer: selected/active axis in HiP state; fallback: if exactly 1 axis exists, use it)
  - Read `VelMax` param for that axis from HiP’s param/telemetry model
    - If unavailable: treat VelMax=0.0 (safe) and log debug
  - Compute `rate_mps = joy.soll_speed_normalized * vel_max_mps`
  - Emit intents to Core:
    - If deadman true (and any other required HiP gates): `EnableAxis(True)` then `JogWinch(rate_mps)`
    - If deadman false: `JogWinch(0.0)` then `EnableAxis(False)` (release-to-stop)
- Ensure intent emission is idempotent and does not spam enable/disable excessively:
  - Use "last sent" caching if there is an established pattern
  - At minimum, avoid emitting repeated identical intents every tick if possible

Important:
- Keep existing HiP UI joystick display behavior
- Do not break existing Hip→Core intent semantics (EStopReset etc.)
- Do not hardcode VelMax constants; always use param

---

## Phase 3 — Tests
Update or add tests to prove the new layering:

1) Core no longer changes cmd velocities from JoyStateUpdate alone.
2) HiP scales `soll_speed` using `VelMax` and emits:
   - `EnableAxis(True)` when deadman true
   - `JogWinch(rate == soll_speed * VelMax)`
3) Integration-ish: with a minimal rig state, feeding JoyStateUpdate into HiP should result in Core cmd frame to DenSi with:
   - enable/control asserted
   - non-zero velocity when soll_speed != 0

Prefer reusing existing tests:
- `tests/test_joy_motion_pipeline.py`
- `tests/unit/test_hip_engine.py` / `test_hip_viewmodel_joy.py`
- add a new focused unit test if needed: `tests/unit/test_hip_joy_soll_speed_motion_clean.py`

All tests: `pytest -q` must pass.

---

## Phase 4 — Manual smoke & docs
Update `docs/MANUAL_TESTING.md` with a short section:
- Run `python -m steuerung3d up --profile 1dev_sim`
- Confirm: joystick moves show in HiP
- With deadman pressed: DenSi reacts (cmd velocity non-zero)
- Release deadman: stop & disable
- Confirm scaling: full deflection yields approx ±VelMax

---

## Acceptance Criteria
- Core no longer derives motion from JoyStateUpdate.
- HiP scales normalized joy speed using VelMax (param truth from DenSi mirrored into HiP).
- HiP emits EnableAxis + JogWinch into Core, resulting in DenSi motion in `1dev_sim`.
- `pytest -q` is green.
- Manual testing steps documented.

## Deliverables
- Refactor changes (Core + HiP)
- Tests
- Notes in `archive/PATCH_NOTES.md`
- Manual smoke documentation