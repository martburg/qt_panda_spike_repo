# HiP sel-gate + status inventory

## Status printing (birds-eye)
- Birds-eye output is built from structured status summaries in the supervisor.
  - [src/steuerung3d/core/stack_runtime.py](src/steuerung3d/core/stack_runtime.py#L446) collects status heartbeats and prints the summary for each process.
- HiP summary is emitted from the controller (primary) and runtime (fallback):
  - [src/steuerung3d/apps/yellow/controllers/hip_controller.py](src/steuerung3d/apps/yellow/controllers/hip_controller.py#L116) `HiPController._emit_birdseye_motion()` builds the "hip ..." line.
    - Current behavior: `mode` is sourced from `snap.core_mode` (authoritative), while `estate` is still included in fields for UI state.
  - [src/steuerung3d/apps/yellow/runtimes/hip_runtime.py](src/steuerung3d/apps/yellow/runtimes/hip_runtime.py#L314) `HipRuntime._emit_status()` emits a low-rate heartbeat.
    - Current behavior: `mode` is `self._last_mode` (core_mode) and `estate` remains a separate field.

## Motion emission / gating
- Motion intents are emitted in [src/steuerung3d/apps/yellow/engines/hip/engine.py](src/steuerung3d/apps/yellow/engines/hip/engine.py#L86) `HipEngine.step()`.
- Gating conditions (current behavior):
  - `snap.core_mode` must be `LIVE`.
  - The axis must be resolved (selected/fixed, or single-axis fallback).
  - Axis must be claimed by this HiP (`get_claim_owner(...) == hip_id`).
  - Deadman must be held.
  - Nonzero speed is allowed only when `joy.select_hip` is true; otherwise speed is forced to 0.0.
- Claim intents are gated separately: when `joy.select_hip` is true and the axis is not owned, a `ClaimAxis` is emitted (rate-limited).
