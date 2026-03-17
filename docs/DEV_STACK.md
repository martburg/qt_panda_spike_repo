# Dev stack and boot profiles

There are two ways to run local demos:

For stack/profile structure and interpolation rules, see:

- `docs/PROFILES.md`


1) **Profile-driven boot (recommended)**

```powershell
python -m steuerung3d up --profile dev_sim
```

2) The historical single-process dev runner:

```powershell
python -m steuerung3d.apps.dev_stack --config configs\dev_plc.toml
```

The profile-driven supervisor is the “real” boot path going forward:

- one reusable supervisor/runtime (`StackRuntime`)
- per-run session logging (one log per process)
- structured birds-eye status via a UDP JSON heartbeat side-channel

See: `docs/STACK_BOOT_STATUS.md`

---

## Legacy dev_stack (single process)

`python -m steuerung3d.apps.dev_stack --config <file.toml>` runs a small end-to-end demo.

What it does:

- runs `CoreEngine` in a real-time loop (`CoreRunner`)
- drains intents from a transport, applies them to `MachineState`
- calls the configured device adapter (`device.step(...)`) every frame
- publishes telemetry snapshots back to the transport
- prints snapshots periodically and toggles ESTOP once during the run

### Run it

Run from the **repo root**:

```powershell
python -m steuerung3d.apps.dev_stack --config configs\dev_plc.toml
```

If you run from `src/` you must adjust the path:

```powershell
python -m steuerung3d.apps.dev_stack --config ..\configs\dev_plc.toml
```

---

## UDP HiP ↔ Core ↔ DenSi demo (parameter editing)

For the HiP/DenSi split UI ("Yellow"), run three processes (three terminals):

**Windows Terminal tip (recommended):**
- Open a terminal in the repo root (Explorer address bar → type `wt` → Enter)
- Split into 3 panes (`Alt+Shift+D` twice)
- In each pane, activate your environment and ensure you're in the repo root.

Also make sure you run the modules as `python -m steuerung3d...` (not `src.steuerung3d...`). If needed, do:

```powershell
python -m pip install -e .
```


1) Core UDP service

```powershell
python -m steuerung3d.apps.core_udp_service --dt 0.1
```

2) DenSi (device endpoint simulator)

```powershell
python -m steuerung3d.apps.den_si
```

3) HiP (operator UI)

```powershell
python -m steuerung3d.apps.hi_p
```

### What to try

In HiP:

- Click **Pos Edit** → fields unlock (white) for that group.
- Enter new values → click **Pos Write** (sends a commit via the command frame).
- Click **Pos Cancel** to abort the edit session.

Notes:

- DenSi starts in a **stopped / not-OK** state by default.
- DenSi’s Edit/Write/Cancel controls are disabled (device-side); editing happens only from HiP.
- Editing is **modal** in HiP: after pressing Edit for a group, other Edit buttons and tab switching are disabled until Write/Cancel.
- HiP↔Core delivery is guarded with `req_id` acks; device-side acceptance is confirmed by observing DenSi’s `params` in telemetry.
- While editing, HiP does not overwrite the active fields with incoming telemetry.
- After Write, HiP shows a **modal dialog** once the device is observed as applied (or after a timeout).
- If HiP must auto-adjust **pos limits** to satisfy `HardMax ≥ UserMax ≥ UserMin ≥ HardMin`, it shows an info dialog with the corrections before sending.
- Guider `PosMin/PosMax` are enforced by **clamping** to `PosMin ≤ PosMax` (no swapping).


## PLC TwinCAT Legacy (Fleet) vs UDP SIM fallback

When running with `plc_twincat_legacy_fleet` on a machine that does **not** have the configured controller IP
(e.g. `172.16.17.5`) present, `dev_stack` will automatically fall back to a local UDP simulation fleet.

The UDP SIM fleet:
- spawns one simulated PLC endpoint per axis
- uses loopback IPs (`127.0.0.x`) so multiple simulated PLCs can share the same remote port (e.g. 15001)
- matches the **measured truth** semantics:
  - `AxisState.enabled` is derived from uplink `Status==4356` and `EStopStatus==0`

See: `docs/PLC_TWINCAT_LEGACY.md`

## Device selection

The device adapter is selected by `device.kind` in TOML:

- `sim` (default): local plant simulation
- `udp_plc_toy`: early semicolon UDP adapter (`adapters/plc/udp_device.py`)
- `plc_twincat_legacy_fleet`: legacy TwinCAT UDP adapter (**obsolete**, see `docs/OBSOLETE.md`) (Anton/Burt/Cecil/Debby…)

See `docs/CONFIG_TOML.md` for the schema and examples.

## UDP SIM fallback (off-network development)

When `device.kind = "plc_twincat_legacy_fleet"`, the dev stack checks whether it can bind to
`controller_ip` (e.g. `172.16.17.5`).

- If the IP exists on the current machine, it uses the real legacy device fleet.
- If the IP is *not* present (common on a laptop/off the PLC network), it automatically starts
  loopback “PLC simulators” and talks to those instead.

This allows you to test:

- LifeTick loopback (16-bit tick) from Core -> HiP -> Core -> DenSi; DenSi shows delta (now - echoed) in its tick field.
- encoding/decoding
- device/fleet wiring
- telemetry integration

…without requiring real PLCs.

---

## Running the full multi-axis demo (profile-driven)

The legacy `setup_stack` wrapper has been **removed**. All local demo wiring is now done via
the profile-driven supervisor:

```powershell
python -m steuerung3d up --profile 1dev_sim
```

This launches the typical local demo stack:

- `core_udp_service`
- `den_si` (one per axis)
- `hi_p` (single in `1dev_sim`)
- optional joystick helpers (`inputd`, `joy2intent`)

Logs and per-process status output are written under `.run/<profile>/...`.

---

## Output

The demo prints one line every ~0.5 seconds at 100 Hz, for all configured axes, e.g.:

```
[dev_stack] controller_ip=172.16.17.5 not present on this host -> using UDP SIM fallback for plc_twincat_legacy_fleet
tick=   50 t=  0.50s mode=LIVE estop=False Anton(...) Burt(...) Cecil(...) Debby(...)
```

Logs are written to `logs/session.jsonl` (JSON Lines) via the recorder.

## Notes

- Windows does not ship `curses` by default; the dev stack is plain stdout for portability.
- UDP on Windows may raise `WinError 10054` (ICMP Port Unreachable mapped to a socket error). The UDP
  device adapters treat this like a dropped packet (best effort receive).
  Config path: run from repo root, pass --config configs/dev_plc.toml (or mention relative path).
- PLC network fallback:
  when controller IP (e.g. 172.16.17.5) not present, dev_stack automatically uses UDP SIM fleet
  mention loopback IP strategy 127.0.0.x so all sims can share port 15001
- One truth policy:
  AxisState.enabled is measured (uplink), derived from Status=4356 and EStopStatus=0
  commanded enable is not the truth (optionally available in ax.meta["cmd_enable"] if you kept it)




### Recommended port plan (Windows-safe)

With 4 axes and `--cmd-base 52001`, DenSi command ports are:

- `cmd-in`: `52001..52004`

**Do not** use `52002` for device telemetry in that case (it overlaps with Debby's command port).

Pick a device telemetry port outside that range, e.g. `52020`:

- Core binds: `--dev-telem-in 127.0.0.1:52020`
- DenSi targets: `--telem-out 127.0.0.1:52020`

UI telemetry (Core → HiPs) uses one port per axis, e.g. `--ui-telem-base 51002` → `51002..51005`.
UI intents (HiPs → Core) use `127.0.0.1:51001` by default.

### Run the full stack

From repo root:

```powershell
python -m steuerung3d up --profile 1dev_sim
```

To run multi-axis demos, use a profile under `configs/profiles/` (or create one) and point it at the desired axes and ports.

Use `configs/profiles/` as the named-profile source of truth.


### How to verify wiring quickly

- DenSi window title shows: `DenSi(<axis>) cmd-in=<host:port> telem-><host:port>`
- HiP window title shows: `HiP(<axis>) telem-in=<host:port> intent-><host:port>`
- Pressing **RequestEstopReset** (historical name; used as drive reset/clear fault in the sim) in one HiP must only affect its corresponding DenSi/axis.

### Parameter editing: why timeouts happened (and the fix)

In multi-axis runs, the HiP transaction layer resends if it does not observe its `req_id` in `core_acks`.
The telemetry receiver can drain multiple snapshots per poll; if the code only checks the **last** snapshot,
it can miss the one-shot ack even though the write succeeded. The fix is to process `core_acks` across **all**
drained snapshots, then render using the last snapshot.
