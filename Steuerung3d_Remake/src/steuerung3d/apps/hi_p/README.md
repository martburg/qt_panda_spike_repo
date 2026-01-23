# HI-P (Human Intent Parser)

Yellow UI in `--role ip`.

Responsibilities:
- receive telemetry from core (`TelemetryIn`)
- convert user interactions into intents (`IntentOut`)

## UDP wiring (default)

- `IntentOut`  → `127.0.0.1:51001` (to core)
- `TelemetryIn` bind `127.0.0.1:51002` (from core)

Run:

```powershell
python -m steuerung3d.apps.hi_p
```

## Parameter editing

HiP is the *only* place where parameter editing is initiated.

- Parameter text fields are disabled (grey) until **Edit** is pressed.
- When active, fields are enabled (white) and **Write/Cancel** become available.
- While a group is being edited, HiP does not overwrite those fields with incoming telemetry.
