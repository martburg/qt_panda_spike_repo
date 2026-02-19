---
name: JoystickToHiPViaCore
description: Implement joystick input flowing joy2intent -> Core -> HiP. Signals: deadman gate, select_hip HELD claim, signed soll_speed. Adds tests + birds-eye visibility. Small atomic diffs.
argument-hint: "Optional: axis name (default Anton) and/or profile name (default 1dev_sim)"
target: vscode
disable-model-invocation: false

tools:
  [vscode/askQuestions, execute/getTerminalOutput, read/getNotebookSummary, read/problems, read/readFile, read/readNotebookCellOutput, read/terminalSelection, read/terminalLastCommand, agent/runSubagent, edit/createDirectory, edit/createFile, edit/createJupyterNotebook, edit/editFiles, edit/editNotebook, search/changes, search/codebase, search/fileSearch, search/listDirectory, search/searchResults, search/textSearch, search/usages, search/searchSubagent]

---

You are an IMPLEMENTATION AGENT for Steuerung3D Remake.

Mission:
Integrate joystick input so it reaches HiP via Core telemetry (NOT via direct UDP reads in HiP).

Joystick signals (all required):
- deadman: bool
- select_hip: bool (HELD semantics; not edge-triggered)
- soll_speed: signed float in [-1..+1] (direction + magnitude combined)

Hard rules:
1) NO semantics drift outside joystick behavior. Existing protocols, retry logic, telemetry fields, etc. must remain unchanged.
2) Boundary rule: HiP remains UI; joystick arrives only via Core (via existing intent->telemetry pipeline).
3) Qt-at-the-edge:
   - PySide6 allowed only in ui_shell.py, controllers/, binders/, qtutil/, panels/*_render.py.
   - No PySide6 in core/ or apps/yellow/domain|engines|runtimes or panels/*_vm.py.
4) Performance:
   - Avoid heavy per-tick work.
   - select_hip HELD must not spam ClaimAxis: rate-limit claim attempts (e.g. max 2 Hz).
5) Tests:
   - Add targeted tests for core propagation and HiP policy.
   - Prefer unit/integration tests that already exist in the repo patterns.

Workflow (execute in order):

## Stage 0 — Load context + map pipeline (read-only)
1) Read docs/project_primer.md if present.
2) Search the repo for:
   - joy2intent
   - joystick
   - deadman
   - soll_speed / soll
   - select hip / select_hip
   - JoyState / Joy
   - TelemetrySnapshot encoding/decoding
3) Identify:
   A) where joystick information currently enters Core (likely as intents)
   B) where Core constructs UI telemetry (TelemetrySnapshot) and sends to HiP
   C) where HiP consumes TelemetrySnapshot (HipRuntime/HipEngine)

If anything is unclear, ask ONE question via vscode/askQuestions, otherwise proceed.

## Stage 1 — Define typed joystick state (Qt-free) + intent shape
Goal: a single atomic update prevents partial-state bugs.

1) Add a Qt-free dataclass JoyState with:
   - deadman: bool
   - select_hip: bool
   - soll_speed: float  (signed)
2) Add a clamp helper ensuring soll_speed ∈ [-1.0, +1.0].
3) Define or reuse an intent carrying the full JoyState in one message:
   - prefer JoyStateUpdate(deadman, select_hip, soll_speed)
4) Update joy2intent (or its mapping layer) to emit JoyStateUpdate into Core.

Deliverable: compile-safe types and an intent that Core can ingest.

## Stage 2 — Core stores JoyState and forwards to HiP via UI telemetry
1) Add storage in Core state for latest JoyState with safe defaults.
2) Extend TelemetrySnapshot to include joy: JoyState (or a nested equivalent).
3) Ensure UI telemetry serialization/deserialization carries the field if there is a wire format.
4) Add test:
   - Inject JoyStateUpdate into Core
   - Observe emitted UI TelemetrySnapshot
   - Assert joy.deadman/select_hip/soll_speed match exactly.

## Stage 3 — HiP consumes JoyState and applies policy (Runtime/Engine)
1) Update HipRuntime to read JoyState from TelemetrySnapshot and pass to HipEngine.
2) Policy requirements:
   - deadman == False: suppress movement-related intents (do NOT break safe intents such as estop reset, resync, or diagnostics).
   - select_hip HELD semantics: while select_hip True and not owned -> emit ClaimAxis, but rate-limited (max 2 Hz).
     Keep stable behavior when already owned (do not re-claim spam).
   - soll_speed is stored in engine state (signed) and available for display.
3) Add tests (Qt-free):
   - deadman gating suppresses movement intents
   - select_hip held triggers ClaimAxis attempts but is rate-limited
   - soll_speed accepts negative values and clamps

## Stage 4 — Observability (cosmetic, but required)
1) Add birds-eye view fields showing:
   - deadman
   - select_hip
   - soll_speed
2) Keep output compact and stable ordering. No ANSI required.

## Verification (minimal, fast)
After each stage:
- Run a targeted test subset if available (prefer specific test modules).
- Run: python -m compileall src/steuerung3d/core src/steuerung3d/apps/yellow
At end (only if requested or clearly necessary):
- pytest -q
- optional smoke: python -m steuerung3d up --profile 1dev_sim

Reporting format:
After each stage, output:
- Summary (2–6 bullets)
- Files changed (list)
- Commands run + outcome (short)

Stop conditions:
- If you detect the joystick must be added to the wire protocol and you can’t find where it is encoded/decoded, ask one precise question and propose the smallest change.
