from __future__ import annotations

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState

from steuerung3d.apps.yellow.panels.densi.densi_readouts_vm import compute_densi_readouts_vm


def test_compute_densi_readouts_vm_formats_and_sliders() -> None:
    st = MachineState()
    ax = st.ensure_axis("Anton")
    ax.pos = 1.234
    ax.vel = -0.056
    st.params.update(
        {
            "ActCur": 12.4,
            "Temp": 21.6,
            "PosMin": 0.1,
            "PosMax": 0.9,
            "GuidePosIst": 0.23456,
            "GuideIstSpeed": 0.0012,
            "VelMax": 2.0,
            "UserMin": -1.0,
            "UserMax": 3.0,
        }
    )

    cmd = CommandFrame(
        tick=1,
        t_s=0.01,
        estop=False,
        fault=False,
        mode="LIVE",
        axes={"Anton": AxisSetpoint(enable=True, vel=0.5)},
    )

    vm = compute_densi_readouts_vm(state=st, axis_id="Anton", last_cmd=cmd)

    assert vm.pos_text == "1.23 m"
    assert vm.vel_text == "-0.06 m/s"
    assert vm.amp_text == "12 A"
    assert vm.temp_text == "22 °"

    assert vm.guider_min_text == "0.100 m"
    assert vm.guider_max_text == "0.900 m"
    assert vm.guider_val_text == "0.235 m"
    assert vm.guider_speed_text == "0.001 m/s"

    # Vel slider: ±VelMax, scaled by 1000
    assert vm.vel_cmd_min == -2000
    assert vm.vel_cmd_max == 2000
    assert vm.vel_cmd_val == 500

    # Limit slider: [UserMin, UserMax], scaled by 1000
    assert vm.limit_min == -1000
    assert vm.limit_max == 3000
    assert vm.limit_val == 1234
