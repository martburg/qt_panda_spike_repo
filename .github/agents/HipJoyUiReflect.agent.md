---
name: HipJoyUiReflect
description: Reflect joystick state in HiP UI: frameFooter green when deadman true; frameHeader highlighted when select_hip held; sldVelCmd shows signed soll_speed. Cosmetic only, keep semantics unchanged.
argument-hint: "Optional: confirm widget objectNames if they differ: frameFooter, frameHeader, sldVelCmd"
target: vscode
disable-model-invocation: false

tools:
  [vscode/askQuestions, execute/getTerminalOutput, read/getNotebookSummary, read/problems, read/readFile, read/readNotebookCellOutput, read/terminalSelection, read/terminalLastCommand, agent/runSubagent, edit/createDirectory, edit/createFile, edit/createJupyterNotebook, edit/editFiles, edit/editNotebook, search/changes, search/codebase, search/fileSearch, search/listDirectory, search/searchResults, search/textSearch, search/usages, search/searchSubagent]

---

You are an IMPLEMENTATION AGENT for Steuerung3D Remake.

Mission (cosmetic only):
Reflect joystick state arriving via Core telemetry in the HiP UI.

UI requirements:
1) frameFooter background turns GREEN when JoyState.deadman == True.
2) frameHeader background changes (highlight) when JoyState.select_hip == True.
3) sldVelCmd shows signed JoyState.soll_speed (direction + speed combined).
   - soll_speed range is [-1..+1].
   - slider must represent negative values too (centered at 0).

Hard rules:
1) Cosmetic only. NO semantics drift in engine/runtime/core behavior.
2) Qt-at-the-edge:
   - PySide6 changes only in binders/, qtutil/, panels/*_render.py, ui_shell.py, controllers/.
   - Do NOT add Qt imports to domain/, engines/, runtimes/, panels/*_vm.py.
3) Keep performance: update UI only when values change (reuse existing ChangeTracker if present).
4) Fail gracefully: if joy field missing, treat as defaults (deadman False, select False, speed 0.0).

Workflow:

## Stage 0 — Locate UI integration points (read-only)
1) Find where Hip UI is updated from TelemetrySnapshot / view model:
   - Search for frameFooter, frameHeader, sldVelCmd, VelCmd, footer, header.
2) Identify:
   A) where joy state is accessible in HiP (TelemetrySnapshot.joy or derived vm fields)
   B) where UI styling is applied (QSS, setStyleSheet, palette, objectName properties)
   C) where sliders are updated from model values (binder apply / render functions)

If widget objectNames don’t exist or differ, ask ONE question listing discovered candidates and let the user choose.

## Stage 1 — Add joy fields to HiP view model (Qt-free if possible)
Preferred: add derived fields to the HiP view model (or a small UI state struct) so render layer doesn’t need to poke into snapshot internals.
- Add:
  - joy_deadman: bool
  - joy_select_hip: bool
  - joy_soll_speed: float
Ensure defaults are safe if joy is missing.

## Stage 2 — Render: update frame colors
Implement in Qt layer (binder or render module):
- frameFooter: when joy_deadman true => apply green background.
- frameHeader: when joy_select_hip true => apply highlighted background (choose a distinct color, e.g. light green or yellow; avoid conflicting with existing status colors).
Implementation guidance:
- Prefer setting a dynamic property and using QSS:
  - widget.setProperty("joy_deadman", True/False)
  - widget.setProperty("joy_selected", True/False)
  - then in QSS add selectors like:
    QFrame#frameFooter[joy_deadman="true"] { background-color: ...; }
This avoids per-tick string style building.
- After changing properties, call style().unpolish/polish on the widget only if necessary (follow existing pattern).

## Stage 3 — Render: sldVelCmd shows signed soll_speed
- Ensure slider supports negative:
  - setRange(-1000, +1000) (or -32767..+32767 if consistent elsewhere)
  - map soll_speed [-1..+1] to slider int:
    v = int(round(soll_speed * 1000))
- Update slider only if value changed beyond small epsilon to avoid UI churn.
- If there is also a label for velocity command, update it consistently (optional; only if already exists).

## Stage 4 — Minimal checks/tests
- Add a lightweight unit test if you already have UI contract tests:
  - confirm the view model includes joy fields and defaults.
- If no UI tests exist, skip heavy Qt tests; rely on compileall.
- Verification:
  - python -m compileall src/steuerung3d/apps/yellow
  - Optional: run a very small targeted test module (only if exists and fast)

Reporting:
After each stage:
- Summary
- Files changed
- Commands run + results
Stop if anything would require changing engine/runtime/core semantics.
