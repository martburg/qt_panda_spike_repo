from __future__ import annotations

import time
from pathlib import Path

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.transport import InMemTransport
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice


def main() -> int:
    raw = InMemTransport()
    rec = JsonlRecorder(Path("logs/session.jsonl"))
    transport = LoggedTransport(raw, rec)

    tb = Timebase(dt_s=0.01)  # 100 Hz
    st = MachineState()
    st.ensure_axis("X")

    plant = SimAxisPlant()
    device = SimDevice(plant)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_snapshot=transport.publish_telemetry,
        on_command_frame=rec.record_command_frame,
    )

    runner = CoreRunner(engine=eng, realtime=True)
    runner.start()

    # ---- Client behavior (v0.1): send some intents, print telemetry ----
    transport.publish_intent(ArmLiveMode())
    transport.publish_intent(EnableAxis(axis_id="X", enable=True))
    transport.publish_intent(JogAxis(axis_id="X", vel=0.6))

    t0 = time.time()
    last_print = 0

    try:
        while True:
            snaps = transport.drain_telemetry(limit=500)
            for snap in snaps:
                if snap.tick - last_print >= 50:  # every 0.5s at 100 Hz
                    last_print = snap.tick
                    x = snap.axes["X"]
                    print(
                        f"tick={snap.tick:5d} t={snap.t_s:6.2f}s mode={snap.mode} "
                        f"estop={snap.estop} X(en={x.enabled}, vel={x.vel:5.2f}, pos={x.pos:8.3f})"
                    )

            if 2.5 < (time.time() - t0) < 2.55:
                transport.publish_intent(SetEstop(estop=True))

            if (time.time() - t0) > 6.0:
                break

            time.sleep(0.01)

    finally:
        runner.stop()
        runner.join(timeout=1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
