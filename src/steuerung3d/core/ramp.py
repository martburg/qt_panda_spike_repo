# ramp.py
from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class RampInputs:
    dt_s: float

    # measured
    pos_ist_m: float

    # limits
    pos_user_min_m: float
    pos_user_max_m: float

    # accel constraints
    acc_max_mps2: float
    dcc_max_mps2: float
    acc_tot_mps2: float

    # UI / mode
    deadman_pressed: bool  # App.Yellow.EsTaster
    joystick_enabled: bool  # (buttons & 32 and buttons & 1) OR recover driving
    in_recover: bool

    # status gating (legacy: only allow velocity when TechOpt and some buttons)
    allow_motion: bool

    # slider input from UI (0..1000, centered 500)
    sld_axis_vel: int  # self.sldAxisVel.GetValue()

    # setup vel max as used by legacy (SetupVelMax)
    setup_vel_max_mps: float  # already resolved (e.g. SpeedMax/10 clamped >=1)


@dataclass(frozen=True)
class RampState:
    pos0_m: float  # legacy Pos0
    vx_mps: float  # legacy VX
    fahrbefehl_old: int  # legacy FahrbefehlOld (1 means previously not pressed)


@dataclass(frozen=True)
class RampOutputs:
    next_state: RampState
    pos_soll_m: float
    speed_soll_mps: float


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def ramp_step(inp: RampInputs, st: RampState) -> RampOutputs:
    """
    Reproduces the essence of legacy RampGenerator():
      - If deadman pressed: ramp vx toward target x using acc_max/dcc_max (or stop if not allowed)
      - Else: ramp vx toward 0 using acc_tot
      - Apply end-limit braking clamp based on dcc_max and distance to user limits
      - Integrate position command: pos_soll = pos0 + vx*dt
    """
    if inp.dt_s <= 0:
        # be safe: no time progression
        return RampOutputs(st, st.pos0_m, st.vx_mps)

    pos0 = st.pos0_m
    vx = st.vx_mps
    fahrbefehl_old = st.fahrbefehl_old

    # Legacy: on first deadman press edge, set Pos0 = PosIst
    if inp.deadman_pressed:
        if fahrbefehl_old == 1:
            pos0 = inp.pos_ist_m
            fahrbefehl_old = 0

        # Compute target velocity x from slider (only when allow_motion)
        if inp.allow_motion and inp.joystick_enabled:
            # Legacy: x = (sld - 500) * 2 * SetupVelMax / 1000
            # => range approx [-SetupVelMax, +SetupVelMax]
            x = (int(inp.sld_axis_vel) - 500) * 2.0 * float(inp.setup_vel_max_mps) / 1000.0
        else:
            x = 0.0

        # Ramp vx toward x with AccMax/DccMax
        if vx < x:
            vx += abs(inp.acc_max_mps2) * inp.dt_s
            if vx >= x:
                vx = x
        elif vx > x:
            vx -= abs(inp.dcc_max_mps2) * inp.dt_s
            if vx <= x:
                vx = x

        # End-stop braking clamp (user limits)
        dcc = max(abs(inp.dcc_max_mps2), 1e-9)

        # Upper limit: distance remaining to max
        dist_to_max = float(inp.pos_user_max_m) - float(inp.pos_ist_m)
        if dist_to_max > 0.0:
            vmax = math.sqrt(dcc * 0.8 * dist_to_max)
            vx = min(vx, vmax)
        else:
            if vx > 0.0:
                vx = 0.0

        # Lower limit: distance remaining to min
        dist_to_min = float(inp.pos_ist_m) - float(inp.pos_user_min_m)
        if dist_to_min > 0.0:
            vmin = -math.sqrt(dcc * 0.8 * dist_to_min)
            vx = max(vx, vmin)
        else:
            if vx < 0.0:
                vx = 0.0

    else:
        # Deadman released: ramp vx toward 0 using AccTot
        x = 0.0
        acc_tot = abs(inp.acc_tot_mps2)

        if vx < x:
            vx += acc_tot * inp.dt_s
            if vx >= x:
                vx = x
        elif vx > x:
            vx -= acc_tot * inp.dt_s
            if vx <= x:
                vx = x

        fahrbefehl_old = 1

    # Integrate commanded position (legacy: PosSoll = Pos0 + VX*dt, and Pos0 is then reused next tick)
    pos_soll = float(pos0) + float(vx) * float(inp.dt_s)

    # Legacy then sets Pos0 = PosSoll at top of next tick.
    next_state = RampState(pos0_m=pos_soll, vx_mps=vx, fahrbefehl_old=fahrbefehl_old)
    return RampOutputs(next_state=next_state, pos_soll_m=pos_soll, speed_soll_mps=vx)


_STRICT_KEEP = _clamp
