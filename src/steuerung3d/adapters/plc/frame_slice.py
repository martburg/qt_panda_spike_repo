from __future__ import annotations

from typing import Iterable

from steuerung3d.core.command_frame import CommandFrame, coerce_param_ops


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
        core_mode=cmd.core_mode,
        axes=sliced_axes,
        intent=getattr(cmd, "intent", True),
        resync=bool(getattr(cmd, "resync", False)),
        gui_not_halt=bool(getattr(cmd, "gui_not_halt", False)),
        estop_reset=bool(getattr(cmd, "estop_reset", False)),
        # Keep param ops global (not axis-scoped yet)
        param_ops=coerce_param_ops(getattr(cmd, "param_ops", []) or []),
        # Slice livetick echoes to the requested axes.
        lifetick_echo={k: v for k, v in dict(getattr(cmd, "lifetick_echo", {}) or {}).items() if k in axis_set},
    )
