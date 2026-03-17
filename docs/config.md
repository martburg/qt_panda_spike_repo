# Configuration (TOML)

This repo currently supports **two** configuration “surfaces”:

1) **Profile-driven stacks (recommended)** — `python -m steuerung3d up --profile …`  
2) **Single-process demo runners** — `python -m steuerung3d.apps.<app> --config …`

3) **Deployments (distributed setups)** — `python -m steuerung3d up --deployment …`

Deployments are the recommended configuration surface once services are intentionally run across multiple machines.
See: `docs/deployments.md`

The goal is to make local development easy *without* coupling core logic to any particular IO mechanism.

---

## 1) Profile-driven stacks (recommended)

Profiles live in:

- `configs/profiles/*.toml` (source of truth)


They describe:

- which **services** to run (core / hip / densi / joy2intent / inputd / …)
- how to **wire** them (ports, endpoints, enabled flags)
- axis expansion (e.g. one service per axis)

CLI entry points:

```powershell
python -m steuerung3d profiles
python -m steuerung3d up     --profile dev_sim
python -m steuerung3d plan   --profile dev_sim
python -m steuerung3d status --profile dev_sim
python -m steuerung3d logs core --profile dev_sim --follow
python -m steuerung3d down   --profile dev_sim
```

See also: `docs/STACK_BOOT_STATUS.md`

---

## 2) Single-process runners (still useful)

These are *not* the preferred long-term boot path, but they remain handy for quick isolated demos
and for debugging specific seams.

### Dev stack (core + device adapter, single process)

Config:

- `configs/dev_plc.toml`

Run:

```powershell
python -m steuerung3d.apps.dev_stack --config configs\dev_plc.toml
```

This runner can automatically fall back to a **UDP SIM fleet** when the configured controller IP
(e.g. `172.16.17.5`) is not present on your host.

### PLC stack (edge adapter / seam tests)

Config:

- `configs/plc_stack.toml`

Run:

```powershell
python -m steuerung3d.apps.plc_stack --config configs\plc_stack.toml
```

### Joystick pipeline demos

Configs:

- `configs/services/joy2intent.toml`
- `configs/services/joy2intent.toml`
- `configs/inputd_gamepad.toml`

Run (example):

```powershell
python -m steuerung3d.apps.joy2intent --config configs\services\joy2intent.toml
python -m steuerung3d.apps.inputd    --config configs\inputd_gamepad.toml
```

(Exact wiring for the end-to-end joystick → intent → core path is typically handled via a stack profile.)

### Log viewer defaults

Config:

- `configs/log_viewer.toml`

Run:

```powershell
python -m steuerung3d.apps.log_viewer <path/to/session.jsonl> --config configs\log_viewer.toml
```

---

## What’s intentionally *not* here

Older docs referenced configs such as `configs/dev_stack.toml`, `configs/core_service.toml`,
`configs/cli_client.toml`, `configs/replay_player.toml`. In this repo snapshot those files are **not present**,
so those references were removed to avoid confusion.

If/when those runners return, reintroduce the config docs alongside the actual files under `configs/`.

---

## Docs location

Project documentation lives in `docs/` at the repository root.
The previous `src/steuerung3d/docs/` package mirror has been removed to avoid drift.
