from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from typing import Any

from steuerung3d.core.control_context import (
    ControlContext,
    ControlContextInputMapping,
    ControlContextMode,
)
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.util.heartbeat import ChangeTracker

from .birds_eye_types import LastIntentsMetaLike, LastSeenLike
from .reporter import emit_birds_eye_status


def _coerce_control_mode(raw: object) -> ControlContextMode:
    mode = str(raw or "")
    if mode == "sync_kinematic_jog":
        return "sync_kinematic_jog"
    if mode == "goto_pose":
        return "goto_pose"
    if mode == "follow_path":
        return "follow_path"
    return "independent_axes"


def _input_mapping_for_mode(mode: ControlContextMode) -> ControlContextInputMapping:
    if mode == "sync_kinematic_jog":
        return "cartesian_xyz"
    if mode == "goto_pose":
        return "pose_speed"
    if mode == "follow_path":
        return "path_speed_trim"
    return "axis_rate"


def _coerce_last_intents_meta(raw: dict[str, Any]) -> LastIntentsMetaLike:
    raw_types = raw.get("types", [])
    types = [str(item) for item in raw_types] if isinstance(raw_types, (list, tuple)) else []
    return {
        "count": int(raw.get("count", 0) or 0),
        "types": types,
    }


def _coerce_last_seen(raw: dict[str, Any]) -> LastSeenLike:
    out: LastSeenLike = {}
    for key in ("intent_ts", "dev_telem_ts", "cmd_ts", "ui_telem_ts", "c2_telem_ts"):
        value = raw.get(key)
        out[key] = None if value is None else float(value)
    return out


def log_state_changes(
    *,
    snap: TelemetrySnapshot,
    state: MachineState,
    state_ch: ChangeTracker,
    log: logging.Logger,
) -> None:
    try:
        mode_v = str(getattr(snap, "core_mode", ""))
        estop_v = bool(getattr(snap, "estop", False))
        fault_v = bool(getattr(snap, "fault", False))
        rig_v = str(getattr(snap, "rig_mode", ""))
        if (
            state_ch.changed("core_mode", mode_v)
            or state_ch.changed("estop", estop_v)
            or state_ch.changed("fault", fault_v)
            or state_ch.changed("rig_mode", rig_v)
        ):
            log.info(
                "state: core_mode=%s estop=%s fault=%s rig_mode=%s",
                mode_v,
                estop_v,
                fault_v,
                rig_v,
            )
        claims = tuple(sorted(dict(getattr(state, "axis_claims", {}) or {}).items()))
        if state_ch.changed("claims", claims):
            log.info("claims: %s", dict(claims))
        pe = bool(getattr(state, "param_edit_active", False))
        pg = str(getattr(state, "param_edit_group", ""))
        if state_ch.changed("param_edit", (pe, pg)):
            log.info("param_edit: active=%s group=%s", pe, pg)
    except Exception:
        pass


def publish_ui_and_c2(
    *,
    snap: TelemetrySnapshot,
    args: Any,
    router: AxisRouter,
    c2_fanout: Any,
    c2_telem_outs: Sequence[object],
    stats: dict[str, int],
    last_seen: dict[str, Any],
) -> None:
    if not args.ui_telem_disable:
        router.publish_ui_snapshot(snap)
    if c2_fanout is not None:
        c2_fanout.publish_telemetry(snap)
        stats["c2_telem_out"] += max(1, len(c2_telem_outs))
        last_seen["c2_telem_ts"] = time.monotonic()


def log_lifetick(
    *,
    snap: TelemetrySnapshot,
    axis_ids: list[str],
    lt_last_ui_log_s_by_axis: dict[str, float],
    log: logging.Logger,
) -> None:
    for axis_id in axis_ids:
        try:
            ax = dict(getattr(snap, "axes", {}) or {}).get(axis_id)
            dev_tick = getattr(ax, "device_tick", None)
            now_s = time.monotonic()
            last_s = float(lt_last_ui_log_s_by_axis.get(axis_id, 0.0))
            if dev_tick is not None and (now_s - last_s) >= 0.5:
                lt_last_ui_log_s_by_axis[axis_id] = now_s
                log.debug(
                    "LIFETICK Core tx UI telem: axis=%s device_tick=%s", axis_id, int(dev_tick)
                )
        except Exception:
            pass


def update_ui_stats(
    *,
    snap: TelemetrySnapshot,
    args: Any,
    router: AxisRouter,
    axis_ids: list[str],
    stats: dict[str, int],
    last_seen: dict[str, Any],
    log: logging.Logger,
) -> None:
    if args.ui_telem_disable:
        return
    ui_mode = str(getattr(args, "ui_telem_mode", "per_axis") or "per_axis").strip().lower()
    n_ui = (
        len(getattr(router, "ui_telem_fanout", []) or []) if ui_mode == "fanout" else len(axis_ids)
    )
    stats["ui_telem_out"] += max(1, n_ui)
    last_seen["ui_telem_ts"] = time.monotonic()
    log.debug("tx ui telem: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)


def publish_control_context(
    *,
    state: MachineState,
    control_context_out: Any,
    context_seq: int,
) -> int:
    next_seq = context_seq + 1
    mode = _coerce_control_mode(getattr(state, "control_mode", ""))
    input_mapping = _input_mapping_for_mode(mode)
    control_context_out.publish_control_context(
        ControlContext(
            seq=int(next_seq),
            mode=mode,
            selected_target_kind="axis",
            input_mapping=input_mapping,
            motion_enabled=True,
        )
    )
    return next_seq


def emit_birds_eye(
    *,
    status: Any,
    snap: TelemetrySnapshot,
    state: MachineState,
    router: AxisRouter,
    axis_ids: list[str],
    last_intents_meta: dict[str, Any],
    last_seen: dict[str, Any],
) -> None:
    emit_birds_eye_status(
        status=status,
        snap=snap,
        state=state,
        router=router,
        axis_ids=axis_ids,
        last_intents_meta=_coerce_last_intents_meta(last_intents_meta),
        last_seen=_coerce_last_seen(last_seen),
    )
