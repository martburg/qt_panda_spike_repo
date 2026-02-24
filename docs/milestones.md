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
- Profile-driven boot supervisor (`python -m steuerung3d up ...`) with per-session logs and birds-eye status
- SIM vs REAL boot semantics via `[rig].device_source` (REAL: discover devices from telemetry, then provision HiP pool)

## Next goals

### 1) Real transport stream (UDP and beyond)
- introduce a real transport implementation for intents/telemetry streams
- keep core decoupled so other backends (pipe/websocket) can be added later

### 2) Multi-axis beyond SIM
- harden multi-endpoint runtime behavior (timeouts, diagnostics)
- clarify PLC heartbeat / staleness handling

### Side milestone
- minimal PLC simulator for integration tests without real PLCs


## 2026-01: Joystick + setup stack integration (local demo)

Completed:

- `inputd` gamepad listener (pygame) with compact console output
- `joy2intent_gamepad.toml` mapping for **setup jogging** (deadman, select winch buttons, fine, left-y)
- Profile-driven `up --profile ...` launches the stack (Core + DenSi + HiP + optional inputd/joy2intent).
- Strict per-axis device command routing (no broadcast) + port overlap guards
- Per-axis UI telemetry slicing (HiPs no longer “pick up” other DenSis)
- HiP txn ack robustness (process `core_acks` across drained snapshots to avoid false timeouts)

Next goals:

1. **Prod PLC targets**
   - Replace localhost targets with configurable axis→(host,port) mapping (e.g. 172.16.17.x)
   - Ensure core_udp_service unicast targets match the PLC network topology

2. **Setup mode ergonomics**
   - One HiP per axis: consistent axis identity in window title + `cmb_axis`
   - Clarify “RequestEstopReset” semantics as drive reset/clear fault (not Safety PLC E-Stop reset)

3. **Joystick → setup intents**
   - Finalize selection semantics (multi-select buttons; one DenSi→one axis)
   - Auto-claim + enable gating under deadman; consistent GUI reflection

4. **Kinematics seam**
   - Add a kinematics module boundary for future 3D rig modes (mapping joystick to multi-winch commands)
