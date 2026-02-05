# Repo hygiene

The supervisor/runtime creates per-run session artefacts under `.run/` (logs, `meta.json`, `LATEST`). These are local runtime outputs and should not be committed.

## .gitignore baseline

Ignore at least:

- `.run/`
- `*.log`

Common extras:

- `vault/` (Obsidian vault)
- `*.jsonl` (JSONL logs)
- `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.venv/`
