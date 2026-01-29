from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from steuerung3d.protocol.raw_controls import RawControls
from steuerung3d.core.intents import (
    Intent,
    ArmLiveMode,
    DisarmToIdle,
    ClearFault,
    JogWinch,
    JogCartesian,
    SetControlMode,
    SmoothStop,
)

from .filters import deadzone_expo
from .state import JoyState


@dataclass(frozen=True)
class JoyBindings:
    axes: Dict[str, int]          # keys: manual_jog,x,y,z
    buttons: Dict[str, int]       # keys: deadman,mode_toggle,winch_next,winch_prev,...
    invert: Dict[str, bool]
    deadzone: float
    expo: float


@dataclass(frozen=True)
class JoyLimits:
    max_winch_mps: float
    fine_scale: float
    max_v: Dict[str, float]       # x,y,z


@dataclass(frozen=True)
class JoyRig:
    winches: List[str]


def _get_axis(rc: RawControls, idx: Optional[int]) -> float:
    if idx is None or idx < 0 or idx >= len(rc.axes):
        return 0.0
    return float(rc.axes[idx])


def _get_btn(rc: RawControls, idx: Optional[int]) -> bool:
    if idx is None or idx < 0 or idx >= len(rc.buttons):
        return False
    return bool(rc.buttons[idx])


def _edge(now: bool, prev: bool) -> bool:
    return now and not prev


def synthesize_intents(
    rc: RawControls,
    st: JoyState,
    rig: JoyRig,
    bind: JoyBindings,
    lim: JoyLimits,
) -> List[Intent]:
    """Map RawControls -> Intents according to current mode and bindings.

    Modes:
      - setup_manual: direct JogWinch on selected winch
      - sync_live: JogCartesian(vx,vy,vz) (kinematics later in core)
    """
    out: List[Intent] = []

    # buttons
    deadman = _get_btn(rc, bind.buttons.get("deadman"))
    mode_toggle = _get_btn(rc, bind.buttons.get("mode_toggle"))
    winch_next = _get_btn(rc, bind.buttons.get("winch_next"))
    winch_prev = _get_btn(rc, bind.buttons.get("winch_prev"))
    fine = _get_btn(rc, bind.buttons.get("fine"))

    arm = _get_btn(rc, bind.buttons.get("arm"))
    disarm = _get_btn(rc, bind.buttons.get("disarm"))
    clear_fault = _get_btn(rc, bind.buttons.get("clear_fault"))
    smooth_stop = _get_btn(rc, bind.buttons.get("smooth_stop"))

    # edges -> mode switching / selection / global verbs
    if _edge(mode_toggle, st.prev_mode_toggle):
        st.mode = "sync_live" if st.mode == "setup_manual" else "setup_manual"
        out.append(SetControlMode(mode=st.mode))

    if rig.winches:
        if _edge(winch_next, st.prev_winch_next):
            st.selected_winch_idx = (st.selected_winch_idx + 1) % len(rig.winches)
        if _edge(winch_prev, st.prev_winch_prev):
            st.selected_winch_idx = (st.selected_winch_idx - 1) % len(rig.winches)

    if _edge(arm, st.prev_arm):
        out.append(ArmLiveMode())
    if _edge(disarm, st.prev_disarm):
        out.append(DisarmToIdle())
    if _edge(clear_fault, st.prev_clear_fault):
        out.append(ClearFault())
    if _edge(smooth_stop, st.prev_smooth_stop):
        out.append(SmoothStop())

    # axes -> motion
    if st.mode == "setup_manual":
        jog_raw = _get_axis(rc, bind.axes.get("manual_jog"))
        if bind.invert.get("manual_jog", False):
            jog_raw = -jog_raw
        jog = deadzone_expo(jog_raw, bind.deadzone, bind.expo)

        rate = jog * float(lim.max_winch_mps)
        if fine:
            rate *= float(lim.fine_scale)

        # --- Setup selection semantics ---
        # Prefer momentary multi-select via buttons select_0..select_3 (or more), mapping to rig.winches[i].
        # If no select_* keys exist, fall back to legacy next/prev single selection.
        select_keys = [k for k in bind.buttons.keys() if k.startswith("select_")]
        selected_idxs: List[int] = []
        if select_keys and rig.winches:
            # Determine max index present in config
            max_i = -1
            for k in select_keys:
                try:
                    i = int(k.split("_", 1)[1])
                    max_i = max(max_i, i)
                except Exception:
                    pass
            for i in range(0, min(len(rig.winches), max_i + 1)):
                if _get_btn(rc, bind.buttons.get(f"select_{i}")):
                    selected_idxs.append(i)
        else:
            # Legacy single-selected winch.
            if deadman and rig.winches:
                selected_idxs = [st.selected_winch_idx]

        active_idxs = set(selected_idxs) if deadman else set()

        # Emit hard-stops for winches that were active last tick but are no longer active.
        for idx in sorted(st.prev_active_winch_idxs - active_idxs):
            if 0 <= idx < len(rig.winches):
                out.append(JogWinch(winch_id=rig.winches[idx], rate=0.0))

        # Emit jog for all currently active winches.
        for idx in sorted(active_idxs):
            if 0 <= idx < len(rig.winches):
                out.append(JogWinch(winch_id=rig.winches[idx], rate=float(rate)))

        st.prev_active_winch_idxs = active_idxs

    else:  # sync_live
        vx = _get_axis(rc, bind.axes.get("x"))
        vy = _get_axis(rc, bind.axes.get("y"))
        vz = _get_axis(rc, bind.axes.get("z"))

        if bind.invert.get("x", False):
            vx = -vx
        if bind.invert.get("y", False):
            vy = -vy
        if bind.invert.get("z", False):
            vz = -vz

        vx = deadzone_expo(vx, bind.deadzone, bind.expo) * float(lim.max_v.get("x", 0.0))
        vy = deadzone_expo(vy, bind.deadzone, bind.expo) * float(lim.max_v.get("y", 0.0))
        vz = deadzone_expo(vz, bind.deadzone, bind.expo) * float(lim.max_v.get("z", 0.0))

        if deadman:
            out.append(JogCartesian(vx=float(vx), vy=float(vy), vz=float(vz)))
        elif st.prev_deadman:
            out.append(JogCartesian(vx=0.0, vy=0.0, vz=0.0))

    # update prevs
    st.prev_deadman = deadman
    st.prev_mode_toggle = mode_toggle
    st.prev_winch_next = winch_next
    st.prev_winch_prev = winch_prev
    st.prev_arm = arm
    st.prev_disarm = disarm
    st.prev_clear_fault = clear_fault
    st.prev_smooth_stop = smooth_stop

    return out
