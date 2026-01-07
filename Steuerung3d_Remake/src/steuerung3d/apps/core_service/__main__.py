from __future__ import annotations

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.transport import InMemTransport


def main() -> int:
    tb = Timebase(dt_s=0.01)  # 100 Hz
    st = MachineState()
    st.ensure_axis("X")
    st.ensure_axis("Y")

    transport = InMemTransport()

    # "Client side": send a couple intents
    transport.publish_intent(EnableAxis(axis_id="X", enable=True))
    transport.publish_intent(JogAxis(axis_id="X", vel=0.5))

    def on_step(state: MachineState, dt: float) -> None:
        # v0.1 "plant": integrate vel directly
        ax = state.axes["X"]
        ax.pos += ax.vel * dt

        # demonstrate estop mid-run
        if state.tick == 250:
            transport.publish_intent(SetEstop(estop=True))
        if state.tick == 350:
            transport.publish_intent(SetEstop(estop=False))
            transport.publish_intent(ArmLiveMode())
            transport.publish_intent(EnableAxis(axis_id="X", enable=True))
            transport.publish_intent(JogAxis(axis_id="X", vel=0.5))

    def on_snapshot(snap) -> None:
        transport.publish_telemetry(snap)

        # "Client side": print occasionally
        if snap.tick % 50 == 0:
            x = snap.axes["X"]
            print(
                f"tick={snap.tick:5d} t={snap.t_s:6.2f}s "
                f"estop={snap.estop} X(en={x.enabled}, vel={x.vel:5.2f}, pos={x.pos:8.3f})"
            )

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        on_step=on_step,
        on_snapshot=on_snapshot,
    )

    eng.run_for_ticks(500)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
