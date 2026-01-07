from __future__ import annotations

import argparse
from pathlib import Path

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import ArmLiveMode, EnableAxis, JogAxis, SetEstop
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.transport import InMemTransport

from steuerung3d.config.core_service_config import load_core_service_config


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Steuerung3D core service (v0.1 demo)")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("configs/core_service.toml"),
        help="Path to TOML config (default: configs/core_service.toml)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    cfg = load_core_service_config(args.config)

    tb = Timebase(dt_s=float(cfg.app.dt_s))
    st = MachineState()
    for ax in cfg.core.axis_ids:
        st.ensure_axis(ax)

    transport = InMemTransport()

    # "Client side": send a couple intents
    if cfg.core.axis_ids:
        transport.publish_intent(EnableAxis(axis_id=cfg.core.axis_ids[0], enable=True))
        transport.publish_intent(JogAxis(axis_id=cfg.core.axis_ids[0], vel=0.5))

    def on_step(state: MachineState, dt: float) -> None:
        # v0.1 "plant": integrate vel directly for each configured axis
        for ax_id in cfg.core.axis_ids:
            ax = state.axes.get(ax_id)
            if ax is None:
                continue
            ax.pos += ax.vel * dt

        # demonstrate estop mid-run
        if state.tick == 250:
            transport.publish_intent(SetEstop(estop=True))
        if state.tick == 350:
            transport.publish_intent(SetEstop(estop=False))
            transport.publish_intent(ArmLiveMode())
            if cfg.core.axis_ids:
                transport.publish_intent(EnableAxis(axis_id=cfg.core.axis_ids[0], enable=True))
                transport.publish_intent(JogAxis(axis_id=cfg.core.axis_ids[0], vel=0.5))

    def on_snapshot(snap) -> None:
        transport.publish_telemetry(snap)

        # "Client side": print occasionally
        if snap.tick % 50 == 0 and cfg.core.axis_ids:
            ax0 = snap.axes[cfg.core.axis_ids[0]]
            print(
                f"tick={snap.tick:5d} t={snap.t_s:6.2f}s "
                f"estop={snap.estop} {cfg.core.axis_ids[0]}(en={ax0.enabled}, vel={ax0.vel:5.2f}, pos={ax0.pos:8.3f})"
            )

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        on_step=on_step,
        on_snapshot=on_snapshot,
    )

    # Use the runner so realtime behavior is configurable
    runner = CoreRunner(engine=eng, realtime=bool(cfg.app.realtime))
    runner.start()
    runner.join(timeout=float(cfg.core.ticks) * float(cfg.app.dt_s) + 2.0)
    runner.stop()
    runner.join(timeout=1.0)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
