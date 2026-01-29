from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

import tomllib


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
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    rig = cfg.get("rig", {}) or {}
    winches = rig.get("winches", [])
    axes = [str(x).strip() for x in winches if str(x).strip()]
    if not axes:
        raise ValueError(f"No [rig].winches found in {path}")
    return axes


def _popen(cmd: List[str], *, new_console: bool) -> subprocess.Popen:
    if _is_windows() and new_console:
        # CREATE_NEW_CONSOLE = 0x00000010
        return subprocess.Popen(cmd, creationflags=0x00000010)
    return subprocess.Popen(cmd)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="steuerung3d.apps.setup_stack",
        description="Launch the full setup stack: inputd + joy2intent + core_udp_service + DenSi fleet + HiP.",
    )
    ap.add_argument("--joy2intent", default="configs/joy2intent_gamepad.toml", help="Path to joy2intent TOML.")
    ap.add_argument("--inputd", default="configs/inputd_gamepad.toml", help="Path to inputd TOML.")

    ap.add_argument("--cmd-base", type=int, default=52001, help="Base UDP port for DenSi CommandIn.")
    ap.add_argument("--ui-telem-base", type=int, default=51002, help="Base UDP port for HiP TelemetryIn bind.")
    ap.add_argument(
        "--dev-telem-out",
        default="127.0.0.1:52002",
        help="TelemetryOut target for all DenSi instances (default 127.0.0.1:52002).",
    )
    ap.add_argument("--densi-dt", type=float, default=0.01, help="DenSi sim timestep (s).")
    ap.add_argument("--core-dt", type=float, default=0.02, help="Core tick (s).")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))

    ap.add_argument("--no-inputd", action="store_true", help="Do not launch inputd.")
    ap.add_argument("--no-joy2intent", action="store_true", help="Do not launch joy2intent.")
    ap.add_argument("--no-hip", action="store_true", help="Do not launch HiP window(s).")
    ap.add_argument(
        "--single-hip",
        action="store_true",
        help="Launch only one HiP window (default: one HiP per axis).",
    )
    ap.add_argument("--no-densi", action="store_true", help="Do not launch DenSi fleet.")
    ap.add_argument("--no-core", action="store_true", help="Do not launch core_udp_service.")

    ap.add_argument(
        "--new-console",
        action="store_true",
        default=_is_windows(),
        help="On Windows, launch components in new console windows (default: true on Windows).",
    )
    args = ap.parse_args()

    joy_cfg = Path(args.joy2intent)
    axes = _axes_from_joy2intent(joy_cfg)
    dev_telem_out = _parse_hostport(args.dev_telem_out)

    procs: List[subprocess.Popen] = []
    try:
        # --- core ---
        if not args.no_core:
            core_cmd = [
                sys.executable,
                "-m",
                "steuerung3d.apps.core_udp_service",
                "--dt",
                str(args.core_dt),
                "--log-level",
                args.log_level,
                "--dev-cmd-base",
                str(args.cmd_base),
                "--dev-cmd-count",
                str(len(axes)),
                "--ui-telem-base",
                str(args.ui_telem_base),
                "--ui-telem-count",
                str(len(axes) if (not args.single_hip and not args.no_hip) else 1),
            ]
            for a in axes:
                core_cmd.extend(["--axis", a])
            procs.append(_popen(core_cmd, new_console=args.new_console))
            time.sleep(0.25)

        # --- DenSi fleet (one per axis) ---
        if not args.no_densi:
            for i, axis_id in enumerate(axes):
                cmd_in_port = args.cmd_base + i
                densi_cmd = [
                    sys.executable,
                    "-m",
                    "steuerung3d.apps.den_si",
                    "--axis",
                    axis_id,
                    "--dt",
                    str(args.densi_dt),
                    "--cmd-in",
                    f"127.0.0.1:{cmd_in_port}",
                    "--telem-out",
                    f"{dev_telem_out[0]}:{dev_telem_out[1]}",
                    "--log-level",
                    args.log_level,
                ]
                procs.append(_popen(densi_cmd, new_console=args.new_console))
                time.sleep(0.12)

        # --- HiP UI ---
        if not args.no_hip:
            if args.single_hip:
                hip_cmd = [
                    sys.executable,
                    "-m",
                    "steuerung3d.apps.hi_p",
                    "--log-level",
                    args.log_level,
                    "--telem-in",
                    f"127.0.0.1:{args.ui_telem_base}",
                ]
                procs.append(_popen(hip_cmd, new_console=False))
                time.sleep(0.15)
            else:
                for i, axis_id in enumerate(axes):
                    telem_port = args.ui_telem_base + i
                    hip_cmd = [
                        sys.executable,
                        "-m",
                        "steuerung3d.apps.hi_p",
                        "--axis",
                        axis_id,
                        "--telem-in",
                        f"127.0.0.1:{telem_port}",
                        "--log-level",
                        args.log_level,
                    ]
                    procs.append(_popen(hip_cmd, new_console=False))
                    time.sleep(0.12)

        # --- inputd ---
        if not args.no_inputd:
            inputd_cmd = [
                sys.executable,
                "-m",
                "steuerung3d.apps.inputd",
                "--config",
                str(Path(args.inputd)),
                "--log-level",
                args.log_level,
            ]
            procs.append(_popen(inputd_cmd, new_console=args.new_console))
            time.sleep(0.15)

        # --- joy2intent ---
        if not args.no_joy2intent:
            joy2intent_cmd = [
                sys.executable,
                "-m",
                "steuerung3d.apps.joy2intent",
                "--config",
                str(joy_cfg),
                "--log-level",
                args.log_level,
            ]
            procs.append(_popen(joy2intent_cmd, new_console=args.new_console))
            time.sleep(0.15)

        print(
            "\n=== setup_stack running ===\n"
            f"axes={axes}\n"
            f"core_udp_service: intents in 51001, ui telem out 51002, dev cmd out {args.cmd_base}..{args.cmd_base + len(axes) - 1}, dev telem in 52002\n"
            f"DenSi telemetry out -> {dev_telem_out[0]}:{dev_telem_out[1]}\n"
            f"joy2intent config: {joy_cfg}\n"
            f"inputd config: {args.inputd}\n"
            "Ctrl+C to stop.\n",
            file=sys.stderr,
        )

        while True:
            # If any child exits, report it (useful during dev).
            for p in list(procs):
                rc = p.poll()
                if rc is not None:
                    procs.remove(p)
                    print(f"[setup_stack] child exited rc={rc}", file=sys.stderr)
            time.sleep(0.5)

        # unreachable
        # return 0
    except KeyboardInterrupt:
        return 0
    finally:
        for p in procs:
            try:
                p.terminate()
            except Exception:
                pass
        for p in procs:
            try:
                p.wait(timeout=1.5)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
