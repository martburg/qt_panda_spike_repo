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
    sel = cfg.get("selection", {})
    winch_ids = sel.get("winch_ids", [])
    axes = [str(x).strip() for x in winch_ids if str(x).strip()]
    if not axes:
        raise ValueError(f"No selection.winch_ids found in {path}")
    return axes


def _popen(cmd: List[str], *, new_console: bool) -> subprocess.Popen:
    if _is_windows() and new_console:
        # CREATE_NEW_CONSOLE = 0x00000010
        return subprocess.Popen(cmd, creationflags=0x00000010)
    return subprocess.Popen(cmd)


def main() -> int:
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
    ap.add_argument("--cmd-base", type=int, default=52001, help="Base UDP port for DenSi CommandIn.")
    ap.add_argument(
        "--telem-out",
        default="127.0.0.1:52002",
        help="TelemetryOut target for all DenSi instances (default 127.0.0.1:52002).",
    )
    ap.add_argument(
        "--dt",
        type=float,
        default=0.01,
        help="DenSi sim timestep (seconds).",
    )
    ap.add_argument(
        "--new-console",
        action="store_true",
        default=_is_windows(),
        help="On Windows, open each DenSi in a new console window (default: true on Windows).",
    )
    ap.add_argument(
        "--also-core",
        action="store_true",
        help="Also launch core_udp_service configured to broadcast commands to the DenSi fleet.",
    )
    ap.add_argument(
        "--core-dt",
        type=float,
        default=0.02,
        help="Core tick (seconds) when using --also-core.",
    )
    ap.add_argument(
        "--log-level",
        default="info",
        choices=("debug", "info", "warning", "error"),
        help="Log level for launched processes (core + DenSi).",
    )
    args = ap.parse_args()

    axes: List[str] = []
    if args.from_joy2intent:
        axes = _axes_from_joy2intent(Path(args.from_joy2intent))
    else:
        axes = [a.strip() for a in args.axis if a and a.strip()]

    if not axes:
        axes = ["X"]

    telem_out = _parse_hostport(args.telem_out)

    procs: List[subprocess.Popen] = []
    try:
        # Optionally start core first so DenSi connects cleanly.
        if args.also_core:
            core_cmd = [
                sys.executable,
                "-m",
                "steuerung3d.apps.core_udp_service",
                "--dt",
                str(args.core_dt),
                "--log-level",
                args.log_level,
                "--dev-telem-in",
                f"{telem_out[0]}:{telem_out[1]}",
                "--dev-cmd-base",
                str(args.cmd_base),
                "--dev-cmd-count",
                str(len(axes)),
            ]
            for a in axes:
                core_cmd.extend(["--axis", a])

            procs.append(_popen(core_cmd, new_console=args.new_console))
            time.sleep(0.2)

        # Launch one DenSi per axis, each binding a unique command port.
        for i, axis_id in enumerate(axes):
            cmd_in_port = args.cmd_base + i
            densi_cmd = [
                sys.executable,
                "-m",
                "steuerung3d.apps.den_si",
                "--axis",
                axis_id,
                "--dt",
                str(args.dt),
                "--cmd-in",
                f"127.0.0.1:{cmd_in_port}",
                "--telem-out",
                f"{telem_out[0]}:{telem_out[1]}",
                "--log-level",
                args.log_level,
            ]
            procs.append(_popen(densi_cmd, new_console=args.new_console))
            time.sleep(0.1)

        # Keep the launcher alive until Ctrl+C, so child processes die with the parent in most shells.
        print(
            f"DenSi fleet running for axes={axes}. Command ports {args.cmd_base}..{args.cmd_base+len(axes)-1}.\n"
            f"TelemetryOut -> {telem_out[0]}:{telem_out[1]}\n"
            f"Ctrl+C to stop.",
            file=sys.stderr,
        )
        while True:
            # If any child exits, report and keep going (useful during dev).
            for p in list(procs):
                rc = p.poll()
                if rc is not None:
                    procs.remove(p)
                    print(f"[densi_fleet] child exited rc={rc}", file=sys.stderr)
            time.sleep(0.5)

    except KeyboardInterrupt:
        return 0
    finally:
        # Best-effort terminate children.
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
