# Steuerung3D Remake — Repository Root

## Purpose

Supporting files for this subtree.

## Subdirectories

- `ST-Code/` — Extracted PLC Structured Text (ST) sources from legacy TwinCAT projects, kept here for reference and protocol archaeology.
- `config/` — Quick-start TOML configs used during development (legacy location). Prefer `configs/` unless a script explicitly points here.
- `configs/` — Canonical TOML configuration files for apps and stacks (dev PLC, sim, replay, log viewer, etc.).
- `docs/` — Human-readable project documentation (architecture notes, decisions, logging, transport, PLC integration).
- `logs/` — Local development logs and captures (usually ignored by git).
- `src/` — Python source tree (package code plus some development artifacts).
- `tools/` — Developer tooling and local scripts (Obsidian ingestion, helper .cmd launchers).

## Files

- `.gitignore`
- `README.md`
- `conftest.py`
- `plc_stack_builder_path_proposal.zip`
- `pyproject.toml`

## Key entry points

- `pyproject.toml`
- `README.md`
- `conftest.py`
- `.gitignore`
- `plc_stack_builder_path_proposal.zip`

## Notes

- This README was auto-generated to help orient the repo. If something is inaccurate, update it to match reality.
