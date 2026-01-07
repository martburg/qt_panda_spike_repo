from __future__ import annotations

import argparse
import time
from pathlib import Path

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.recording import JsonlRecorder, LoggedTransport
from steuerung3d.protocol.transport import InMemTransport

from steuerung3d.config.dev_stack_config import load_dev_stack_config


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Steuerung3D dev stack (SIM device + in-mem transport)")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("configs/dev_stack.toml"),
        help="Path to TOML config (default: configs/dev_stack.toml)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    cfg = load_dev_stack_config(args.config)

    raw = InMemTransport()
    rec = JsonlRecorder(Path(cfg.app.log_path))
    transport = LoggedTransport(raw, rec)

    tb = Timebase(dt_s=float(cfg.app.dt_s))
    st = MachineState()
    for ax in cfg.sim.axis_ids:
        st.ensure_axis(ax)

    device = SimDevice(SimAxisPlant())

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_snapshot=transport.publish_telemetry,
        on_command_frame=rec.record_command_frame,
    )

    runner = CoreRunner(engine=eng, realtime=bool(cfg.app.realtime))
    runner.start()

    # ---- Client behavior (v0.1): send some intents, print telemetry ----
    transport.publish_intent(ArmLiveMode())
    for ax in cfg.sim.axis_ids:
        transport.publish_intent(EnableAxis(axis_id=ax, enable=True))

    if cfg.sim.axis_ids:
        transport.publish_intent(JogAxis(axis_id=cfg.sim.axis_ids[0], vel=0.6))

    t0 = time.time()
    last_print = 0

    try:
        while True:
            snaps = transport.drain_telemetry(limit=500)
            for snap in snaps:
                if snap.tick - last_print >= 50:
                    last_print = snap.tick
                    # Print first configured axis (keeps output compact)
                    ax0 = snap.axes.get(cfg.sim.axis_ids[0]) if cfg.sim.axis_ids else None
                    extra = ""
                    if ax0 is not None and cfg.sim.axis_ids:
                        extra = f" {cfg.sim.axis_ids[0]}(en={ax0.enabled}, vel={ax0.vel:5.2f}, pos={ax0.pos:8.3f})"
                    print(
                        f"tick={snap.tick:5d} t={snap.t_s:6.2f}s mode={snap.mode} "
                        f"estop={snap.estop}" + extra
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
