# Transport layer

This project uses a *transport* abstraction to decouple the **core engine** from any particular IO mechanism
(in-process queues, UDP, pipes, websockets, etc.).

Today we ship an in-process transport (`InMemTransport`) and a JSONL recording wrapper (`LoggedTransport`).
The PLC integration lives in an *edge adapter* (UDP + codec) and is intentionally kept outside the core.

## What “transport” means here

A *transport* is the boundary between:

- **Producers:** UI/CLI clients publishing intents (operator actions, mode changes, jog commands…)
- **Core engine:** consumes intents and emits:
  - telemetry snapshots (state)
  - command frames (the “full-state setpoint” the device should follow)

Transport is *not* “networking”. It is an interface that can be backed by networking later.

## Current implementation

### InMemTransport (authoritative in-process transport)

`InMemTransport` provides:

- `publish_intent(intent)` / `drain_intents()`
- `publish_telemetry(snapshot)` / `drain_telemetry()`

It is deliberately minimal and deterministic (good for unit tests and for record/replay).

### LoggedTransport (recording wrapper)

`LoggedTransport` wraps a transport and records traffic to JSONL via `JsonlRecorder`.

Recorded streams are used for:

- offline debugging (what intent caused what state change?)
- deterministic replay
- future regression tests

### Deep debugging: CommandFrame logging

**Status: implemented.**

The architecture logs **CommandFrames** alongside intents and telemetry:

- `CoreEngine` calls an optional `on_command_frame(cmd_frame)` hook each tick.
- `JsonlRecorder.record_command_frame(...)` writes `kind="command_frame"` records to JSONL.
- `JsonlReader.iter_command_frames()` reads them back.
- The replay path can compare generated vs recorded command frames to detect nondeterminism/regressions.

To *use* these logs, see `docs/logging.md` and the `log_viewer` CLI.

## Legacy / compatibility (“shim”)

Older code used `InMemBus` (deque-based).

A **shim** is a thin compatibility layer that keeps old imports working while routing behavior to the new implementation.

In our case:

- Old imports like `from steuerung3d.protocol.inmem_bus import InMemBus`
- can temporarily return an object backed by `InMemTransport`,
- while raising deprecation warnings and guiding migration.

Goal: remove duplicate queue/bus implementations and converge on `InMemTransport`.
