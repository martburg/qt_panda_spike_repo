from __future__ import annotations

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Dict, Optional

from steuerung3d.config.lifetick_config import LifetickTraceConfig, load_lifetick_config
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, ParamOp, coerce_param_ops
from steuerung3d.core.core_mode import CoreMode, core_mode_value
from steuerung3d.core.intent_handlers.lease import axis_lease_allows_any
from steuerung3d.core.joy_state import canonicalize_selected_axes
from steuerung3d.core.motion_gate import axis_local_motion_allowed
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


def _supervisor_manual_active_axes(state: MachineState, *, joy_deadman: bool) -> set[str]:
    if not bool(joy_deadman):
        return set()
    active: set[str] = set()
    for axis_id, cmd in state.axis_cmd.items():
        if not bool(getattr(cmd, "enable", False)):
            continue
        owner = str(state.axis_owner(axis_id) or "")
        if not owner:
            continue
        if str(state.claim_owner(axis_id) or ""):
            continue
        if axis_local_motion_allowed(state, axis_id):
            active.add(axis_id)
    return active

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


def _supervisor_manual_active_axes(state: MachineState, *, joy_deadman: bool) -> set[str]:
    if not bool(joy_deadman):
        return set()
    active: set[str] = set()
    for axis_id, cmd in state.axis_cmd.items():
        if not bool(getattr(cmd, "enable", False)):
            continue
        owner = str(state.axis_owner(axis_id) or "")
        if not owner:
            continue
        if str(state.claim_owner(axis_id) or ""):
            continue
        if axis_local_motion_allowed(state, axis_id):
            active.add(axis_id)
    return active


def _compute_resync_any(state: MachineState) -> bool:
    """Return legacy/global resync pulse state.

    Multi-axis code should prefer ``_compute_resync_by_axis``. The legacy
    global field is kept for single-axis compatibility only.
    """
    return bool(getattr(state, "resync_req", False))


def _compute_resync_by_axis(state: MachineState) -> dict[str, bool]:
    m = getattr(state, "resync_req_by_axis", {})
    return {str(k): bool(v) for k, v in dict(m).items()} if isinstance(m, dict) else {}


def _compute_estop_reset_any(state: MachineState) -> bool:
    """Return whether any estop-reset pulse should be emitted this tick.

    Canonical source is ``state.estop_reset_req_by_axis`` (per-axis, one-shot).
    ``state.estop_reset_req`` is legacy/global and only kept for compatibility.
    """
    if bool(getattr(state, "estop_reset_req", False)):
        return True
    m = getattr(state, "estop_reset_req_by_axis", {})
    if isinstance(m, dict):
        try:
            return any(bool(v) for v in m.values())
        except Exception:
            return bool(getattr(state, "estop_reset_req", False))
    return False


def _compute_main_reset_by_axis(state: MachineState) -> dict[str, bool]:
    m = getattr(state, "main_reset_req_by_axis", {})
    return dict(m) if isinstance(m, dict) else {}


def _compute_guider_reset_by_axis(state: MachineState) -> dict[str, bool]:
    m = getattr(state, "guider_reset_req_by_axis", {})
    return dict(m) if isinstance(m, dict) else {}


def _compute_param_ops_any(state: MachineState) -> list[ParamOp]:
    """Flatten any pending ParamOps into a single list for CommandFrame.

    Notes:
    - In multi-axis mode, core_udp_service routes param ops per-axis separately.
      This aggregate is mainly for single-axis adapters and backward compatibility.
    - We keep legacy ``pending_param_ops`` as well, but prefer per-axis storage.
    """
    ops: list[ParamOp] = []
    per_axis = getattr(state, "pending_param_ops_by_axis", {})
    if isinstance(per_axis, dict):
        for axis_id in sorted(per_axis.keys()):
            v = per_axis.get(axis_id) or []
            if isinstance(v, list):
                ops.extend(v)
    legacy = getattr(state, "pending_param_ops", []) or []
    if isinstance(legacy, list):
        ops.extend(legacy)
    return ops


def build_command_frame(state: MachineState) -> CommandFrame:
    axes: Dict[str, AxisSetpoint] = {}
    for axis_id, cmd in state.axis_cmd.items():
        if axis_id in (state.densi_registry or {}):
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
    joy_deadman = bool(getattr(joy, "deadman", False)) if joy is not None else False
    selected_axes = (
        set(canonicalize_selected_axes(getattr(joy, "selected_axes", ())))
        if joy is not None
        else set()
    )
    # Motion-resolution policy:
    # - Explicit selected_axes + deadman are authoritative. Only those axes may move.
    # - In local/manual mode, a selected axis may still move when that specific
    #   axis is individually ready, even if global core_mode is below LIVE.
    if selected_axes and joy_deadman:
        if core_mode == CoreMode.LIVE.value:
            active_axes = set(selected_axes)
        else:
            active_axes = {
                axis_id for axis_id in selected_axes if axis_local_motion_allowed(state, axis_id)
            }
    else:
        active_axes = set()

    active_axes |= _supervisor_manual_active_axes(state, joy_deadman=joy_deadman)

    for axis_id, sp in axes.items():
        if (axis_id not in active_axes) and abs(float(sp.vel)) > 1e-6:
            axes[axis_id] = AxisSetpoint(enable=bool(sp.enable), vel=0.0)

    return CommandFrame(
        tick=state.tick,
        t_s=state.t_s,
        estop=False,  # <-- important policy change
        fault=state.fault,
        core_mode=core_mode,
        axes=axes,
        estop_reset=_compute_estop_reset_any(state),  # pulse from HI-P intent (derived)
        resync=resync_any,  # legacy ReSync pulse
        param_ops=coerce_param_ops(_compute_param_ops_any(state)),
        lifetick_echo=lifetick_echo,
        resync_by_axis=_compute_resync_by_axis(state),
        main_reset_by_axis=_compute_main_reset_by_axis(state),
        guider_reset_by_axis=_compute_guider_reset_by_axis(state),
    )
