# Recent Dev Notes: PLC chain stabilization

Date: 2026-02-08

## Achieved (current stable invariants)
- PLC-wire chain runs with:
  - **LiveTick roundtrip** (uplink LifetickUItx → UI → downlink LifetickUIrx echo → device roundtrip measurement)
  - **E-Stop bit wrangling** (raw word preserved; `estop` derived from cause bits)
  - **Parameter mapping** (PLC field names mapped into internal keys; HiP shows params; writes roundtrip)
- Regression coverage:
  - Unit tests for codec/mapping behavior
  - Integration tests that spawn Core and verify UDP roundtrips

## Notes
- Avoid “field stealing” for ticks: LiveTick uses uplink field #1 and downlink field #0 as per ST.
- Avoid clearing `state.params` when an incoming snapshot carries an empty params dict.
