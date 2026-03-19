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

## Archive / generated artefact policy

Keep generated snapshots and archive material in one canonical location. Avoid committing duplicate generated readmes, stale local analysis dumps such as `pyright_out.txt`, or docs links that point to files that do not exist anymore.

When archiving historical material, prefer `docs/archive/` for documentation-facing reference content and keep `archive/` limited to quarantined historical material that still needs to live in the tree.

