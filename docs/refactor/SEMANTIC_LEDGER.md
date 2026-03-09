# Steuerung3D Semantic Ledger

This document tracks all declared semantic changes.

Only Lane 2 changes appear here.

---

## Template

### Entry ID:
### Date:
### Subsystem:
### Change Type: (ownership / aggregation / lifecycle / config / pipeline / naming / other)
### Motivation:

### Before:
Describe old behavior precisely.

### After:
Describe new behavior precisely.

### Impact Surface:
Modules/files affected.

### Tests:
List tests added or modified.

### Smoke Verification:
Describe manual runtime check result.

### Decision Owner:
Human / Joint

---

# Entries

This file mirrors the repo-root `SEMANTIC_LEDGER.md`.

If you update semantics, update both:
- `/SEMANTIC_LEDGER.md`
- `/docs/refactor/SEMANTIC_LEDGER.md`

See latest entry in the repo root.

## 2026-03-09 — Intent dispatch typing cleanup at core intent boundary

**Lane:** 2 (Declared Semantic Fix)

### Change
- Replaced the broad `Dict[Type[Intent], Callable[[MachineState, Intent], None]]` dispatch tables in `core/intent_handler_impl.py` with explicit narrowing helpers:
  - `_apply_ungated_intent(...)`
  - `_apply_live_only_intent(...)`
  - `_motion_axis_id(...)`
- The ungated/live-only split remains the same, but subtype handlers are now only called after concrete intent narrowing.

### Motivation
- Remove static ambiguity at the core intent application boundary.
- Eliminate subtype attribute access through broad `Intent` call signatures without hiding the issue behind `cast(...)` or `# type: ignore`.

### Files
- `src/steuerung3d/core/intent_handler_impl.py`
- `tests/test_intent_handler_gated_dispatch.py`

### Expected impact
- No intended runtime behavior change.
- Same claim/release, control-mode, motion gating, estop, reset, and resync behavior; clearer and safer dispatch structure for future refactors.
