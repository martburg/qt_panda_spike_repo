## Stack profiles

Canonical stack profile location: `configs/profiles/*.toml`.

These TOML files are consumed by:

```bash
python -m steuerung3d up --profile 1dev_sim
python -m steuerung3d profiles
```

Notes:
- `configs/stacks/` remains supported for backward compatibility, but new profiles
  should be added here.
