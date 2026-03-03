from __future__ import annotations

from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import JogCartesian
from steuerung3d.core.rig_types import RigMode
from steuerung3d.core.state import MachineState


def _mk_live_state(*, rig_mode: RigMode, lease_rig: str = "hip") -> MachineState:
    st = MachineState()
    st.core_mode = CoreMode.LIVE
    st.estop = False
    st.fault = False
    st.lease_rig = str(lease_rig)
    st.rig_mode = rig_mode
    return st


def test_jog_cartesian_is_ignored_when_no_xyz_axes_exist() -> None:
    st = _mk_live_state(rig_mode=RigMode.SYNC_ACTIVE, lease_rig="hip")
    st.ensure_axis("Anton")
    st.axis_cmd["Anton"].enable = True
    st.axis_cmd["Anton"].vel = 0.0

    apply_intent(st, JogCartesian(vx=1.0, vy=2.0, vz=3.0, hip_id="hip"))

    assert "X" not in st.axis_cmd
    assert "Y" not in st.axis_cmd
    assert "Z" not in st.axis_cmd
    assert st.axis_cmd["Anton"].vel == 0.0


def test_jog_cartesian_requires_sync_active_even_with_rig_lease() -> None:
    st = _mk_live_state(rig_mode=RigMode.SETUP_MANUAL, lease_rig="hip")

    for ax in ("X", "Y", "Z"):
        st.ensure_axis(ax)
        st.axis_cmd[ax].enable = True
        st.axis_cmd[ax].vel = 0.0

    apply_intent(st, JogCartesian(vx=1.0, vy=0.0, vz=0.0, hip_id="hip"))

    assert st.axis_cmd["X"].vel == 0.0
    assert st.axis_cmd["Y"].vel == 0.0
    assert st.axis_cmd["Z"].vel == 0.0
    assert "rig_mode_required" in str(getattr(st, "lease_last_denial_reason", ""))


def test_jog_cartesian_sets_velocities_when_sync_active_and_leased() -> None:
    st = _mk_live_state(rig_mode=RigMode.SYNC_ACTIVE, lease_rig="hip")

    for ax in ("X", "Y", "Z"):
        st.ensure_axis(ax)
        st.axis_cmd[ax].enable = True
        st.axis_cmd[ax].vel = 0.0

    for ax in ("X", "Y", "Z"):
        st.axis_claims[ax] = "hip"

    apply_intent(st, JogCartesian(vx=1.0, vy=2.0, vz=3.0, hip_id="hip"))

    assert st.axis_cmd["X"].vel == 1.0
    assert st.axis_cmd["Y"].vel == 2.0
    assert st.axis_cmd["Z"].vel == 3.0
