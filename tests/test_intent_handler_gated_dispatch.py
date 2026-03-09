from __future__ import annotations

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EnableAxis, JogWinch, RequestAxisLease, SetControlMode
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.rig_types import DensiRuntime
from steuerung3d.core.state import MachineState


def _seed_ready_axis(st: MachineState, axis_id: str, *, hip_id: str = "hip") -> None:
    st.ensure_axis(axis_id)
    st.densi_registry[axis_id] = DensiRuntime(device_id=axis_id, last_seen_core_tick=st.tick)
    st.core_axis_gate[axis_id] = {
        "in_scope": True,
        "missing": False,
        "stale": False,
        "hard_estop_active": False,
        "fault_estop_active": False,
        "ready": True,
    }
    apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id=hip_id, req_id=f"lease-{axis_id}"))
    st.set_axis_claim(axis_id, hip_id)


def test_ungated_control_intent_still_applies_outside_live() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED

    apply_intent(st, SetControlMode(mode="setup_manual"))

    assert str(getattr(st, "control_mode", "")) == "setup_manual"


def test_live_only_motion_still_uses_local_axis_fallback_outside_live() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    st.estop = False
    st.fault = False
    st.joy = JoyState(deadman=True, selected_axes=("Anton",))
    _seed_ready_axis(st, "Anton")

    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hip"))
    apply_intent(st, JogWinch(winch_id="Anton", rate=0.4, hip_id="hip"))

    assert st.axis_cmd["Anton"].enable is True
    assert st.axis_cmd["Anton"].vel == 0.4
    assert build_command_frame(st).axes["Anton"].vel == 0.4


def test_estop_still_blocks_live_only_motion_path() -> None:
    st = MachineState()
    st.core_mode = CoreMode.LIVE
    st.estop = True
    st.joy = JoyState(deadman=True, selected_axes=("Anton",))
    _seed_ready_axis(st, "Anton")

    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hip"))
    apply_intent(st, JogWinch(winch_id="Anton", rate=0.7, hip_id="hip"))

    assert st.axis_cmd["Anton"].enable is False
    assert st.axis_cmd["Anton"].vel == 0.0
