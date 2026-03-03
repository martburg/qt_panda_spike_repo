"""Resync command handling for DenSi engine (Qt-free)."""

from __future__ import annotations

from typing import Callable

from steuerung3d.core.command_frame import CommandFrame

from .types import L0Top


def handle_resync_cmd(
    *,
    cmd: CommandFrame,
    l0_top: L0Top,
    clear_cut_markers: Callable[[bool], None],
    arm_cut_follow_live: Callable[[], None],
) -> None:
    if l0_top == L0Top.CONNECTED and bool(getattr(cmd, "resync", False)):
        arm_cut_follow_live()
