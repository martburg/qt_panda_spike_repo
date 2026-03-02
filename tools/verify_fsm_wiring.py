from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.axis_types import AxisTelemetry as LegacyAxisTelemetry
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.state import MachineState


def make_tel(axis_id: str, *, own_pid_rx: str, enabled: bool) -> LegacyAxisTelemetry:
    return LegacyAxisTelemetry(
        link_ok=True,
        name=axis_id,
        own_pid_rx=own_pid_rx,
        lifetick_tx=0,
        status_word=4356,          # "ready" heuristic
        guide_status_word=0,
        estop_status_dword=0,
        system_time="",
        pos_ist=0.0,
        vel_ist=0.0,
        estop_active=False,
        fault_active=False,
        enabled=enabled,
    )


def main() -> None:
    axis_id = "X"
    pid = "4711"

    tb = Timebase(dt_s=0.01)
    st = MachineState()

    # Core mode matters because enforce_core_mode_actions() runs every tick
    st.core_mode = CoreMode.LIVE

    # Create axis once, then configure it
    ax = st.ensure_axis(axis_id)
    ax.kind = "legacy_twincat"                  # <-- critical
    ax.meta["own_pid_tx"] = pid

    st.ensure_axis_cmd(axis_id)                 # creates axis_cmd["X"]

    # Make sure the FSM config will use the same pid (optional but cleaner)
    st.controller_pid = pid                     # <-- recommended (if MachineState allows it)

    # seed a "link ok + PID echo" telemetry blob so FSM can claim
    ax.tel = make_tel(axis_id, own_pid_rx=pid, enabled=False)

    def device_step(state: MachineState, cmd: CommandFrame, dt: float) -> None:
        """
        Fake device: when command frame requests enable, next tick telemetry will show enabled=True.
        This proves:
          engine -> drive_legacy_axis_fsms -> build_command_frame -> device_step feedback loop
        """
        ax = state.ensure_axis(axis_id)
        sp = cmd.axes.get(axis_id)
        want_enable = bool(sp.enable) if sp else False

        # update common surface (logging view)
        ax.enabled = want_enable

        # update legacy telemetry blob for next tick
        ax.tel = make_tel(axis_id, own_pid_rx=pid, enabled=want_enable)

    eng = CoreEngine(timebase=tb, state=st, device_step=device_step)

    print("tick | fsm_state     | cmd_enable | tel.enabled | ax.enabled")
    print("-----+--------------+-----------+-------------+----------")

    for _ in range(12):
        eng.step_once()
        ax = st.axes[axis_id]
        cmd_enable = st.axis_cmd[axis_id].enable
        tel_enabled = getattr(ax.tel, "enabled", None)
        fsm_state = ax.meta.get("fsm_state", "?")
        print(f"{st.tick:4d} | {fsm_state:12} | {str(cmd_enable):9} | {str(tel_enabled):11} | {str(ax.enabled):8}")


if __name__ == "__main__":
    main()
