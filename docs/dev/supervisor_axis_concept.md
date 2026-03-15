# Supervisor axis-centric concept

The supervisor manages **controlled axes / supervised units**, not mandatory
Densi–HiP pairs.

- DenSi = axis/device-side execution participant
- HiP = optional single-axis detail HMI
- Supervisor = multi-axis overview, group actions, synchronized movement,
  and future kinematic coordination

A HiP may be opened or attached when detailed single-axis adjustment or
parameter editing is required, but HiP is not required for the supervisor's
primary orchestration role.

This means the supervisor table is interpreted as **one row per axis**.
Future synchronized movement and kinematic transforms should be implemented in
this layer.
