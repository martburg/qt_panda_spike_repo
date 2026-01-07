# Transport Layer

This project uses a **transport seam** to decouple:

- **Producers** of messages (CLI/UI, replay engine, network adapters)
from
- **Consumers** of messages (core runner, state machine, logging, telemetry sinks)

The transport carries two logical streams:

- **Intents**: commands / user inputs / mode changes (things we want the machine to do)
- **Telemetry**: observations / measurements / state snapshots (things the machine reports)

This keeps “commanded vs measured” clean and prevents accidental coupling.

## Canonical transport: `InMemTransport`

For local runs, tests, and the “walking skeleton”, we use:

- Module: `steuerung3d.protocol.transport`
- Class: `InMemTransport`

It is the **single canonical** in-process transport.

### Interface (conceptual)

`InMemTransport` provides two channels with symmetric operations:

- `publish_intent(intent)` / `drain_intents()`
- `publish_telemetry(sample)` / `drain_telemetry()`

**Publish** pushes a message into the channel.  
**Drain** returns all currently queued messages (FIFO order), typically used once per tick.

> Note: Exact message types depend on the layer (e.g. `Intent`, `TelemetrySample`, `AxisTelemetry`, etc.).  
> The transport does not interpret messages; it just moves them.

## Why not `InMemBus`?

Historically the repo had **duplicate** deque-based `InMemBus` implementations in multiple locations.
That caused ambiguity and invited divergence.

Those modules are now **deprecated** and exist only as **shims** (compatibility aliases) pointing to `InMemTransport`.

### Deprecation policy

- `steuerung3d.core.inmem_bus` and `steuerung3d.protocol.inmem_bus` remain importable
- They may emit a `DeprecationWarning` and alias `InMemTransport` as `InMemBus`
- New code must import `InMemTransport` directly

Preferred import:

```python
from steuerung3d.protocol.transport import InMemTransport
transport = InMemTransport()
```

Old import (still works, but discouraged):

```python
from steuerung3d.protocol.inmem_bus import InMemBus
bus = InMemBus()  # actually InMemTransport
```

## Design goals of the transport seam

1. **Testability**
   - Unit tests can inject an in-memory transport and drive the system deterministically.

2. **Replaceability**
   - When we add a real network adapter (UDP, ZeroMQ, etc.), it should be a drop-in replacement at the seam.

3. **Clear ownership of concurrency**
   - The transport defines thread/process-safe boundaries.
   - The core runner/tick loop should not care whether the source is local or remote.

4. **Record/replay friendliness**
   - JSONL logging and replay can sit “next to” the transport:
     - record everything that crosses the boundary
     - replay by re-feeding intents and validating telemetry

## Typical wiring

A common pattern is:

- One central `InMemTransport` instance in the core runner
- Producers publish intents (CLI, UI, scripts, replay)
- The runner drains intents once per tick and feeds the state machine
- The runner publishes telemetry snapshots once per tick
- Observers drain telemetry (UI, logger, recorder)

```text
[ CLI / UI / Replay ] --publish_intent-->  (Transport)  --drain_intents--> [ Runner -> State Machine ]
[ Runner ]            --publish_telemetry-> (Transport)  --drain_telemetry-> [ UI / Logger / Recorder ]
```

## Future transports

The intent is to support additional transport backends without touching core logic, e.g.:

- `UdpTransport` (or `UdpAdapter`) for inter-process / inter-machine setups
- “RecordedTransport” wrappers for deterministic replay
- Optional bridging to external systems (PLC gateways, field busses, etc.)

All of these should preserve the same conceptual contract: two streams (intents + telemetry), publish/drain semantics, and no business logic inside the transport itself.
