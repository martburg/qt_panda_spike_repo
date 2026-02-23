PLC Integration over UDP

This document captures the constraints, design decisions, and current implementation shape for the PLC boundary.

Constraints

PLC communication is UDP.

The wire format is fixed by the PLC (semicolon-delimited strings, order-sensitive).

We do not get “nice transport features” (acks, ordering, retries) from the PLC side.

Therefore we must design for loss, duplication, and reordering.

Important property: full-state setpoints

The PLC accepts full-state setpoints per tick (not only incremental commands).

This is the single most important constraint-relaxer, because it makes the command stream effectively idempotent:

drops are corrected by the next tick

duplicates are harmless

minor reordering is typically tolerable

This is why Steuerung3D prefers producing a complete CommandFrame every tick.

Boundary architecture

We separate the PLC boundary into three layers.

1) Link (bytes move)

Example: UdpLink

Responsibilities:

sockets, bind/target, non-blocking drain

no knowledge of the PLC message meaning

2) PLC Codec (bytes mean something)

Example: PlcCodec

Responsibilities:

encode CommandFrame → PLC command datagram

decode PLC telemetry datagram → TelemetrySnapshot (best-effort)

Telemetry decoding is intentionally robust:

invalid or partially parsed packets are ignored

3) Device adapter (connects core to PLC)

We implement device_step(state, command_frame, dt) via:

PlcEndpoint (one PLC, owns some axes)

MultiPlcDevice (N endpoints, fan-out TX, fan-in RX, merge state)

This keeps the core clean and makes mixed axis assignments a configuration problem.

Mixed axis assignments

We must support multiple real-world assignment modes:

one PLC per axis

Anton at 172.16.17.1

Burt at 172.16.17.2

Cecil at 172.16.17.3

Debby at 172.16.17.4

one PLC controls multiple axes

mixed (some PLCs single-axis, some multi-axis)

Design choice:

model N endpoints each with a list of owned axes

validate that no axis is owned by more than one endpoint

Merge policy (v0.1 default)

When multiple PLCs provide telemetry, we merge as follows:

Axis measurements:

for each received snapshot, apply axis values for axes contained in that snapshot

Global flags:

estop = OR across latest snapshots received this tick (safe default)

fault = OR across latest snapshots received this tick (safe default)

Core mode:

core-owned (we do not overwrite MachineState.core_mode from PLC telemetry in v0.1)

PLC-reported mode may still be logged for debugging

These policies are intentionally conservative and can be refined later.

Telemetry “latest wins”

We explicitly avoid telemetry backlog:

each endpoint drains a limited number of datagrams per tick

we keep only the latest valid snapshot per endpoint

older snapshots are effectively dropped

This preserves responsiveness in the UI and prevents stale telemetry from catching up after pauses.

Configuration status: TOML is a stub for now

A TOML config format is present in code because it will be needed once multi-axis deployments become common.

However, today (while we are still single-axis / early bring-up) we intentionally keep the PLC endpoint mapping hardcoded in apps/plc_stack/main.py.

Rationale:

field mapping for PLC telemetry is still evolving

we want fewer moving parts during early bring-up

hardcoding keeps runtime behavior obvious and avoids config drift

Planned next step:

move endpoint mapping (IP/ports/axis ownership) into TOML once:

we have more than one axis in active use, and

the PLC telemetry field map is stabilized.

Future improvements (non-blocking)

Record additional log kinds:

udp_tx_plc / udp_rx_plc for byte-level correlation

Support “single bind port” demux by source IP if PLCs all send to the same port

Introduce richer non-PLC channels (ZMQ/NATS/etc.) using the same Link/Codec split