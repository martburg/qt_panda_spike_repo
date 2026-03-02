from __future__ import annotations

import logging

from steuerung3d.core.axis_ids import normalize_axis_id
from steuerung3d.core.intents import EchoLifeTick, JoyStateUpdate, SetControlMode, SmoothStop
from steuerung3d.core.joy_state import JoyState, clamp_soll_speed
from steuerung3d.core.state import MachineState

log = logging.getLogger("core")


def handle_set_control_mode(state: MachineState, intent: SetControlMode) -> None:
    setattr(state, "control_mode", str(getattr(intent, "mode", "")))


def handle_smooth_stop(state: MachineState, _intent: SmoothStop) -> None:
    for cmd in state.axis_cmd.values():
        cmd.vel = 0.0


def handle_echo_lifetick(state: MachineState, intent: EchoLifeTick) -> None:
    axis_id = normalize_axis_id(getattr(intent, "axis_id", ""))
    if not axis_id:
        return
    v16 = int(getattr(intent, "value", 0)) & 0xFFFF
    state.lifetick_echo_by_axis[axis_id] = v16
    log.debug(
        "LIFETICK Core rx EchoLifeTick: axis=%s value=%d hip_id=%s",
        axis_id,
        v16,
        str(getattr(intent, "hip_id", "") or ""),
    )


def handle_joy_state_update(state: MachineState, intent: JoyStateUpdate) -> None:
    state.joy = JoyState(
        deadman=bool(getattr(intent, "deadman", False)),
        select_hip=bool(getattr(intent, "select_hip", False)),
        soll_speed=clamp_soll_speed(float(getattr(intent, "soll_speed", 0.0))),
    )
