# Semantic Ledger

This file records *declared* semantic changes (RefOS Lane 2) made during stabilization.

## 2026-02-24

- **Change:** Exclude transitions-based FSM tests from automated runs by default.
  - **Why:** The optional third-party dependency `transitions` is not required for core functionality and is not available in some CI/dev environments.
  - **How:** Introduced marker `requires_transitions` and opt-in environment gate `RUN_TRANSITIONS_TESTS=1`.
  - **Files:** `conftest.py`, `pytest.ini`, `tests/test_axis_fsm.py` (plus removal of redundant `tests/conftest.py`).
  - **Expected impact:** `pytest` default run skips those tests; developers can opt-in locally.
