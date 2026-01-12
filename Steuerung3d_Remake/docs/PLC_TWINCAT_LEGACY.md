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
