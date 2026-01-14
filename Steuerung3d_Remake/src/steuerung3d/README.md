# src / steuerung3d

## Purpose

Main Python package implementing the Steuerung3D remake: core tick/engine, protocol boundary, adapters, and runnable apps.

## Subdirectories

- `adapters/` — Device and transport adapters: PLC UDP devices, sim devices, and helper links.
- `apps/` — Runnable entrypoints (`python -m ...`) for CLI client, core service, dev stack, PLC sim, PLC stack builder, replay player, and log viewer.
- `common/` — Small shared utilities used across the codebase (e.g., timebase abstractions).
- `config/` — Typed configuration loaders and dataclasses for each app; includes TOML loader utilities.
- `configs/` — Package-level defaults / embedded example configs shipped with the library.
- `core/` — Core domain logic: machine state, intents, state machine, command frame generation, executor, ramping, telemetry snapshots.
- `docs/` — Package-coupled documentation copies; used when distributing docs with the Python package.
- `legacy_program/` — Reference material copied from the legacy program (kept for comparison during migration).
- `logs/` — Logging helpers and schemas for JSONL recordings and telemetry capture.
- `protocol/` — Protocol boundary: codecs, transport abstractions, recording, and the legacy PLC frame parser.
- `tests/` — Test package and unit tests ensuring the core/protocol/adapters stay stable across refactors.

## Files

- `__init__.py`

## Key entry points

- `__init__.py`

## Notes

- This README was auto-generated to help orient the repo. If something is inaccurate, update it to match reality.
