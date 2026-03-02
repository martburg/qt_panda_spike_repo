from __future__ import annotations

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intent_handlers.enforce import enforce_core_mode_actions
from steuerung3d.core.intent_handlers.reset_resync import axis_reset_allowed
from steuerung3d.core.intents import (
    RequestEstopReset,
    RequestGuiderReset,
    RequestMainReset,
    RequestResync,
    SetEstop,
)
from steuerung3d.core.state import MachineState


def handle_set_estop(state: MachineState, intent: SetEstop) -> None:
    want_estop = bool(getattr(intent, "estop", False))
    state.estop = bool(want_estop)

    if state.estop:
        for ax in state.axes.values():
            ax.enabled = False
            ax.vel = 0.0
        for cmd in state.axis_cmd.values():
            cmd.enable = False
            cmd.vel = 0.0

    enforce_core_mode_actions(state)


def handle_request_estop_reset(state: MachineState, intent: RequestEstopReset) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")

    allowed, _reason = axis_reset_allowed(state, axis_id, hip_id)
    if not allowed:
        key = axis_id or "<none>"
        state.estop_reset_denied_count_by_axis[key] = int(state.estop_reset_denied_count_by_axis.get(key, 0)) + 1
        return

    if axis_id:
        state.estop_reset_req_by_axis[axis_id] = True
    else:
        key = axis_id or "<none>"
        state.estop_reset_denied_count_by_axis[key] = int(state.estop_reset_denied_count_by_axis.get(key, 0)) + 1
        return

    enforce_core_mode_actions(state)


def handle_request_resync(state: MachineState, intent: RequestResync) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")

    if axis_id:
        owner = state.claim_owner(axis_id)
        if owner and hip_id and owner != hip_id:
            return
        state.resync_req_by_axis[axis_id] = True
    else:
        state.resync_req = True


def _claim_allows(state: MachineState, axis_id: str, hip_id: str) -> bool:
    axis_id = normalize_axis_id(axis_id)
    hip_id = str(hip_id or "")
    if not axis_id:
        return False
    owner = state.claim_owner(axis_id)
    if owner and hip_id and owner != hip_id:
        return False
    return True


def handle_request_main_reset(state: MachineState, intent: RequestMainReset) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    if not _claim_allows(state, axis_id, hip_id):
        return
    state.main_reset_req_by_axis[axis_id] = True
    enforce_core_mode_actions(state)


def handle_request_guider_reset(state: MachineState, intent: RequestGuiderReset) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    hip_id = str(getattr(intent, "hip_id", "") or "")
    if not _claim_allows(state, axis_id, hip_id):
        return
    state.guider_reset_req_by_axis[axis_id] = True
    enforce_core_mode_actions(state)
