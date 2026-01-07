from __future__ import annotations

import sys
import time

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    JogAxis,
    SetEstop,
)
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.transport import InMemTransport


HELP = """commands:
  help
  live                 -> ArmLiveMode
  idle                 -> DisarmToIdle
  estop on|off         -> SetEstop(True/False)
  clearfault           -> ClearFault
  enable <AXIS> on|off -> EnableAxis
  jog <AXIS> <VEL>     -> JogAxis (requires enable + LIVE)
  show                 -> print one latest telemetry (if available)
  quit
"""


def parse_and_send(cmd: str, tr: InMemTransport) -> bool:
    parts = cmd.strip().split()
    if not parts:
        return True

    c = parts[0].lower()

    try:
        if c in ("quit", "exit"):
            return False
        if c == "help":
            print(HELP)
            return True
        if c == "live":
            tr.publish_intent(ArmLiveMode())
            return True
        if c == "idle":
            tr.publish_intent(DisarmToIdle())
            return True
        if c == "clearfault":
            tr.publish_intent(ClearFault())
            return True
        if c == "estop" and len(parts) == 2:
            tr.publish_intent(SetEstop(estop=(parts[1].lower() == "on")))
            return True
        if c == "enable" and len(parts) == 3:
            axis = parts[1]
            on = parts[2].lower() == "on"
            tr.publish_intent(EnableAxis(axis_id=axis, enable=on))
            return True
        if c == "jog" and len(parts) == 3:
            axis = parts[1]
            vel = float(parts[2])
            tr.publish_intent(JogAxis(axis_id=axis, vel=vel))
            return True
        if c == "show":
            return True

        print("Unknown/invalid command. Type 'help'.")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return True


def main() -> int:
    tr = InMemTransport()

    tb = Timebase(dt_s=0.01)
    st = MachineState()
    st.ensure_axis("X")
    st.ensure_axis_cmd("X")

    device = SimDevice(SimAxisPlant())

    latest = None

    def on_snapshot(snap):
        nonlocal latest
        latest = snap
        tr.publish_telemetry(snap)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=tr.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_snapshot=on_snapshot,
    )

    runner = CoreRunner(engine=eng, realtime=True)
    runner.start()

    print("CLI client started.")
    print(HELP)

    last_print_tick = 0

    try:
        while True:
            # periodic telemetry print
            if latest is not None and latest.tick - last_print_tick >= 100:  # every 1s
                last_print_tick = latest.tick
                x = latest.axes.get("X")
                if x:
                    print(
                        f"[tele] tick={latest.tick} t={latest.t_s:.2f}s mode={latest.mode} "
                        f"estop={latest.estop} X(en={x.enabled}, vel={x.vel:.3f}, pos={x.pos:.3f})"
                    )
                else:
                    print(f"[tele] tick={latest.tick} t={latest.t_s:.2f}s mode={latest.mode} estop={latest.estop}")

            # prompt
            sys.stdout.write("> ")
            sys.stdout.flush()
            line = sys.stdin.readline()
            if not line:
                break

            if line.strip().lower() == "show":
                if latest is None:
                    print("(no telemetry yet)")
                else:
                    x = latest.axes.get("X")
                    print(latest)
                continue

            cont = parse_and_send(line, tr)
            if not cont:
                break

            time.sleep(0.01)

    finally:
        runner.stop()
        runner.join(timeout=1.0)

    print("bye.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
