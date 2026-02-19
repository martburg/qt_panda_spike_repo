---
Task: Generate a durable project primer for Steuerung3d_Remake.

Goal:
Create a file docs/project_primer.md that captures the essential architecture, rewrite goals, invariants, and operational philosophy of the project so that future sessions can use it as compact context.

Constraints:
- Read-only analysis first.
- Do NOT run full pytest.
- Do NOT start the stack.
- Avoid heavy terminal commands.
- Keep the output concise but deep (max ~1200 lines, aim for clarity).
- Use file paths and symbol references grounded in the repo.
- Do not speculate — if something is unclear, mark it explicitly.

Research phase:
1. Identify main apps/modules (core service, HiP, DenSi, joy2intent, inputd, SIM adapters).
2. Identify protocol definitions and canonical sources of truth (especially legacy_plc_anton.md or equivalent).
3. Identify key domain types (TelemetrySnapshot, CommandFrame, MachineState, ESTOP specs, tick helpers).
4. Identify integration tests that freeze semantics (e.g., LifeTick echo roundtrip).
5. Identify any docs explaining architecture or profiles.
6. Identify logging and timing mechanisms that influence responsiveness.

Then create the file:

docs/project_primer.md

With this structure:

# Steuerung3d_Remake – Project Primer

## 1. Project Purpose
- Why the rewrite exists.
- What problems it solves.
- What must never regress.

## 2. System Architecture
- High-level process map.
- Responsibilities of:
  - Core
  - HiP
  - DenSi
  - joy2intent
  - inputd
  - SIM / adapters
- Describe UDP data flow at a conceptual level.

## 3. Canonical Sources of Truth
- Explicitly name PLC protocol spec files.
- Explicitly state which files define wire protocol meaning.
- Call out legacy_plc_anton.md if present.

## 4. Semantic Contracts (No-Regression Rules)
Enumerate invariants:
- EStop / Armed / Ready semantics
- OK-chain handling
- LifeTick echo semantics
- Tick delta vs display age semantics
- Logging must not degrade UI responsiveness
- Any test-frozen behaviors discovered

## 5. Data Model Overview
List and describe core domain types:
- TelemetrySnapshot
- CommandFrame
- Intent
- MachineState
- ESTOP structures
- Tick helpers

## 6. Testing Strategy
- Fast vs integration tests.
- Known semantic guard tests.
- Recommended workflow (smoke vs full suite).

## 7. Operational Workflow
- How to start stack.
- Profiles.
- Where logs live.
- Common debugging entry points.

## 8. Current Refactor Direction
- Summarize architectural goals (modularization, decoupling UI from logic, protocol consolidation).
- Identify current pain points from code structure.

## 9. Glossary
Define domain-specific terminology.

Style rules:
- Clear, scannable, structured.
- No giant paragraphs.
- Use bullet lists where possible.
- Use inline `code` for symbols.
- Use [file](path) references.
- No speculation.
- No open-ended questions.
- No TODOs unless clearly marked.

After writing:
- Show the diff.
- Suggest a concise commit message.
- Stop.
