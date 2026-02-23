# HiP core_mode refactor notes

Date: 2026-02-23
Branch: hip-coremode-cutover

## Where HiP reads mode

- HiP runtime consumes telemetry in [src/steuerung3d/apps/yellow/runtimes/hip_runtime.py](../../src/steuerung3d/apps/yellow/runtimes/hip_runtime.py).
  - Uses `snap.core_mode` for status/heartbeat.
  - Legacy `snap.mode` is still read defensively (may be empty after cutover).
- HiP engine evaluates mode in [src/steuerung3d/apps/yellow/engines/hip/engine.py](../../src/steuerung3d/apps/yellow/engines/hip/engine.py).
  - `mode_now = str(getattr(snap, "core_mode", ""))`.

## Motion intent gating conditions (current)

HiP emits motion intents (EnableAxis/JogWinch) only when all of the following are true:

1) `motion_axis_id` is resolved (selected axis or single-axis fallback).
2) `core_mode` is `LIVE`.
3) The axis claim owner matches the current HiP (`get_claim_owner(snap, axis_id) == hip_id`).
4) Deadman is held (`joy.deadman` is true).

Additional related gates:
- If deadman is false, HiP emits stop intents (EnableAxis False + JogWinch 0) for the motion axis.
- Select-hip (`joy.select_hip`) only affects auto-claim behavior, not motion gating directly.
- Core enforces select gating (`joy.select_hip`) when building command frames.

## Temporary debug logging

A temporary log line was added in the HiP runtime to capture:
- `core_mode`, `legacy_mode` (if present)
- `dm`, `sel`, `sp`
- `motion_enabled` (based on the gating conditions above)

This log is rate-limited to ~1 Hz and should be removed once refactor is complete.
