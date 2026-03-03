# Kinematics prep TODO (E–G)

## E) Profiles / wiring doc
- Expand `docs/runtime/profiles.md` with:
  - processes started per profile (especially `1dev_sim_remote_joy`)
  - UDP ports + direction arrows (who publishes intents, who serves telemetry)
  - axis ids present in the profile

## F) Frozen configuration content
- Define and document which rig parameters are frozen at ARMED_SYNC:
  - participating axes/device ids
  - anchors (world frame)
  - (future) per-axis calibration: drum radius, direction sign, soft limits, etc.
- Define which values are allowed to change in SYNC_ACTIVE (ideally none structural).

## G) Kinematics invariants test pack
Add a minimal, solver-agnostic invariant suite for the future kinematics module:
- deterministic outputs for same input
- output entry per participating axis
- no NaN/inf
- respects simple velocity sanity bounds (if any are introduced)
