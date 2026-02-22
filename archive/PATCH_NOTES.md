# Drop-in Docs Overlay

This zip contains:

- docs/boot_to_recover.md  (canonical boot→sync→recover/resync process description)

Extract into repo root to place the doc under ./docs/.

## JoyStateUpdate -> DenSi motion wiring (discovery)

Baseline tests:
- pytest -q fails during collection: missing dependency "transitions" (tests/test_axis_fsm.py imports core/axis_fsm.py).

Motion intent and handler chain (canonical):
- JoyStateUpdate is accepted in core/intent_handler.py and stored on state.joy (JoyState.soll_speed).
- Hip UI engine (apps/yellow/engines/hip/engine.py) uses JoyState + deadman + claim to emit JogWinch intents via apps/yellow/domain/joy_motion_map.py::map_soll_speed_to_jog_winch().
- Core intent handler applies JogWinch in core/intent_handler.py: sets axis_cmd.vel for the axis (winch_id).

DenSi command frame build + velocity field:
- core/executor.py::build_command_frame builds CommandFrame with AxisSetpoint(enable, vel).
- AxisSetpoint.vel is the velocity setpoint (units/s placeholder) used downstream as SpeedSollIN.
- DenSi engine step_plant_with_clamp() passes CommandFrame to plc_anton_vel_cmd.py, which reads AxisSetpoint.vel as commanded speed (SpeedSollIN).

VelMax location and read path:
- Core param registry: core/param_registry.py defines VelMax in the "vel" group.
- DenSi motion law reads params["VelMax"] (or SpeedMaxUI) inside plc_anton_vel_cmd.py to clamp speed.
- DenSi engine sets a default VelMax in state.params (apps/yellow/engines/densi/engine.py).

Additional JoyStateUpdate source:
- apps/joy2intent/mapping.py synthesizes JoyStateUpdate from joystick inputs (soll_speed clamped in core/joy_state.py).

## JoyStateUpdate -> DenSi motion wiring (implementation)

Summary:
- JoyStateUpdate now emits a JogWinch intent in core/intent_handler.py, scaled by VelMax and forced to 0 when deadman is released.
- New tests cover JoyStateUpdate scaling and command frame flow in tests/test_joy_motion_pipeline.py.
- PLC boolean token tests and UDP PLC command decode tests were added/updated to enforce True/False tokens and fallbacks.
- Manual smoke steps added to docs/MANUAL_TESTING.md for 1dev_sim deadman/velocity verification.

TODO:
- Consider multi-axis selection policy for JoyStateUpdate (currently single-axis only).
