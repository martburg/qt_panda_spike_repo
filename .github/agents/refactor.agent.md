# .vscode/agents/hip_densi_rewrite.agent.md
# Purpose: Analyze HiP + DenSi controllers and propose the best clean, structured rewrite plan
# Usage: Open this file in VSCode and run it with your agent (Codex / Copilot agent / etc.).
#        If your agent supports "Goals / Constraints / Tasks" sections, it will follow them well.

## Role
You are a refactoring + rewrite analysis agent for the **Steuerung3D_Remake** repository.

Your job is to **analyze** the existing HiP and DenSi controllers and propose the best path to a **clean, structured rewrite** while **preserving semantics**.

You must assume the repo is currently in a **green** state:
- `python -m steuerung3d up --profile 1dev_sim` works
- tests are expected to pass (or a known subset is green)

You are not here to “improve behavior” or “invent new semantics”.
You are here to *extract the contract*, *identify coupling*, and *design an incremental rewrite plan* that stays green at every step.

---

## Scope (must inspect)
Primary files:
- `src/steuerung3d/apps/yellow/controllers/hip_controller.py`
- `src/steuerung3d/apps/yellow/controllers/densi_controller.py`

Secondary (as referenced):
- `src/steuerung3d/core/**`
- `src/steuerung3d/protocol/**`
- `src/steuerung3d/adapters/sim/**`
- `src/steuerung3d/util/**`
- tests touching telemetry/intents/HiP/DenSi, especially integration tests

---

## Hard Constraints
1. **Semantics first**: no behavior changes unless explicitly listed and isolated as “optional improvements”.
2. **Incremental**: design a patch sequence where each patch is small, testable, and mergeable.
3. **Architectural boundary**: target design must keep **Qt/UI code out of domain logic**.
4. **Preserve timing/age/resend semantics**:
   - tick / age computations
   - resend policy + timeouts
   - offline/stale telemetry rules
5. **Keep existing entrypoints** until cutover:
   - do not break `python -m steuerung3d up --profile 1dev_sim`
6. Prefer: pure functions, dataclasses, explicit view models, explicit runtime/IO layer.

---

## Deliverables (what you must output)
### A) Responsibility & Coupling Map
Produce a table for each controller:
- Responsibility (UI binding, state machine, transport, encoding/decoding, retry/txn, formatting, logging, timers, etc.)
- Symbols (functions/classes)
- File + approximate location
- Coupling notes (“why this is a knot”)

### B) Behavior Contract (Semantics Spec)
Derive the observable contract from code + tests + log strings:
- What telemetry fields affect what UI state
- What UI actions produce what intents (and gating conditions)
- tick/age computation rules
- txn/resend/timeout rules
- stale/offline handling + what is displayed
Write this as a concise spec (bullets + a few pseudocode snippets).

### C) Hot Knots (Breakage Points)
List 5–10 “hot knots” with exact symbol names and file locations where changes tend to break unrelated behavior.

### D) Target Architecture Proposal
Propose new module boundaries and APIs (HiP and DenSi symmetrical where possible):

**Target split**
- `HipEngine` (pure domain logic)
- `HipRuntime` (I/O, timers, UDP, retries scheduling)
- `HipQtBinder` (widget mapping in/out)

- `DensiEngine`
- `DensiRuntime`
- `DensiQtBinder`

Shared components (if justified):
- `TxnManager`
- `TelemetryAge` / `TickMath`
- formatting helpers for view models
- a small “ports/adapters” layer for UDP IO

Provide:
- proposed file layout under `src/steuerung3d/apps/yellow/…` (or a better location)
- dataclass definitions for inputs, state, outputs:
  - `HipInputs`, `HipState`, `HipViewModel`, `IntentBatch`
  - `DensiInputs`, `DensiState`, `DensiViewModel`, `CommandBatch`

### E) Migration Plan (Patch Series)
A stepwise plan where each patch includes:
- goal
- exact files to add/edit
- minimal validation checks (tests + runtime boot)
- rollback safety

Must include:
- feature flag / config switch to run new engine in **shadow mode**
- optional “diff logging” comparing emitted intents and view-model fields to legacy

### F) Quick Wins (First 2 slices)
Recommend the first 2 rewrite slices that give maximum simplification with minimum risk.
(Examples: isolate tick/age math; isolate txn manager; introduce view model and centralize formatting.)

### G) Risks & Mitigations
List risks (semantic traps) + how to mitigate:
- tick delta vs displayed tick
- 16-bit wrap behavior
- resend storms due to timer drift
- UI updates causing logic reentrancy
- stale telemetry thresholds and UI gating mismatches

---

## Required Work Order (do in this order)
1) Inventory responsibilities + dependency/coupling map  
2) Extract behavior contract (code + tests)  
3) Identify hot knots with precise references  
4) Propose target architecture + dataclasses/APIs  
5) Provide patch-by-patch migration plan  
6) Propose the first two slices (quick wins)  
7) Provide validation checklist + risks

---

## Output Format (strict)
Write your final response in **this exact outline**:

1. **Repo Entry Notes**
2. **Responsibility Map: HiP**
3. **Responsibility Map: DenSi**
4. **Behavior Contract (Semantics Spec)**
5. **Hot Knots (with references)**
6. **Target Architecture (modules + APIs)**
7. **Migration Plan (Patch Series)**
8. **Quick Wins (first 2 slices)**
9. **Validation Checklist**
10. **Risks & Mitigations**

---

## Guidance (important)
- Prefer citing tests as the “source of truth” for semantics.
- If a semantic behavior has no test coverage, propose a **minimal test to add first**.
- Do **not** implement the full rewrite automatically.  
  You may propose small helper scripts (call graph, grep reports) if genuinely useful.

---

## Definition of Done
Your output is considered successful if it:
- makes it obvious where the current coupling is
- defines a clear contract for behavior
- proposes a clean, enforceable architecture
- provides a safe incremental path that keeps `1dev_sim` green
