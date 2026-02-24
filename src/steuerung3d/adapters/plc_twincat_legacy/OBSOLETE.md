# Obsolete: TwinCAT legacy adapter

This package exists to support legacy TwinCAT/PLC integration experiments and historical UDP framing.

**Status:** obsolete / retained for reference.

For the Steuerung3D Remake stack, the canonical PLC protocol is defined by the Beckhoff ST truth source
(see `docs/legacy_plc_anton.md` / `ST-Code/` as applicable) and implemented under `src/steuerung3d/adapters/plc/`
+ `src/steuerung3d/protocol/`.

If you are starting new work, prefer the non-legacy adapters.
