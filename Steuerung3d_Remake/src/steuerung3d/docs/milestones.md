# Milestones

This is a living checklist of what we’ve already achieved and what comes next.

## Achieved

### Foundation
- Core tick + `MachineState` scaffolding
- Intents + telemetry stream separated from the core logic

### Transport
- Converged on `InMemTransport` as baseline transport
- Deprecated legacy deque-based bus approach via a shim/migration path

### TOML (active, stub phase)
- TOML loader implemented for PLC stack config
- Validation rules (axis ownership, ports, names)
- Default `configs/plc_stack.toml` established
- `apps/plc_stack` reads TOML via `--config` (default path provided)

### Multi-axis (SIM-first, config-driven)
- Multi-axis SIM device path tested (X/Y jogging)
- TOML-driven multi-axis test proves config → axes → engine works
- `apps/plc_stack` “builder path” keeps tests and runtime aligned
- PLC endpoint construction is importable + unit-testable (fake UDP links)

### Logging / deep debugging (implemented)
- JSONL recording exists for intents + telemetry
- Command frames are recorded per tick (`kind="command_frame"`)
- Replay tooling can read command frames and compare against generated frames
- Smoke tests cover command-frame logging invariants (e.g., ESTOP clamp)

## Next goals (reordered priorities)

### 1) Finish TOML activation across stacks
- migrate other app entrypoints (dev/replay tools) to the TOML config approach
- document per-stack schema and defaults
- (optional) add a “config lint” CLI command

### 2) Multi-axis beyond SIM
- confirm CommandFrame semantics for N axes (ordering, defaults)
- define how to handle unexpected/absent axes (should be prevented by validation)
- harden multi-endpoint runtime behavior (timeouts, diagnostics)

### 3) Logging usability
- add a small CLI “log viewer” for commanded vs measured over time
- add regression tests that compare commandframe sequences across versions

## Side milestone (later / “when bored”)
- PLC simulator (minimal) for integration tests without real PLCs
