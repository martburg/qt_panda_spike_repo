# Steuerung3D Path Authoring and Visualization

## Overview

For Steuerung3D, the most promising split is:

- **Blender for authoring**
- **Panda3D for runtime visualization**
- **Qt / PySide6 for the application shell**
- **Steuerung3D domain logic for kinematics, constraints, validation, retiming, and execution**

This document captures the architectural reasoning behind that split, with a particular focus on path authoring under real machine constraints.

---

## Why this split feels right

### Blender
Blender is very good at:

- drawing and editing paths
- placing cameras and targets in 3D space
- shaping curves intuitively
- defining rough timing intent
- giving users a familiar spatial authoring tool

Blender is **not** the source of motion truth for a physical wire-driven system.

It does not know:

- winch length limits
- actuator velocity limits
- actuator acceleration / jerk limits
- workspace singularities or weak regions
- rope slack / tension issues
- whether a visually smooth Cartesian path is physically harsh in actuator space

So Blender should author **intent**, not executable machine motion.

### Panda3D
Panda3D is a good fit for:

- live 3D scene rendering
- anchors, cables, payload/camera, targets, ghost poses
- workspace visualization
- picking, highlighting, overlays, and diagnostics in 3D
- runtime playback and scene feedback

Panda3D should be the **renderer**, not the application core.

### Qt / PySide6
Qt remains the natural shell for:

- operator panels
- diagnostics
- tables and plots
- settings and configuration
- path review and approval tools
- engineering controls

### Steuerung3D domain layer
This layer must own:

- machine geometry
- kinematics
- machine state
- workspace constraints
- path feasibility analysis
- retiming
- executable trajectory generation

---

## Core principle

**A Blender path is a proposal; only the compiled Steuerung3D trajectory is executable truth.**

This principle keeps the architecture healthy.

Blender authors a candidate path.  
Steuerung3D validates, transforms, retimes, and compiles it into something the machine can safely execute.

---

## The three layers of motion

A useful distinction is:

### 1. Geometric path
Where in space should the camera go?

### 2. Time law
How fast should it move along that path?

### 3. Machine trajectory
What must each actuator do over time to realize that path within physical constraints?

Blender is good at authoring (1), and partly expressing artistic intent for (2).  
Steuerung3D must own (3).

---

## Why path feasibility depends on workspace location

For a wire-driven system, a curve that looks smooth in Cartesian space may be difficult or impossible for the winches to realize.

Reasons include:

- the same Cartesian motion can require very different rope-length changes depending on pose
- near workspace boundaries, actuator demands may rise sharply
- near singular or weak configurations, small Cartesian changes may cause large actuator changes
- actuator acceleration demand depends on both curve shape and where that curve lies in the workspace

So there is no single global “minimum bend radius” that guarantees feasibility everywhere.

Instead, feasible curvature is:

- **pose-dependent**
- **direction-dependent**
- **limit-dependent**
- **kinematics-dependent**

This is why Blender alone cannot be the authority for path validity.

---

## Recommended architecture

```text
Blender curve / keyframes
    -> export authoring intent
    -> Steuerung3D path compiler
    -> kinematic feasibility analysis
    -> retiming / constraint handling
    -> compiled executable trajectory
    -> runtime playback + monitoring
```

---

## Suggested responsibility split

## Blender should own

- authored camera path
- waypoints and spline handles
- look-at targets or framing helpers
- shot markers
- rough creative timing intent
- optional environment references for authoring

## Steuerung3D should own

- path sampling
- inverse kinematics over the full path
- actuator position / velocity / acceleration estimation
- workspace validity checks
- singularity / weakness detection
- speed-profile calculation
- retiming to satisfy limits
- final trajectory generation
- execution-time monitoring

---

## Authoring path vs compiled path

Do not treat the Blender spline as the final executable artifact.

Instead, distinguish between:

### Shot Path / Authoring Path
The original path authored in Blender.

### Validated Path
A sampled and checked version of the authored path, with diagnostics attached.

### Compiled Trajectory
A fully timed, machine-specific trajectory that satisfies the current rig geometry and limits.

This distinction matters because the same authored path may compile differently for:

- different rig geometries
- different payloads
- different winch limits
- different safety margins
- different machine profiles

---

## Path compiler concept

A dedicated motion layer in Steuerung3D is recommended.

Possible module sketch:

```text
src/steuerung3d/motion/
    path_model.py
    path_sampling.py
    feasibility.py
    retiming.py
    trajectory.py
```

### `path_model.py`
Defines the imported or internal representation of a path:
- world-space path
- optional target/look-at track
- orientation hints
- shot metadata

### `path_sampling.py`
Responsible for:
- arc-length-based sampling
- adaptive refinement in high-curvature areas
- producing discrete pose samples for analysis

### `feasibility.py`
Responsible for:
- inverse kinematics at each sample
- limit checks on actuator positions
- velocity / acceleration estimation
- workspace / singularity / slack diagnostics
- producing feasibility reports

### `retiming.py`
Responsible for:
- adjusting progression speed along the path
- slowing the system down where needed
- generating feasible speed profiles

### `trajectory.py`
Produces the final machine-executable artifact:
- time-stamped trajectory
- per-axis references
- metadata about machine profile, limits, and source path

---

## Path feasibility analysis

A useful first implementation is to analyze path segments and classify them visually.

Suggested status classes:

- **Green**: comfortably feasible
- **Yellow**: feasible but near limits
- **Red**: infeasible
- **Blue**: kinematically valid, but only at much lower speed

This could be shown:
- in the Panda3D scene
- in an editor view
- alongside actuator-space plots in the Qt shell

This would help users understand that a path can be geometrically reasonable while still being dynamically poor.

---

## Retiming before reshaping

There are two broad ways to fix a problematic path:

### Level A: retiming only
Keep the geometry fixed.  
Reduce speed where needed so the path becomes feasible.

This should be the first-line correction strategy.

### Level B: geometric repair
If retiming is insufficient:
- reshape the curve
- alter local curvature
- move sections away from bad workspace regions
- suggest changes to waypoints or tangents

This is more complex and should come later.

Initially, the system should not silently alter authored curves.  
It should diagnose problems clearly and let the user decide.

---

## Actuator-space diagnostics are essential

A path can look elegant in 3D and still be poor in actuator space.

So the system should support engineering views such as:

- rope length vs time
- actuator velocity vs time
- actuator acceleration vs time
- limit margin vs path position
- workspace distance / singularity margin along the path

This is where the Qt shell becomes especially important.

Recommended split:
- Panda3D for intuitive spatial understanding
- Qt for engineering truth and detailed diagnostics

---

## Runtime visualization role of Panda3D

Panda3D should render a scene snapshot derived from domain state, not become the source of truth itself.

Suggested flow:

```text
telemetry / joystick / program / compiled trajectory
    -> domain state
    -> kinematics / motion layer
    -> scene snapshot
    -> Panda3D adapter
    -> render
```

Panda3D should visualize:

- anchors
- cables
- payload/camera pose
- target pose ghost
- path preview
- current path progress
- workspace volume / forbidden zones
- warnings and overlays
- selected axis or selected shot context

---

## Blender as authoring companion, not control core

Blender can be very valuable in the overall workflow:

- scene layout
- path creation
- visual planning
- shot design
- export of rig-related authoring data

But the executable semantics should always be imposed by Steuerung3D after import.

That keeps:
- physical truth in one place
- machine-specific behavior deterministic
- runtime safety independent from authoring tools

---

## Recommended workflow

### In Blender
- design the shot
- place the candidate path
- place optional look-at targets
- define rough timing and intent
- export path data

### In Steuerung3D editor
- import the path
- map it into machine/world coordinates
- sample and validate it
- run feasibility analysis
- colorize problem regions
- retime for feasibility
- inspect actuator-space plots
- approve or revise

### In runtime
- execute only compiled trajectories
- monitor tracking error and limit margins
- support safe pause / abort / resume

---

## Recommended first implementation phases

### Phase 1
- Blender exports spline or polyline control data
- Steuerung3D samples path densely
- inverse kinematics is run at each sample
- actuator velocity and acceleration are estimated numerically
- feasibility is checked under a nominal speed
- path is colorized green/yellow/red

### Phase 2
- automatic retiming is added
- feasible speed profile is computed
- compiled timeline is generated

### Phase 3
- orientation / look-at support
- adaptive refinement
- better diagnostics and editing hints
- optional assisted local smoothing / repair

---

## Summary

The best current architectural direction is:

- **Blender for path and shot authoring**
- **Steuerung3D for kinematics, feasibility, retiming, and execution**
- **Panda3D for runtime 3D visualization**
- **Qt for shell, diagnostics, and engineering tools**

The most important takeaway is:

**Blender authors intent. Steuerung3D compiles executable truth.**

That separation is what allows a path to be both creatively authored and physically safe.
