from __future__ import annotations

from pathlib import Path

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop, RequestAxisLease
from steuerung3d.core.state import MachineState
from steuerung3d.core.mode import Mode
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport, JsonlReader
from steuerung3d.protocol.transport import InMemTransport


def test_record_and_replay(tmp_path: Path):
    log = tmp_path / "session.jsonl"

    # --- record ---
    raw = InMemTransport()
    rec = JsonlRecorder(log)
    tr = LoggedTransport(raw, rec)

    tb = Timebase(dt_s=0.01)
    st = MachineState()
    st.ensure_axis("X")
    st.core_mode = CoreMode.LIVE
    st.mode = Mode.LIVE

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=tr.drain_intents,
        handle_intent=apply_intent,
        on_step=lambda s, dt: _plant(s, dt),
        on_snapshot=tr.publish_telemetry,
    )

    # inject some intents at known ticks
    hip_id = "hipA"
    tr.publish_intent(RequestAxisLease(axis_id="X", hip_id=hip_id, req_id="lease-1"))
    tr.publish_intent(ArmLiveMode())          # stamped tick=0
    eng.step_once()                           # tick=1
    tr.publish_intent(EnableAxis(axis_id="X", enable=True, hip_id=hip_id))  # stamped tick=1
    tr.publish_intent(JogAxis(axis_id="X", vel=0.5, hip_id=hip_id))         # stamped tick=1

    for _ in range(20):                       # run a bit
        eng.step_once()

    tr.publish_intent(SetEstop(estop=True))   # stamped near end
    for _ in range(5):
        eng.step_once()

    final_pos_record = st.axes["X"].pos
    final_tick_record = st.tick

    # --- replay (quick check): ensure log contains telemetry at final tick ---
    r = JsonlReader(log)
    snaps = list(r.iter_telemetry())
    assert snaps[-1].tick == final_tick_record
    assert abs(snaps[-1].axes["X"].pos - final_pos_record) < 1e-12


def _plant(state: MachineState, dt: float) -> None:
    ax = state.axes["X"]
    ax.pos += ax.vel * dt
