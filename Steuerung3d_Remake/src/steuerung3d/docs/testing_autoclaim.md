# Testing: Auto-Discovery + Auto-Claim (current milestone)

This test pack verifies three things:

1. **Axis discovery**: the core can list axes for the UI based on telemetry/state.
2. **Exclusive claims**: only the claiming HiP may enable/jog a claimed axis.
3. **UDP discovery behavior**: `UdpPlcDevice` creates axes when telemetry arrives for unknown axis IDs.

## Run
From repo root (with your venv active):

```bash
pytest -q
```

## Optional smoke helper (no Qt)
```bash
python tools/smoke_autoclaim.py
```
