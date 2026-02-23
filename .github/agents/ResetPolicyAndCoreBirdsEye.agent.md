---
name: ResetPolicyAndCoreBirdsEye
description: Enforce per-axis EStopReset policy (only attached/lease-owner HiP may reset its DenSi). Improve birds-eye into a core “Frederik panel” showing per-axis scope, estop ladder, attachment, and block reasons. No env vars. Keep pytest green.
argument-hint: "Use profile 1dev_sim. Verify birds-eye lines and that reset intent is dropped when not attached."
---

# ResetPolicyAndCoreBirdsEye Agent

## Mission
1) **Policy:** Ensure an EStop reset request can only affect the DenSi/axis the requesting HiP is attached to (or lease-owner of). Prevent cross-axis resets.
2) **Core UI:** Improve birds-eye into a “Frederik panel” (core safety aggregator view) that clearly shows:
   - core mode (ESTOP/IDLE/READY/LIVE)
   - per-axis ladder state and scope
   - attachment/lease owner
   - why core is blocked (which axis and which condition)
   - whether EStopReset is currently allowed for that axis and requesting hip

## Non-goals
- Do not implement full safetyPLC emulation beyond diagnostics display.
- Do not change motion semantics or introduce new debug sockets.
- Do not add new external dependencies.

## Constraints / Invariants
- “Attached to axis” must be derived from existing lease/claim/attachment state.
- The system must be robust even if attachment info is missing; default to safe (deny reset).
- All changes must be test-covered and `pytest -q` must stay green.

---

## Phase 0 — Discovery (no behavior change)
1) Run `pytest -q`
2) Locate:
   - Intent type(s) for estop reset: `RequestEstopReset` / `EstopReset` / similar
   - Where Core routes reset commands to DenSi command frames or per-axis outputs
   - How Core identifies the origin of an intent (hip_id / sender identity)
   - Where attachment/lease ownership is stored:
     - e.g. `state.leases`, `axis.claim_owner`, `hip_id`, `lease_owner`
   - Where birds-eye lines are emitted and how to add per-axis structured fields
3) Write findings to `archive/PATCH_NOTES.md`:
   - exact file/function names for reset routing
   - exact data path for attachment/lease owner
   - proposed minimal field list for Frederik panel

Stop after Phase 0 notes.

---

## Phase 1 — Make reset axis-scoped and enforce policy in Core
### 1.1 Ensure reset intent is axis-scoped
If `RequestEstopReset` does not carry axis_id, update schema to:
- `RequestEstopReset(axis_id: str, hip_id: str="")` (or equivalent existing fields)
If it already carries axis_id, keep it and document.

Update:
- intent dataclass in `src/steuerung3d/core/intents.py`
- codec encode/decode in `src/steuerung3d/protocol/codec.py` (and `protocol/codec.py` mapping table)
- any callsites in HiP that emit reset to include axis_id

### 1.2 Enforce “only attached hip can reset” in Core
In core intent handling/routing (likely `src/steuerung3d/core/intent_handler.py` or `apps/core_udp_service` path):
- When receiving `RequestEstopReset(axis_id=...)`:
  - Determine `owner = get_claim_owner(state, axis_id)` or `lease_owner` for that axis
  - Determine `sender_hip_id` from intent (preferred) or from message metadata if available
  - If `sender_hip_id != owner` (or not attached):
    - Drop intent (no effect)
    - Emit a birds-eye policy event / increment counter: `reset_denied += 1`
    - Include reason: `not_owner`
  - Else:
    - Allow and route to DenSi command for that axis

Safe default:
- If owner cannot be determined or sender cannot be trusted, deny reset.

### 1.3 Update HiP to only emit reset for its attached axis
In HiP logic where reset button triggers:
- determine currently attached/selected axis
- emit `RequestEstopReset(axis_id=<that axis>, hip_id=<this hip>)`
- If no axis attached/selected, do not emit; optionally show UI disabled state (diagnostics only)

---

## Phase 2 — “Frederik panel” in birds-eye (Core line)
Enhance birds-eye emission for Core:
- Add a single compact summary line plus structured fields.

### Summary should include:
- `core_mode=<...>`
- `blocked_by=[axis:reason,...]` (first 1–3 reasons)

### Fields should include per-axis table in a structured list:
For each axis:
- `axis_id`
- `in_scope` (from key1/key2 / listed logic, if available; else assume true)
- `axis_mode` or ladder flags:
  - `estop` `fault` `started` `armed` `ready`
- `owner_hip_id` (lease/claim)
- `reset_allowed` (boolean computed: owner exists + axis in estop + reset_possible)
- optionally `reset_denied_count` per tick

Keep it lightweight:
- emit_every 0.5–1.0s
- do not spam logs

Also add a small “policy” section:
- `last_reset_request = {axis_id, sender_hip_id, allowed, reason}`

---

## Phase 3 — Tests
Add unit tests to cover policy:
1) Given axis owner = hipA:
   - reset from hipA to axis -> allowed (routes)
   - reset from hipB to axis -> denied (no effect)
2) Missing owner/sender -> denied
3) Codec roundtrip for RequestEstopReset includes axis_id (and hip_id if present)

Add tests for birds-eye formatting robustness:
- core birds-eye emitter does not crash with missing axis scope fields

Preferred test locations:
- `tests/test_core_reset_policy.py`
- `tests/test_protocol_codec_intents.py` (if exists)
- or extend existing tests.

---

## Acceptance Criteria
- Reset cannot be applied cross-axis: only attached/lease-owner HiP can reset its axis.
- Denied resets are visible in birds-eye (core policy diagnostic).
- Birds-eye “Frederik panel” shows:
  - per-axis ladder and attachment/ownership
  - reasons blocking core from leaving ESTOP/IDLE/READY
- `pytest -q` green.

## Deliverables
- Policy enforcement in Core
- Updated intent schema (if needed) and callsites
- Birds-eye Frederik panel enhancements
- Tests
- `archive/PATCH_NOTES.md` updated