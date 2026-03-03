# Rig kinematics seam

This document defines the integration seam for adding rig/world kinematics.

## Inputs

- World-frame motion command (cartesian): desired end-effector/world velocity **and** position intent.
  - For v0: `JogCartesian(vx, vy, vz, hip_id=...)` is interpreted as a *velocity* command in the fixed world frame.
- Frozen rig configuration (`RigSyncConfig`) created at the ARMED_SYNC boundary:
  - `participating`: tuple of axis/device ids in the rig
  - `anchors`: per-axis anchor points in the fixed world frame

## Outputs

The kinematics layer produces an **n-DOF to n-DOF** mapping for the participating axes:

- per-axis commanded velocity (for actuator PID feed-forward)
- per-axis commanded position/target (for actuator PID setpoint)

Notes:
- Final saturation, limits, and arbitration are enforced by the actuators.
- Core may later add additional geometric constraints (e.g. collision envelopes), but the
  safety-critical enforcement remains at the actuator level.

## Ownership and gating

- Core safety gate (`core_mode == LIVE`, not ESTOP/FAULT) remains authoritative for motion.
- Rig workflow gate:
  - cartesian/rig motion commands are accepted only in `RigMode.SYNC_ACTIVE`.
  - configuration is frozen from `RigMode.ARMED_SYNC` onward.

## World frame

The world frame is fixed to the world (no implicit local frame transforms). Any UI/local frames
must be converted before producing core intents.
