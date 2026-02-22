---
name: BirdsEyeMotionDiagnostics
description: Improve birds-eye diagnostics (status_in) for HiP, Core, and DenSi so we can see joystick→intent→cmd→apply and identify which gate blocks motion. No env vars, no behavior changes.
argument-hint: "Use profile 1dev_sim. status_in already present (net.status_in)."
---

# BirdsEyeMotionDiagnostics Agent

## Mission
Add first-class motion diagnostics to the birds-eye stream so we can quickly answer:
- Is HiP producing EnableAxis/JogWinch with correct m/s scaling (via VelMax)?
- Is Core accepting intents and generating non-zero cmd frames (and is enable true)?
- Is DenSi receiving cmd frames (ControlIN, SpeedSollIN) and applying them (vel_applied) or gating them?

## Constraints / Rules
- NO env vars.
- NO new sockets / sniffers / mirrors.
- NO behavior changes to motion logic (only diagnostics).
- Emission must be robust: never crash; tolerate missing fields.
- Keep noise low: emit_every ~= 0.5s or 1.0s.
- Use existing `status_in` transport (observability/status emitter already exists).

## Phase 0 — Baseline & Discovery
1) Run `pytest -q` (capture output).
2) Locate observability helpers:
   - where StatusEmitter is constructed (likely `core/observability.py` or similar)
   - how services emit status today (if any).
3) Identify where to hook for each component:
   - HiP: where intents are produced each tick and where params (VelMax) are visible
   - Core: where intents are applied and where per-axis cmd state exists
   - DenSi: where last cmd is decoded and applied

Write short notes to `archive/PATCH_NOTES.md`.

## Phase 1 — HiP birds-eye: joystick→scaled speed→intents
Implement in `src/steuerung3d/apps/yellow/controllers/hip_controller.py`:

Add a helper `_emit_birdseye_motion(snap, intents_out, ...)` called once per tick.

Fields to emit (flat keys are fine):
- `component="hip"`
- `axis_selected` (string; empty if none)
- `deadman` (bool)
- `select_hip` (bool)
- `joy_soll_speed_norm` (float)
- `velmax` (float; from params shown in hip)
- `joy_rate_mps` (float computed: norm * velmax; if velmax missing -> 0)
- `intents_out_types` (comma-joined unique type names)
- `intents_out_count` (int)
- `estop`, `fault`, `mode` (if present in snap/viewmodel)
- `sel`, `dm`, `enable` (if visible in hip state/viewmodel)
- `lease_state/claimed_owner` (if visible)

Summary string should be compact and human:
"hip axis=Anton dm=1 sel=1 estop=0 deadman=1 v=-0.30m/s out=[EnableAxis,JogWinch]"

If intents_out aren’t easily accessible, capture whatever “outgoing intents” list is passed to the sender in the controller/engine boundary.

## Phase 2 — Core birds-eye: intent ingress→axis cmd state
Implement in `src/steuerung3d/apps/core_udp_service.py` (or whichever module is the running core service):

Emit once per tick:
- `component="core"`
- `intents_in_count` (count processed since last emit)
- `intents_in_types` (unique types)
- per-axis cmd snapshot (for each axis, include):
  - `axis_id`
  - `cmd_enable`
  - `cmd_vel`
  - `cmd_sel/dm` if present
  - `lease/owner` if available
  - `gate_reason` (if core computes any gating flags)
Use a concise encoding:
- either include one dict per axis in a list field `axes=[{...}]`
- or flatten keys: `Anton.enable`, `Anton.vel`, etc.

Summary example:
"core in=[JogWinch,EnableAxis] Anton(enable=1 vel=-0.30)"

Important: do NOT add heavy formatting; keep it machine readable + human skim.

## Phase 3 — DenSi birds-eye: cmd rx + gates + applied
Implement in `src/steuerung3d/apps/den_si.py` (the actual DenSi process is better than the Yellow controller):

Emit once per tick:
- `component="densi"`
- `axis_id`
- `last_cmd_rx_age_ms` (if available; otherwise last cmd tick)
- decoded cmd fields:
  - `ControlIN`/enable
  - `SpeedSollIN` (raw)
  - `Mode` (E/G/etc)
  - `Intent` flag if present
- internal gates:
  - `estop`, `fault`
  - `ready_for_sollvel` / equivalent if exists
  - `lifetick_ok` / stale flags if exists
- applied:
  - `vel_applied`
  - `pos`, `vel` (sim plant)

Summary example:
"densi Anton ctrl=1 soll=-0.30 ready=1 estop=0 applied=-0.30"

## Phase 4 — Tests (lightweight)
- Add unit tests that constructing/using birds-eye emission functions does not crash when optional fields missing.
- Do not test full UDP delivery; just test formatting/data extraction.

## Acceptance Criteria
- `pytest -q` green.
- Running `python -m steuerung3d up --profile 1dev_sim` shows regular birds-eye lines for hip/core/densi.
- Birds-eye makes it obvious which gate is false if motion does not occur:
  - HiP: shows whether EnableAxis/JogWinch emitted and computed v
  - Core: shows whether cmd_enable/vel set for axis
  - DenSi: shows whether ControlIN + SpeedSollIN received and applied

## Deliverables
- Birds-eye diagnostics for hip/core/densi
- Notes in archive/PATCH_NOTES.md describing fields and where they come from
- Small tests guarding against crashes