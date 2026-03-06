# Architecture overview

This repo is a deliberately small “walking skeleton” that keeps the boundaries of the final system
visible early.

Canonical architecture references:
- `docs/Architectural_Primer_v4_full.md` (full spec)
- `docs/Architectural_Primer.md` (summary)

## Core principles

- **Single source of truth:** `MachineState` owns the system state.
- **Deterministic stepping:** a `Timebase` defines `dt` and produces ticks.
- **Device boundary:** the core talks to hardware (real PLCs or sims) through `device.step(state, cmd, dt)`.
- **Intent/telemetry transport:** clients publish intents; the core publishes snapshots.
- **Record/replay:** transports can be wrapped to log traffic (JSONL).

## Key modules

- `steuerung3d/core/state.py`
  - `MachineState`: global tick/time, core_mode, safety flags
  - `AxisState`: measured state (pos/vel/enabled/fault)
  - `AxisCommandState`: commanded state (enable/vel) stored separately

- `steuerung3d/core/param_registry.py`
  - Canonical parameter registry (groups, tolerances, normalization)

- `steuerung3d/core/command_frame.py`
  - `CommandFrame`: one “frame” of commanded values produced by the core

- `steuerung3d/core/engine.py`
  - `CoreEngine.step_once()`
    - drain intents
    - update state
    - build a command frame
    - call the device adapter
    - publish a snapshot

- `steuerung3d/protocol/transport.py`
  - `InMemTransport`: in-process intent + telemetry queues

- `steuerung3d/protocol/recording.py`
  - `JsonlRecorder`: writes JSON lines
  - `LoggedTransport`: wraps a transport and records in/out messages

- `steuerung3d/protocol/core_runner.py`
  - `CoreRunner`: runs `CoreEngine` in its own thread (real-time-ish)

## Device adapters

- `steuerung3d/adapters/sim/*`
  - simulation device + plant (local development)

- `steuerung3d/adapters/plc/udp_device.py`
  - early minimal UDP adapter (toy protocol)

- `steuerung3d/adapters/plc_twincat_legacy/*`
  - **obsolete** TwinCAT legacy UDP protocol adapter (kept for reference/field rigs).
  - See: `docs/OBSOLETE.md` and `docs/PLC_TWINCAT_LEGACY.md`.

## Why the command frame seam matters

The core produces a `CommandFrame` that is independent of transport and device details. This keeps:

- the core deterministic and testable
- device adapters replaceable (SIM, legacy PLC, future protocols)
- logging and regression testing straightforward

## HiP ↔ DenSi parameter editing (axis-agnostic)

In addition to motion / mode intents, the system supports an **axis-agnostic parameter edit flow**
between:

- **HiP** (Human Intent Parser / operator UI)
- **DenSi** (Device Endpoint Simulator)

The flow is deliberately simple and mirrors the UI buttons:

- **Edit** → prime DenSi to accept new values for a parameter group
- **Write** → commit new values to DenSi
- **Cancel** → abort the edit session (no changes applied)

This is modeled as a small state machine per edit group (e.g. `pos`, `vel`, `filter`, `guider`).

### Intents

HiP emits intents (over UDP or in-memory transport):

- `BeginParamEdit(group)`
- `CommitParamEdit(group, values)`
- `CancelParamEdit(group)`

The **core** applies these to `MachineState` and emits the corresponding operations in the
next `CommandFrame`.

### CommandFrame

`CommandFrame` carries a list of parameter operations (axis-agnostic):

- `param_ops: [ {op: begin|commit|cancel, group, values?, session_id?, req_id?} ... ]`

This keeps parameter traffic on the same deterministic “frame seam” as motion commands.

### Telemetry

DenSi reports parameter edit state and applied values in telemetry so HiP can:

- enable/disable fields and buttons correctly
- show the effective values after a write

In practice the DenSi/PLC side is treated as semi-frozen: we avoid adding new protocol obligations there.
So the system uses a two-layer guarantee:

- **HiP ↔ Core**: guarded delivery via `req_id` acks (dedupe + retry).
- **Core ↔ DenSi**: *observed confirmation* by comparing the requested values to DenSi’s reported `params` in telemetry.
  Core publishes `param_commit_status` (`pending/applied/timeout`) so the UI can present a clear result.

Important UI detail:

- While a group is in **active edit mode**, HiP must **not** overwrite in-progress user typing
  with periodic telemetry refresh. Only non-active groups should be refreshed.

### UI gating policy

- **HiP**: parameter text fields are disabled (grey) until Edit is pressed; active fields become enabled (white).
  Editing is **modal**: once a group is in edit mode, other Edit buttons and tab switching are disabled until Write/Cancel.
  After Write, HiP shows a **modal dialog** once Core observes the device as applied (or a timeout if not confirmed).
  If HiP auto-adjusts **pos** limits to satisfy `HardMax ≥ UserMax ≥ UserMin ≥ HardMin`, it shows an info dialog listing the adjustments before sending.
- **DenSi**: Edit/Write/Cancel controls are disabled (greyed). DenSi acts as a “device endpoint”, not an operator.

### Safety / startup

DenSi starts in a **stopped / not-OK** state by default so the safe state is visible immediately.
Diagnostic buttons “Set All” / “Clear All” remain purely diagnostic and keep their semantics.

Axis FSM (controller-side)

Each axis has a controller-side FSM that governs mode, safety gating, and recovery.

The FSM is implemented using the transitions library.

It consumes events derived from:

operator intents (enable/disable, request recover)

safety/estop status from uplink

watchdog / comm health

It outputs “allowed actions” and state, which downstream code uses to:

accept or reject commands

force safe command defaults (e.g., zero velocity)

trigger recover procedures

Why this exists

Legacy PLC protocol is order-sensitive and permissive.

Without an explicit FSM, safety & recover logic leaks into UI and transport.

A test-driven FSM makes the system deterministic and regression-safe.

Key states

IDLE: safe, not driving motion.

ENABLED (or ACTIVE): normal running state (whatever you named it).

ESTOP: safety stop asserted → commands must be gated.

RECOVER: explicit recovery sequence before returning to idle/ready.

Key transitions

enable: IDLE → ENABLED

estop: * → ESTOP

recover_request: ESTOP → RECOVER

recover_done: RECOVER → IDLE

disable: ENABLED → IDLE



## Axis-scoped UDP routing (no broadcast)

For real PLC integration (and to avoid surprising cross-talk in sim), the device command path is **strictly per-axis**:

- Core builds one device command payload **per axis**
- The UDP service sends it to exactly one target (host:port) for that axis
- Broadcast fallback is **not allowed** in multi-axis mode

This matches the frozen PLC contract: each PLC endpoint must receive only the data it expects.

### Port overlap guard

A common Windows pitfall is overlapping ports when running local sims:

- DenSi `cmd-in` uses a contiguous range (e.g. `52001..52004`)
- Core `dev_telem_in` must not be within that range

Launchers enforce this and refuse to start if an overlap is detected.

## Per-axis UI telemetry slicing

Device telemetry arrives multiplexed (all DenSi instances send to a single `dev_telem_in` port).
The core maintains per-axis caches for device-specific fields and publishes **one telemetry stream per HiP**:

- each HiP receives a snapshot containing only its axis (`axes={Anton: ...}`)
- per-axis fields such as `params`, `estop_status_word`, and param-commit status are taken from the correct axis cache

This prevents the “last-writer wins” effect where HiPs appear to show the telemetry of different DenSis.

## Transaction acks (HiP)

Ack signals (`core_acks`) are one-shot fields in telemetry snapshots. The receiver may drain multiple snapshots per poll.
Therefore, the HiP must process acks across **all** drained snapshots before deciding to resend or time out.



# HiP ↔ DenSi Attachment Model

## Overview

The system supports **multiple HiP operator consoles** and **multiple DenSi device endpoints**.

A HiP must **attach to a control target** before it can issue motion or parameter intents.

The current implementation phase supports **1:1 attachment**:

HiP → DenSi

However, the architecture deliberately models attachment using **abstract targets** rather than
hardcoding a HiP→DenSi relationship. This allows future support for grouped DenSis and coordinated motion.

---

## Core Ownership Principle

Attachment authority is **centralized in the Core**.

The core maintains the canonical mapping:

target_id → hip_id | None

Where:

- `target_id` identifies an **attachable target**
- `hip_id` identifies the owning HiP
- `None` means the target is currently free

This ensures:

- deterministic ownership
- no double attachment
- consistent view for all HiPs

HiPs never negotiate ownership directly with DenSis.

---

## Attachable Targets

An **attachable target** represents something a HiP can control.

Current implementation:

target_kind = "leaf"  
members = {single DenSi}

Example:

target: Anton  
members: {Anton}

Future targets may represent **groups of DenSis**.

Example (future):

target: FrontRig  
members: {Anton, Debby, Cecil}

Internally this abstraction prevents the system from baking in the assumption that
an “axis” always corresponds to a single physical device.

---

## Boot Behavior

On system startup:

- all **DenSis register themselves** as available targets
- all **HiPs start unattached**
- all targets start **unclaimed**

Thus the initial state is:

HiP1 → NotAttached  
HiP2 → NotAttached  

Anton → free  
Debby → free  
Cecil → free

---

## Attach Procedure

Operator selects a target in the HiP UI.

HiP sends an intent:

ClaimTarget(target_id)

Core grants the claim only if:

target.claimed_by == None

If successful:

target.claimed_by = hip_id

Core telemetry then updates all HiPs.

---

## Detach Procedure

Selecting **NotAttached** releases the current claim.

HiP sends:

ReleaseTarget(target_id)

Core clears the ownership:

target.claimed_by = None

The target immediately becomes available to other HiPs.

---

## Stale Ownership Cleanup

If a HiP disappears (watchdog timeout / lost lifetick):

Core automatically releases all targets owned by that HiP.

This prevents stranded DenSis after console crashes.

---

## UI Visibility Rules

Each HiP should display:

- `NotAttached`
- all **free targets**
- its **currently attached target**

Targets claimed by other HiPs are not attachable.

A birds-eye diagnostic view should show something like:

Anton → hip1  
Debby → free  
Cecil → hip2

---

## Current Semantic Scope

In the current system phase:

- one target corresponds to **exactly one DenSi**
- each HiP may attach to **at most one target**
- each target may be owned by **at most one HiP**

This results in a strict **1:1 mapping**.

The attach layer exists purely to define **control authority** and does not define motion semantics.

---

# Future Extension: Grouped DenSi Targets

The attachment model is designed to support **group targets**.

Example:

target: FrontRig  
members: {Anton, Debby}

If a HiP attaches to `FrontRig`, it implicitly controls both DenSis.

To preserve exclusivity:

Two targets conflict if their **member sets overlap**.

Example:

Anton  
FrontRig {Anton, Debby}

If `Anton` is claimed individually, `FrontRig` cannot be claimed.

If `FrontRig` is claimed, neither `Anton` nor `Debby` can be attached individually.

This rule guarantees deterministic ownership even with grouped targets.

---

# Future Extension: Coordination and Sync Semantics

Grouped targets introduce a second architectural concern:

**coordination semantics**.

A group is not simply a set of DenSis; it is a **coordinated plant** with a defined motion model.

Examples of coordination profiles:

- equal_axis
- ratio_axis
- leader_follower
- rig_kinematic

Each profile defines:

- how group commands map to leaf DenSi setpoints
- acceptable position/velocity error
- supervision policy and fault reactions

Important design decision:

**Coordination supervision belongs to the core/coordination layer, not the HiP.**

HiPs display sync state but do not define or enforce it.

This layer will be implemented in a later architectural step.

---

# Summary

Current architecture stage:

HiP → Target → DenSi

- targets represent single DenSis
- ownership is enforced by core
- system supports N HiPs and N DenSis
- attach/detach semantics are deterministic

Future architecture:

HiP → Target → {DenSi...}

- targets may represent groups
- coordination profiles define sync semantics
- supervision is centralized in core

Attachment Terminology & Diagrams
This section standardizes terminology used across the codebase and documentation for
HiP ↔ DenSi attachment and future grouped control.

Core Terms
HiP
Human Interface Panel — the operator console.

Responsibilities:

send operator intents
display telemetry
request attach / detach
A HiP does not own motion semantics and does not enforce coordination rules.

DenSi
A device endpoint controlling a physical actuator.

Responsibilities:

execute leaf commands
report telemetry
enforce local safety conditions
A DenSi never decides ownership; it simply executes commands from the core.

Target
A Target is something a HiP can attach to.

Examples:

Leaf target:

Anton → {Anton}

Future group target:

FrontRig → {Anton, Debby}

A target therefore represents control authority, not necessarily a single device.

Properties:

target_id
members (set of DenSis)
target_kind = leaf | group
claimed_by
Claim
A claim assigns ownership of a target to a HiP.

Mapping maintained by core:

target_id → hip_id | None

Rules:

each target can have at most one owner
each HiP can control at most one target (current phase)
claims are released when a HiP detaches or disappears
Current System Diagram
Current phase supports 1:1 attachment.

HiP → Target → DenSi

Example:

HiP_A → Anton → Anton

Internally:

target: Anton
members: {Anton}

Multi‑Device Environment
Multiple HiPs and DenSis may exist simultaneously.

Example system state:

HiP_A → Anton
HiP_B → Debby
HiP_C → NotAttached

Anton → hip_A
Debby → hip_B
Cecil → free

Ownership remains exclusive and enforced by core.

Future Group Targets
Future systems may expose group targets.

Example:

FrontRig → {Anton, Debby}

Diagram:

HiP_A → FrontRig → {Anton, Debby}

Rules:

group claims block individual members
individual member claims block groups containing them
Conflict rule:

Two targets conflict if their member sets intersect.

Coordination Layer (Future)
Grouped targets introduce coordination semantics.

A target may specify a coordination profile:

equal_axis
ratio_axis
leader_follower
rig_kinematic
These profiles define:

command transformation to leaf DenSis
acceptable deviation tolerances
supervision policy
Coordination supervision will live in the core / coordination layer, not in the HiP.

Design Principle
The attachment layer defines who controls what.

It does not define how motion is coordinated.

This separation allows the system to scale from:

HiP → DenSi

to

HiP → Target → {DenSi...}

without redesigning the ownership model.
