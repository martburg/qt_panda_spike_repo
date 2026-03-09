"""Core intent application.

This module applies high-level Intents to the in-memory MachineState.

Refactor note (Lane 2, small and declared):
The previous implementation stored subtype-specific handlers in broad
callable dispatch tables. This version keeps the ungated/live-only split,
but performs explicit narrowing before calling subtype handlers so the
intent boundary is statically clear while preserving runtime behavior.
"""

from __future__ import annotations

import logging

from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.intent_handlers.claims import (
    claim_axis as _claim_axis,
    release_axis as _release_axis,
)
from steuerung3d.core.intent_handlers.enforce import enforce_core_mode_actions
from steuerung3d.core.intent_routes.control import (
    handle_echo_lifetick,
    handle_joy_state_update,
    handle_set_control_mode,
    handle_smooth_stop,
)
from steuerung3d.core.intent_routes.leases import (
    handle_release_axis_lease,
    handle_release_rig_lease,
    handle_request_axis_lease,
    handle_request_rig_lease,
)
from steuerung3d.core.intent_routes.motion import (
    handle_enable_axis,
    handle_jog_axis,
    handle_jog_cartesian,
    handle_jog_winch,
    handle_local_axis_manual,
)
from steuerung3d.core.intent_routes.params import (
    handle_param_cancel,
    handle_param_edit_begin,
    handle_param_write,
)
from steuerung3d.core.intent_routes.safety import (
    handle_request_estop_reset,
    handle_request_guider_reset,
    handle_request_main_reset,
    handle_request_resync,
    handle_set_estop,
)
from steuerung3d.core.intents import (
    ClaimAxis,
    EchoLifeTick,
    EnableAxis,
    Intent,
    JogAxis,
    JogCartesian,
    JogWinch,
    JoyStateUpdate,
    LocalAxisManualRequest,
    ParamCancel,
    ParamEditBegin,
    ParamWrite,
    ReleaseAxis,
    ReleaseAxisLease,
    ReleaseRigLease,
    RequestAxisLease,
    RequestEstopReset,
    RequestGuiderReset,
    RequestMainReset,
    RequestResync,
    RequestRigLease,
    SetControlMode,
    SetEstop,
    SmoothStop,
)
from steuerung3d.core.motion_gate import axis_local_motion_allowed
from steuerung3d.core.state import MachineState

log = logging.getLogger("core")


def _apply_ungated_intent(state: MachineState, intent: Intent) -> bool:
    if isinstance(intent, SetControlMode):
        handle_set_control_mode(state, intent)
        return True
    if isinstance(intent, SmoothStop):
        handle_smooth_stop(state, intent)
        return True
    if isinstance(intent, ClaimAxis):
        _claim_axis(state, intent.axis_id, intent.hip_id, intent.req_id)
        return True
    if isinstance(intent, ReleaseAxis):
        _release_axis(state, intent.axis_id, intent.hip_id, intent.req_id)
        return True
    if isinstance(intent, RequestRigLease):
        handle_request_rig_lease(state, intent)
        return True
    if isinstance(intent, ReleaseRigLease):
        handle_release_rig_lease(state, intent)
        return True
    if isinstance(intent, RequestAxisLease):
        handle_request_axis_lease(state, intent)
        return True
    if isinstance(intent, ReleaseAxisLease):
        handle_release_axis_lease(state, intent)
        return True
    if isinstance(intent, EchoLifeTick):
        handle_echo_lifetick(state, intent)
        return True
    if isinstance(intent, JoyStateUpdate):
        handle_joy_state_update(state, intent)
        return True
    if isinstance(intent, LocalAxisManualRequest):
        handle_local_axis_manual(state, intent)
        return True
    if isinstance(intent, SetEstop):
        handle_set_estop(state, intent)
        return True
    if isinstance(intent, RequestEstopReset):
        handle_request_estop_reset(state, intent)
        return True
    if isinstance(intent, RequestResync):
        handle_request_resync(state, intent)
        return True
    if isinstance(intent, RequestMainReset):
        handle_request_main_reset(state, intent)
        return True
    if isinstance(intent, RequestGuiderReset):
        handle_request_guider_reset(state, intent)
        return True
    if isinstance(intent, ParamEditBegin):
        handle_param_edit_begin(state, intent)
        return True
    if isinstance(intent, ParamWrite):
        handle_param_write(state, intent)
        return True
    if isinstance(intent, ParamCancel):
        handle_param_cancel(state, intent)
        return True
    return False


def _motion_axis_id(intent: Intent) -> str:
    if isinstance(intent, (EnableAxis, JogAxis)):
        return str(intent.axis_id or "")
    if isinstance(intent, JogWinch):
        return str(intent.winch_id or "")
    return ""


def _apply_live_only_intent(state: MachineState, intent: Intent) -> bool:
    if isinstance(intent, EnableAxis):
        handle_enable_axis(state, intent)
        return True
    if isinstance(intent, JogAxis):
        handle_jog_axis(state, intent)
        return True
    if isinstance(intent, JogWinch):
        handle_jog_winch(state, intent)
        return True
    if isinstance(intent, JogCartesian):
        handle_jog_cartesian(state, intent)
        return True
    return False


def apply_intent(state: MachineState, intent: Intent) -> None:
    """Apply an intent to MachineState.

    Policy (now, with latched ESTOP):
      - ESTOP state is device-authoritative (measured via telemetry).
      - Operator can request a reset (pulse) via RequestEstopReset.
      - Fault clear is still a core-side request (later also device-verified).
      - Motion/control intents only apply in LIVE.
    """

    if _apply_ungated_intent(state, intent):
        return

    core_mode = core_mode_value(getattr(state, "core_mode", "")).upper()
    is_live = bool(core_mode) and (core_mode == CoreMode.LIVE.value)

    is_live_only = isinstance(intent, (EnableAxis, JogAxis, JogWinch, JogCartesian))
    if not is_live_only:
        return

    if bool(state.estop):
        enforce_core_mode_actions(state)
        return

    if is_live:
        _apply_live_only_intent(state, intent)
        return

    axis_id = _motion_axis_id(intent)
    if axis_id and axis_local_motion_allowed(state, axis_id):
        _apply_live_only_intent(state, intent)
        return

    enforce_core_mode_actions(state)
