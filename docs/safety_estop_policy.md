# Safety / E-Stop Policy (v0.1)

## Core principle
The **only authority** for the *actual* E-Stop state is the **device** (real PLC / Safety SPS, or Den-Si simulation).

The UI must NOT be treated as a safety device.

## Current v0.1 semantics

### Device telemetry
- `TelemetrySnapshot.estop` is the truth (“E-Stop is engaged”).
- When telemetry says estop=True, the system is in ESTOP mode and motion is clamped.

### Command frames
Command frames are for **commands**, not truth.
- `CommandFrame.estop` may be present for legacy compatibility, but it must not be used as “truth”.
- For “reset request”, we send a **pulse**:
  - `CommandFrame.estop_reset` (bool pulse, one tick)

### Intents
- HI-P emits **RequestEstopReset** when the operator clicks `btnEStopReset`.
- This is a *request*, not a guarantee: the Safety SPS/device may still refuse until conditions are safe.

## Latched E-Stop model (recommended now)
- Once the device enters estop=True, it stays latched until:
  1) Safety SPS/device is OK to clear AND
  2) core sends `estop_reset` pulse (originating from HI-P)

So:
- UI can request reset
- Device decides when it actually clears
- Telemetry reflects the resulting truth

## Simulator (Den-Si)
Den-Si may inject diagnostic E-Stop to test the seam, but it still behaves like “device truth”:
- injection affects telemetry estop
- core must not claim estop state on its own