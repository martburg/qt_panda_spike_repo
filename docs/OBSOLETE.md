# Obsolete / legacy components

This page lists modules that are still present in the repo for compatibility or
reference, but are **not** part of the recommended development path.

## Obsolete apps

- `steuerung3d.apps.core_service`
  - **Use instead:** `steuerung3d.apps.core_udp_service` via stack profiles
    (`python -m steuerung3d up --profile ...`).

- `steuerung3d.apps.plc_twincat_legacy_edge`
  - **Use instead:** schema-driven PLC adapter under `steuerung3d.adapters.plc`.

## Obsolete adapters

- `steuerung3d.adapters.plc_twincat_legacy`
  - Legacy TwinCAT UDP protocol adapter.
  - **Use instead:** `steuerung3d.adapters.plc`.

## Notes

Keeping these modules lets us:
- replay old logs / rigs without rewriting everything at once
- compare legacy protocol behavior against the newer schema-driven approach

New docs should link here instead of treating obsolete modules as first-class.
