# Refactor Change Template

## Session
Date:
Branch:
Subsystem:
Lane: (1 = Stabilize, 2 = Semantic Fix)

---

## Stage
(0 / 1 / 2)

---

## Scope Fence
Files or modules touched:

---

## Description of Change

---

## Semantic Declaration
- [ ] No semantic change
- [ ] Small declared semantic change (ledger updated)

If semantic change:
Explain clearly what changed and why.

---

## Tests
- Existing tests passing?
- New tests added?
- Which files?

Command:
pytest -q

Result:

---

## Smoke Test

Command:
python -m steuerung3d up --profile 1dev_sim

Manual checks performed:
- Ownership claim?
- Enable axis?
- Jog?
- Mode transitions?
- Stale frame rejection?

Result:

---

## Diff Summary

Explain what changed and why safe.

---

## Next Tickets