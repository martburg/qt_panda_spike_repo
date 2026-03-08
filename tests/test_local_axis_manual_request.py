from __future__ import annotations

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.intent_handler import apply_intent, enforce_core_mode_actions
from steuerung3d.core.intents import JoyStateUpdate, LocalAxisManualRequest
from steuerung3d.core.rig_types import DensiRuntime
from steuerung3d.core.state import MachineState


def _seed_axis_gate(st: MachineState, axis_id: str, *, ready: bool, fault: bool = False) -> None:
    st.core_axis_gate[axis_id] = {
        "in_scope": True,
        "missing": False,
        "stale": False,
        "hard_estop_active": False,
        "fault_estop_active": bool(fault),
        "ready": bool(ready),
        "key_mode": "KEY0",
    }


def test_local_axis_manual_request_moves_all_selected_ready_axes() -> None:
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    st.estop = False
    st.fault = False
    apply_intent(st, JoyStateUpdate(deadman=True, selected_axes=("Anton", "Debby")))
    for axis_id in ("Anton", "Debby"):
        st.ensure_axis(axis_id)
        st.densi_registry[axis_id] = DensiRuntime(device_id=axis_id, last_seen_core_tick=st.tick)
        _seed_axis_gate(st, axis_id, ready=True)
        st.set_axis_claim(axis_id, f"hip-{axis_id}")

    apply_intent(
        st, LocalAxisManualRequest(axis_ids=("Anton", "Debby"), enable=True, rate=0.4)
    )
    enforce_core_mode_actions(st)

    assert st.axis_cmd["Anton"].enable is True
    assert st.axis_cmd["Debby"].enable is True
    assert st.axis_cmd["Anton"].vel == 0.4
    assert st.axis_cmd["Debby"].vel == 0.4


def test_local_axis_manual_request_ignores_unready_axis_and_keeps_ready_one() -> None:
    st = MachineState()
    st.core_mode = CoreMode.FAULT
    st.estop = False
    st.fault = True
    apply_intent(st, JoyStateUpdate(deadman=True, selected_axes=("Anton", "Debby")))
    for axis_id, ready, fault in (("Anton", False, True), ("Debby", True, False)):
        st.ensure_axis(axis_id)
        st.densi_registry[axis_id] = DensiRuntime(device_id=axis_id, last_seen_core_tick=st.tick)
        _seed_axis_gate(st, axis_id, ready=ready, fault=fault)
        st.set_axis_claim(axis_id, f"hip-{axis_id}")

    apply_intent(
        st, LocalAxisManualRequest(axis_ids=("Anton", "Debby"), enable=True, rate=0.6)
    )
    enforce_core_mode_actions(st)

    assert st.axis_cmd["Anton"].vel == 0.0
    assert st.axis_cmd["Debby"].enable is True
    assert st.axis_cmd["Debby"].vel == 0.6
