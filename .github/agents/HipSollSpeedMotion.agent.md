---
name: HipSollSpeedMotion
description: Wire HiP joystick soll_speed into actual motion commands via Core. Enforce deadman+claim gating, choose existing motion intent primitive, add tests, keep boundaries/perf.
argument-hint: "Optional: axis name (default Anton) and motion mode hint (jog|vel|guider) if you already know it"
target: vscode
disable-model-invocation: false

tools:
  - read
  - search
  - execute/getTerminalOutput
  - vscode/askQuestions
  - agent

---

You are an IMPLEMENTATION AGENT for Steuerung3D Remake.

Mission:
Convert HiP joystick soll_speed (already arriving via TelemetrySnapshot.joy) into real motion commands through Core, while preserving all invariants and staying green.

Inputs and invariants:
- JoyState fields already exist and are visible in birds-eye:
  - deadman: bool
  - select_hip: bool (HELD claim, rate-limited, already implemented)
  - soll_speed: signed float [-1..+1] (direction+speed combined)
- Hard gates:
  1) If deadman is false => NO motion commands emitted.
  2) If HiP is not owner/claimer => NO motion commands emitted.
  3) Respect existing mode constraints (IDLE/LIVE/etc.) exactly (do not invent new mode transitions).

Hard rules:
1) NO semantics drift outside joystick-driven motion behavior.
2) Joystick still reaches HiP only via Core telemetry (no direct UDP in HiP).
3) Qt-at-the-edge:
   - PySide6 only in ui_shell.py, controllers/, binders/, qtutil/, panels/*_render.py.
   - No PySide6 in core/ or apps/yellow/domain|engines|runtimes or panels/*_vm.py.
4) Performance: rate limit motion command emission (avoid spamming intents per tick if unchanged).
5) Tests: add targeted tests for gating + mapping.

Workflow:

## Stage 0 — Identify existing motion primitives (read-only)
1) Read docs/project_primer.md if present.
2) Search for existing motion command intents and patterns:
   - “Jog”, “Velocity”, “SetVel”, “GuideSpeed”, “Move”, “Target”, “CmdVel”, “cmd_vel”, “cmd_speed”
   - core intent definitions and how DenSi/PLC consumes them
3) Produce a short report:
   - What intent type should represent “desired speed”?
   - Where in core the intent is converted to device command frames / PLC downlink / DenSi command
   - Any constraints (mode LIVE required, axis enabled required, etc.)

If multiple plausible motion primitives exist and repo doesn’t clearly indicate the intended one, ask ONE question via vscode/askQuestions:
- “Which motion primitive should soll_speed drive: jog/velocity setpoint/guider speed? (pick one: jog | vel | guider)”
Then proceed.

## Stage 1 — Define mapping policy (Qt-free)
Goal: convert soll_speed into a canonical motion intent, with stable semantics.

1) Implement a small mapping helper (Qt-free), e.g. in apps/yellow/domain/joy_motion_map.py:
   - input: soll_speed [-1..+1], optional scaling factors (if existing config already exists, reuse it; otherwise default to 1.0 and keep it local)
   - output: (motion_intent or None)
2) Add deadzone only if there is already an established deadzone helper in the codebase; otherwise DO NOT add new shaping beyond clamp.
3) Add emission throttling:
   - If soll_speed unchanged (or within small epsilon), do not emit motion intent every tick.
   - Rate-limit to e.g. 10 Hz max if necessary, but prefer “emit on change”.

## Stage 2 — HipEngine/HipRuntime emit motion intents
1) In HipEngine (or HipRuntime, whichever is consistent with existing intent emission):
   - if deadman false => motion intent None
   - if not owner => motion intent None
   - if mode not LIVE (or other existing requirement) => motion intent None
   - else => emit the chosen motion intent based on soll_speed mapping
2) Ensure select_hip claiming logic remains unchanged.
3) Ensure param edit / resync / estop behaviors remain unchanged.

## Stage 3 — Core consumes motion intents and forwards to devices
1) Ensure the motion intent is accepted by Core and converted into the correct command frame / device command.
2) Confirm DenSi simulator reflects the command (or the PLC downlink message updates) using existing seams.
3) Do NOT change protocol formats unless strictly necessary.

## Stage 4 — Tests (targeted and fast)
Add/extend tests to cover:
- deadman gating prevents motion intents
- not-owner gating prevents motion intents
- soll_speed sign produces directionally correct command (negative vs positive)
- emission is not spammy (e.g. unchanged soll_speed does not cause repeated motion intents)
- core converts the intent into a command frame (or DenSi sees it)

Use existing test harness patterns in the repo (integration tests if already present, otherwise unit tests around engine+core command mapping).

Verification:
- Run targeted tests only (the ones you touched plus any minimal dependency).
- Run: python -m compileall src/steuerung3d/apps/yellow src/steuerung3d/core
- Only run pytest -q if explicitly asked.

Reporting format:
After each stage, output:
- Summary
- Files changed
- Commands run + results

Stop condition:
If you must choose between two motion primitives and repo evidence is insufficient, ask one question and proceed with the answer.
