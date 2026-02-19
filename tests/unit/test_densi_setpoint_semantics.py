from __future__ import annotations

from steuerung3d.apps.yellow.engines.densi.setpoint_semantics import normalize_cmd_for_plant
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState


def _cmd() -> CommandFrame:
    return CommandFrame(
        tick=1,
        t_s=0.0,
        estop=False,
        fault=False,
        mode="TEST",
        axes={"A": AxisSetpoint(enable=True, vel=1.0)},
    )


def test_normalize_cmd_for_plant_pass_through() -> None:
    st = MachineState()
    cmd = _cmd()
    out = normalize_cmd_for_plant(cmd, state=st, dt_s=0.01, axis_ids=["A"], drive_ready=True)
    assert out is cmd


def test_normalize_cmd_for_plant_clamps_on_estop() -> None:
    st = MachineState(estop=True)
    cmd = _cmd()
    out = normalize_cmd_for_plant(cmd, state=st, dt_s=0.01, axis_ids=["A", "B"], drive_ready=True)
    assert out is not cmd
    assert set(out.axes.keys()) == {"A", "B"}
    assert out.axes["A"].enable is False
    assert out.axes["A"].vel == 0.0
    assert out.axes["B"].enable is False
    assert out.axes["B"].vel == 0.0


def test_normalize_cmd_for_plant_clamps_when_not_ready() -> None:
    st = MachineState(estop=False)
    cmd = _cmd()
    out = normalize_cmd_for_plant(cmd, state=st, dt_s=0.01, axis_ids=["A"], drive_ready=False)
    assert out is not cmd
    assert out.axes["A"].enable is False
    assert out.axes["A"].vel == 0.0
