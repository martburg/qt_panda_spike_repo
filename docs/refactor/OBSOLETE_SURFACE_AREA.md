# Obsolete surface area — deletion plan

This repo intentionally keeps some **obsolete** code paths for compatibility or
reference. RefOS v2 says we may **rename / dedupe / remove dead code** in Lane 1
as long as we do not introduce silent semantic drift.

This document is a staging area for reaching the point where we can **delete**
these modules with confidence.

## Canonical supported stack

The supported stack (used by profiles like `1dev_sim`) is:

- `steuerung3d.apps.core_udp_service`
- `steuerung3d.apps.hi_p`
- `steuerung3d.apps.den_si`
- `steuerung3d.apps.joy2intent`

Everything else must either be:

- explicitly marked **obsolete**, and
- isolated from supported imports.

## Current obsolete modules

### Apps

- `steuerung3d.apps.core_service` (obsolete)
- `steuerung3d.apps.plc_twincat_legacy_edge` (obsolete)

The `core/app_catalog.py` keeps these entries for discoverability and
compatibility.

### Adapters

- `steuerung3d.adapters.plc_twincat_legacy` (legacy TwinCAT semicolon protocol)

## Obsolete state surfaces (ready-to-delete candidates)

These are legacy/global fields that should become **read-only derived views**
and then be deleted once no supported code reads them.

- `MachineState.estop_reset_req` (use `estop_reset_req_by_axis`)
- `MachineState.resync_req` (use `resync_req_by_axis`)
- `MachineState.pending_param_ops` (use `pending_param_ops_by_axis`)

Deletion readiness:

1) `grep -RIn "\\bestop_reset_req\\b" src/steuerung3d` shows no reads (or only in `legacy/`).
2) Same for `resync_req` and `pending_param_ops`.
3) Multi-axis smoke (two densis) demonstrates one-shot isolation per axis.

## “Ready to delete” checklist

Before deleting a module tree, ensure all of the following are true:

1. **No supported app imports it**
   - `core_udp_service`, `hi_p`, `den_si`, `joy2intent` must not import it.
2. **No supported profile depends on it**
   - `configs/stacks/*.toml` used in CI / daily work must not reference it.
3. **Tests cover the supported alternative**
   - any behavior the obsolete module provided has a test for the replacement.
4. **Docs updated**
   - remove or relocate references to obsolete entrypoints.
5. **Lane 2 declaration if CLI/API surface changes**
   - removing entrypoints or public modules is semantic for operators.

## How to measure progress

Use grep to find imports / references:

- `grep -RIn "plc_twincat_legacy" src/steuerung3d`
- `grep -RIn "plc_twincat_legacy_edge" src/steuerung3d`

When the only remaining references live under `apps/dev_stack/` or `tools/` and
no supported stack imports them, we are close to being able to delete the
surface area (Lane 2: declared + ledger + tests).
