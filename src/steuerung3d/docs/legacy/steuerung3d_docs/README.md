# Docs index

- `docs/transport.md` — transport abstraction, recording, deep debugging hooks (CommandFrame logging)
- `docs/config.md` — TOML config overview and per-stack schemas
- `docs/plc_stack.md` — PLC stack architecture, builder surface, testing strategy
- `docs/logging.md` — JSONL log format, replay, and log viewer usage
- `docs/decisions.md` — reasons behind major design decisions (lightweight ADRs)
- `docs/milestones.md` — achieved milestones and next goals

Quick start:

```bash
# PLC stack (UDP edge adapter)
python -m steuerung3d.apps.plc_stack --config configs/plc_stack.toml

# Dev stack (SIM-first)
python -m steuerung3d.apps.dev_stack --config configs/dev_stack.toml

# View logs (commanded vs measured)
python -m steuerung3d.apps.log_viewer logs/session.jsonl --config configs/log_viewer.toml
```
