# LiveTick semantics (legacy-compatible)

## Goal
The legacy system uses a very small "alive" loop to make sure the *operator UI* is still actively participating in the control loop.

It is **not primarily a latency / RTT measurement** (RTT can be observed, but the control purpose is a watchdog).

## Fields
We keep two integer fields per axis:

- `lifetick_tx`  
  **Device-originated** counter that increments periodically and is sent in telemetry.

- `lifetick_rx`  
  **HiP-originated** echo of the last value of `lifetick_tx` that HiP has seen. This echo is carried back to the device in the next command frame and is mirrored into telemetry so HiP can display it if desired.

## Data flow
1. **DenSi / device**
   - Increments `lifetick_tx` (in this repo: we set it to the current DenSi tick per axis).
   - Publishes it in telemetry.

2. **HiP (operator GUI)**
   - On each telemetry receive, reads `lifetick_tx` for the currently selected axis.
   - Emits an `EchoLifeTick(axis_id, hip_id, lifetick=lifetick_tx)` intent when the value changes.

3. **Core**
   - Stores the most recent echo request per axis (honoring axis claims).
   - Adds the stored echo value into the next `CommandFrame.lifetick_echo[axis_id]`.

4. **DenSi / device**
   - Reads `CommandFrame.lifetick_echo[axis_id]`.
   - Copies it into `lifetick_rx` in telemetry (mirroring), so the UI can verify that the echo is being carried.

## Notes
- With this design, if **HiP stops running or stops receiving telemetry**, it will stop emitting `EchoLifeTick` intents. The echo value in the command frame will stop advancing accordingly.
- The design is **multi-axis friendly**: the echo is tracked per axis.
- RTT is not explicitly computed here. If you want a rough RTT later, you can compare when a `lifetick_tx` value first appeared vs when you see the same value in `lifetick_rx`.
