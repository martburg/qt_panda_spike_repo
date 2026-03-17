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

## Obsolete state surfaces (status)

The previously tracked legacy/global one-shot fields have now been removed from
active code:

- `MachineState.estop_reset_req` → removed; use `estop_reset_req_by_axis`
- `MachineState.resync_req` → removed; use `resync_req_by_axis`
- `MachineState.pending_param_ops` → removed; use `pending_param_ops_by_axis`

Current repo truth:

1) Reset / resync / param one-shots are axis-scoped only.
2) Supported runtime code should not reference the removed global fields.
3) Multi-axis smoke demonstrates one-shot isolation per axis.

## “Ready to delete” checklist

Before deleting a module tree, ensure all of the following are true:

1. **No supported app imports it**
   - `core_udp_service`, `hi_p`, `den_si`, `joy2intent` must not import it.
2. **No supported profile depends on it**
   - supported profiles live under `configs/profiles/*.toml`; `configs/stacks/*.toml` has been removed.
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
