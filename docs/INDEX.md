# Steuerung3D Remake — Docs Index

This repo is a **src/** layout Python project.

## Start here

- **README**: `README.md`
- **Architecture overview**: `docs/ARCHITECTURE.md`
- **Repo layout & hygiene**: `docs/REPO_STRUCTURE.md`, `docs/REPO_HYGIENE.md`
- **How to run the dev stack**: `docs/DEV_STACK.md`
- **Testing**: `docs/testing.md`, `docs/MANUAL_TESTING.md`

## Protocols

- **PLC/TwinCAT legacy protocol (overview)**: `docs/protocols/legacy_plc_protocols.md`
- **Canonical Anton PLC UDP contract**: `docs/protocols/legacy_plc_anton.md`
- **Wire encoder/decoder notes**: `docs/protocol_plc_wire.md`, `docs/plc_integration.md`, `docs/runbook_udp_seams.md`
- **Safety / E‑Stop policy**: `docs/safety_estop_policy.md`

## Logging & replay

- `docs/logging.md`
- `docs/logging_and_replay.md`
- `docs/livetick.md`

## Milestones / decisions

- `docs/milestones.md`
- `docs/decisions.md`

## Legacy sources

- `ST-Code/` — ST / TwinCAT project extracts kept verbatim.
- `docs/legacy/` — legacy docs and notes.
- `legacy/` — quarantined historical code and unused modules (see `legacy/README.md`).

## Archive

- `docs/archive/` — patch notes and generated readmes kept for reference.

## Repo graphs / analysis artifacts

- Super-pruned stack graph: `docs/graphs/steuerung3d_stack_superpruned_graph.png`
- Pruned stack graph: `docs/graphs/steuerung3d_stack_pruned_graph.png`
- Dead code candidates report (snapshot): `docs/graphs/obs_steuerung3d_dead_code_candidates.md`
