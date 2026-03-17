# src / steuerung3d / configs

## Purpose

Package-level defaults / embedded example configs shipped with the library.

## Files

- `dev_plc.toml`
- `inputd_gamepad.toml`
- `log_viewer.toml`
- `plc_stack.toml`

## Key entry points

- `__init__.py`
- `plc_stack.toml`

## Notes

- This README was auto-generated to help orient the repo. If something is inaccurate, update it to match reality.
- Stack profiles live in `configs/profiles/*.toml` and are the authoritative source.
- `configs/profiles/*.toml` is the single source of truth for named stack profiles.
- `python tools/check.py` validates the repo without any legacy mirror step.
