# Transport layer

This project uses a *transport* abstraction to decouple the **core engine** from any particular IO mechanism
(in-process queues, UDP, pipes, websockets, etc.).

Today we ship:

- an in-process transport (`InMemTransport`) for the original v1 streams (intents + telemetry)
- an expanded in-process transport (`InMemTransportV2`) for all runtime streams
- JSONL recording wrappers (`LoggedTransport`, `LoggedTransportV2`)

The PLC integration lives in an *edge adapter* (UDP + codec) and is intentionally kept outside the core.

## What “transport” means here

A *transport* is the boundary between:

- **Producers:** UI/CLI clients publishing intents (operator actions, mode changes, jog commands…)
- **Core engine:** consumes intents and emits telemetry snapshots and command frames.
- **Input devices:** can publish raw_controls (the pre-joy2intent seam).

Transport is *not* “networking”. It is an interface that can be backed by networking later.

## Current implementation

### InMemTransport (authoritative in-process transport)

`InMemTransport` provides:

- `publish_intent(intent)` / `drain_intents()`
- `publish_telemetry(snapshot)` / `drain_telemetry()`

It is deliberately minimal and deterministic (good for unit tests and for record/replay).

### TransportV2 (full stream set)

Newer stacks use `TransportV2`, which adds two more streams:

- `raw_controls`: inputd/gamepad -> joy2intent
- `command_frames`: core -> device adapters

`InMemTransportV2` implements all four streams.

### LoggedTransport / LoggedTransportV2 (recording wrappers)

`LoggedTransport` wraps a transport and records traffic to JSONL via `JsonlRecorder`.

Recorded streams are used for:

- offline debugging (what intent caused what state change?)
- deterministic replay
- future regression tests

### Deep debugging: multi-stream logging

**Status: implemented.**

The JSONL recorder supports these record kinds:

- `intent`
- `telemetry`
- `raw_controls`
- `command_frame`

To *use* these logs, see `docs/logging.md` and the `log_viewer` CLI.

## Legacy / compatibility (“shim”)

Older code used `InMemBus` (deque-based).

A **shim** is a thin compatibility layer that keeps old imports working while routing behavior to the new implementation.

In our case:

- Old imports like `from steuerung3d.protocol.inmem_bus import InMemBus`
- can temporarily return an object backed by `InMemTransport`,
- while raising deprecation warnings and guiding migration.

Goal: remove duplicate queue/bus implementations and converge on `InMemTransport`.
