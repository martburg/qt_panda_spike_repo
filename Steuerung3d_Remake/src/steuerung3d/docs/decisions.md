# Design decisions

This file collects the *reasons* behind major architectural choices.
Think of them as lightweight ADRs (Architecture Decision Records).

## 1) Transport abstraction (InMemTransport as baseline)

**Decision:** The core engine talks to a `Transport` API, not directly to sockets/UDP/UI.

**Reason:**
- unit tests become deterministic
- record/replay is natural
- IO backends can evolve without rewriting the core

## 2) Full-state setpoints (CommandFrame)

**Decision:** The device boundary consumes full-state commanded setpoints each tick.

**Reason:**
- matches PLC reality (“full state setpoints”)
- simplifies recovery: any tick contains the whole intended state
- makes logging + debugging more meaningful (“what did we command?”)

## 3) UDP for PLC edge adapter

**Decision:** We stick to UDP for PLC communication.

**Reason:**
- no influence on PLC sender/receiver side
- PLC protocol is already UDP
- we keep reliability features at higher layers if needed, but do not require them

## 4) Config file over environment variables

**Decision:** Prefer TOML config checked into the repo (or deployed alongside it).

**Reason:**
- reproducible setups (especially important on set)
- easier to review and share
- supports multi-endpoint + multi-axis mapping cleanly

## 5) Multi-axis mapping is config-owned

**Decision:** Axis-to-PLC assignment lives in config, not code.

**Reason:**
- supports “one PLC per axis” and “one PLC for multiple axes”
- avoids hardcoding rig topology
- allows incremental migration from legacy setups

## 6) Builders are importable (testable wiring)

**Decision:** `apps/plc_stack` exposes `build_core` and `build_plc_device` as importable functions.

**Reason:**
- tests can validate “real wiring” without running CLI entrypoints
- PLC construction can be tested with fake links (no sockets, no PLC needed)
- production and tests stay aligned

## 7) Deep debugging via CommandFrame logging

**Decision:** Record command frames per tick alongside intents + telemetry in JSONL.

**Reason:**
- enables “commanded vs measured” analysis offline
- makes replay deterministic and regression-friendly
- catches accidental behavior changes early
