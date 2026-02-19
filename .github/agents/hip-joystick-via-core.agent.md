---
name: hip-joystick-via-core
description: Integrate joystick input into HiP via Core telemetry (deadman, select_hip held, signed soll_speed).
prompt: You are a repo-executor for Steuerung3D Remake.

  Goal: Integrate joystick input into HiP via CORE telemetry (NOT direct UDP in HiP).
  Joystick signals:
  - deadman: bool (gate movement-related intents)
  - select_hip: bool (HELD semantics, not edge-triggered; while held attempt claim, rate-limited)
  - soll_speed: signed float in [-1..+1] (direction+speed combined)

  Hard constraints:
  1) NO semantics drift outside joystick integration.
  2) Qt boundaries remain:
     - PySide6 only in ui_shell.py, controllers/, binders/, qtutil/, panels/*_render.py.
     - No PySide6 in core/ or apps/yellow/domain|engines|runtimes or panels/*_vm.py.
  3) Performance: keep per-tick work small; rate-limit repeated intents.
  4) Add tests:
     - core propagation: joystick update reaches UI telemetry snapshot.
     - hip policy: deadman gating, held-claim with rate limit, signed soll_speed clamp.

  Implementation stages (execute in order):
  STAGE 0 — Map current pipeline
  - Find where joy2intent emits into core.
  - Find where core builds TelemetrySnapshot and sends to HiP.
  - Find where HiP consumes snapshot.

  STAGE 1 — Define JoyState and update intent
  - Add Qt-free dataclass JoyState(deadman, select_hip, soll_speed).
  - Clamp soll_speed to [-1, +1].
  - Prefer a single JoyStateUpdate intent carrying all three fields.

  STAGE 2 — Core stores and forwards JoyState in UI telemetry
  - Store latest JoyState in core with defaults.
  - Extend TelemetrySnapshot to include joy: JoyState.
  - Update UI telemetry serialization if needed.
  - Add a test proving propagation unchanged.

  STAGE 3 — HiP consumes JoyState via runtime/engine
  - HipRuntime extracts JoyState and passes to HipEngine.
  - HipEngine policy:
    - deadman false suppresses movement intents (don’t break resync/estop).
    - select_hip held attempts ClaimAxis while not owned, rate-limited (max 2 Hz).
    - soll_speed signed stored and surfaced in diagnostics.

  STAGE 4 — Observability
  - birds-eye shows deadman/select_hip/soll_speed compactly.

  Verification:
  - pytest -q
  - python -m compileall src/steuerung3d/core src/steuerung3d/apps/yellow
  - optional: python -m steuerung3d up --profile 1dev_sim
