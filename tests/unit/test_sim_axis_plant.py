from __future__ import annotations

from steuerung3d.adapters.sim.axis_plant import AxisPlantParams, SimAxisPlant
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop, RequestAxisLease
from steuerung3d.core.state import MachineState


def test_sim_plant_acc_limits_and_estop():
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    st.ensure_axis("X")

    plant = SimAxisPlant(params={"X": AxisPlantParams(max_vel=10.0, max_acc=1.0)})

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=lambda: [],
        handle_intent=apply_intent,
        device_step=plant.step,
        on_snapshot=lambda snap: None,
    )

    # Arm LIVE and command motion
    hip_id = "hipA"
    apply_intent(st, RequestAxisLease(axis_id="X", hip_id=hip_id, req_id="lease-1"))
    apply_intent(st, ArmLiveMode())
    apply_intent(st, EnableAxis(axis_id="X", enable=True, hip_id=hip_id))
    apply_intent(st, JogAxis(axis_id="X", vel=5.0, hip_id=hip_id))

    # After 1 tick, max dv = acc*dt = 0.01 -> vel should be 0.01
    eng.step_once()
    assert abs(st.axes["X"].vel - 0.01) < 1e-12

    # ESTOP: core clamps command => plant disables & zeros measured on next tick
    apply_intent(st, SetEstop(estop=True))
    eng.step_once()
    assert st.axes["X"].enabled is False
    assert st.axes["X"].vel == 0.0
