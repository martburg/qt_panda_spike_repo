from __future__ import annotations

import argparse
import time
from pathlib import Path

from steuerung3d.config.plc_stack_config import load_plc_stack_config
from steuerung3d.core.intents import EnableAxis, JogAxis, SetEstop
from steuerung3d.protocol.core_runner import CoreRunner

from .builder import build_core, build_plc_device, collect_axes


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Steuerung3D PLC stack (UDP edge adapter)")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("configs/plc_stack.toml"),
        help="Path to TOML config (default: configs/plc_stack.toml)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    cfg = load_plc_stack_config(args.config)

    # --- PLC edge adapter (UDP) ---
    device, endpoints = build_plc_device(cfg)

    # --- Core (real app builder path) ---
    rt = build_core(cfg, device_step=device.step, enable_logging=True)
    tr = rt.transport
    eng = rt.engine
    axes = collect_axes(cfg)

    runner = CoreRunner(engine=eng, realtime=bool(cfg.app.realtime))
    runner.start()

    # --- demo behavior (safe defaults; adjust for your rig) ---
    for a in axes:
        tr.publish_intent(EnableAxis(axis_id=a, enable=True))

    if axes:
        tr.publish_intent(JogAxis(axis_id=axes[0], vel=0.6))

    t0 = time.time()
    last_print = 0

    try:
        while True:
            snaps = tr.drain_telemetry(limit=500)
            for snap in snaps:
                if snap.tick - last_print >= 50:
                    last_print = snap.tick
                    ax0 = snap.axes[axes[0]] if axes else None
                    print(
                        f"tick={snap.tick:5d} t={snap.t_s:6.2f}s core_mode={snap.core_mode} "
                        f"estop={snap.estop} fault={snap.fault} "
                        f"rx_ticks={device.last_rx_tick_by_endpoint} "
                        + (
                            f"{axes[0]}(en={ax0.enabled}, vel={ax0.vel:5.2f}, pos={ax0.pos:8.3f})"
                            if ax0
                            else ""
                        )
                    )

            if 2.5 < (time.time() - t0) < 2.55:
                tr.publish_intent(SetEstop(estop=True))

            if (time.time() - t0) > 6.0:
                break

            time.sleep(0.01)

    finally:
        runner.stop()
        runner.join(timeout=1.0)
        for ep in endpoints:
            ep.link.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
