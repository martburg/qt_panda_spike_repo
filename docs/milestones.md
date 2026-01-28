# Milestones

This is a living checklist of what we’ve already achieved and what comes next.

## Achieved

- Transport abstraction and InMemTransport baseline
- TOML activated across stacks (root `configs/`, `--config` on entrypoints)
- Multi-axis SIM-first path (config-driven axes)
- Importable builders for plc_stack (`build_core`, `build_plc_device`)
- JSONL recording of intents + telemetry + command frames (deep debugging)
- Logging usability:
  - log viewer CLI (commanded vs measured per tick)
  - regression test for command-frame sequence fingerprint

## Next goals

### 1) Real transport stream (UDP and beyond)
- introduce a real transport implementation for intents/telemetry streams
- keep core decoupled so other backends (pipe/websocket) can be added later

### 2) Multi-axis beyond SIM
- harden multi-endpoint runtime behavior (timeouts, diagnostics)
- clarify PLC heartbeat / staleness handling

### Side milestone
- minimal PLC simulator for integration tests without real PLCs
