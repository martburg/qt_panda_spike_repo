## Stack profiles

Canonical profile location: `configs/profiles/*.toml`.

These TOML files are consumed by:

```bash
python -m steuerung3d up --profile 1dev_sim
python -m steuerung3d profiles
```

Notes:
- `configs/profiles/*.toml` is the source of truth for named profiles.
- `configs/profiles/*.toml` is the only named-profile location.
- Edit profiles here directly.
- `python tools/check.py` no longer enforces any compatibility mirror.
