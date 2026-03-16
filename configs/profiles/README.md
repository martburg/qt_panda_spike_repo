## Stack profiles

Canonical profile location: `configs/profiles/*.toml`.

These TOML files are consumed by:

```bash
python -m steuerung3d up --profile 1dev_sim
python -m steuerung3d profiles
```

Notes:
- `configs/profiles/*.toml` is the source of truth for named profiles.
- `configs/stacks/*.toml` remains only as a strict compatibility mirror for older docs/scripts.
- Do not edit `configs/stacks/*.toml` directly.
- `python tools/check.py` enforces mirror correctness through `tools/check_legacy_stacks.py`.
- After changing a profile here, refresh the mirror with `python tools/sync_legacy_stacks.py`.
