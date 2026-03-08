from __future__ import annotations

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.intent_handlers.lease import axis_lease_allows as _axis_lease_allows
from steuerung3d.core.intents import (
    EnableAxis,
    JogAxis,
    JogCartesian,
    JogWinch,
    LocalAxisManualRequest,
)
from steuerung3d.core.motion_gate import axis_local_motion_allowed
from steuerung3d.core.rig_types import RigMode
from steuerung3d.core.state import MachineState


def handle_enable_axis(state: MachineState, intent: EnableAxis) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    enable = bool(getattr(intent, "enable", False))
    hip_id = getattr(intent, "hip_id", "")

    state.ensure_axis(axis_id)
    if not _axis_lease_allows(state, axis_id, hip_id):
        state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
        return
    claim = state.claim_owner(axis_id)
    if claim and hip_id and claim != hip_id:
        return
    if claim and not hip_id:
        return
    cmd = state.axis_cmd[axis_id]
    cmd.enable = bool(enable)
    if not cmd.enable:
        cmd.vel = 0.0


def handle_jog_axis(state: MachineState, intent: JogAxis) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    vel = float(getattr(intent, "vel", 0.0))
    hip_id = getattr(intent, "hip_id", "")

    state.ensure_axis(axis_id)
    if not _axis_lease_allows(state, axis_id, hip_id):
        state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
        return
    claim = state.claim_owner(axis_id)
    if claim and hip_id and claim != hip_id:
        return
    if claim and not hip_id:
        return
    cmd = state.axis_cmd[axis_id]
    if cmd.enable:
        cmd.vel = float(vel)


def handle_jog_winch(state: MachineState, intent: JogWinch) -> None:
    axis_id = normalize_axis_id(getattr(intent, "winch_id", ""))
    rate = float(getattr(intent, "rate", 0.0))
    hip_id = getattr(intent, "hip_id", "")

    state.ensure_axis(axis_id)
    if not _axis_lease_allows(state, axis_id, hip_id):
        state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
        return
    claim = state.claim_owner(axis_id)
    if claim and hip_id and claim != hip_id:
        return
    if claim and not hip_id:
        return
    cmd = state.axis_cmd[axis_id]
    if cmd.enable:
        cmd.vel = float(rate)


def handle_jog_cartesian(state: MachineState, intent: JogCartesian) -> None:
    hip_id = getattr(intent, "hip_id", "")
    lease_rig = str(getattr(state, "lease_rig", "") or "")
    if not lease_rig or (hip_id and lease_rig != hip_id):
        state.lease_last_denial_reason = "rig_lease_required"
        return

    rm = getattr(state, "rig_mode", RigMode.DISCOVERY)
    if str(rm) != str(RigMode.SYNC_ACTIVE):
        state.lease_last_denial_reason = "rig_mode_required:SYNC_ACTIVE"
        return

    vx = float(getattr(intent, "vx", 0.0))
    vy = float(getattr(intent, "vy", 0.0))
    vz = float(getattr(intent, "vz", 0.0))

    for axis_id, vel in (("X", vx), ("Y", vy), ("Z", vz)):
        if axis_id in state.axes or axis_id in state.axis_cmd:
            if not _axis_lease_allows(state, axis_id, hip_id):
                state.lease_last_denial_reason = f"axis_lease_required:{axis_id}"
                continue
            claim = state.claim_owner(axis_id)
            if claim and hip_id and claim != hip_id:
                continue
            if claim and not hip_id:
                continue
            cmd = state.ensure_axis_cmd(axis_id)
            if cmd.enable:
                cmd.vel = float(vel)


def handle_local_axis_manual(state: MachineState, intent: LocalAxisManualRequest) -> None:
    axis_ids = tuple(normalize_axis_id(a) for a in tuple(getattr(intent, "axis_ids", ()) or ()))
    axis_ids = tuple(a for a in axis_ids if a)
    enable = bool(getattr(intent, "enable", False))
    rate = float(getattr(intent, "rate", 0.0))
    is_live = core_mode_value(getattr(state, "core_mode", "")).upper() == CoreMode.LIVE.value

    for axis_id in axis_ids:
        state.ensure_axis(axis_id)
        cmd = state.axis_cmd[axis_id]
        if not enable:
            cmd.enable = False
            cmd.vel = 0.0
            continue
        if not str(state.axis_owner(axis_id) or ""):
            state.lease_last_denial_reason = f"axis_owner_required:{axis_id}"
            continue
        if (not is_live) and (not axis_local_motion_allowed(state, axis_id)):
            continue
        cmd.enable = True
        cmd.vel = float(rate)
