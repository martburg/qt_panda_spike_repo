# src / steuerung3d / adapters

## Purpose

Device and transport adapters: PLC UDP devices, sim devices, and helper links.

## Subdirectories

- `links/` — Link abstractions (e.g., UDP link) to connect endpoints/ports in a testable way.
- `plc/` — Generic PLC transport/device utilities (UDP device, line/frame codecs, validation, endpoint helpers).
- `plc_stack/` — Thin package that groups PLC stack wiring helpers (import convenience).
- `plc_twincat_legacy/` — Legacy TwinCAT PLC protocol adapter: encode/decode semicolon-separated frames, status decoding, fleet construction from TOML.
- `sim/` — Simulation adapters: simple axis plant + device implementation used for deterministic tests and offline runs.

## Files

- `__init__.py`

## Key entry points

- `__init__.py`

## Notes

- This README was auto-generated to help orient the repo. If something is inaccurate, update it to match reality.
