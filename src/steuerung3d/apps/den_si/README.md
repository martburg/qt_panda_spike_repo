# Den-Si (Device Endpoint Simulator)

Yellow UI in `--role cfc`.

Responsibilities:
- receive CommandFrames from core (`CommandIn`)
- step a simulated device at its own dt
- publish device telemetry back to core (`TelemetryOut`)

## UDP wiring (default)

- `CommandIn` bind `127.0.0.1:52001` (from core)
- `TelemetryOut` → `127.0.0.1:52002` (to core)

Run:

```powershell
python -m steuerung3d.apps.den_si
```

## Parameter editing (device-side)

DenSi behaves like a device endpoint:

- Starts in a **stopped / not-OK** state by default.
- Edit/Write/Cancel controls are disabled (greyed): the operator side is HiP.
- Receives parameter edit operations embedded in the command frame and reports state via telemetry.
