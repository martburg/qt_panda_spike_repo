from __future__ import annotations

from pathlib import Path

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport, JsonlReader
from steuerung3d.protocol.transport import InMemTransport


def test_record_and_replay_multi_axis_sim(tmp_path: Path):
    """Smoke-test record/replay with >1 axis using the SIM device.

    Why this exists:
      - Multi-axis is a first-class requirement.
      - PLCs may be unavailable during development.
      - We still want deterministic logs we can inspect and later replay.

    This test does NOT require a PLC.
    """

    log = tmp_path / "session_multi_axis.jsonl"

    axis_ids = ["X", "Y"]

    # --- record ---
    raw = InMemTransport()
    rec = JsonlRecorder(log)
    tr = LoggedTransport(raw, rec)

    tb = Timebase(dt_s=0.01)
    st = MachineState()
    for a in axis_ids:
        st.ensure_axis(a)

    sim = SimDevice(plant=SimAxisPlant())

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=tr.drain_intents,
        handle_intent=apply_intent,
        device_step=sim.step,
        on_command_frame=rec.record_command_frame,
        on_snapshot=tr.publish_telemetry,
    )

    # Inject some intents at known ticks
    tr.publish_intent(ArmLiveMode())  # stamped tick=0

    eng.step_once()  # tick=1

    # Enable both axes
    for a in axis_ids:
        tr.publish_intent(EnableAxis(axis_id=a, enable=True))  # stamped tick=1

    # Jog both axes with different velocities
    tr.publish_intent(JogAxis(axis_id="X", vel=0.5))   # stamped tick=1
    tr.publish_intent(JogAxis(axis_id="Y", vel=-0.25))  # stamped tick=1

    # Run a bit
    eng.run_for_ticks(40)

    # Hit estop near the end and run a few more ticks to ensure clamp applies
    tr.publish_intent(SetEstop(estop=True))
    eng.run_for_ticks(10)

    final_tick_record = st.tick
    final_pos_record = {a: st.axes[a].pos for a in axis_ids}

    # --- replay (quick check): ensure log contains telemetry at final tick ---
    r = JsonlReader(log)
    snaps = list(r.iter_telemetry())
    assert snaps, "expected telemetry records"

    frames = list(r.iter_command_frames())
    assert frames, "expected command_frame records"
    assert len(frames) == len(snaps)

    last = snaps[-1]
    assert last.tick == final_tick_record

    last_cmd = frames[-1]
    assert last_cmd.tick == final_tick_record

    # Multi-axis invariants: each snapshot contains all configured axes
    for snap in snaps:
        for a in axis_ids:
            assert a in snap.axes

    for a in axis_ids:
        assert abs(last.axes[a].pos - final_pos_record[a]) < 1e-12

    # Deep debugging sanity: after ESTOP is set, command frames must clamp all setpoints.
    # We set estop once and then ran 10 more ticks.
    estop_start_tick = final_tick_record - 10 + 1
    for cf in frames:
        if cf.tick >= estop_start_tick:
            assert cf.estop is True
            for a in axis_ids:
                assert a in cf.axes
                assert cf.axes[a].enable is False
                assert abs(cf.axes[a].vel) == 0.0
