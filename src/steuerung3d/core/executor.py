from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from steuerung3d.config.lifetick_config import LifetickTraceConfig, load_lifetick_config
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, coerce_param_ops
from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.intent_handlers.lease import axis_lease_allows_any
from steuerung3d.core.rig_logic import densi_online
from steuerung3d.core.state import MachineState

log = logging.getLogger("core")

# Lifetick tracing: avoid per-tick spam in the *core* logger.
_lt_last_cmd_log_by_axis: dict[str, float] = {}

_lifetick_cfg: Optional[LifetickTraceConfig] = None
_lifetick_logger: Optional[logging.Logger] = None


def _get_lifetick_cfg() -> LifetickTraceConfig:
    global _lifetick_cfg
    if _lifetick_cfg is None:
        # Config lives in-repo, but is intentionally optional.
        _lifetick_cfg = load_lifetick_config(Path("configs/debug/lifetick.toml"))
    return _lifetick_cfg


def _get_lifetick_logger() -> Optional[logging.Logger]:
    """Return a dedicated lifetick logger when enabled.

    This keeps main core logs readable while allowing high-frequency tracing
    into a rotating file ("oscilloscope" style).
    """

    global _lifetick_logger
    if _lifetick_logger is not None:
        return _lifetick_logger

    cfg = _get_lifetick_cfg()
    if not cfg.enable:
        return None

    logger = logging.getLogger("lifetick")
    logger.propagate = False
    logger.setLevel(logging.INFO)

    log_path = Path(cfg.path)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If we cannot create dirs, fall back to no special handler.
        return None

    handler = RotatingFileHandler(
        log_path,
        maxBytes=int(cfg.max_bytes),
        backupCount=int(cfg.backup_count),
        encoding="utf-8",
    )
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
    logger.addHandler(handler)

    _lifetick_logger = logger
    return _lifetick_logger


def _compute_resync_any(state: MachineState) -> bool:
    resync_any = bool(getattr(state, "resync_req", False))
    if resync_any:
        return True
    m = getattr(state, "resync_req_by_axis", {})
    if isinstance(m, dict):
        try:
            return any(bool(v) for v in m.values())
        except Exception:
            return bool(getattr(state, "resync_req", False))
    return False


def build_command_frame(state: MachineState) -> CommandFrame:
    axes: Dict[str, AxisSetpoint] = {}
    for axis_id, cmd in state.axis_cmd.items():
        if hasattr(state, "densi_registry") and axis_id in dict(getattr(state, "densi_registry", {})):
            if not densi_online(state, axis_id):
                axes[axis_id] = AxisSetpoint(enable=False, vel=0.0)
                continue
        if not axis_lease_allows_any(state, axis_id):
            axes[axis_id] = AxisSetpoint(enable=False, vel=0.0)
            continue
        axes[axis_id] = AxisSetpoint(enable=cmd.enable, vel=cmd.vel)
    lifetick_echo = dict(getattr(state, "lifetick_echo_by_axis", {}))

    # LIFETICK trace: Core -> devices (via CommandFrame.lifetick_echo)
    now_s = time.monotonic()
    cfg = _get_lifetick_cfg()
    lifetick = _get_lifetick_logger()
    every_s = float(cfg.every_s) if cfg.every_s is not None else 0.5
    axis_ids = sorted(set(axes.keys()) | set(lifetick_echo.keys()))
    for axis_id in axis_ids:
        v = lifetick_echo.get(axis_id, None)
        last_s = float(_lt_last_cmd_log_by_axis.get(axis_id, 0.0))
        if (now_s - last_s) >= every_s:
            _lt_last_cmd_log_by_axis[axis_id] = now_s
            # LifeTick is useful while debugging connectivity, but too chatty
            # for everyday use. Keep it at DEBUG and throttled.
            log.debug(
                "LIFETICK Core tx cmd: axis=%s cmd_tick=%s echo=%s",
                axis_id,
                state.tick,
                int(v) & 0xFFFF if isinstance(v, int) else v,
            )
            if lifetick is not None:
                lifetick.info(
                    "axis=%s cmd_tick=%s echo=%s",
                    axis_id,
                    state.tick,
                    int(v) & 0xFFFF if isinstance(v, int) else v,
                )

    resync_any = _compute_resync_any(state)

    core_mode = core_mode_value(getattr(state, "core_mode", ""))
    joy = getattr(state, "joy", None)
    joy_select = bool(getattr(joy, "select_hip", False)) if joy is not None else False
    if core_mode != CoreMode.LIVE.value:
        for axis_id, sp in axes.items():
            axes[axis_id] = AxisSetpoint(enable=bool(sp.enable), vel=0.0)
    elif not joy_select:
        for axis_id, sp in axes.items():
            if abs(float(sp.vel)) > 1e-6:
                axes[axis_id] = AxisSetpoint(enable=bool(sp.enable), vel=0.0)

    return CommandFrame(
        tick=state.tick,
        t_s=state.t_s,
        estop=False,  # <-- important policy change
        fault=state.fault,
        core_mode=core_mode,
        axes=axes,
        estop_reset=state.estop_reset_req,  # pulse from HI-P intent
        resync=resync_any,  # legacy ReSync pulse
        param_ops=coerce_param_ops(getattr(state, "pending_param_ops", [])),
        lifetick_echo=lifetick_echo,
    )