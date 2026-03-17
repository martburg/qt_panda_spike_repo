from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot

from .densi_runtime_types import DensiRuntimeStatusLike
from .runtime_kernel import compute_health, emit_runtime_status, with_health_fields


@dataclass(frozen=True)
class DensiStatusPayload:
    level: str
    summary: str
    fields: dict[str, Any]


def _axis_id(runtime: DensiRuntimeStatusLike) -> str:
    axis_ids = list(getattr(runtime, "_axis_ids", []) or [])
    return str(axis_ids[0]) if axis_ids else ""


def _engine_state(runtime: DensiRuntimeStatusLike) -> object:
    return getattr(getattr(runtime, "engine", object()), "state", object())


def _command_setpoint(cmd: CommandFrame | None, axis: str) -> tuple[bool, float]:
    if cmd is None or not axis:
        return False, 0.0
    try:
        sp = (getattr(cmd, "axes", {}) or {}).get(axis)
    except Exception:
        sp = None
    if sp is None:
        return False, 0.0
    try:
        return bool(getattr(sp, "enable", False)), float(getattr(sp, "vel", 0.0) or 0.0)
    except Exception:
        return False, 0.0


def _axis_applied_state(
    runtime: DensiRuntimeStatusLike, axis: str
) -> tuple[float, float, int | None]:
    if not axis:
        return 0.0, 0.0, None
    try:
        ax = (getattr(_engine_state(runtime), "axes", {}) or {}).get(axis)
    except Exception:
        ax = None
    if ax is None:
        return 0.0, 0.0, None
    try:
        vel_applied = float(getattr(ax, "vel", 0.0) or 0.0)
        pos_applied = float(getattr(ax, "pos", 0.0) or 0.0)
        lifetick_age_ticks = int(getattr(ax, "meta", {}).get("plc_lifetick_age_ticks", 0))
        return vel_applied, pos_applied, lifetick_age_ticks
    except Exception:
        return 0.0, 0.0, None


def build_densi_status_payload(
    *, runtime: DensiRuntimeStatusLike, now_ns: int
) -> DensiStatusPayload:
    h = compute_health(
        now_ns=int(now_ns),
        last_rx_ns=getattr(runtime, "_last_cmd_ns", None),
        stale_after_ms=int(getattr(runtime, "_stale_after_ms", 0)),
        seen_first_rx=bool(getattr(runtime, "_seen_first_cmd", False)),
        estop=bool(getattr(runtime, "_last_estop", False)),
        fault=bool(getattr(runtime, "_last_fault", False)),
    )
    axis = _axis_id(runtime)
    mode = str(getattr(runtime, "_last_mode", "") or "")
    online = bool(getattr(h, "online", False))
    cmd = getattr(runtime, "_last_cmd", None)
    cmd_mode = str(getattr(cmd, "core_mode", "") or "") if cmd is not None else ""
    cmd_intent = bool(getattr(cmd, "intent", False)) if cmd is not None else False
    cmd_enable, cmd_vel = _command_setpoint(cmd, axis)

    state = _engine_state(runtime)
    ready_for_sollvel = bool(getattr(getattr(runtime, "engine", object()), "drive_ready", False))
    estop_now = bool(getattr(state, "estop", False))
    fault_now = bool(getattr(state, "fault", False))
    vel_applied, pos_applied, lifetick_age_ticks = _axis_applied_state(runtime, axis)

    summary = (
        f"densi axis={axis or '-'} ctrl={int(cmd_enable)} "
        f"soll={cmd_vel:+.2f} ready={int(ready_for_sollvel)} "
        f"estop={int(estop_now)} applied={vel_applied:+.2f}"
    )
    fields = with_health_fields(
        {
            "component": "densi",
            "axis": axis,
            "core_mode": mode,
            "online": bool(online),
            "tick": int(getattr(state, "tick", 0) or 0),
            "last_cmd_rx_age_ms": -1
            if getattr(h, "age_ms", None) is None
            else float(getattr(h, "age_ms", 0.0)),
            "cmd_core_mode": str(cmd_mode),
            "cmd_intent": bool(cmd_intent),
            "cmd_enable": bool(cmd_enable),
            "cmd_vel": float(cmd_vel),
            "ready_for_sollvel": bool(ready_for_sollvel),
            "vel_applied": float(vel_applied),
            "pos": float(pos_applied),
            "lifetick_age_ticks": lifetick_age_ticks,
            "debug": {
                "axis_selected": axis,
                "attached": bool(axis),
                "core_mode": mode,
                "cmd_enable": bool(cmd_enable),
                "cmd_vel": float(cmd_vel),
                "vel_applied": float(vel_applied),
                "lifetick_age_ticks": lifetick_age_ticks,
                "last_cmd_ns": getattr(runtime, "_last_cmd_ns", None),
            },
        },
        health=h,
        estop=bool(estop_now),
        fault=bool(fault_now),
    )
    return DensiStatusPayload(
        level=str(getattr(h, "level", "") or ""),
        summary=summary,
        fields=fields,
    )


def emit_status(rt: DensiRuntimeStatusLike, now_ns: int) -> None:
    if rt._status is None:
        return
    payload = build_densi_status_payload(runtime=rt, now_ns=now_ns)
    emit_runtime_status(
        rt._status,
        level=payload.level,
        summary=payload.summary,
        fields=payload.fields,
        log=rt._log,
        exc_tag="densi.status.emit",
        exc_msg="DenSi status emission failed",
    )


def publish_telemetry_and_heartbeat(
    rt: DensiRuntimeStatusLike, snap: TelemetrySnapshot, now_ns: int
) -> None:
    if rt._ch.changed("core_mode", str(getattr(snap, "core_mode", ""))):
        rt._log.info("core_mode=%s", getattr(snap, "core_mode", ""))
    if rt._ch.changed("estop", bool(getattr(snap, "estop", False))):
        rt._log.info(
            "estop=%s word=%s",
            bool(getattr(snap, "estop", False)),
            hex(int(getattr(snap, "estop_status_word", 0))),
        )
    if rt._ch.changed("fault", bool(getattr(snap, "fault", False))):
        rt._log.info("fault=%s", bool(getattr(snap, "fault", False)))

    rt._hb.inc("telem_tx", 1)
    rt._hb.set("tick", int(getattr(snap, "tick", 0)))
    rt._hb.set("core_mode", str(getattr(snap, "core_mode", "")))
    rt._hb.set("estop", bool(getattr(snap, "estop", False)))
    rt._hb.set("fault", bool(getattr(snap, "fault", False)))
    axis = _axis_id(rt)
    if axis:
        rt._hb.set("axis", axis)
    if rt._last_cmd_ns is not None:
        rt._hb.set("cmd_age_ms", int((int(now_ns) - int(rt._last_cmd_ns)) / 1_000_000.0))
    rt._hb.emit(rt._log)
    rt._last_mode = str(getattr(rt._last_cmd, "core_mode", "") or "")
    rt._last_estop = bool(getattr(rt._last_cmd, "estop", False))
    rt._last_fault = bool(getattr(rt._last_cmd, "fault", False))
    emit_status(rt, now_ns)

    if rt._log.isEnabledFor(logging.DEBUG) and rt._dbg_rl is not None:
        try:
            now_s = time.monotonic()
            if rt._dbg_rl.due(now_s):
                rt._dbg_rl.mark(now_s)
                try:
                    dt = None
                    if getattr(rt.engine.state, "axes", None):
                        ax0 = next(iter(rt.engine.state.axes.values()))
                        dt = ax0.meta.get("device_tick")
                except Exception:
                    dt = None
                rt._log.debug("device_tick=%s", dt)
                rt._log.debug(
                    "tx telem: tick=%s estop=%s fault=%s estop_word=%s",
                    snap.tick,
                    snap.estop,
                    snap.fault,
                    hex(snap.estop_status_word),
                )
        except Exception:
            pass
