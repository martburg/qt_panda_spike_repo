"""Legacy stack launcher (compat wrapper).

`setup_stack` predates the profile-driven boot CLI. Users still rely on its
convenient flags and default behavior, so we keep the command as a thin
compatibility layer.

Implementation rule:
  - No supervision logic lives here.
  - We translate legacy flags into a :class:`~steuerung3d.core.stack_spec.StackSpec`
    and run it with :class:`~steuerung3d.core.stack_runtime.StackRuntime`.

This keeps *one* boot/supervisor implementation going forward.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Tuple

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None  # type: ignore

from steuerung3d.core.stack_runtime import StackRuntime
from steuerung3d.core.stack_spec import ServiceSpec, StackSpec


def _is_windows() -> bool:
    return os.name == "nt"


def _parse_hostport(s: str, default_host: str = "127.0.0.1") -> Tuple[str, int]:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty host:port")
    if s.count(":") == 0:
        return (default_host, int(s))
    host, port_s = s.rsplit(":", 1)
    host = host.strip() or default_host
    return (host, int(port_s))


def _axes_from_joy2intent(path: Path) -> List[str]:
    """Legacy convenience: read [rig].winches from an old joy2intent config.

    New boot profiles own axes; joy2intent binding configs should not.
    We keep this helper so old configs keep working.
    """
    if tomllib is None:  # pragma: no cover
        raise RuntimeError("tomllib not available (requires Python 3.11+)")
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    rig = cfg.get("rig", {}) or {}
    winches = rig.get("winches", [])
    axes = [str(x).strip() for x in winches if str(x).strip()]
    if not axes:
        raise ValueError(f"No [rig].winches found in {path} (use --axes or a stack profile)")
    return axes


def _parse_axes_arg(s: str) -> List[str]:
    axes = [a.strip() for a in (s or "").split(",") if a.strip()]
    if not axes:
        raise ValueError("--axes must be a non-empty comma-separated list")
    return axes


def build_stack_spec_from_args(args: argparse.Namespace) -> StackSpec:
    """Build a StackSpec matching historical setup_stack behavior."""
    # Determine axes.
    axes: List[str]
    if args.axes:
        axes = _parse_axes_arg(args.axes)
    else:
        axes = _axes_from_joy2intent(Path(args.joy2intent))

    # Determine core device telemetry bind with the old "avoid cmd port overlap" rule.
    dev_telem_s = args.dev_telem_in or args.dev_telem_out or "127.0.0.1:52002"
    dev_telem_bind = _parse_hostport(dev_telem_s)

    cmd_lo = int(args.cmd_base)
    cmd_hi = cmd_lo + len(axes) - 1
    if args.dev_telem_in is None and args.dev_telem_out is None:
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(cmd_lo, cmd_hi + 1):
            dev_telem_bind = ("127.0.0.1", cmd_lo + 100)

    hip_count = 0 if args.no_hip else (1 if args.single_hip else len(axes))

    net = {
        "bind_host": "127.0.0.1",
        "cmd_base": int(args.cmd_base),
        "ui_telem_base": int(args.ui_telem_base),
        "dev_telem_in": f"{dev_telem_bind[0]}:{dev_telem_bind[1]}",
    }

    services: dict[str, ServiceSpec] = {}

    # --- core ---
    services["core"] = ServiceSpec(
        enabled=not args.no_core,
        module="steuerung3d.apps.core_udp_service",
        mode="single",
        args=[
            "--dt",
            str(args.core_dt),
            "--log-level",
            args.log_level,
            "--dev-telem-in",
            net["dev_telem_in"],
            "--dev-cmd-base",
            str(net["cmd_base"]),
            "--dev-cmd-count",
            str(len(axes)),
            "--ui-telem-base",
            str(net["ui_telem_base"]),
            "--ui-telem-count",
            str(hip_count if hip_count > 0 else 1),
            # axes are repeatable flags
            *sum((["--axis", a] for a in axes), start=[]),
        ],
    )

    # --- DenSi fleet ---
    services["densi"] = ServiceSpec(
        enabled=not args.no_densi,
        module="steuerung3d.apps.den_si",
        mode="per_axis",
        args=[
            "--axis",
            "{axis}",
            "--dt",
            str(args.densi_dt),
            "--cmd-in",
            "{net.bind_host}:{net.cmd_base+axis_index}",
            "--telem-out",
            "{net.dev_telem_in}",
            "--log-level",
            args.log_level,
        ],
    )

    # --- HiP UI ---
    services["hip"] = ServiceSpec(
        enabled=not args.no_hip,
        module="steuerung3d.apps.hi_p",
        mode="single" if args.single_hip else "per_axis",
        args=[
            "--log-level",
            args.log_level,
            "--telem-in",
            "{net.bind_host}:{net.ui_telem_base}" if args.single_hip else "{net.bind_host}:{net.ui_telem_base+axis_index}",
        ],
    )

    # --- inputd ---
    services["inputd"] = ServiceSpec(
        enabled=not args.no_inputd,
        module="steuerung3d.apps.inputd",
        mode="single",
        args=["--log-level", args.log_level],
        config=args.inputd,
    )

    # --- joy2intent ---
    # We intentionally keep wiring defaults inside joy2intent for now.
    # Boot profiles can override with --raw-in/--intent-out/--winches.
    services["joy2intent"] = ServiceSpec(
        enabled=not args.no_joy2intent,
        module="steuerung3d.apps.joy2intent",
        mode="single",
        args=["--log-level", args.log_level],
        config=args.joy2intent,
    )

    return StackSpec(
        name="setup_stack",
        base_dir=Path.cwd(),
        axes=axes,
        net=net,
        services=services,
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="steuerung3d.apps.setup_stack",
        description="Legacy launcher: inputd + joy2intent + core_udp_service + DenSi fleet + HiP.",
    )
    ap.add_argument(
        "--joy2intent",
        default="configs/joy2intent_bindings_gamepad.toml",
        help="Path to joy2intent TOML (bindings). Legacy configs may include [rig].winches.",
    )
    ap.add_argument("--inputd", default="configs/inputd_gamepad.toml", help="Path to inputd TOML.")
    ap.add_argument(
        "--axes",
        default=None,
        help="Comma-separated axes (overrides legacy [rig].winches in joy2intent).",
    )

    ap.add_argument("--cmd-base", type=int, default=52001, help="Base UDP port for DenSi CommandIn.")
    ap.add_argument("--ui-telem-base", type=int, default=51002, help="Base UDP port for HiP TelemetryIn bind.")
    ap.add_argument(
        "--dev-telem-in",
        default=None,
        help=(
            "Core Device TelemetryIn bind host:port. DenSi instances will send telemetry to this address. "
            "If omitted, defaults to 127.0.0.1:52002 unless that overlaps the DenSi cmd port range, in which case "
            "it auto-shifts to cmd_base+100."
        ),
    )
    ap.add_argument("--dev-telem-out", default=None, help=argparse.SUPPRESS)
    ap.add_argument("--densi-dt", type=float, default=0.01, help="DenSi sim timestep (s).")
    ap.add_argument("--core-dt", type=float, default=0.02, help="Core tick (s).")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))

    ap.add_argument("--no-inputd", action="store_true", help="Do not launch inputd.")
    ap.add_argument("--no-joy2intent", action="store_true", help="Do not launch joy2intent.")
    ap.add_argument("--no-hip", action="store_true", help="Do not launch HiP window(s).")
    ap.add_argument("--single-hip", action="store_true", help="Launch only one HiP window.")
    ap.add_argument("--no-densi", action="store_true", help="Do not launch DenSi fleet.")
    ap.add_argument("--no-core", action="store_true", help="Do not launch core_udp_service.")

    ap.add_argument(
        "--new-console",
        action="store_true",
        default=_is_windows(),
        help="On Windows, launch components in new console windows (default: true on Windows).",
    )
    ap.add_argument(
        "--keep-sessions",
        type=int,
        default=5,
        help="Keep the last N log sessions under .run/setup_stack/sessions (default: 5).",
    )

    args = ap.parse_args()
    spec = build_stack_spec_from_args(args)

    rt = StackRuntime(
        spec,
        run_base=Path(".run"),
        keep_last_sessions=max(1, int(args.keep_sessions)),
        new_console=bool(args.new_console),
    )
    rt.start()
    return rt.run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
