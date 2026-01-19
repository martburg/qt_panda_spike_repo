# Den-Si (Device Endpoint Simulator)

Yellow UI in `--role cfc`.

Responsibilities:
- receive CommandFrames from core (`CommandIn`)
- step a simulated device at its own dt
- publish device telemetry back to core (`TelemetryOut`)

This app is currently scaffolded with an in-memory telemetry stub.
Tomorrow we swap the ports to UDP.
