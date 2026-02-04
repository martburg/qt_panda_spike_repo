# Logging, replay, and log viewing

This repo has **two** log streams:

1) **Session logs (per process)** from the stack supervisor (`python -m steuerung3d up ...`).
2) **JSONL event logs** (intents/telemetry/command frames) written by the recorder.

They serve different purposes:
- session logs answer: *"what did each process print / why did it exit?"*
- JSONL logs answer: *"what did the system do tick-by-tick?"*

---

## Session logs (supervisor)

Each `up` run creates a session dir:

```
.run/<stack>/sessions/<timestamp>/
  core.log
  densi-Anton.log
  hip-Debby.log
  ...
  meta.json
```

Helper commands:

```bash
python -m steuerung3d status --profile dev_sim
python -m steuerung3d logs core --profile dev_sim --follow
python -m steuerung3d down --profile dev_sim
```

By default we keep the last 5 sessions; older ones are deleted.

---

## JSONL event logs (recorder)

Recorder logs are written as **JSONL** (one JSON object per line).

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

## High-rate diagnostic traces

Some signals can be very chatty (multiple axes, multiple processes, many times per second). To keep the default developer experience readable, these are **DEBUG** by default:

- **LifeTick** transmit/echo traces (`LIFETICK ...`)

When you need them, start the stack (or the specific app) with:

```bash
python -m steuerung3d.apps.setup_stack --log-level debug ...
```

Tip: if you only care about one component, set that process to DEBUG and leave the rest at INFO.
