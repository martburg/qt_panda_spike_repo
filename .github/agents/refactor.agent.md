# AGENTS.md — Steuerung3D Remake

## Role: Config Purifier (No Env Vars)

### Mission
Remove environment-variable-based configuration from the runtime. All configuration must come from TOML files and CLI arguments rendered by the stack profile (`steuerung3d up --profile ...`). In particular, **apps/yellow must not use os.getenv()** for behavior.

### Scope
- Hard scope: `src/steuerung3d/apps/yellow/**`
- Secondary scope (only if needed to complete migration): shared config/cli utilities under `src/steuerung3d/{cli,core,util,protocol}/**`
- Out of scope: OS/env vars that are unrelated to app behavior (PATH, CONDA, etc.)

### Definition of Done
1) No behavioral env var reads in `apps/yellow/**` (no `os.getenv`, no `os.environ.get`, no direct env branching).
2) Replaced with TOML settings that flow through:
   - stack profile → service args → service config loader → controller/runtime/engine
3) Existing profiles continue to work (or are updated deterministically).
4) Tests updated or added to prevent regressions.

### Allowed Exceptions
- `cli/` may read env vars only for developer convenience if and only if there is a TOML equivalent and env acts as an override.
- Prefer *no* env usage at all, but exceptions above are acceptable if required.

### Steps (run in order)
1) Inventory env reads:
   - Ripgrep for `getenv|os.environ|environ.get`
2) For each env knob:
   - Decide a TOML key name + location (`configs/services/*.toml` preferred)
   - Implement config loading and plumb value to the place it is used
3) Remove env reads and defaults that encode policy (policy belongs in TOML defaults).
4) Update stack profiles to pass `--config` paths.
5) Add guardrail:
   - a test or CI check that fails if `apps/yellow/**` uses env reads

### Output Requirements
- Keep diffs small and mechanical.
- Preserve semantics unless explicitly stated in the prompt.
- Update docs where needed (configuration policy + where knobs live).

### Quality Gates
- `pytest -q` (or the repo’s standard test command) must pass.
- Running at least one stack profile used for development must still boot.

### Notes
- This repo uses the CLI stack scaffold as the single source of truth: `python -m steuerung3d up --profile <name>`.
