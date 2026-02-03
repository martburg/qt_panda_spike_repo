from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import tomllib


@dataclass
class ChildProc:
    """A supervised child process with a stable human name and an associated log file."""

    name: str
    proc: subprocess.Popen
    log_path: Optional[Path] = None


def _tail_text(path: Path, max_lines: int = 40) -> str:
    """Return the last N lines of a text file, best-effort."""
    try:
        txt = path.read_text(encoding="utf-8", errors="replace")
        lines = txt.splitlines()
        tail = lines[-max_lines:]
        return "\n".join(tail)
    except Exception:
        return ""


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


def _popen(
    name: str,
    cmd: List[str],
    *,
    new_console: bool,
    log_dir: Optional[Path],
) -> ChildProc:
    """Start a child process with a stable name and a per-child log file."""

    log_path: Optional[Path] = None
    stdout_handle = None
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        # Use a stable file name; names are unique (we include axis_id).
        log_path = log_dir / f"{name}.log"
        stdout_handle = open(log_path, "a", encoding="utf-8", errors="replace")
        stdout_handle.write(f"\n--- spawn {name} @ {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        stdout_handle.flush()

    popen_kwargs = dict(
        stdout=stdout_handle,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    if _is_windows() and new_console:
        # CREATE_NEW_CONSOLE = 0x00000010
        proc = subprocess.Popen(cmd, creationflags=0x00000010, **popen_kwargs)
    else:
        proc = subprocess.Popen(cmd, **popen_kwargs)

    if stdout_handle is not None:
        stdout_handle.write(f"pid={proc.pid} cmd={' '.join(cmd)}\n")
        stdout_handle.flush()
    return ChildProc(name=name, proc=proc, log_path=log_path)


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
        "--dev-telem-in",
        default=None,
        help=(
            "Core Device TelemetryIn bind host:port. DenSi instances will send telemetry to this address. "
            "If omitted, defaults to 127.0.0.1:52002 unless that overlaps the DenSi cmd port range, in which case "
            "it will auto-shift to cmd_base+100."
        ),
    )
    # Backward-compat alias (older wrapper called it --dev-telem-out)
    ap.add_argument(
        "--dev-telem-out",
        default=None,
        help=argparse.SUPPRESS,
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
    dev_telem_s = args.dev_telem_in or args.dev_telem_out or "127.0.0.1:52002"
    dev_telem_bind = _parse_hostport(dev_telem_s)

    # Avoid overlap: cmd ports are cmd_base..cmd_base+len(axes)-1
    cmd_lo = int(args.cmd_base)
    cmd_hi = cmd_lo + len(axes) - 1
    if args.dev_telem_in is None and args.dev_telem_out is None:
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(cmd_lo, cmd_hi + 1):
            dev_telem_bind = ("127.0.0.1", cmd_lo + 100)

    # Per-child logs help a lot when a subprocess exits early (rc!=0)
    log_dir = Path(".run") / "setup_stack"
    log_dir.mkdir(parents=True, exist_ok=True)

    procs: List[ChildProc] = []
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
                "--dev-telem-in",
                f"{dev_telem_bind[0]}:{dev_telem_bind[1]}",
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
            procs.append(_popen("core", core_cmd, new_console=args.new_console, log_dir=log_dir))
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
                f"{dev_telem_bind[0]}:{dev_telem_bind[1]}",
                    "--log-level",
                    args.log_level,
                ]
                procs.append(_popen(f"densi-{axis_id}", densi_cmd, new_console=args.new_console, log_dir=log_dir))
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
                procs.append(_popen(f"hip-{axes[0]}", hip_cmd, new_console=False, log_dir=log_dir))
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
                    procs.append(_popen(f"hip-{axis_id}", hip_cmd, new_console=False, log_dir=log_dir))
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
            procs.append(_popen("inputd", inputd_cmd, new_console=args.new_console, log_dir=log_dir))
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
            procs.append(_popen("joy2intent", joy2intent_cmd, new_console=args.new_console, log_dir=log_dir))
            time.sleep(0.15)

        print(
            "\n=== setup_stack running ===\n"
            f"axes={axes}\n"
            f"core_udp_service: intents in 51001, ui telem out {args.ui_telem_base}.., dev cmd out {args.cmd_base}..{args.cmd_base + len(axes) - 1}, dev telem in {dev_telem_bind[0]}:{dev_telem_bind[1]}\n"
            f"DenSi telemetry out -> {dev_telem_bind[0]}:{dev_telem_bind[1]}\n"
            f"joy2intent config: {joy_cfg}\n"
            f"inputd config: {args.inputd}\n"
            "Ctrl+C to stop.\n",
            file=sys.stderr,
        )

        while True:
            # If any child exits, report it (useful during dev).
            for child in list(procs):
                rc = child.proc.poll()
                if rc is not None:
                    procs.remove(child)
                    msg = f"[setup_stack] child exited name={child.name} pid={child.proc.pid} rc={rc}"
                    if child.log_path:
                        msg += f" log={child.log_path}"
                    print(msg, file=sys.stderr)
                    # Print a short tail to make early-exit debugging fast.
                    if child.log_path:
                        tail = _tail_text(child.log_path, max_lines=40)
                        if tail.strip():
                            print("[setup_stack] --- last log lines ---", file=sys.stderr)
                            print(tail, file=sys.stderr)
                            print("[setup_stack] --- end ---", file=sys.stderr)
            time.sleep(0.5)

        # unreachable
        # return 0
    except KeyboardInterrupt:
        return 0
    finally:
        for child in procs:
            try:
                child.proc.terminate()
            except Exception:
                pass
        for child in procs:
            try:
                child.proc.wait(timeout=1.5)
            except Exception:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
