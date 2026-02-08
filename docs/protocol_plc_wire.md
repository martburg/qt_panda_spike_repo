# PLC Wire Protocol (DenSi / KommAnton__MAIN.st aligned)

This document captures the *current, tested* on-wire behavior for the PLC-style UDP protocol used between:
- **DenSi / PLC-sim** (device side)
- **Core** (router/engine)
- **HiP** (UI / operator)

It is intended as a regression reference: if behavior changes, update tests + this document together.

## Channels and ports (typical dev profiles)

- **IntentIn** (HiP/joy2intent → Core): UDP `:51001` (JSON)
- **UI telemetry** (Core → HiP): UDP `:51002` (JSON)
- **Device command** (Core → DenSi): UDP `:52001..` (PLC-wire text, one per axis)
- **Device telemetry** (DenSi → Core): UDP `:52020` (PLC-wire text)

## Wire framing

- PLC-wire packets are ASCII/UTF-8 text with `;` as separator.
- Uplink contains an `EOD\` marker token, then a small tail block.

## LiveTick (roundtrip) semantics

**Goal:** measure the on-wire roundtrip latency in device ticks, and provide a stable “TimeTick/LifeTick” display in HiP.

### Uplink (DenSi → Core)
- **Field #1**: `LifetickUItx` (device-generated tick counter; 16-bit semantics)
- Core decodes this and forwards it to HiP as the axis tick value used by the legacy display.

### HiP behavior
- HiP displays the delta of successive ticks (legacy TimeTick behavior).
- HiP echoes the last received tick back to the device via an intent:
  - `EchoLifeTick(axis_id, value=<last LifetickUItx>)`

### Downlink (Core → DenSi)
- **Field #0**: `LifetickUIrx` (echo value from HiP, routed through Core)
- DenSi computes a “roundtrip age” (conceptually): `(LifetickUItx - LifetickUIrx) & 0xFFFF`

**Invariant guarded by tests:** Injected `LifetickUItx` must appear unmodified in UI telemetry and be echoed back as `LifetickUIrx` on the next downlink.

## E-Stop word semantics

- The uplink includes **one raw E-Stop status word** (`EStopStatus`).
- The UI “bit wrangling” panel must reflect the decoded bits from this raw word.
- The boolean `estop` state is derived from **CAUSE bits**, not from `EStopStatus != 0` (OK/ready bits can be set while not in estop).

**Invariant guarded by tests:** “OK bits only” must not force `estop=True`, but the raw word must still be preserved for UI decoding.

## Parameter mapping (PLC fields → internal keys)

Parameters are present on the wire using the legacy PLC field names. Core maps those into the internal parameter keys that HiP uses.

Examples (non-exhaustive):
- `PosMaxHardUI` → `HardMax`
- `PosMaxUserUI` → `UserMax`
- `SpeedMaxUI` → `VelMax`
- `SpeedMaxforUI` → `VelMaxMot`
- `AccIN` → `AccMax`
- `DccIN` → `DccMax`
- `FilterP/I/D/IL` → `P/I/D/IL`
- `GuidePitchUI` → `Pitch`
- `GuideRollUI` → `Roll`
- `GuideYawUI` → `Yaw`
- `RampenformUI` → `RampForm`

### Tail fields after `EOD\`
Some values arrive after the `EOD\` marker and are mapped similarly:
- `PosWinUI` → `PosWin`
- `VelWinUI` → `VelWin`
- `AccTotUI` → `AccMove`

**Invariant guarded by tests:** PLC uplink carrying these fields must populate `TelemetrySnapshot.params` with internal keys.

## Wireshark filters (quick reference)

Display filter (dev default ports):
```wireshark
udp && (udp.port==50100 || udp.port==51001 || udp.port==51002 || udp.port==52001 || udp.port==52020 || udp.port==51200)
```

Suggested coloring rules:
- Core ← intents: `udp.dstport == 51001`
- Core → HiP telemetry: `udp.dstport == 51002`
- Core → DenSi downlink: `udp.dstport == 52001`
- DenSi → Core uplink: `udp.dstport == 52020`
- inputd: `udp.dstport == 50100`
- birds/status: `udp.dstport == 51200`
