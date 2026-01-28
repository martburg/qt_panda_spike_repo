from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.state import MachineState


def test_ticks_are_deterministic():
    tb = Timebase(dt_s=0.02)
    st = MachineState()
    eng = CoreEngine(timebase=tb, state=st)

    eng.run_for_ticks(10)
    assert st.tick == 10
    assert abs(st.t_s - (10 * 0.02)) < 1e-12
