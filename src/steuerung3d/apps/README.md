# src / steuerung3d / apps

## Purpose

Runnable entrypoints (`python -m ...`) for stack services and developer tooling.

The canonical way to boot a stack is the profile-driven supervisor:

- `python -m steuerung3d up --profile <name>`

For a single source of truth on which apps are supported vs obsolete, see:

- `steuerung3d.core.app_catalog`

## Subdirectories

- `core_udp_service/` — **Canonical** core process used by stack profiles.
- `hi_p/` — Human Intent Parser (UI/controller).
- `den_si/` — Device endpoint simulator.
- `joy2intent/` — Joystick input -> intents bridge.
- `inputd/` — Input daemon (keyboard/misc sources).

Developer tools:

- `cli_client/` — Minimal CLI that can send intents/commands and display telemetry.
- `dev_stack/` — Convenience app that wires a local dev stack based on TOML and runs it end-to-end.
- `log_viewer/` — CLI log viewer for comparing commanded vs measured signals from JSONL recordings.
- `replay_player/` — Replays recorded JSONL sessions through the core engine.

Legacy / obsolete:

- `core_service/` — **obsolete** (superseded by `core_udp_service` + StackSpec profiles).
- `plc_twincat_legacy_edge/` — **obsolete** TwinCAT legacy UDP edge adapter.

## Notes

- If something here is inaccurate, update it to match reality.
