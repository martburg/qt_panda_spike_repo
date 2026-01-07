from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

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

from steuerung3d.config.cli_client_config import load_cli_client_config


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


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Steuerung3D CLI client (SIM stack for v0.1)")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("configs/cli_client.toml"),
        help="Path to TOML config (default: configs/cli_client.toml)",
    )
    return p.parse_args()


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
    args = _parse_args()
    cfg = load_cli_client_config(args.config)

    tr = InMemTransport()

    tb = Timebase(dt_s=float(cfg.app.dt_s))
    st = MachineState()
    for ax in cfg.client.axis_ids:
        st.ensure_axis(ax)
        st.ensure_axis_cmd(ax)

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

    runner = CoreRunner(engine=eng, realtime=bool(cfg.app.realtime))
    runner.start()

    print("CLI client started.")
    print(HELP)

    last_print_tick = 0

    try:
        while True:
            # periodic telemetry print (first axis)
            if latest is not None and latest.tick - last_print_tick >= 100:
                last_print_tick = latest.tick
                ax0 = cfg.client.axis_ids[0] if cfg.client.axis_ids else None
                if ax0 and ax0 in latest.axes:
                    x = latest.axes[ax0]
                    print(
                        f"[tele] tick={latest.tick} t={latest.t_s:.2f}s mode={latest.mode} "
                        f"estop={latest.estop} {ax0}(en={x.enabled}, vel={x.vel:.3f}, pos={x.pos:.3f})"
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
