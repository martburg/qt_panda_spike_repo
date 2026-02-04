# Docs index

- `docs/MANUAL_TESTING.md` — manual runbook (what to run and what to observe)
- `docs/transport.md` — transport abstraction, recording, deep debugging hooks (CommandFrame logging)
- `docs/config.md` — TOML config overview and per-stack schemas
- `docs/plc_stack.md` — PLC stack architecture, builder surface, testing strategy
- `docs/logging.md` — JSONL log format, replay, and log viewer usage
- `docs/STACK_BOOT_STATUS.md` — profile-driven boot, per-session logs, birds-eye status
- `docs/decisions.md` — reasons behind major design decisions (lightweight ADRs)
- `docs/milestones.md` — achieved milestones and next goals

Quick start:

```bash
# Profile-driven boot (recommended)
python -m steuerung3d up --profile dev_sim

# PLC stack (UDP edge adapter)
python -m steuerung3d.apps.plc_stack --config configs/plc_stack.toml

# Dev stack (SIM-first)
python -m steuerung3d.apps.dev_stack --config configs/dev_plc.toml

# View logs (commanded vs measured)
python -m steuerung3d.apps.log_viewer logs/session.jsonl --show-intents
```
