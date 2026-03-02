"""Core intent application.

This module applies high-level Intents to the in-memory MachineState.

Refactor note (Lane 1):
The previous implementation used one large match/case block.
We now route intents through small domain modules under
`steuerung3d.core.intent_routes`.

Semantics are preserved.
"""

from __future__ import annotations

import logging
from typing import Callable, Dict, Type

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
from steuerung3d.core.state import MachineState

log = logging.getLogger("core")

Handler = Callable[[MachineState, Intent], None]


UNGATED_DISPATCH: Dict[Type[Intent], Handler] = {
    # Operator control (non-safety)
    SetControlMode: lambda s, i: handle_set_control_mode(s, i),
    SmoothStop: lambda s, i: handle_smooth_stop(s, i),
    # Claims
    ClaimAxis: lambda s, i: _claim_axis(s, i.axis_id, i.hip_id, i.req_id),
    ReleaseAxis: lambda s, i: _release_axis(s, i.axis_id, i.hip_id, i.req_id),
    # Leases
    RequestRigLease: lambda s, i: handle_request_rig_lease(s, i),
    ReleaseRigLease: lambda s, i: handle_release_rig_lease(s, i),
    RequestAxisLease: lambda s, i: handle_request_axis_lease(s, i),
    ReleaseAxisLease: lambda s, i: handle_release_axis_lease(s, i),
    # UI livetick echo + joy
    EchoLifeTick: lambda s, i: handle_echo_lifetick(s, i),
    JoyStateUpdate: lambda s, i: handle_joy_state_update(s, i),
    # Safety / global requests
    SetEstop: lambda s, i: handle_set_estop(s, i),
    RequestEstopReset: lambda s, i: handle_request_estop_reset(s, i),
    RequestResync: lambda s, i: handle_request_resync(s, i),
    RequestMainReset: lambda s, i: handle_request_main_reset(s, i),
    RequestGuiderReset: lambda s, i: handle_request_guider_reset(s, i),
    # Params
    ParamEditBegin: lambda s, i: handle_param_edit_begin(s, i),
    ParamWrite: lambda s, i: handle_param_write(s, i),
    ParamCancel: lambda s, i: handle_param_cancel(s, i),
}


LIVE_ONLY_DISPATCH: Dict[Type[Intent], Handler] = {
    EnableAxis: lambda s, i: handle_enable_axis(s, i),
    JogAxis: lambda s, i: handle_jog_axis(s, i),
    JogWinch: lambda s, i: handle_jog_winch(s, i),
    JogCartesian: lambda s, i: handle_jog_cartesian(s, i),
}


def apply_intent(state: MachineState, intent: Intent) -> None:
    """Apply an intent to MachineState.

    Policy (now, with latched ESTOP):
      - ESTOP state is device-authoritative (measured via telemetry).
      - Operator can request a reset (pulse) via RequestEstopReset.
      - Fault clear is still a core-side request (later also device-verified).
      - Motion/control intents only apply in LIVE.
    """

    handler = UNGATED_DISPATCH.get(type(intent))
    if handler is not None:
        handler(state, intent)
        return

    # --- MODE-GATED INTENTS (LIVE only) ---
    core_mode = core_mode_value(getattr(state, "core_mode", "")).upper()
    is_live = False
    if core_mode:
        is_live = core_mode == CoreMode.LIVE.value

    if not is_live or bool(state.estop) or bool(state.fault):
        enforce_core_mode_actions(state)
        return

    handler = LIVE_ONLY_DISPATCH.get(type(intent))
    if handler is not None:
        handler(state, intent)
        return

    # Unknown / intentionally ignored intents are a no-op.
    return
