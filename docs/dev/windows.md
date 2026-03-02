# Windows dev notes

## Line endings

To avoid noisy diffs and "corrupt patch" situations caused by CRLF/LF churn, prefer keeping the repo in LF.

Recommended (per-repo):

```bash
git config core.autocrlf false
```

If you already have CRLF changes in your working tree, you can usually normalize by re-checking out after setting the config.

## Python tooling

The canonical local gate is:

```bash
python tools/check.py
```

And the canonical smoke profile used during refactors is:

```bash
python -m steuerung3d up --profile 1dev_sim_remote_joy
```
