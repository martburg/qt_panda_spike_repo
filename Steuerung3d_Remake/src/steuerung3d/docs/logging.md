# Logging, replay, and log viewing

Logs are written as **JSONL** (one JSON object per line).

## Record kinds

Records share a common envelope like:

- `schema`: a schema id (e.g. `steuerung3d.log/v1`)
- `kind`: one of:
  - `intent`
  - `telemetry`
  - `command_frame`
- `tick`: engine tick index
- `payload`: the encoded object

## Deep debugging workflow

You typically want three views of the same run:

1. **Intents** — what the operator/UI asked for
2. **CommandFrames** — what the core commanded (full-state setpoint)
3. **Telemetry** — what the device/plant reported back

This allows “commanded vs measured” analysis and makes regressions visible.

## Log viewer CLI

The log viewer prints a per-tick table comparing **commanded** and **measured** values.

Run:

```bash
python -m steuerung3d.apps.log_viewer logs/session.jsonl --config configs/log_viewer.toml
```

Useful flags (depending on your implementation):
- `--from-tick`, `--to-tick`
- `--every N`
- `--axes X,Y,Z`
- `--csv` for spreadsheet-friendly output
- `--show-intents` to include intent counts per tick

## Replay and regression

Replay tooling can read `command_frame` records and compare them against frames generated during replay.

In tests we also maintain a **CommandFrame sequence regression** check:

- run a deterministic SIM scenario
- hash the command frame sequence
- compare to a baseline hash

If the baseline changes intentionally, update the hash and document why in the commit message.
