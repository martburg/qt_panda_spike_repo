# Code review notes: LiveTick v3 (fixes HiP crash)

## Why you saw the crash
Your error:
- `AttributeError: 'HiPController' object has no attribute '_on_axis_selected'`
- `AttributeError: 'HiPController' object has no attribute 'start_polling'`

Those are core methods that `steuerung3d.apps.hi_p.__main__` expects.
The previous drop-in accidentally overwrote `.../controllers/hip_controller.py` with a trimmed version of the controller that did not contain those methods.

This v3 drop-in restores the *full* `hip_controller.py` from your repo snapshot and adds LiveTick changes in a minimal, non-disruptive way.

## What changed
### Added intent
- `EchoLifeTick` intent (HiP -> Core) in:
  - `src/steuerung3d/core/intents.py`
  - `src/steuerung3d/protocol/codec.py`
  - handled in `src/steuerung3d/core/intent_handler.py`

### Added command-frame field
- `CommandFrame.lifetick_echo: Dict[str,int]` (Core -> DenSi/device) in:
  - `src/steuerung3d/core/command_frame.py`
  - decoded in `src/steuerung3d/protocol/codec.py`
  - populated in `src/steuerung3d/core/executor.py`

### Added telemetry fields
- `AxisTelemetry.lifetick_tx` and `AxisTelemetry.lifetick_rx` (both default to 0 for backward compat) in:
  - `src/steuerung3d/core/telemetry.py`

### DenSi behavior
- On every DenSi tick:
  - set `lifetick_tx = state.tick`
  - mirror `lifetick_rx` from the last received `CommandFrame.lifetick_echo[axis_id]`

### HiP behavior
- On every telemetry receive:
  - read `lifetick_tx` for the currently selected axis
  - when it changes, publish `EchoLifeTick(...)`

## Compatibility / risk notes
- Telemetry decoding stays backward-compatible because the new AxisTelemetry fields have defaults.
- The echo is only advanced while HiP runs and receives telemetry (matches legacy intent).
- Core only accepts the echo if the axis is claimed by that HiP (or unclaimed).

## Suggested commit message
```
feat(livetick): add legacy-compatible livetick echo loop (hip->core->densi)

- introduce EchoLifeTick intent and per-axis lifetick_echo in CommandFrame
- extend AxisTelemetry with lifetick_tx/lifetick_rx (backward-compatible defaults)
- DenSi sets lifetick_tx and mirrors lifetick_rx from last command frame
- HiP echoes livetick_tx via intent when it changes (restores legacy semantics)
```
