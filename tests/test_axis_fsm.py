from steuerung3d.core.axis_fsm import AxisFSM, AxisFsmConfig, ST_IDLE, ST_ESTOP, ST_RECOVER
from steuerung3d.core.axis_types import AxisTelemetry, AxisRequest


def tel_ok(**kw):
    base = dict(
        link_ok=True,
        name="Anton",
        own_pid_rx="0000",
        lifetick_tx=1,
        status_word=0,
        guide_status_word=0,
        estop_status_dword=0,
        estop_active=False,
        fault_active=False,
        enabled=False,
    )
    base.update(kw)
    return AxisTelemetry(**base)


def test_estop_forces_safe_and_enters_estop():
    fsm = AxisFSM(AxisFsmConfig(controller_pid="4711"))
    req = AxisRequest(want_enable=True, want_motion=True, cmd_speed=1.0, cmd_pos=10.0)

    cmd = fsm.step(tel_ok(estop_active=True, estop_status_dword=1), req)
    assert fsm.state == ST_ESTOP
    assert cmd.intent_str == "False"
    assert cmd.speed_soll == 0.0
    assert cmd.resync in (0.0, 1.0)  # depends on req.want_resync


def test_estop_clear_enters_recover():
    fsm = AxisFSM(AxisFsmConfig(controller_pid="4711"))

    # drive into estop
    fsm.step(tel_ok(estop_active=True, estop_status_dword=1), AxisRequest())
    assert fsm.state == ST_ESTOP

    # clear estop -> recover
    fsm.step(tel_ok(estop_active=False, estop_status_dword=0), AxisRequest(want_resync=True))
    assert fsm.state == ST_RECOVER


def test_claim_ack_by_pid_echo():
    fsm = AxisFSM(AxisFsmConfig(controller_pid="4711"))

    # link up -> idle
    fsm.step(tel_ok(), AxisRequest(want_claim=False))
    assert fsm.state == ST_IDLE

    # want claim -> claiming
    fsm.step(tel_ok(), AxisRequest(want_claim=True))
    assert fsm.state == "claiming"

    # PLC echoes our PID -> ready
    fsm.step(tel_ok(own_pid_rx="4711"), AxisRequest(want_claim=True))
    assert fsm.state == "ready"
