---
name: HipEmitJogIntentsFromJoy
description: >
  In HiP, translate existing JOY telemetry fields (dm/sel/sp already present) into proper
  motion intents (Enable/Arm + Jog/VelCmd) routed to core, gated by ownership + core_mode
  + safety facts. Do not inject motion in core. Add/adjust tests (do not run pytest in agent env).
tools:
  - read
  - search
  - edit
  - terminal
handoff:
  to: supervisor
  message: >
    Summarize the final diff, point to the exact HiP tick location where intents are emitted,
    list the intent types used/added, and provide a short runbook snippet for Martin to verify
    with `python -m steuerung3d up --profile 1dev_sim`. Note: tests were updated but not executed
    due to agent environment limitations.
---