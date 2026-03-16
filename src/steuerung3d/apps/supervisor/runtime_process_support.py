from __future__ import annotations

import os
import shlex
import subprocess
import sys
from collections.abc import Callable

from .models import SupervisorProfile


def launch_children(*, profile: SupervisorProfile) -> list[subprocess.Popen[str]]:
    children: list[subprocess.Popen[str]] = []
    if profile.launch_stack:
        cmd = [
            sys.executable,
            "-m",
            "steuerung3d",
            "up",
            "--profile",
            profile.launch_stack,
        ]
        children.append(subprocess.Popen(cmd, cwd=os.getcwd(), text=True))
        return children

    env = dict(os.environ)
    for axis in profile.axes:
        for cmd_text in (axis.hip_launch, axis.densi_launch):
            if not cmd_text:
                continue
            argv = shlex.split(cmd_text)
            children.append(subprocess.Popen(argv, cwd=os.getcwd(), env=env, text=True))
    return children


def launch_hip_child(*, cmd_text: str) -> subprocess.Popen[str]:
    env = dict(os.environ)
    argv = shlex.split(str(cmd_text).strip())
    return subprocess.Popen(argv, cwd=os.getcwd(), env=env, text=True)


def refresh_hip_processes(
    *,
    profile: SupervisorProfile,
    hip_children: dict[str, list[subprocess.Popen[str]]],
    set_hip_open_count: Callable[[str, int], None],
    release_hip_authority: Callable[[str, str], None],
) -> None:
    for unit_id, children in list(hip_children.items()):
        alive = [child for child in children if child.poll() is None]
        exited = len(children) - len(alive)
        if alive:
            hip_children[unit_id] = alive
        else:
            hip_children.pop(unit_id, None)
        set_hip_open_count(unit_id, len(alive))
        if exited > 0 and len(alive) == 0:
            axis = next((axis for axis in profile.axes if axis.unit_id == str(unit_id)), None)
            if axis is not None and axis.hip_id:
                release_hip_authority(axis.axis_id, axis.hip_id)


def terminate_children(*, children: list[subprocess.Popen[str]]) -> None:
    for child in children:
        try:
            child.terminate()
        except Exception:
            pass


def terminate_hip_children(*, hip_children: dict[str, list[subprocess.Popen[str]]]) -> None:
    for children in hip_children.values():
        terminate_children(children=children)
