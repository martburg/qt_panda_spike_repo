from __future__ import annotations

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.executor import build_command_frame
from steuerung3d.core.intent_handler import enforce_core_mode_actions
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import EnableAxis, JogCartesian, JogWinch, RequestAxisLease
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.rig_types import DensiRuntime, RigMode
from steuerung3d.core.state import MachineState


def _seed_axis_gate(st: MachineState, axis_id: str, *, ready: bool) -> None:
    st.core_axis_gate[axis_id] = {
        "in_scope": True,
        "missing": False,
        "stale": False,
        "hard_estop_active": False,
        "fault_estop_active": False,
        "ready": bool(ready),
    }


def test_local_ready_axis_can_move_while_other_axis_is_not_ready() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    st.estop = False
    st.fault = False
    st.joy = JoyState(deadman=True, selected_axes=("Anton",))

    for axis_id, ready in (("Anton", True), ("Debby", False)):
        st.ensure_axis(axis_id)
        st.densi_registry[axis_id] = DensiRuntime(device_id=axis_id, last_seen_core_tick=st.tick)
        _seed_axis_gate(st, axis_id, ready=ready)
        apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id="hip", req_id=f"lease-{axis_id}"))
    st.set_axis_claim("Anton", "hip")

    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hip"))
    apply_intent(st, JogWinch(winch_id="Anton", rate=0.6, hip_id="hip"))

    assert st.axis_cmd["Anton"].enable is True
    assert st.axis_cmd["Anton"].vel == 0.6

    cmd = build_command_frame(st)
    assert cmd.axes["Anton"].vel == 0.6
    assert cmd.axes["Debby"].vel == 0.0



def test_local_ready_axis_survives_per_tick_enforce_outside_live() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    st.estop = False
    st.fault = False
    st.joy = JoyState(deadman=True, selected_axes=("Anton",))

    for axis_id, ready in (("Anton", True), ("Debby", False)):
        st.ensure_axis(axis_id)
        st.densi_registry[axis_id] = DensiRuntime(device_id=axis_id, last_seen_core_tick=st.tick)
        _seed_axis_gate(st, axis_id, ready=ready)
        apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id="hip", req_id=f"lease-{axis_id}"))
    st.set_axis_claim("Anton", "hip")

    apply_intent(st, EnableAxis(axis_id="Anton", enable=True, hip_id="hip"))
    apply_intent(st, JogWinch(winch_id="Anton", rate=0.6, hip_id="hip"))
    enforce_core_mode_actions(st)

    assert st.axis_cmd["Anton"].vel == 0.6
    assert st.axis_cmd["Debby"].vel == 0.0


def test_local_not_ready_axis_stays_blocked_outside_live() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    st.estop = False
    st.fault = False
    st.joy = JoyState(deadman=True, selected_axes=("Debby",))

    st.ensure_axis("Debby")
    st.densi_registry["Debby"] = DensiRuntime(device_id="Debby", last_seen_core_tick=st.tick)
    _seed_axis_gate(st, "Debby", ready=False)
    apply_intent(st, RequestAxisLease(axis_id="Debby", hip_id="hip", req_id="lease-debby"))
    st.set_axis_claim("Debby", "hip")

    apply_intent(st, EnableAxis(axis_id="Debby", enable=True, hip_id="hip"))
    apply_intent(st, JogWinch(winch_id="Debby", rate=0.6, hip_id="hip"))

    assert st.axis_cmd["Debby"].enable is False
    assert st.axis_cmd["Debby"].vel == 0.0
    assert build_command_frame(st).axes["Debby"].vel == 0.0



def test_local_ready_axis_can_move_while_other_axis_is_in_fault() -> None:
    st = MachineState()
    st.core_mode = CoreMode.FAULT
    st.estop = False
    st.fault = True
    st.joy = JoyState(deadman=True, selected_axes=("Debby",))

    for axis_id, ready, fault_active in (("Anton", False, True), ("Debby", True, False)):
        st.ensure_axis(axis_id)
        st.densi_registry[axis_id] = DensiRuntime(device_id=axis_id, last_seen_core_tick=st.tick)
        st.core_axis_gate[axis_id] = {
            "in_scope": True,
            "missing": False,
            "stale": False,
            "hard_estop_active": False,
            "fault_estop_active": bool(fault_active),
            "ready": bool(ready),
        }
        apply_intent(st, RequestAxisLease(axis_id=axis_id, hip_id="hip", req_id=f"lease-{axis_id}"))
    st.set_axis_claim("Debby", "hip")

    apply_intent(st, EnableAxis(axis_id="Debby", enable=True, hip_id="hip"))
    apply_intent(st, JogWinch(winch_id="Debby", rate=0.6, hip_id="hip"))
    enforce_core_mode_actions(st)

    assert st.axis_cmd["Debby"].enable is True
    assert st.axis_cmd["Debby"].vel == 0.6
    assert st.axis_cmd["Anton"].vel == 0.0

    cmd = build_command_frame(st)
    assert cmd.axes["Debby"].enable is True
    assert cmd.axes["Debby"].vel == 0.6


def test_group_cartesian_motion_still_requires_live_sync_active() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    st.rig_mode = RigMode.SYNC_ACTIVE
    st.lease_rig = "hip"
    st.estop = False
    st.fault = False

    for ax in ("X", "Y", "Z"):
        st.ensure_axis(ax)
        st.densi_registry[ax] = DensiRuntime(device_id=ax, last_seen_core_tick=st.tick)
        _seed_axis_gate(st, ax, ready=True)
        st.axis_cmd[ax].enable = True
        st.axis_claims[ax] = "hip"

    apply_intent(st, JogCartesian(vx=1.0, vy=2.0, vz=3.0, hip_id="hip"))

    assert st.axis_cmd["X"].vel == 0.0
    assert st.axis_cmd["Y"].vel == 0.0
    assert st.axis_cmd["Z"].vel == 0.0
