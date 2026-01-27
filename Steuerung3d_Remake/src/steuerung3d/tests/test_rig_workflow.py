import math

from steuerung3d.core.state import MachineState
from steuerung3d.core.mode import Mode
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import (
    SetRigMode,
    SetDensiParticipating,
    SetDensiAnchor,
    ArmSync,
    EnterSync,
    RecoverToLastGood,
    ResyncNow,
)
from steuerung3d.core.rig_types import RigMode
from steuerung3d.core.rig_logic import enforce_rig_invariants, note_densi_seen


def test_arm_sync_and_enter_sync() -> None:
    st = MachineState()
    st.mode = Mode.LIVE

    # Two densis online
    st.ensure_axis('A').pos = 1.0
    st.ensure_axis('B').pos = 2.0
    note_densi_seen(st, 'A')
    note_densi_seen(st, 'B')

    apply_intent(st, SetRigMode(rig_mode='SETUP_MANUAL'))
    apply_intent(st, SetDensiParticipating(device_id='A', participating=True))
    apply_intent(st, SetDensiParticipating(device_id='B', participating=True))
    apply_intent(st, SetDensiAnchor(device_id='A', x=0, y=0, z=0))
    apply_intent(st, SetDensiAnchor(device_id='B', x=1, y=0, z=0))

    apply_intent(st, ArmSync())
    assert st.rig_mode == RigMode.ARMED_SYNC

    apply_intent(st, EnterSync())
    assert st.rig_mode == RigMode.SYNC_ACTIVE
    assert st.rig_last_good_lengths['A'] == 1.0
    assert st.rig_last_good_lengths['B'] == 2.0


def test_sync_recover_to_last_good() -> None:
    st = MachineState()
    st.mode = Mode.LIVE
    st.ensure_axis('A').pos = 1.0
    st.ensure_axis('B').pos = 2.0
    note_densi_seen(st, 'A')
    note_densi_seen(st, 'B')

    apply_intent(st, SetRigMode(rig_mode='SETUP_MANUAL'))
    apply_intent(st, SetDensiParticipating(device_id='A', participating=True))
    apply_intent(st, SetDensiParticipating(device_id='B', participating=True))
    apply_intent(st, SetDensiAnchor(device_id='A', x=0, y=0, z=0))
    apply_intent(st, SetDensiAnchor(device_id='B', x=1, y=0, z=0))

    apply_intent(st, ArmSync())
    apply_intent(st, EnterSync())

    # drift lengths (simulate uncontrolled stop)
    st.axes['A'].pos = 1.5
    st.axes['B'].pos = 1.0

    # estop event during sync -> recover mode
    st.estop = True
    enforce_rig_invariants(st)
    assert st.rig_mode == RigMode.SYNC_RECOVER

    # clear estop and recover
    st.estop = False
    st.mode = Mode.LIVE
    apply_intent(st, RecoverToLastGood())

    # run a small closed-loop simulation to converge
    dt = 0.01
    for i in range(500):
        st.tick += 1
        enforce_rig_invariants(st)
        va = st.axis_cmd.get('A').vel if 'A' in st.axis_cmd else 0.0
        vb = st.axis_cmd.get('B').vel if 'B' in st.axis_cmd else 0.0
        st.axes['A'].pos += va * dt
        st.axes['B'].pos += vb * dt
        if (abs(st.axes['A'].pos - 1.0) < st.rig_recover_plan.tol) and (abs(st.axes['B'].pos - 2.0) < st.rig_recover_plan.tol):
            break

    assert abs(st.axes['A'].pos - 1.0) < st.rig_recover_plan.tol
    assert abs(st.axes['B'].pos - 2.0) < st.rig_recover_plan.tol
    assert st.rig_mode == RigMode.ARMED_SYNC

    # resync now keeps current as last good
    st.rig_mode = RigMode.SYNC_RECOVER
    st.axes['A'].pos = 7.0
    st.axes['B'].pos = 8.0
    apply_intent(st, ResyncNow())
    assert st.rig_mode == RigMode.ARMED_SYNC
    assert st.rig_last_good_lengths['A'] == 7.0
    assert st.rig_last_good_lengths['B'] == 8.0
