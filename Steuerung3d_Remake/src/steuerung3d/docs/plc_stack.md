# PLC stack (UDP edge adapter)

`apps/plc_stack` is the intended “real rig” entry point that connects the core engine to PLCs via UDP.

It is split into:

1. **Core wiring** (config → axes → transport/logging → engine) in an importable builder module
2. **PLC edge adapter** (UDP + codec) constructed from config

This split is intentional so unit tests can use the *real app wiring* while swapping the device implementation.

## Key property of the real PLC

The PLC accepts **full state setpoints** (not incremental commands).

This matches our `CommandFrame` approach:
each tick the engine emits the full commanded state for all axes.

## Builder surface (importable API)

### `build_core(cfg, device_step, enable_logging=True)`

Builds:

- `MachineState` with axes from config
- `InMemTransport` (optionally wrapped with JSONL logging via `LoggedTransport`)
- `CoreEngine` wired to:
  - drain intents from transport
  - apply intents
  - call `device_step(state, command_frame, dt)`
  - publish telemetry
  - record command frames (deep debugging)

Returns a runtime bundle (transport, engine, state, timebase).

### `build_plc_device(cfg, link_factory=None, codec_factory=None)`

Builds the PLC edge adapter:

- for each configured endpoint:
  - `UdpLink(bind=(...), target=(...))`
  - `PlcCodec(spec=PlcWireSpec(...))`
  - `PlcEndpoint(name, axis_ids, link, codec)`
- validates endpoint/axis ownership
- returns `(MultiPlcDevice, endpoints)`

The optional factories exist so unit tests can pass **fake links/codecs**
and avoid binding sockets.

## App entrypoint

```bash
python -m steuerung3d.apps.plc_stack --config configs/plc_stack.toml
```
