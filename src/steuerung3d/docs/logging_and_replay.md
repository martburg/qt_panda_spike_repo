Logging and Replay

Steuerung3D uses a JSONL session log to support deep debugging, reproducible tests, and post-mortem analysis.

Why JSONL

Append-only

Human-inspectable

Easy tooling (grep, jq, Python scripts)

Good “one record per event” model

Record kinds

All records share:

schema: schema identifier (currently steuerung3d.log/v1)

kind: record kind

wall_ns: local monotonic timestamp (for latency/jitter analysis)

tick: engine tick the record is associated with (best-effort for intents)

intent

Represents a client request (arm, jog, enable, estop, …).

Why log intents:

answers “what did the operator / UI ask the system to do?”

telemetry

Represents a snapshot of the system state at a tick.

Why log telemetry:

answers “what did the system report / show?”

can be replayed and compared across implementations

command_frame

Represents the complete commanded setpoints computed by the core for a tick.

Why log command frames:

closes the loop between intent and resulting commands

supports commanded vs measured analysis:

intent → state machine → command_frame (commanded)

PLC telemetry → state update (measured)

This is essential for debugging cases where:

the core produced the right command, but the device didn’t follow

the device behaved correctly, but telemetry parsing was wrong

mode/estop clamping modified commands unexpectedly

Tick stamping and causality

Telemetry and command frames have a natural tick.

Intents are stamped with the most recent telemetry tick observed by the logger wrapper (best-effort).

In a single-process dev stack this is deterministic enough to correlate events.
In a distributed deployment it is still useful, but you may later want correlation IDs if needed.

Future: byte-level PLC correlation

Once PLC telemetry parsing is stable, we can optionally log raw PLC I/O:

udp_tx_plc: what we sent (endpoint, bytes length, maybe a small hash)

udp_rx_plc: what we received (endpoint, parse status)

This turns the JSONL into an internal Wireshark and speeds up field debugging.