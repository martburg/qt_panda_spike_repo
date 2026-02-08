# Testing

## Quick run
```bash
pytest -q
```

## Test structure

- **Unit tests**: fast checks for codec/mapping semantics.
- **Integration tests** (`@pytest.mark.integration`): spawn Core in-process and probe UDP roundtrips to guard *on-wire* behavior.

Run only integration tests:
```bash
pytest -q -m integration
```

Run everything (default):
```bash
pytest -q
```

## PLC-wire integration regression guards

### 1) Core ⇄ HiP livetick echo roundtrip (PLC)
Test: `tests/integration/test_roundtrip_core_hip_plc.py`

What it guarantees:
- A PLC uplink line injected into Core’s device telemetry port is decoded.
- The injected `LifetickUItx` is forwarded to UI telemetry (HiP).
- When a HiP-style `EchoLifeTick` intent is sent, Core mirrors it into PLC downlink field #0 (`LifetickUIrx`).

This catches regressions where:
- uplink parsing breaks,
- device tick is not forwarded,
- echo intent isn’t applied to downlink.

### 2) Core ⇄ DenSi param write roundtrip (PLC)
Test: `tests/integration/test_roundtrip_core_densi_plc.py`

What it guarantees:
- Param edit + write intents produce a PLC downlink telegram with `Modus == 'w'`.
- The probe reflects the written values into uplink.
- Core forwards them to UI telemetry as internal parameter keys (e.g. `P`, `HardMax`, etc.).

This catches regressions where:
- params are on the wire but not mapped to `TelemetrySnapshot.params`,
- core accidentally clears cached params,
- write-mode downlink is malformed.

## Debugging tips

- Verify UDP flows with **Statistics → Conversations → UDP**.
- Use **Follow → UDP Stream** to see whether packets are PLC-wire text or JSON.
