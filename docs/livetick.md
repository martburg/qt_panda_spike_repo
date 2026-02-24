# LifeTick (end-to-end health probe)

LifeTick is a small, continuous “loopback” signal to verify **end‑to‑end freshness** across the dev stack:

**Core → HiP → Core → DenSi (UI)**

We use it to quickly detect:

- stalled hops (a process stopped receiving or sending)
- mixed identities (echo from the wrong child/process)
- packet reordering or loss that makes the UI feel stale

## Signal semantics

There are **two related but different** “tick” concepts in this repo:

### 1) Legacy PLC LifeTick (device‑origin)

This is the one we keep for compatibility with the frozen TwinCAT PLC programs.

- The **PLC/device emits** a 16‑bit tick: `LifetickUItx` (uplink field 1).
- The **UI echoes** the last received tick back as `LifetickUIrx` (downlink field 25).
- The PLC uses the echoed value as a simple freshness/health signal.  
  **This is not a strict RTT measurement.** It’s a loopback staleness indicator.

In our stack this becomes:

**PLC → Core → HiP → Core → (back to PLC via DenSi/device)**

We expose two numbers to the UI:

- `device_tick` (== `LifetickUItx`)
- `lifetick_age` (== `(device_tick - lifetick_rx) mod 65536`)

### 2) Core tick (internal)

Core also has its own `CommandFrame.tick` for scheduling/replay/debugging.
Don’t confuse this with the PLC LifeTick above.


## What DenSi shows

In the DenSi panel, `txt_tick` is **not a raw tick counter**.

It shows the **LifeTick delta**:

- **Δticks** = (last_sent_tick − last_echo_tick) modulo 65536
- optionally also shown as **Δms** using the stack timebase

Interpretation:

- **Δticks ≈ 0**: echo is current (best case)
- **small Δticks**: echo is slightly behind (normal under load)
- **large / growing Δticks**: echo is not keeping up (investigate)

Wrap-around is handled using modulo arithmetic, so a rollover of the underlying 16‑bit tick does not create a spurious spike.

## Logging policy

LifeTick can generate a lot of traffic, so **LifeTick trace logging is DEBUG-only**.

If you need to debug the LifeTick path, run the stack with debug logging, e.g.:

```bash
python -m steuerung3d up --profile 1dev_sim  # (or another profile) --log-level debug ...
```

Normal `INFO` output should stay readable and focus on:

- first telemetry reception
- connection/timeout warnings
- faults and estop transitions

## Troubleshooting checklist

If Δticks grows steadily:

1. Verify all expected HiP children are running (one per axis) and receiving telemetry.
2. Confirm that the HiP identity / axis_id routing matches (no axis cross-talk).
3. Check UDP port wiring (IntentOut / TelemetryIn) for each child.
4. Temporarily enable debug logging and look for missing LifeTick rx/tx in the chain.
