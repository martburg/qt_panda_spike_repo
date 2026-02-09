# Repo cleanup notes

This fork intentionally reduces clutter in `src/steuerung3d/` while keeping **legacy artifacts and ST sources** in-tree.

## What moved

### 1) Legacy Python (non-runtime)
- `legacy/legacy_program/…` contains the historic 3DSteuerung script(s) and helpers.
  - The Python2/legacy file was renamed to `*.py2` to avoid accidental Python3 parsing.

### 2) Attic modules (currently unused)
- `legacy/attic_src/steuerung3d/…` contains modules that were **not imported** anywhere in `src/` or `tests/` in this snapshot.
  - They remain available for reference, cherry-picking, or re-introduction.

## Why

- Keep the runnable stack focused (Core/HiP/DenSi/inputd/joy2intent).
- Keep PLC/ST sources available for audit and future protocol work.
- Avoid accidental breakage due to legacy Python2 syntax.

## Integration tests that spawn subprocesses

The integration tests start `python -m steuerung3d.apps.core_udp_service`. When the project is not installed (`pip install -e .`), subprocesses do **not** inherit pytest’s `conftest.py` sys.path injection.

Therefore the tests now export `PYTHONPATH=<repo>/src` for the subprocess.

