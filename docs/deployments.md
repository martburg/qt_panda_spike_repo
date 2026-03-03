# Deployments (distributed service configuration)

Steuerung3D Remake is designed so that **services can run on different machines** (e.g. Core on the main controller, HiP on an operator console, DenSi on a test box, joy2intent on a remote joystick gateway).

This requires a **central deployment definition** that answers:

- What services exist for this show/site?
- Which host runs which service?
- Which per-service TOML config should each service use?
- How do we produce **offline** runtime bundles so operation does not depend on GitHub?

This document introduces a third configuration surface: **deployments**.

---

## Configuration surfaces

The repo supports three config “surfaces”, in increasing order of operational maturity:

1. **Profile-driven stacks** (recommended for local/dev): `python -m steuerung3d up --profile …`
2. **Single-process runners** (demo/debug): `python -m steuerung3d.apps.<app> --config …`
3. **Deployments** (recommended for real distributed setups): `python -m steuerung3d up --deployment …`

Profiles remain useful for local development, but deployments become the **source of truth** once services are intentionally distributed.

---

## Directory layout

Canonical locations:

- `configs/services/*.toml` — per-service configuration (ports, limits, logging knobs, etc.)
- `configs/deployments/*.toml` — **central topology** (what runs where + which service-config is used)
- optional (not versioned): `configs/deployments/private/*.toml` — per-site or per-host overrides (secrets, credentials)

Suggested rule of thumb:

- **Commit** deployments and service configs to the repo.
- Keep **secrets** out of Git (even private GitHub). Use `private/` overrides or an external path like `/etc/steuerung3d/`.

---

## Deployment file schema

A deployment TOML defines:

- an identity / version label
- a set of named hosts
- a set of services, each mapped to a host and a per-service config

Minimal example:

```toml
[deployment]
id = "show_foo"
version = "2026-03-03"
expected_git_rev = "b2f42d2" # optional: helps prevent version drift

[hosts.corebox]
addr = "172.16.17.5"

[hosts.joybox]
addr = "192.168.8.147"

[service.core]
host = "corebox"
config = "configs/services/core.toml"

[service.hip]
host = "corebox"
config = "configs/services/hip.toml"

[service.joy2intent]
host = "joybox"
config = "configs/services/joy2intent.toml"
```

Notes:

- `hosts.<name>.addr` is a human-readable mapping. It does not have to be IP-only (can be DNS).
- `service.<name>.config` is a repo-relative path to the per-service TOML.
- A deployment can include multiple instances of a service (e.g. one DenSi per axis) by using a stable naming convention like `densi_anton`, `densi_debby`, etc.

---

## Runtime selection: exactly one active deployment

Multiple deployments may exist in the repo (one per show/site). The important invariant is:

> Only **one** deployment is active for a given `up` run.

Enforce this by requiring an explicit selection at startup:

- `python -m steuerung3d up --deployment configs/deployments/show_foo.toml`

If neither `--deployment` nor a dedicated environment variable is provided, boot should fail fast with a clear error.

For developer convenience, you *may* maintain a local, gitignored pointer:

- `configs/deployments/CURRENT.toml` (gitignored)

but production boot should prefer an explicit named deployment file.

---

## Per-service configs: one place for operational knobs

Operational parameters must live in per-service configs under `configs/services/`.

Example: joystick → intent mapping / limits (e.g. max manual jog velocity) belongs in:

- `configs/services/joy2intent.toml`

This avoids “magic defaults” spread across multiple TOMLs and code fallbacks.

Recommended policy for limits and safety-relevant parameters:

- Prefer explicit TOML values.
- Avoid silent code defaults; if a value is missing, error loudly (or centralize a single default constant and log it).

---

## Offline operation: render per-host bundles

Runtime must not depend on GitHub availability.

Recommended workflow:

1. Author / review changes in the repo (private GitHub is fine).
2. Tag or pin a commit for the show.
3. **Render** a per-host bundle from the deployment file.

Bundle output shape:

```text
out/deployments/show_foo/
  corebox/
    core.toml
    hip.toml
    run_core.(cmd|sh)
    run_hip.(cmd|sh)
  joybox/
    joy2intent.toml
    run_joy2intent.(cmd|sh)
```

Each `run_*.cmd`/`.sh` passes `--config <resolved_path>` (or `--deployment` + `--service <name>`) so the service never “guesses” config locations.

In field setups, keep a zipped copy of these bundles on each machine (and/or a USB stick) as the *known-good* offline snapshot.

---

## Logging and observability

On startup, every service should log:

- deployment id/version
- resolved per-service config path
- (optional) current git rev and whether it matches `expected_git_rev`
- key operational limits (e.g. max manual jog velocity)

This makes misconfiguration visible immediately, especially on remote nodes.

---

## Migration from profiles to deployments

- Profiles remain the canonical dev boot surface.
- Introduce deployments incrementally:
  - Start by moving per-service knobs into `configs/services/`.
  - Then add a deployment file that describes where each service runs.
  - Finally, add a small “deployment resolver / renderer” tool to generate per-host bundles.

The goal is evolutionary: keep your existing supervisor and services, but make the distributed topology explicit and reproducible.
