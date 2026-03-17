# Runtime profiles

Profiles live in `configs/profiles/*.toml` and are referenced via:

```bash
python -m steuerung3d up --profile <name>
```

## Available profiles

- `1dev_sim.toml` — single-machine dev simulation stack.
- `1dev_sim_remote.toml` — dev simulation with remote endpoints.
- `1dev_sim_remote_joy.toml` — dev simulation + remote joystick path (current smoke default).
- `anton_core_densi.toml` — core + DenSi for Anton.
- `dev_real.toml` — real hardware profile (use with care).
- `dev_sim.toml` — dev simulation.
- `dev_sim_c2.toml` — dev simulation variant.
- `dev_sim_c2_only.toml` — dev simulation variant.
- `joy_local_to_remote_core.toml` — joystick local -> remote core wiring.
- `only_densi_anton.toml` — DenSi-only for Anton.

Named stack profiles live under `configs/profiles/*.toml`. Direct `.toml` paths still work when passed explicitly.
