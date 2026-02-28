# Legacy: configs/stacks

`configs/profiles/*.toml` is the **source of truth**.

This directory (`configs/stacks/*.toml`) remains as a **compatibility mirror** for older
docs/scripts that still reference the historic "stack" naming.

Do **not** edit files here directly.

To refresh the mirror after changing profiles:

```powershell
python tools/sync_legacy_stacks.py
```

To verify the mirror is in sync:

```powershell
python tools/check_legacy_stacks.py
```
