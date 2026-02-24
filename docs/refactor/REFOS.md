# Steuerung3D Refactor Operating System (RefOS v2)
Scope: Whole repository
Operational Mode: Stabilize (1 densi)
Semantic Policy: Small declared changes allowed

---

## 1. Mission

Stabilize and streamline Steuerung3D while:
- Sticking to 1 densi (`1dev_sim`)
- Preventing silent semantic drift
- Improving clarity, ownership handling, mode aggregation, and IO contracts
- Keeping tests green and runtime stable

---

## 2. Modes

### Lane 1 — Stabilize (default)
Refactor only.
- No semantic change.
- Structural cleanup.
- Rename, dedupe, move, remove dead code.
- Tests must remain green.

### Lane 2 — Declared Semantic Fix
Small semantic change allowed if:
- Explicitly declared.
- Documented in SEMANTIC_LEDGER.md.
- At least one test added or updated.
- Smoke-tested in `1dev_sim`.

No undeclared semantic changes.

---

## 3. Scope Fence

Allowed:
- Whole repo read access.
- Whole repo edits if directly improving stability and clarity.
- Documentation alignment.

Operational constraint:
- Only 1 densi active.
- No multi-densi scaling work.
- No PLC protocol changes without explicit declaration.

---

## 4. Stage Model

### Stage 0 — Recon (mandatory)
- Identify target subsystem.
- Identify truth source (ST/docs/runtime/tests).
- Identify friction.
- Identify tests protecting it.
- Declare Lane (1 or 2).

No code changes.

---

### Stage 1 — Small Structural Pass
- Mechanical cleanup.
- Remove duplication.
- Normalize naming locally.
- No behavior change.

Gate:
- pytest -q
- manual smoke run

---

### Stage 2 — Semantic Tightening (Lane 2 only)
- Clarify ownership.
- Remove implicit state creation.
- Fix aggregation inconsistencies.
- Enforce invariants.

Gate:
- pytest -q
- smoke run
- ledger entry
- tests updated

---

## 5. Mandatory Gates

After each batch:

1. `pytest -q`
2. `python -m steuerung3d up --profile 1dev_sim`
3. If Lane 2 → ledger updated + tests added

No exceptions.

---

## 6. Semantic Drift Detection Checklist

For every change ask:

- Did any default value change?
- Did any implicit behavior become explicit?
- Did ownership checks tighten?
- Did mode aggregation conditions change?
- Did command/state pipeline logic change?
- Did any public API/CLI flag change?

If yes → must be Lane 2.

---

## 7. Truth Hierarchy

1. PLC ST (canonical if applicable)
2. Protocol docs derived from ST
3. Runtime behavior in sim
4. Tests (must reflect truth)
5. Comments/legacy docs (lowest trust)

Conflicts must be logged in Semantic Ledger.

---

## 8. Definition of Done

A change batch is done only if:
- Tests pass
- Smoke test passes
- Diff explained
- Lane declared
- Ledger updated (if needed)