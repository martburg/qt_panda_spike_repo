from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from steuerung3d.core.net import parse_hostport


def is_windows() -> bool:
    return os.name == "nt"


def axes_from_joy2intent(path: Path) -> list[str]:
    cfg = tomllib.loads(path.read_text(encoding="utf-8"))
    sel = cfg.get("selection", {})
    winch_ids = sel.get("winch_ids", [])
    axes = [str(x).strip() for x in winch_ids if str(x).strip()]
    if not axes:
        raise ValueError(f"No selection.winch_ids found in {path}")
    return axes


def sanitize_axis_id(s: str) -> str:
    s = (s or "").strip()
    if "," in s:
        s = s.split(",")[-1].strip()
    return s


def popen(cmd: list[str], *, new_console: bool) -> subprocess.Popen[Any]:
    if is_windows() and new_console:
        return subprocess.Popen(cmd, creationflags=0x00000010)
    return subprocess.Popen(cmd)


@dataclass
class Child:
    kind: str
    axis: str
    cmd: list[str]
    p: subprocess.Popen[Any]


def fmt_cmd(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)


def resolve_axes(*, axis_args: Sequence[str], from_joy2intent: str | None) -> list[str]:
    if from_joy2intent:
        axes = axes_from_joy2intent(Path(from_joy2intent))
    else:
        axes = [a.strip() for a in axis_args if a and a.strip()]
    axes = [sanitize_axis_id(a) for a in axes if sanitize_axis_id(a)]
    return axes or ["X"]


def parse_telem_out(value: str) -> tuple[str, int]:
    return parse_hostport(value)


def build_core_cmd(
    *,
    axes: Sequence[str],
    telem_out: tuple[str, int],
    cmd_base: int,
    ui_telem_base: int,
    core_dt: float,
    log_level: str,
) -> list[str]:
    cmd = [
        sys.executable,
        "-m",
        "steuerung3d.apps.core_udp_service",
        "--dt",
        str(core_dt),
        "--log-level",
        log_level,
        "--dev-telem-in",
        f"{telem_out[0]}:{telem_out[1]}",
        "--dev-cmd-base",
        str(cmd_base),
        "--dev-cmd-count",
        str(len(axes)),
        "--ui-telem-base",
        str(ui_telem_base),
        "--ui-telem-count",
        str(len(axes)),
    ]
    for axis_id in axes:
        cmd.extend(["--axis", axis_id])
    return cmd


def build_densi_cmd(
    *, axis_id: str, cmd_in_port: int, telem_out: tuple[str, int], dt: float, log_level: str
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "steuerung3d.apps.den_si",
        "--axis",
        axis_id,
        "--dt",
        str(dt),
        "--cmd-in",
        f"127.0.0.1:{cmd_in_port}",
        "--telem-out",
        f"{telem_out[0]}:{telem_out[1]}",
        "--log-level",
        log_level,
    ]


def launch_children(
    *,
    axes: Sequence[str],
    telem_out: tuple[str, int],
    cmd_base: int,
    dt: float,
    log_level: str,
    new_console: bool,
    also_core: bool,
    ui_telem_base: int,
    core_dt: float,
) -> list[Child]:
    children: list[Child] = []
    if also_core:
        core_cmd = build_core_cmd(
            axes=axes,
            telem_out=telem_out,
            cmd_base=cmd_base,
            ui_telem_base=ui_telem_base,
            core_dt=core_dt,
            log_level=log_level,
        )
        children.append(
            Child(kind="core", axis="", cmd=core_cmd, p=popen(core_cmd, new_console=new_console))
        )
        time.sleep(0.2)

    for i, axis_id in enumerate(axes):
        cmd_in_port = cmd_base + i
        densi_cmd = build_densi_cmd(
            axis_id=axis_id,
            cmd_in_port=cmd_in_port,
            telem_out=telem_out,
            dt=dt,
            log_level=log_level,
        )
        children.append(
            Child(
                kind="densi",
                axis=axis_id,
                cmd=densi_cmd,
                p=popen(densi_cmd, new_console=new_console),
            )
        )
        time.sleep(0.1)
    return children


def startup_message(*, axes: Sequence[str], telem_out: tuple[str, int], cmd_base: int) -> str:
    axis_map_lines = ["Axis -> CommandIn:"]
    for i, axis_id in enumerate(axes):
        axis_map_lines.append(f"  {axis_id}: 127.0.0.1:{cmd_base + i}")
    return (
        f"DenSi fleet running for axes={list(axes)}. Command ports {cmd_base}..{cmd_base + len(axes) - 1}.\n"
        f"TelemetryOut -> {telem_out[0]}:{telem_out[1]}\n"
        + "\n".join(axis_map_lines)
        + "\nCtrl+C to stop."
    )


def reap_children(children: list[Child]) -> list[str]:
    messages: list[str] = []
    for child in list(children):
        rc = child.p.poll()
        if rc is None:
            continue
        children.remove(child)
        label = "core" if child.kind == "core" else f"DenSi[{child.axis}]"
        messages.append(f"[densi_fleet] {label} exited rc={rc} cmd={fmt_cmd(child.cmd)}")
    return messages


def terminate_children(children: Sequence[Child]) -> None:
    for child in children:
        try:
            child.p.terminate()
        except Exception:
            pass
    for child in children:
        try:
            child.p.wait(timeout=1.5)
        except Exception:
            pass
