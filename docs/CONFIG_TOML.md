# TOML configuration

Most applications select a device adapter and runtime parameters using a TOML file.

In v0.x the dev stack uses these keys:

- `[device]`
  - `kind` (string) selects the adapter

Supported `kind` values:

- `sim` (default)
- `udp_plc_toy`
- `plc_twincat_legacy_fleet` (**obsolete**, see `docs/OBSOLETE.md`)

---

## `sim`

No extra configuration is required.

```toml
[device]
kind = "sim"
```

---

## `udp_plc_toy`

Early semicolon-separated adapter (`src/steuerung3d/adapters/plc/udp_device.py`).

```toml
[device]
kind = "udp_plc_toy"

[device.udp_plc_toy]
remote_ip = "127.0.0.1"
remote_port = 55001
```

---

## `plc_twincat_legacy_fleet`

> Status: **obsolete**. Kept for older field rigs and reference. Prefer `sim` or the schema-driven PLC adapter (`steuerung3d.adapters.plc`).


Legacy TwinCAT/Beckhoff UDP protocol used by the winches (Anton/Burt/Cecil/Debby…).

### Structure

```toml
[device]
kind = "plc_twincat_legacy_fleet"

[device.plc_twincat_legacy_fleet.defaults]
controller_ip = "172.16.17.5"
remote_port = 15001
timeout_s = 0.02
modus = "E"
intent = true

[[device.plc_twincat_legacy_fleet.axes]]
axis_id = "Anton"
remote_ip = "172.16.17.1"
local_port = 15001

[[device.plc_twincat_legacy_fleet.axes]]
axis_id = "Burt"
remote_ip = "172.16.17.2"
local_port = 15002

[[device.plc_twincat_legacy_fleet.axes]]
axis_id = "Cecil"
remote_ip = "172.16.17.3"
local_port = 15003

[[device.plc_twincat_legacy_fleet.axes]]
axis_id = "Debby"
remote_ip = "172.16.17.4"
local_port = 15004
```

### Meaning

- `controller_ip`: local IP to bind per-axis UDP sockets to. On the real controller network this is typically `172.16.17.5`.
- `remote_ip`: PLC/winch IP.
- `remote_port`: UDP port on each PLC for this legacy protocol (commonly `15001`).
- `local_port`: per-axis local port on the controller side. In the legacy system this is typically `15001..15006`.

### Off-network fallback

`apps/dev_stack` checks whether `controller_ip` exists on the current machine.
If it does not (e.g. you run on a laptop off the PLC subnet), dev_stack automatically falls back to
loopback UDP simulators while still exercising the same codec/device code path.

See `docs/DEV_STACK.md`.
