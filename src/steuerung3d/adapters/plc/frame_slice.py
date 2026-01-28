from __future__ import annotations

from typing import Iterable

from steuerung3d.core.command_frame import CommandFrame


def slice_command_frame(cmd: CommandFrame, axis_ids: Iterable[str]) -> CommandFrame:
    """
    Return a shallow copy of cmd that contains only setpoints for axis_ids.

    This is a pure helper:
      - no UDP
      - no PLC formatting
      - no state mutation
    """
    axis_set = set(axis_ids)
    sliced_axes = {axis_id: sp for axis_id, sp in cmd.axes.items() if axis_id in axis_set}

    # CommandFrame is a dataclass, so reconstruct it explicitly for clarity.
    return CommandFrame(
        tick=cmd.tick,
        t_s=cmd.t_s,
        estop=cmd.estop,
        fault=cmd.fault,
        mode=cmd.mode,
        axes=sliced_axes,
        estop_reset=src.estop_reset
    )
