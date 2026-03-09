from __future__ import annotations

import argparse
import sys
import time

from .launcher_support import (
    is_windows,
    launch_children,
    parse_telem_out,
    reap_children,
    resolve_axes,
    startup_message,
    terminate_children,
)


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="steuerung3d.apps.densi_fleet",
        description="Launch multiple DenSi windows (one per axis) with unique command ports.",
    )
    ap.add_argument(
        "--axis",
        action="append",
        default=[],
        help="Axis id to launch (repeatable). Example: --axis Anton --axis Debby",
    )
    ap.add_argument(
        "--from-joy2intent",
        default=None,
        help="Read axes from selection.winch_ids in a joy2intent TOML.",
    )
    ap.add_argument(
        "--cmd-base", type=int, default=52001, help="Base UDP port for DenSi CommandIn."
    )
    ap.add_argument(
        "--telem-out",
        default="127.0.0.1:52002",
        help="TelemetryOut target for all DenSi instances (default 127.0.0.1:52002).",
    )
    ap.add_argument("--dt", type=float, default=0.01, help="DenSi sim timestep (seconds).")
    ap.add_argument(
        "--new-console",
        action="store_true",
        default=is_windows(),
        help="On Windows, open each DenSi in a new console window (default: true on Windows).",
    )
    ap.add_argument(
        "--also-core",
        action="store_true",
        help="Also launch core_udp_service configured to route per-axis commands to the DenSi fleet (no broadcast).",
    )
    ap.add_argument(
        "--ui-telem-base",
        type=int,
        default=51002,
        help="When using --also-core, base UDP port for UI telemetry targets (one per axis).",
    )
    ap.add_argument(
        "--core-dt", type=float, default=0.02, help="Core tick (seconds) when using --also-core."
    )
    ap.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
        help="Log level for launched processes (core + DenSi).",
    )
    return ap


def main() -> int:
    args = build_arg_parser().parse_args()
    axes = resolve_axes(axis_args=args.axis, from_joy2intent=args.from_joy2intent)
    telem_out = parse_telem_out(args.telem_out)

    children = []
    try:
        children = launch_children(
            axes=axes,
            telem_out=telem_out,
            cmd_base=args.cmd_base,
            dt=args.dt,
            log_level=args.log_level,
            new_console=args.new_console,
            also_core=args.also_core,
            ui_telem_base=args.ui_telem_base,
            core_dt=args.core_dt,
        )
        print(
            startup_message(axes=axes, telem_out=telem_out, cmd_base=args.cmd_base), file=sys.stderr
        )
        while True:
            for msg in reap_children(children):
                print(msg, file=sys.stderr)
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0
    finally:
        terminate_children(children)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
