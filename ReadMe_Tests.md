# ReadMe_Tests

## Purpose

This document describes the two supervisor smoke tests created during the current automation pass:

1. `tools/smoke_supervisor_sequence.py`
2. `tools/smoke_supervisor_hip_param.py`

Both tests are **system-level smoke tests**. They do not replace unit tests. Their job is to boot a realistic local stack, drive a narrow but high-value operational path, and fail fast when the stack no longer behaves like the manual operator workflow.

They were created to cover the most fragile integration seams in the current supervisor architecture:

- supervisor startup and stack orchestration
- supervisor -> core intent flow
- supervisor -> DenSi action flow
- core -> DenSi telemetry fanout
- HiP ownership / attach behavior
- scripted input injection without depending on a real joystick
- parameter edit roundtrip through a real HiP process

---

## Why there are two separate smoke tests

The two tests deliberately cover **different operating phases**.

### 1) `smoke_supervisor_sequence.py`
This is the **boot / safety / resync / ready / motion** smoke.

It exercises the operator path that begins at startup and continues through:

- ESReset
- ESStart
- Resync
- `chkEsTaster`
- deadman + velocity based motion
- release / stop validation

This test answers: **“Can the main supervised motion path still be driven end to end?”**

### 2) `smoke_supervisor_hip_param.py`
This is the **IDLE / open HiP / edit parameter** smoke.

It intentionally stops **before READY motion mode** because parameter editing is not allowed in READY. It verifies that a HiP can be opened for one axis while the system remains in synced IDLE, and that one safe parameter write can be driven through the HiP-side machinery.

This test answers: **“Can a single-axis HiP be opened and used for an IDLE-only engineering edit path?”**

Keeping these flows separate is architecturally cleaner because motion readiness and parameter editing belong to different operational modes.

---

## Shared architectural pattern

Both tests rely on the same design principle:

- start a realistic local multi-process stack
- drive it only through supported external seams
- observe success through telemetry and logs
- shut the stack down automatically unless `--keep-running` is requested

The core implementation lives in:

- `src/steuerung3d/apps/supervisor/smoke_sequence_support.py`

This module contains the orchestration helpers that:

- launch the supervisor and wait for the `.run/.../sessions/...` directory
- discover and verify child processes
- send reset/start/resync/action traffic
- inspect fanout telemetry
- watch DenSi logs for confirmation tokens
- open HiPs and drive smoke-only control channels
- shut the stack down cleanly

So the tool scripts in `tools/` are intentionally thin wrappers. The real logic is centralized in `smoke_sequence_support.py`.

---

# Test 1: `tools/smoke_supervisor_sequence.py`

## Goal

This smoke automates the current main supervisor commissioning sequence:

1. launch supervisor GUI + local stack
2. wait until the selected axes are present
3. issue **ESReset**
4. issue **ESStart**
5. issue **Resync**
6. confirm that **system time starts advancing** in the DenSi uplink after resync
7. assert that `chkEsTaster` drives the axes from **IDLE -> ARMED -> READY**
8. inject a scripted joystick sequence
9. confirm **motion occurs**
10. release the injected command and confirm the axes **stop**

This is the smoke that most closely mirrors the manual “can we make the machine move?” workflow.

---

## Files involved

### Entry point
- `tools/smoke_supervisor_sequence.py`

### Supervisor profile
- `configs/supervisor/smoke_2pairs_motion.toml`

### Stack profile
- `configs/profiles/supervisor_2axes_core_fanout_smoke_motion.toml`

### Scripted input simulator
- `src/steuerung3d/apps/inputd_sim/__main__.py`
- `src/steuerung3d/apps/inputd_sim/config.py`
- `src/steuerung3d/apps/inputd_sim/control.py`
- `src/steuerung3d/apps/inputd_sim/runtime.py`

### Inputd-sim service config
- `configs/services/inputd_sim_smoke.toml`

### Inputd-sim scenario
- `configs/inputd_sim/smoke_deadman_forward.toml`

### Shared smoke orchestration
- `src/steuerung3d/apps/supervisor/smoke_sequence_support.py`

---

## Why `inputd_sim` was introduced

This test intentionally does **not** depend on a real joystick.

That was a deliberate architectural step.

Instead of coupling smoke success to:

- a specific USB joystick being present
- driver state on the workstation
- manual timing by the operator
- Windows focus / GUI interaction issues

we use a dedicated seam called `inputd_sim`.

### Benefits

- deterministic input timing
- scriptable button and axis values in TOML
- reusable for future smoke scenarios
- easier CI-style local automation
- preserves the real downstream path through `joy2intent`

This keeps the test realistic: motion still flows through the normal pipeline.
The only thing swapped is the *source* of joystick packets.

---

## Motion test data flow

The motion smoke uses this chain:

`inputd_sim` -> `joy2intent` -> `core_udp_service` -> `DenSi` -> telemetry fanout -> supervisor observer

So even though the joystick source is simulated, the rest of the stack remains realistic.

---

## `inputd_sim` scenario model

The simulator was built so that **any button and axis input can be scripted in TOML**.

### Service config example
`configs/services/inputd_sim_smoke.toml`

This defines:

- UDP output address for fake joystick packets
- optional control socket for start / restart / idle
- number of axes and buttons
- default neutral values
- path to a scenario file

### Scenario example
`configs/inputd_sim/smoke_deadman_forward.toml`

This file uses aliases so the scenario stays readable:

- axis aliases like `manual_jog`
- button aliases like `deadman`

and then defines timed steps, for example:

- neutral hold
- drive with deadman pressed and axis deflected
- release to zero

### Important design point
The scenario format is generic. It is **not hardcoded** to the first smoke use case.
That means future scripted tests can model:

- different velocity ramps
- deadman timing edge cases
- axis selection buttons
- multiple button combinations
- more complex start/stop profiles

---

## Default command

```bash
python tools/smoke_supervisor_sequence.py
```

Default profile:

```text
configs/supervisor/smoke_2pairs_motion.toml
```

---

## Useful CLI options

### Timing / observation
- `--startup-timeout-s`
- `--ready-grace-s`
- `--observe-timeout-s`
- `--settle-s`
- `--publish-interval-s`
- `--brake-grace-s`

### Motion acceptance thresholds
- `--motion-pos-delta-min`
- `--motion-vel-move-eps`
- `--motion-vel-zero-eps`
- `--motion-release-settle-s`

### Process control
- `--keep-running`

`--keep-running` is useful when you want the smoke to stop after success and leave the GUI + stack alive for manual inspection.

---

## What the test actually verifies

### ESReset
The test sends `RequestEstopReset` intents for all selected axes and waits for DenSi log confirmation.

Primary confirmation token:

- `cmd_estop_reset=True`

### ESStart
The test sends the DenSi-side ESStart action and waits for DenSi confirmation.

Primary confirmation token:

- `ESStart pressed`

### Resync
The test sends `RequestResync` and then watches the DenSi uplink tail until the transmitted system time advances.

This is important: **the running system time is not expected before resync**. It is explicitly used as the post-resync proof that the DenSi uplink is alive and advancing.

### `chkEsTaster`
The test then drives the supervisor-side `chkEsTaster` action and confirms phase progression through the observed estate/status word:

- initial: `IDLE`
- intermediate: `ARMED`
- final: `READY`

The brake grace period is accounted for via `--brake-grace-s`.

### Motion start
After READY, the smoke triggers `inputd_sim` to run its scenario.
The scenario currently drives:

- deadman true
- forward manual jog value

The test verifies that selected axes show:

- position change greater than the configured minimum
- non-zero motion velocity while active

### Motion stop
After the scenario releases the controls, the test waits until final axis velocity returns near zero.

---

## Output summary

The tool prints a compact summary including:

- session directory
- selected axes
- reset / estart / resync publish counts
- observed axes with running system time
- `chkEsTaster` phase progression per axis
- motion start/end positions
- motion deltas
- peak observed absolute velocity
- final absolute velocity after release

These summary lines are meant to be human-readable and useful during manual debugging.

---

## Expected pass condition

A passing run means:

- the stack booted
- selected DenSis were reachable
- ESReset was acknowledged
- ESStart was acknowledged
- resync caused system time to advance
- `chkEsTaster` reached READY after the brake grace delay
- the scripted motion produced real movement
- the release brought the axes back to a near-stopped state

---

## Typical failure classes

If this smoke fails, the problem is usually in one of these categories:

1. **stack boot / port conflicts**
   - old processes still bound to loopback ports
   - child processes failed to launch

2. **reset/start wiring**
   - supervisor action path broken
   - DenSi action input miswired

3. **resync / uplink semantics**
   - system time not advancing after resync
   - observer attached to the wrong telemetry fanout port

4. **ready transition / brake timing**
   - `chkEsTaster` dropped too early
   - brake grace too short

5. **motion input path**
   - `inputd_sim` not running
   - `joy2intent` not consuming the simulated stream
   - deadman / axis mapping mismatch

---

# Test 2: `tools/smoke_supervisor_hip_param.py`

## Goal

This smoke covers a different but equally important path:

1. launch supervisor GUI + local stack
2. drive the system only as far as **synced IDLE**
3. open one HiP for one selected axis
4. confirm that ownership transfers to that HiP
5. edit one safe parameter through a smoke control channel
6. confirm that the parameter write is observed as accepted on the system side
7. optionally restore the original value

This is intentionally an **IDLE-only** test.

### Important domain rule
Parameter edits are **not** validated in READY.
The test does **not** continue into `chkEsTaster` / READY, because the intended engineering workflow is:

- remain in IDLE
- open HiP
- edit parameter
- verify acceptance

---

## Files involved

### Entry point
- `tools/smoke_supervisor_hip_param.py`

### Supervisor profile
- `configs/supervisor/smoke_2pairs_hip_param.toml`

### Stack profile
- `configs/profiles/supervisor_2axes_core_fanout_hip_param.toml`

### HiP smoke control
- `src/steuerung3d/apps/hi_p/smoke_control.py`

### Safe parameter specification
- `src/steuerung3d/apps/hi_p/smoke_param_specs.py`

### HiP controller integration
- `src/steuerung3d/apps/yellow/controllers/hip_controller.py`

### Shared smoke orchestration
- `src/steuerung3d/apps/supervisor/smoke_sequence_support.py`

---

## Why the HiP parameter test is separate

This smoke is about **ownership and parameter writeback**, not about motion.

Mixing it into the READY/motion smoke would make the sequence semantically wrong:

- READY is the wrong phase for parameter editing
- failures would be harder to localize
- ownership / HiP attach problems would be hidden behind motion concerns

By isolating it, the test becomes a targeted regression detector for:

- supervisor open-HiP command path
- ownership propagation
- HiP-side smoke command handling
- parameter commit/writeback observation

---

## HiP parameter smoke data flow

The parameter smoke uses this path:

`supervisor smoke helper` -> supervisor open-hip action -> HiP process claims axis -> HiP smoke control UDP -> HiP controller -> parameter intent/writeback path -> observed value / status

So this test is exercising a real HiP process, not a fake in-memory stand-in.

---

## Current safe parameter spec

The current safe parameter definition is:

- parameter: `VelMax`
- group: `vel`
- smoke edit value: `1.75`
- restore value: `1.0`

This comes from:

- `src/steuerung3d/apps/hi_p/smoke_param_specs.py`

The intent was to start with one narrow, reversible, low-risk engineering write before generalizing.

---

## Default command

```bash
python tools/smoke_supervisor_hip_param.py
```

Default profile:

```text
configs/supervisor/smoke_2pairs_hip_param.toml
```

---

## Useful CLI options

- `--profile`
- `--axis`
- `--startup-timeout-s`
- `--ready-grace-s`
- `--observe-timeout-s`
- `--settle-s`
- `--publish-interval-s`
- `--no-restore`
- `--keep-running`

### `--axis`
Lets you pick which selected axis should receive the HiP open + parameter edit.
If omitted, the first selected axis is used.

### `--no-restore`
Leaves the edited value in place after verification.
Normally the smoke attempts to restore the original value after the roundtrip succeeds.

---

## What the test actually verifies

### Boot to synced IDLE
The test first reuses the same bootstrap as the motion smoke:

- ESReset
- ESStart
- Resync
- system time advancing

But it stops there.

### Open HiP for one axis
The smoke issues the open-HiP path and waits until ownership is visible for the chosen axis.

The key assertion is that the chosen axis becomes owned by the expected HiP ID, for example:

- `hip_anton`

### Read baseline parameter
Before writing, the smoke tries to observe the current parameter value for the chosen axis.

This is used so the test can optionally restore the previous value later.

### Inject smoke parameter edit
The smoke then sends a `HiPSmokeCommand` over the dedicated HiP smoke control UDP channel.

The command carries:

- action
- parameter group
- parameter values

The current use is an `edit` command for the `vel` group.

### Observe write acceptance
The smoke then waits until the requested value is observable from the system side.
Depending on branch state, that observation can come from:

- direct parameter observation
- commit status observation
- writeback signals
- DenSi / HiP-side confirmation hooks

### Optional restore
If restoration is enabled and the original value is known, the test drives a second smoke write back to the original value and verifies the restore roundtrip.

---

## Output summary

The tool prints a summary including:

- session directory
- selected axes
- chosen axis and HiP id
- reset / estart / resync counts
- open-HiP command count
- parameter command count
- restore command count
- owner before / after open
- parameter name and group
- original value
- edited value
- observed value after write
- observed status after write
- optional restore result

---

## Expected pass condition

A passing run means:

- the stack reached synced IDLE
- the chosen HiP claimed the target axis
- the smoke parameter write reached the HiP-side edit path
- the requested parameter value became observable
- optional restore succeeded if enabled

---

## Current caveat / maturity note

During development this second smoke was the more experimental of the two.

The architecture is sound and the seam is now present, but depending on the exact branch snapshot you are on, this test may still fail in one of the final observation stages, especially around:

- discovering the baseline parameter value
- detecting the parameter apply acknowledgment reliably
- observing the writeback on the right side of the stack

So this README describes the **intended finished behavior** of the test, while also acknowledging that this smoke was still being tightened during the implementation pass.

In contrast, the main supervisor motion smoke was already the more stable / greener of the two.

---

# How to debug failures

## Session directory
Both tools print the session directory under `.run/.../sessions/...`.
That directory is the first thing to inspect.

Useful logs usually include:

- `core.log`
- `densi-Anton.log`
- `densi-Debby.log`
- `inputd.log` or `inputd_sim` related logs
- `joy2intent.log`
- `hi_p*.log` when the HiP smoke is involved

## Fast interpretation guide

### If ESReset fails
Look in the DenSi logs for missing reset tokens and in the core log for missing intent propagation.

### If ESStart fails
Look at the supervisor action path and DenSi action input binding.

### If system time never advances after resync
Check that resync is actually being issued and that the observer is attached to the correct telemetry stream.

### If `chkEsTaster` never reaches READY
Check whether the signal is being pulsed too briefly, whether the brakes have enough grace time, and whether the observed state word is parsed correctly.

### If motion never occurs
Check `inputd_sim` start control, scenario contents, and `joy2intent` mapping.

### If HiP ownership never appears
Check the open-HiP command path and whether the HiP process is reading the correct telemetry fanout port.

### If HiP parameter write never becomes observable
Check HiP smoke control, parameter spec/group routing, and the observation hook used to confirm apply.

---

# Recommended next extensions

The current design was intentionally built so the smoke suite can grow without architectural churn.

## Natural next steps for the motion smoke

- add reverse motion scenario
- add per-axis selection scenarios
- add deadman edge-case timing scenarios
- add multi-step motion profiles in TOML
- add failure-mode scenarios such as idle-only or premature release

## Natural next steps for the HiP smoke

- support multiple safe parameter specs
- support selecting the parameter from CLI
- verify explicit commit status transitions
- verify restore behavior more strictly
- add a second smoke for “open HiP without parameter write”

---

# Short operational summary

## `smoke_supervisor_sequence.py`
Use this when you want to know:

**“Can the 2-axis supervisor stack boot, clear safety, resync, reach READY, and move under scripted joystick input?”**

## `smoke_supervisor_hip_param.py`
Use this when you want to know:

**“Can I stop in IDLE, open one HiP, and perform a safe single-parameter engineering edit roundtrip?”**

Both belong in the repo because together they cover the two highest-value operator paths introduced in this work:

- the main motion commissioning path
- the HiP-based IDLE engineering edit path
