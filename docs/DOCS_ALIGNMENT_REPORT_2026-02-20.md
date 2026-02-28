# Docs ↔ Code alignment report (2026-02-20)

This pass focused on **eliminating stale entry points and file references** introduced by recent refactors.

## What was updated

### 1) `docs/config.md` (and packaged copy)

- Rewritten to match the **actual config files present** under `configs/`.
- Clarifies the two supported configuration surfaces:
  - **Profiles** (`configs/profiles/*.toml`, via `python -m steuerung3d up --profile ...`; legacy mirror: `configs/stacks/*.toml`)
  - **Single-process runners** (e.g. `apps/dev_stack`, `apps/plc_stack`, `apps/joy2intent`, `apps/inputd`)
- Removed references to non-existent files:
  - `configs/dev_stack.toml`
  - `configs/replay_player.toml`
  - `configs/cli_client.toml`
  - `configs/core_service.toml`

### 2) Marked obsolete docs (prefixed `obs_`)

- `docs/transport_layer.md` → `docs/obs_transport_layer.md`
- `docs/graphs/steuerung3d_dead_code_candidates.md` → `docs/graphs/obs_steuerung3d_dead_code_candidates.md`

Each now contains a short header explaining why it is obsolete and where to look instead.

### 3) Generated doc indexes refreshed

- `docs/README.generated.md`

These now list current files and note that obsolete docs are prefixed with `obs_`.

### 4) Index fixups

- `docs/INDEX.md` updated to reference the renamed obsolete graph report.

## Conventions going forward

- **Authoritative docs** live under `docs/`.
- `docs/` is the single canonical docs tree. (The old `src/steuerung3d/docs/` mirror has been removed.)
- When a doc becomes misleading after refactors, rename it with `obs_` rather than silently deleting it.

