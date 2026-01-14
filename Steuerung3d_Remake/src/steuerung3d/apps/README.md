# src / steuerung3d / apps

## Purpose

Runnable entrypoints (`python -m ...`) for CLI client, core service, dev stack, PLC sim, PLC stack builder, replay player, and log viewer.

## Subdirectories

- `cli_client/` — Minimal CLI that can send intents/commands and display telemetry against a running core service or stack.
- `core_service/` — Main long-running core service process: ticks the engine, talks to devices, emits telemetry, and records logs.
- `dev_stack/` — Convenience app that wires a full dev stack (core + device) based on TOML and runs it end-to-end.
- `log_viewer/` — CLI log viewer for comparing commanded vs measured signals over time from JSONL recordings.
- `plc_sim/` — Legacy PLC simulator UI/process: emulates the TwinCAT PLC side to exercise the main app without hardware.
- `plc_stack/` — PLC stack builder app: loads PLC endpoints from TOML and constructs the wiring (and optionally runs it).
- `replay_player/` — Replays recorded JSONL sessions through the core engine for regression tests and debugging.

## Files

- `__init__.py`

## Key entry points

- `__init__.py`

## Notes

- This README was auto-generated to help orient the repo. If something is inaccurate, update it to match reality.
