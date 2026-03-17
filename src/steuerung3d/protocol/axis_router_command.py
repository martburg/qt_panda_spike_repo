from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Optional, cast

from steuerung3d.core.command_frame import CommandFrame, ParamOp, coerce_param_ops

if TYPE_CHECKING:
    from .axis_router import AxisRouter


def publish_command_frames(
    router: "AxisRouter",
    cmd_frame: CommandFrame,
    *,
    estop_reset_by_axis: Optional[Mapping[str, bool]] = None,
    param_ops_by_axis: Optional[Mapping[str, list[ParamOp]]] = None,
) -> int:
    estop_reset_by_axis = estop_reset_by_axis or {}
    param_ops_by_axis = param_ops_by_axis or {}

    sent = 0
    for axis_id in router.axis_ids:
        sp = cmd_frame.axes.get(axis_id)
        if sp is None:
            continue

        echo_val: int | None = None
        try:
            raw_echo_map = getattr(cmd_frame, "lifetick_echo", {}) or {}
            echo_map = (
                cast(dict[str, object], raw_echo_map) if isinstance(raw_echo_map, dict) else {}
            )
            raw_echo_val = echo_map.get(axis_id)
            if isinstance(raw_echo_val, (int, float, str)):
                echo_val = int(raw_echo_val)
        except Exception:
            echo_val = None
        lifetick_echo_axis = {axis_id: (echo_val & 0xFFFF)} if echo_val is not None else {}

        resync_map = getattr(cmd_frame, "resync_by_axis", {}) or {}
        resync_axis = bool(resync_map.get(axis_id, False))

        frame_axis = CommandFrame(
            tick=cmd_frame.tick,
            t_s=cmd_frame.t_s,
            estop=cmd_frame.estop,
            fault=cmd_frame.fault,
            core_mode=cmd_frame.core_mode,
            axes={axis_id: sp},
            intent=bool(getattr(cmd_frame, "intent", True)),
            resync=resync_axis,
            gui_not_halt=bool(getattr(cmd_frame, "gui_not_halt", False)),
            lifetick_echo=lifetick_echo_axis,
            resync_by_axis={axis_id: True} if resync_axis else {},
            estop_reset=bool(estop_reset_by_axis.get(axis_id, False)),
            param_ops=coerce_param_ops(param_ops_by_axis.get(axis_id, [])),
            main_reset_by_axis={
                axis_id: bool(getattr(cmd_frame, "main_reset_by_axis", {}).get(axis_id, False))
            },
            guider_reset_by_axis={
                axis_id: bool(getattr(cmd_frame, "guider_reset_by_axis", {}).get(axis_id, False))
            },
        )

        out = router.dev_cmd_out_by_axis.get(axis_id)
        if out is None:
            continue
        out.publish_command_frame(frame_axis)
        sent += 1
    return sent
