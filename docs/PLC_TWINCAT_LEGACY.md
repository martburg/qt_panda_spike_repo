# PLC TwinCAT Legacy Protocol (v0.1 Contract)

This document defines the **semantics + invariants** for the legacy TwinCAT UDP protocol used by the winches
(e.g. Anton/Burt/Cecil/Debby). The goal is to make the protocol *explicit* and testable while we modernize the stack.

## Scope

- Transport: UDP
- Encoding: UTF-8 text line, semicolon-separated fields (`;`), typically with a trailing `;`
- One UDP endpoint per winch axis
- One downlink line sent each frame (watchdog)
- One uplink line received (best effort) each frame

> Canonical field order lives in code:
> - Uplink fields: `WINCH_UP_FIELDS` in `src/steuerung3d/adapters/plc_twincat_legacy/codec.py`
> - Downlink fields: the downlink model + encoder in the same module.

This doc documents the **meaning** and **rules**; the exact field positions are authoritative in the codec constants.

---

## Wire framing

### Downlink (controller → PLC)
- One semicolon-separated line per UDP packet.
- No quoting / escaping.
- Trailing separator `;` is allowed and expected.
- Downlink must be sent **every frame** (watchdog).

### Uplink (PLC → controller)
- One semicolon-separated line per UDP packet.
- The line is split into:
  - **Prefix**: fixed number of fields (legacy uses 38 prefix fields)
  - **EOD marker**: literal `EOD`
  - **Tail**: 7 tail fields (legacy telemetry addendum)
- Trailing separator `;` is allowed and expected.

Example shape (not literal field values):

<prefix fields...>;EOD;<tail fields...>;


---

## Invariants (must-haves)

### 1) Watchdog: send every frame
The controller must send a downlink packet for each winch **every frame**, even if no axis setpoint is present in the command.

Rationale: PLC expects a lifetick/watchdog to maintain ownership / liveness.

### 2) Lifetick source (global, deterministic)
`lifetick = CommandFrame.tick & 0xFFFF`

- The tick comes from **core**, not wall-clock.
- Mask to 16-bit for legacy compatibility.

### 3) Enable edge behavior: rebase PosSoll to PosIst
On **rising enable** (after safety gating):

- `PosSoll := last measured PosIst`
- Do **not** integrate `vel * dt` in the same enable-edge frame.
- Integration begins on the next frame.

Rationale: PLC tracks following error; rebasing prevents an immediate step error spike.

### 4) One truth: enabled is measured
`AxisState.enabled` is **PLC-reported truth**, not commanded intent.

- Commanded enable is an *intent* and may be stored separately (e.g. `AxisCommandState.enable` or `AxisState.meta["cmd_enable"]`).
- The `enabled` field in telemetry must be derived from PLC uplink state.

---

## Measured semantics (uplink interpretation)

### Key measured fields
These names refer to the decoded uplink mapping in `codec.py`:

- `PosIst` — measured position
- `SpeedIstUI` — measured speed (UI units)
- `Status` — legacy status word (numeric)
- `EStopStatus` — estop state (numeric)
- `GuideStatus` — guide state (numeric)
- `Name` — winch name / axis label (string)

### Enabled (measured truth)
Current v0.1 rule (derived from ST behavior observed):
- `STATUS_READY = 4356`
- `enabled_meas = (EStopStatus == 0) and (Status == STATUS_READY)`

This is intentionally conservative:
- If PLC does not report “ready”, we treat enabled as false.
- If estop status is nonzero, enabled is false.

### Fault
Current v0.1 rule:
- `fault = (EStopStatus != 0) or (Status != 0)`

> Note: This will likely be refined once we have live PLCs again and can map additional status codes.

---

## Command semantics (downlink intent)

### Key commanded fields (subset)
The downlink encoder in `codec.py` and the dataclass `TwinCATLegacyWinchDownlink` define the precise field list.
The controller currently uses a minimal subset:

- `lifetick` — required every frame (see invariants)
- `modus` — legacy PLC selector (default `"E"` in adapter; not core_mode)
- `control_in` — minimal enable/control bit used by the UDP SIM to decide if the axis is enabled
- `speed_soll` — commanded speed (UI units)
- `pos_soll` — local integrated position setpoint
- `own_pid`, `control_pid_tx`, `intent` — legacy session/ownership fields (present for compatibility; semantics still being validated)
- `guide_control_ui`, `guide_soll_speed` — guide control placeholders
- `estop_reset`, `resync`, `gui_not_halt` — legacy knobs (placeholders until verified)

---

## Simulation parity (UDP SIM)
The UDP simulator must reflect the same semantics as the real adapter expects:

- When simulated axis is enabled:
  - Emit `Status = 4356` in uplink.
  - Emit `EStopStatus = 0`.
- When disabled:
  - Emit `Status = 0` (or other non-ready).
- SIM should echo lifetick via `LifetickUItx` for visibility.

Implementation: `src/steuerung3d/adapters/plc_twincat_legacy/udp_sim.py`

---

## Edge adapter process (TransportV2 bridge)

When running the stack as multiple processes, we bridge the frozen PLC wire protocol
to the internal CommandFrame/TelemetrySnapshot seam via an "edge" process.

Code:

- `src/steuerung3d/adapters/plc_twincat_legacy/edge.py` (bridge logic)
- `src/steuerung3d/apps/plc_twincat_legacy_edge/__main__.py` (CLI runner)

The edge adapter consumes **CommandFrame** from a UDP `cmd-in` socket and publishes
**TelemetrySnapshot** to a UDP `telem-out` target. Separately, it talks to the real PLC
using the strict semicolon protocol.

Typical example for Anton (values from `legacy_plc_anton.md`):

```bash
python -m steuerung3d.apps.plc_twincat_legacy_edge \
  --axis Anton \
  --cmd-in 172.16.17.5:52001 \
  --telem-out 172.16.17.5:52002 \
  --plc-remote 172.16.17.2:15001 \
  --local-bind 172.16.17.5:15002
```

Notes:

- `--local-bind` must match the controller-side port the PLC expects to reply to.
- On Windows, `recvfrom()` may raise WinError 10054 when a PLC is unreachable; the edge
  adapter treats this like a dropped packet.

---

## Testing contract (regression guards)
Tests must enforce:

- Device sends every frame (even with no axis setpoint)
- Lifetick comes from `cmd.tick & 0xFFFF`
- Enable-edge rebases `pos_soll` to last `PosIst` exactly (no `vel*dt` on edge)
- `AxisState.enabled` is derived from uplink status (measured truth)
- Fleet test loads TOML config and steps all axes

---

## Open items (expected to refine with live PLC access)
- Full meaning of `control_in` bitfield and other control flags
- Complete status word mapping (beyond `4356`)
- Meaning of tail fields after `EOD`
- Ownership/session interplay (`own_pid`, `control_pid_tx`, `intent`)
- Multi-rate / dropped packet behavior under real network conditions


# PLC TwinCAT legacy UDP protocol

This adapter implements the legacy semicolon-separated UDP protocol used by the Beckhoff/TwinCAT PLC
programs for the winches (Anton/Burt/Cecil/Debby …).

The code lives in:

- `src/steuerung3d/adapters/plc_twincat_legacy/codec.py`
- `src/steuerung3d/adapters/plc_twincat_legacy/device.py`
- `src/steuerung3d/adapters/plc_twincat_legacy/fleet.py`
- `src/steuerung3d/adapters/plc_twincat_legacy/config.py`
- `src/steuerung3d/adapters/plc_twincat_legacy/udp_sim.py` (loopback simulators for off-network development)

---

## High-level behavior

- One UDP socket per axis.
- Every control frame sends a **downlink** line to each PLC.
- Every control frame attempts to receive one **uplink** line from each PLC (best effort).
- A “lifetick” must be sent **every frame**.

On Windows, UDP `recvfrom()` may raise `WinError 10054` when the remote port is unreachable. The
adapter treats this like a dropped packet.

---

## Lines and separators

- Fields are positional.
- Separator is `;`.
- Many PLC packets end with a trailing separator (`;`).
- Uplink packets contain an explicit `EOD` marker that splits prefix and tail fields.

The codec is intentionally strict about positional mapping but tolerant about extra/unknown fields.

---

## Lifetick

- The downlink contains a `LifetickUIrx` field.
- The uplink contains a `LifetickUItx` field.

The adapter uses the core **command tick** as lifetick (tests assert this).

---

## Enable edge and PLC integrator

The PLC keeps internal tracking of following error. When an axis is re-enabled, the setpoint-side
integrator must be aligned to the measured position (`PosIst`) so the PLC does not interpret an
instantaneous following error spike.

Implementation note:

- On a `False -> True` enable transition, the downlink should load the position-related integrator
  with the last received `PosIst`.

(Exact field names and behavior are preserved in the adapter and covered by tests.)

---

## Fleet wiring

The legacy system uses one controller IP and per-axis local ports, e.g.:

- PLCs: `172.16.17.1..4` (Anton/Burt/Cecil/Debby)
- Controller: `172.16.17.5`
- PLC port: typically `15001`
- Controller local ports: typically `15001..15004` (and higher for other devices)

See `docs/CONFIG_TOML.md` for the TOML schema.

---

## UDP simulators (off-network)

When you are not on the PLC subnet, `apps/dev_stack` can automatically start loopback PLC simulators
and talk to them instead:

- Each simulated PLC binds to a unique loopback IP (`127.0.0.x`) but the same port.
- The simulated PLC replies with a valid uplink line and echoes lifetick.

This is a convenience to validate codec/device behavior without real hardware.

See `docs/DEV_STACK.md`.
