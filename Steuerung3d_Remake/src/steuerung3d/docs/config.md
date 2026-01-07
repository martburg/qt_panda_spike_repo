# Configuration

We use **TOML** as the configuration format for runtime wiring.

## Status

- TOML is now *active* for the PLC stack (`apps/plc_stack`).
- This is still a **stub phase**:
  - we ship a default `configs/plc_stack.toml`
  - apps default to that file path
  - additional app stacks will be migrated to TOML incrementally

## Why TOML (design decision)

- human-readable, versionable config file in the repo
- easy to review changes in PRs
- supports nested structures cleanly (`[[plc_endpoints]]` lists)

## PLC stack schema

### `[app]`
- `dt_s`: engine tick step in seconds
- `realtime`: whether the core runner sleeps to real time
- `log_path`: JSONL log output path

### `[[plc_endpoints]]`
One table per PLC endpoint.

Required:
- `name`
- `bind_host`, `bind_port`
- `target_host`, `target_port`
- `axis_ids` (list of axes owned by this endpoint)

Optional (codec hints, used as defaults):
- `delimiter`
- `encoding`
- `float_fmt`
- `true_token`, `false_token`

## Validation rules

- At least one endpoint must exist
- endpoint names must be unique
- each axis can only be owned by one endpoint
- ports must be > 0, target_host must be present

## Future direction (not done yet)

- unify all app configs (dev_stack, plc_stack, replay) under one schema
- provide “profiles” for different rigs or deployments
- support overrides (CLI flags, env) without losing reproducibility
