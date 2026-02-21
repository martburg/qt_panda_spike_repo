from __future__ import annotations

from steuerung3d.apps.yellow.engines.densi.plc_anton_vel_cmd import step_plc_anton_vel_cmd
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState


def _mk_state() -> MachineState:
    st = MachineState()
    st.ensure_axis("Anton")
    st.estop = False
    st.fault = False
    st.params.update(
        {
            "VelMax": 10.0,
            "AccMove": 1.0,
            "AccMax": 1.0,
            "DccMax": 1.0,
            "UserMax": 300.0,
            "UserMin": 0.0,
            "P": 0.0,
            "I": 0.0,
            "D": 0.0,
            "IL": 0.0,
        }
    )
    return st


def _mk_cmd(*, vel: float, lifetick: int = 0) -> CommandFrame:
    return CommandFrame(
        tick=lifetick,
        t_s=0.0,
        estop=False,
        fault=False,
        mode="IDLE",
        axes={"Anton": AxisSetpoint(enable=True, vel=float(vel))},
        lifetick_echo={"Anton": int(lifetick)},
    )


def test_accel_ramp_limits_velocity() -> None:
    st = _mk_state()
    cmd = _mk_cmd(vel=5.0, lifetick=1)

    step_plc_anton_vel_cmd(
        state=st,
        cmd=cmd,
        dt_s=1.0,
        axis_ids=["Anton"],
        ready_for_sollvel=True,
        lifetick_stale_after_ticks=50,
    )

    ax = st.axes["Anton"]
    assert 0.9 <= ax.vel <= 1.1


def test_soft_limit_braking_caps_speed() -> None:
    st = _mk_state()
    st.params["UserMax"] = 1.0
    st.params["DccMax"] = 1.0
    st.params["AccMove"] = 10.0
    st.axes["Anton"].pos = 0.99

    cmd = _mk_cmd(vel=10.0, lifetick=2)
    step_plc_anton_vel_cmd(
        state=st,
        cmd=cmd,
        dt_s=1.0,
        axis_ids=["Anton"],
        ready_for_sollvel=True,
        lifetick_stale_after_ticks=50,
    )

    ax = st.axes["Anton"]
    assert ax.vel <= 0.11


def test_lifetick_stale_gate_forces_zero_speed() -> None:
    st = _mk_state()
    cmd = _mk_cmd(vel=2.0, lifetick=10)

    for _ in range(3):
        step_plc_anton_vel_cmd(
            state=st,
            cmd=cmd,
            dt_s=0.1,
            axis_ids=["Anton"],
            ready_for_sollvel=True,
            lifetick_stale_after_ticks=2,
        )

    ax = st.axes["Anton"]
    assert abs(ax.vel) <= 1e-6


def test_position_trim_adds_velocity_bias() -> None:
    st = _mk_state()
    st.params.update({"P": 1.0, "I": 0.0, "D": 0.0, "IL": 10.0, "PosSoll": 5.0})
    st.axes["Anton"].pos = 0.0

    cmd = _mk_cmd(vel=0.0, lifetick=11)
    step_plc_anton_vel_cmd(
        state=st,
        cmd=cmd,
        dt_s=0.1,
        axis_ids=["Anton"],
        ready_for_sollvel=True,
        lifetick_stale_after_ticks=50,
    )

    ax = st.axes["Anton"]
    assert ax.vel > 0.0
