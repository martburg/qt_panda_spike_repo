# Repo structure (streamlined)

- `src/steuerung3d/` — python package (runtime code only)
- `tests/` — pytest suite (unit + integration)
- `configs/` — TOML configs used by apps and tests (dev defaults)
- `docs/` — design docs and runbooks
- `tools/` — helper scripts (dev / ops)

Notes:
- `pyproject.toml` points pytest to `tests/`.
- Config defaults in apps use relative paths like `configs/plc_stack.toml`.
