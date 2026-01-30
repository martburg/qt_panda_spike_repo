# Design decisions

This file collects the *reasons* behind major architectural choices.
Think of them as lightweight ADRs (Architecture Decision Records).

## 1) Transport abstraction (InMemTransport as baseline)

**Decision:** The core engine talks to a `Transport` API, not directly to sockets/UDP/UI.

**Reason:** deterministic tests, record/replay, replaceable IO.

## 2) Full-state setpoints (CommandFrame)

**Decision:** The device boundary consumes full-state commanded setpoints each tick.

**Reason:** matches PLC reality; improves recovery; improves debuggability.

## 3) UDP for PLC edge adapter

**Decision:** Stick to UDP for PLC communication.

**Reason:** PLC is fixed; reliability handled elsewhere if needed.

## 4) Config file over environment variables

**Decision:** Prefer TOML config checked into the repo.

**Reason:** reproducible on set; reviewable; supports multi-endpoint mapping.

## 5) Multi-axis mapping is config-owned

**Decision:** Axis-to-PLC assignment lives in config, not code.

**Reason:** supports mixed assignments; avoids hardcoded topology.

## 6) Builders are importable (testable wiring)

**Decision:** `apps/plc_stack` exposes `build_core` and `build_plc_device`.

**Reason:** tests and production stay aligned; PLC construction testable without sockets.

## 7) Deep debugging via CommandFrame logging

**Decision:** Record command frames per tick alongside intents + telemetry in JSONL.

**Reason:** commanded vs measured analysis; deterministic replay; catches regressions.

## 8) Regression testing via command sequence fingerprint

**Decision:** Maintain a stable fingerprint (hash) of the command-frame sequence for a deterministic scenario.

**Reason:** quickly detects accidental behavioral drift across refactors.


## 2026-01-30: No broadcast to PLC endpoints (strict per-axis routing)

**Decision:** Device command traffic is strictly **one datagram per axis per tick**, routed to a unique target per axis.
Broadcast fallback is removed.

**Rationale:**
- PLC code is frozen; it cannot implement “ignore unrelated fields/axes”.
- Broadcast hides configuration mistakes and creates dangerous cross-talk (resets/params applied to multiple axes).
- Per-axis routing matches the final network topology (PLCs at 172.16.17.x).

**Implementation notes:**
- Launchers enforce `len(axes) == len(dev_cmd_targets)` in multi-axis mode.
- Guard against port overlap between DenSi `cmd-in` range and Core `dev_telem_in`.
- UI telemetry is sliced per axis so each HiP sees only its axis state/params/commit status.
