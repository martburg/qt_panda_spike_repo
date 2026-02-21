# setup_stack

One-command launcher for the **initial setup / winch jogging** stack:

```
inputd (gamepad)  -> RawControls UDP :50100
joy2intent        -> Intents    UDP :51001
core_udp_service  -> UI Telem   UDP :51002
                 -> Dev Cmd    UDP :52001.. (broadcast)
DenSi fleet       -> Dev Telem  UDP :52002
HiP UI            -> shows per-axis state and commanded velocity
```

Note: `setup_stack` is a legacy wrapper. `--single-hip` binds UI telemetry on a shared port.
For strict per-axis unicast or C2-only wiring, use stack profiles.

## Run

From repo root:

```bat
python -m steuerung3d.apps.setup_stack \
  --joy2intent configs/joy2intent_gamepad.toml \
  --inputd configs/inputd_gamepad.toml
```

Defaults are chosen to match the current configs, so this also works:

```bat
python -m steuerung3d.apps.setup_stack
```

Stop with **Ctrl+C**.
