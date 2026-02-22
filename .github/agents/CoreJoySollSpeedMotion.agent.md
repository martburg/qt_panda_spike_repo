---
name: CoreJoySollSpeedMotion
description: Implement Option A: in Core, convert JoyStateUpdate.soll_speed (normalized) into motion intent (JogWinch/VelCmd) with scaling via VelMax (m/s). Add tests ensuring DenSi cmd frames become non-zero under deadman and proper gating.
argument-hint: "Run from repo root. Provide remote/local stack context if asked."
---

# CoreJoySollSpeedMotion Agent

You are a VSCode/Codex implementation agent working inside this repository.

## Mission
Wire joystick motion into the Core→DenSi pipeline by implementing **Option A**:
- Core receives `JoyStateUpdate(deadman, select_hip, soll_speed)` (normalized in [-1,1])
- Core converts this into the canonical motion intent used for DenSi command-frame generation
- **Scale normalized speed to m/s using VelMax** (not inside DenSi; scale in Core using params)
- Maintain existing safety gates (deadman/estop/lease/selection) and do not regress existing tests

## Non-goals
- Do not redesign the intent schema broadly
- Do not change DenSi physics or command parser semantics
- Do not implement Bird’s Eye DenSi debug in this ticket (separate ticket)
- Do not add new dependencies

## Constraints / Invariants
- `JoyStateUpdate` is already decoded and clamped (see `core/joy_state.py`, `protocol/codec.py`)
- Joystick speed is **normalized** at some stage; we must convert to **m/s** via `VelMax`
- Do not break:
  - `tests/test_joy_motion_pipeline.py`
  - `tests/test_hip_*`
  - PLC legacy codec roundtrips
- Follow existing architectural patterns: core intent handler emits canonical intents; cmd frame builder consumes canonical intents.

## High-level plan (phased)

### Phase 0 — Baseline & Discovery (no changes)
1) Run unit tests: `pytest -q`
2) Locate canonical motion intent + handler:
   - Search for `JogWinch` and/or existing motion intents and where they affect DenSi cmd frames
   - Identify where cmd frames for DenSi are assembled and what field represents velocity (m/s)
3) Locate parameter source for velocity limit:
   - Identify where `VelMax` is stored (param registry / telemetry snapshot / axis config)
   - Determine units (m/s) and how to read it inside Core

Deliverable: short notes in `archive/PATCH_NOTES.md` describing:
- Which intent type Core uses to drive DenSi velocity
- Which function builds DenSi cmd frames from intents
- Where VelMax lives and how to read it

### Phase 1 — Implement JoyStateUpdate → Motion intent emission (Core)
Implement Option A in the Core intent pipeline:
- In `src/steuerung3d/core/intent_handler.py`, in the `case JoyStateUpdate(...)` branch:
  - Keep updating stored `JoyState` (existing behavior)
  - If `deadman` is true:
    - Compute `v_mps = soll_speed_normalized * vel_max_mps`
    - Emit the canonical motion intent for axis `"Anton"` (or per selected axis if supported)
  - If `deadman` is false:
    - Emit a “stop” motion intent (velocity=0) to ensure release-to-stop semantics
- Ensure gating remains correct:
  - If the architecture uses lease/claim/sel/dm gating later, do not bypass it
  - Do not emit motion intent if core policy indicates it would be ignored (but still safe to emit stop)

Implementation detail:
- Do NOT hardcode vel_max constants.
- Read VelMax via the existing parameter access path used elsewhere in Core (param registry / axis config / telemetry state).
- If VelMax is not available, default to 0.0 m/s (safe) and log a debug message.

### Phase 2 — Tests
Add/extend tests to cover:
1) When deadman is true and `soll_speed=-1.0`, emitted motion intent has velocity `-VelMax` (m/s)
2) When deadman is false, emitted motion intent is “stop” (0 m/s)
3) The motion intent leads to non-zero cmd frames to DenSi in an integration-ish test (if cheap), or at least ensures the cmd builder sees the motion intent.

Prefer adding to existing test modules:
- `tests/test_joy_motion_pipeline.py` (best fit)
- Or create `tests/unit/test_core_joy_soll_speed_motion.py` if needed

### Phase 3 — Manual smoke
Document manual steps in `docs/MANUAL_TESTING.md` or `docs/dev_notes_recent.md`:
- Run `python -m steuerung3d up --profile 1dev_sim`
- Move joystick, confirm DenSi cmd frames contain non-zero velocities (Wireshark/telemetry)
- Confirm release-to-stop

## Acceptance Criteria
- `pytest -q` passes
- Moving joystick with deadman true produces DenSi cmd frames with **non-zero velocity fields** proportional to `VelMax`
- Releasing deadman produces stop semantics (velocity=0)
- No regressions in HiP UI joystick display
- No changes required in DenSi for scaling

## Deliverables
- Code changes in Core intent handling to emit motion intents
- Tests proving scaling + deadman gating
- Notes in `archive/PATCH_NOTES.md` summarizing the wiring and VelMax source