# Configuration (TOML)

All runtime entrypoints are configured via **TOML files** under the repo root `configs/` directory.

## Shared conventions

Most stacks have an `[app]` section with:

- `dt_s` — tick step (seconds)
- `realtime` — whether to sleep to real time (if the runner supports it)
- `log_path` — JSONL output path (stacks that record)

## PLC stack (`configs/plc_stack.toml`)

`[[plc_endpoints]]` maps axis ownership to PLC endpoints (UDP bind + target).
See `docs/plc_stack.md`.

Run:
```bash
python -m steuerung3d.apps.plc_stack --config configs/plc_stack.toml
```

## Dev stack (`configs/dev_stack.toml`)

SIM-first run of core + sim device + recording.

Run:
```bash
python -m steuerung3d.apps.dev_stack --config configs/dev_stack.toml
```

## Replay player (`configs/replay_player.toml`)

Offline replay of a JSONL session.

Run:
```bash
python -m steuerung3d.apps.replay_player path/to/session.jsonl --config configs/replay_player.toml
```

## CLI client (`configs/cli_client.toml`)

Human-driven intent publishing from terminal.

Run:
```bash
python -m steuerung3d.apps.cli_client --config configs/cli_client.toml
```

## Core service (`configs/core_service.toml`)

Headless core runner for development.

Run:
```bash
python -m steuerung3d.apps.core_service --config configs/core_service.toml
```

## Log viewer (`configs/log_viewer.toml`)

Defaults for the `log_viewer` CLI.

Run:
```bash
python -m steuerung3d.apps.log_viewer path/to/session.jsonl --config configs/log_viewer.toml
```
