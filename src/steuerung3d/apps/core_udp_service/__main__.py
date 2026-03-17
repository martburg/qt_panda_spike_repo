from __future__ import annotations

import argparse
import logging

from steuerung3d.core.status import StatusEmitter
from steuerung3d.util.app_bootstrap import bootstrap_logging

from .runtime_loop import run_core_udp_service

log = logging.getLogger("core_udp_service")


def _add_core_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    ap.add_argument("--dt", type=float, default=0.02, help="Core tick (s)")
    ap.add_argument(
        "--intent-in",
        default="127.0.0.1:51001",
        help="Operator IntentIn bind host:port (default 127.0.0.1:51001).",
    )
    ap.add_argument(
        "--control-context-target",
        default="127.0.0.1:51010",
        help="ControlContext UDP target host:port for colocated joy2intent (default 127.0.0.1:51010).",
    )
    ap.add_argument(
        "--axis",
        action="append",
        # Important: for action='append', argparse will *append to the default*.
        # Using a non-empty default would silently inject an extra axis (e.g. 'X')
        # and break strict per-axis routing.
        default=[],
        help="Axis ids to initialize in core state (repeatable). Example: --axis Anton --axis Debby",
    )


def _add_dev_cmd_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--dev-cmd-target",
        action="append",
        default=[],
        help=(
            "Device CommandOut target(s) as host:port. Repeatable. "
            "If not provided, defaults to 127.0.0.1:52001. "
            "One target per axis (no broadcast)."
        ),
    )
    ap.add_argument(
        "--dev-cmd-host",
        default="127.0.0.1",
        help="Host used with --dev-cmd-base/--dev-cmd-count (default 127.0.0.1).",
    )
    ap.add_argument(
        "--dev-cmd-base",
        default=None,
        help=(
            "Convenience: base port for Device CommandOut targets (e.g. 52001). "
            "Use with --dev-cmd-count and --dev-cmd-host for distributed setups."
        ),
    )
    ap.add_argument(
        "--dev-cmd-count",
        type=int,
        default=0,
        help=(
            "Convenience: number of Device CommandOut targets to generate from base port. "
            "For distributed setups use --dev-cmd-host or explicit --dev-cmd-target host:port."
        ),
    )


def _add_dev_telem_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--dev-telem-in",
        default="127.0.0.1:52002",
        help=(
            "Device TelemetryIn bind host:port (default 127.0.0.1:52002). "
            "Tip: choose a port that does not overlap your --dev-cmd-base..range."
        ),
    )


def _add_ui_telem_args(ap: argparse.ArgumentParser) -> None:
    # UI telemetry targets
    ap.add_argument(
        "--ui-telem-target",
        action="append",
        default=[],
        help=(
            "UI TelemetryOut target(s) as host:port. Repeatable. "
            "If not provided, defaults to 127.0.0.1:51002. "
            "In per_axis mode there must be one target per axis; in fanout mode snapshots are sent to every target."
        ),
    )
    ap.add_argument(
        "--ui-telem-host",
        default="127.0.0.1",
        help="Host used with --ui-telem-base/--ui-telem-count (default 127.0.0.1).",
    )
    ap.add_argument(
        "--ui-telem-base",
        default=None,
        help="Convenience: base port for UI TelemetryOut broadcast (e.g. 51002).",
    )
    ap.add_argument(
        "--ui-telem-count",
        type=int,
        default=0,
        help="Convenience: number of UI TelemetryOut targets to generate from base port.",
    )
    ap.add_argument(
        "--ui-telem-disable",
        action="store_true",
        help="Disable UI TelemetryOut (C1) entirely.",
    )
    ap.add_argument(
        "--ui-telem-mode",
        default="per_axis",
        choices=("per_axis", "fanout"),
        help="UI telemetry routing mode: per_axis (legacy) or fanout (full snapshots to every HiP).",
    )


def _add_c2_telem_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument(
        "--c2-telem-target",
        action="append",
        default=[],
        help=(
            "C2 Rig TelemetryOut target(s) as host:port. Repeatable. "
            "If omitted, no C2 telemetry is emitted."
        ),
    )
    ap.add_argument(
        "--c2-telem-host",
        default="127.0.0.1",
        help="Host used with --c2-telem-base/--c2-telem-count (default 127.0.0.1).",
    )
    ap.add_argument(
        "--c2-telem-base",
        default=None,
        help="Convenience: base port for C2 telemetry targets (e.g. 51100).",
    )
    ap.add_argument(
        "--c2-telem-count",
        type=int,
        default=0,
        help="Convenience: number of C2 telemetry targets to generate from base port.",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    _add_core_args(ap)
    _add_dev_cmd_args(ap)
    _add_dev_telem_args(ap)
    _add_ui_telem_args(ap)
    _add_c2_telem_args(ap)
    return ap


def main() -> int:
    ap = build_arg_parser()
    args = ap.parse_args()

    bootstrap_logging(role="core", log_level=args.log_level)
    log.info("log level = %s", str(args.log_level).upper())

    # Optional structured heartbeat (supervisor birds-eye). Controlled by env:
    #   ST3D_STATUS_OUT, ST3D_STACK_NAME, ST3D_SERVICE_NAME, ST3D_INSTANCE
    status = StatusEmitter.from_env(default_service="core")

    return run_core_udp_service(args=args, status=status)


if __name__ == "__main__":
    raise SystemExit(main())
