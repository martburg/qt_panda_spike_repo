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
- `configs/stacks/*.toml` remains only as a strict compatibility mirror for older docs/scripts.
- The compatibility mirror is enforced by `python tools/check.py` via `tools/check_legacy_stacks.py`.
- Edit `configs/profiles/*.toml`, then refresh the mirror with `python tools/sync_legacy_stacks.py` when needed.
