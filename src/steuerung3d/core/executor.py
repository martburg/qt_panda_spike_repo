from __future__ import annotations

from typing import Dict
import logging
import time

log = logging.getLogger("core") 

# Lifetick tracing: avoid per-tick spam. Log at most every 0.5s per axis.
_LT_LOG_EVERY_S = 0.5
_lt_last_cmd_log_by_axis: dict[str, float] = {}

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, coerce_param_ops
from steuerung3d.core.state import MachineState


def _axis_lease_allows(state: MachineState, axis_id: str) -> bool:
    holders = getattr(state, "lease_axis_holders", {}) or {}
    if not isinstance(holders, dict):
        return False
    vals = holders.get(axis_id, [])
    if not isinstance(vals, (list, tuple)):
        return False
    return len([v for v in list(vals) if str(v)]) > 0


def build_command_frame(state: MachineState) -> CommandFrame:
    axes: Dict[str, AxisSetpoint] = {}
    for axis_id, cmd in state.axis_cmd.items():
        if not _axis_lease_allows(state, axis_id):
            axes[axis_id] = AxisSetpoint(enable=False, vel=0.0)
            continue
        axes[axis_id] = AxisSetpoint(enable=cmd.enable, vel=cmd.vel)
    lifetick_echo = dict(getattr(state, "lifetick_echo_by_axis", {}))

    # LifeTick echo map is updated frequently; keep at DEBUG to avoid log spam.
    log.debug("core cmd lifetick_echo=%s", state.lifetick_echo_by_axis)

    # LIFETICK trace: Core -> devices (via CommandFrame.lifetick_echo)
    now_s = time.monotonic()
    axis_ids = sorted(set(axes.keys()) | set(lifetick_echo.keys()))
    for axis_id in axis_ids:
        v = lifetick_echo.get(axis_id, None)
        last_s = float(_lt_last_cmd_log_by_axis.get(axis_id, 0.0))
        if (now_s - last_s) >= _LT_LOG_EVERY_S:
            _lt_last_cmd_log_by_axis[axis_id] = now_s
            # LifeTick is useful while debugging connectivity, but too chatty
            # for everyday use. Keep it at DEBUG and throttled.
            log.debug(
                "LIFETICK Core tx cmd: axis=%s cmd_tick=%s echo=%s",
                axis_id,
                state.tick,
                int(v) & 0xFFFF if isinstance(v, int) else v,
            )

    resync_any = bool(getattr(state, "resync_req", False))
    try:
        if not resync_any:
            m = getattr(state, "resync_req_by_axis", {})
            if isinstance(m, dict):
                resync_any = any(bool(v) for v in m.values())
    except Exception:
        resync_any = bool(getattr(state, "resync_req", False))

    return CommandFrame(
        tick=state.tick,
        t_s=state.t_s,
        estop=False,  # <-- important policy change
        fault=state.fault,
        mode=state.mode.value,
        axes=axes,
        estop_reset=state.estop_reset_req,  # pulse from HI-P intent
        resync=resync_any,  # legacy ReSync pulse
        param_ops=coerce_param_ops(getattr(state, "pending_param_ops", [])),
        lifetick_echo=lifetick_echo,
    )