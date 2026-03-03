# DenSi Fleet Launcher

This helper starts **one DenSi window per axis** with **unique UDP command ports**.

Why: during setup you often want to jog multiple winches in parallel (multi-select on the gamepad),
and the easiest way to make this visible in the simulator is to run multiple DenSi instances.

## Quick start

### Launch from your gamepad mapping

If your `configs/services/joy2intent.toml` contains:

```toml
[selection]
winch_ids = ["Anton", "Debby", "Cecil", "Burt"]
```

Run:

```bash
python -m steuerung3d.apps.densi_fleet --from-joy2intent configs/services/joy2intent.toml --also-core
```

This will:

* start `core_udp_service` configured to broadcast command frames to ports `52001..` (one per axis)
* start one DenSi per axis binding those ports

### Manual list

```bash
python -m steuerung3d.apps.densi_fleet --axis Anton --axis Debby --axis Cecil --axis Burt --also-core
```

## Ports

* DenSi `CommandIn`: `127.0.0.1:(cmd_base + i)` (default base: `52001`)
* DenSi `TelemetryOut`: shared target `127.0.0.1:52002`

`core_udp_service` binds telemetry on `52002` and broadcasts command frames to all command ports.
