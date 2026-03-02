# test_ramp.py
import math

from steuerung3d.core.ramp import RampInputs, RampState, ramp_step


def test_deadman_press_edge_sets_pos0():
    st = RampState(pos0_m=0.0, vx_mps=0.0, fahrbefehl_old=1)
    inp = RampInputs(
        dt_s=0.01,
        pos_ist_m=12.34,
        pos_user_min_m=-100.0,
        pos_user_max_m=100.0,
        acc_max_mps2=2.0,
        dcc_max_mps2=2.0,
        acc_tot_mps2=5.0,
        deadman_pressed=True,
        joystick_enabled=True,
        in_recover=False,
        allow_motion=True,
        sld_axis_vel=500,
        setup_vel_max_mps=3.0,
    )
    out = ramp_step(inp, st)
    # with centered slider target x=0 => vx=0, but pos0 should have been snapped to pos_ist
    assert abs(out.pos_soll_m - 12.34) < 1e-9


def test_ramps_toward_positive_target():
    st = RampState(pos0_m=0.0, vx_mps=0.0, fahrbefehl_old=0)
    inp = RampInputs(
        dt_s=0.1,
        pos_ist_m=0.0,
        pos_user_min_m=-100.0,
        pos_user_max_m=100.0,
        acc_max_mps2=1.0,
        dcc_max_mps2=1.0,
        acc_tot_mps2=5.0,
        deadman_pressed=True,
        joystick_enabled=True,
        in_recover=False,
        allow_motion=True,
        sld_axis_vel=1000,     # full forward => x ~ +setup_vel_max
        setup_vel_max_mps=2.0,
    )
    out = ramp_step(inp, st)
    # target x = (1000-500)*2*2/1000 = 2.0 m/s
    # vx increases by acc*dt = 0.1
    assert abs(out.speed_soll_mps - 0.1) < 1e-9


def test_deadman_release_brakes_with_acc_tot():
    st = RampState(pos0_m=0.0, vx_mps=1.0, fahrbefehl_old=0)
    inp = RampInputs(
        dt_s=0.1,
        pos_ist_m=0.0,
        pos_user_min_m=-100.0,
        pos_user_max_m=100.0,
        acc_max_mps2=1.0,
        dcc_max_mps2=1.0,
        acc_tot_mps2=5.0,
        deadman_pressed=False,
        joystick_enabled=False,
        in_recover=False,
        allow_motion=False,
        sld_axis_vel=1000,
        setup_vel_max_mps=2.0,
    )
    out = ramp_step(inp, st)
    # vx should decrease by acc_tot*dt = 0.5 => 0.5
    assert abs(out.speed_soll_mps - 0.5) < 1e-9


def test_upper_endstop_clamps_speed():
    st = RampState(pos0_m=0.0, vx_mps=5.0, fahrbefehl_old=0)
    inp = RampInputs(
        dt_s=0.01,
        pos_ist_m=9.9,
        pos_user_min_m=-10.0,
        pos_user_max_m=10.0,   # only 0.1 m left
        acc_max_mps2=100.0,
        dcc_max_mps2=4.0,
        acc_tot_mps2=5.0,
        deadman_pressed=True,
        joystick_enabled=True,
        in_recover=False,
        allow_motion=True,
        sld_axis_vel=1000,
        setup_vel_max_mps=10.0,
    )
    out = ramp_step(inp, st)
    vmax = math.sqrt(4.0 * 0.8 * 0.1)
    assert out.speed_soll_mps <= vmax + 1e-9
