from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import cast

from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.intents import Intent, JogCartesian, JogWinch, LocalAxisManualRequest
from steuerung3d.protocol.raw_controls import RawControls

from .mapping import JoyReportLike, synthesize_intents
from .startup import Joy2IntentRuntime
from .status import build_status_payload, emit_status

log = logging.getLogger("joy2intent")


@dataclass
class RuntimeState:
    next_t: float
    last_rx_ns: int | None = None
    sent_stale_zero: bool = False
    last_buttons: list[int] = field(default_factory=list)
    last_axes: list[float] = field(default_factory=list)
    last_axis_pairs: list[str] = field(default_factory=list)
    last_selected_axes: list[str] = field(default_factory=list)
    last_select_map: list[str] = field(default_factory=list)
    latest_ctx: ControlContext | None = None


def log_startup(rt: Joy2IntentRuntime) -> None:
    cfg = rt.cfg
    st = rt.state
    log.info(
        "joy2intent started mode=%s raw_in=%s intent_out=%s tick_hz=%.1f stale_after_ms=%d "
        "max_winch_mps=%.3f fine_scale=%.3f deadzone=%.3f expo=%.3f hip_id=%s winches=%s select_buttons=%s",
        st.mode,
        cfg.raw_in,
        cfg.intent_out,
        cfg.tick_hz,
        cfg.stale_after_ms,
        cfg.max_winch_mps,
        cfg.fine_scale,
        cfg.deadzone,
        cfg.expo,
        cfg.hip_id,
        list(cfg.winches),
        list(cfg.select_buttons),
    )


def _update_runtime_inputs(
    *, rt: Joy2IntentRuntime, state: RuntimeState, now_ns: int
) -> RawControls | None:
    rcs = rt.raw_in.drain_raw_controls(limit=50)
    rc: RawControls | None = rcs[-1] if rcs else None
    ctxs = rt.context_in.drain_contexts(limit=20)
    if ctxs:
        state.latest_ctx = ctxs[-1]
    rt.hb.inc("rx", len(rcs))
    if state.last_rx_ns is not None:
        rt.hb.set("age_ms", int((now_ns - state.last_rx_ns) / 1_000_000.0))
    rt.hb.set("mode", getattr(rt.state, "mode", "?"))
    return rc


def _update_button_axis_snapshots(
    *, rc: RawControls, rt: Joy2IntentRuntime, state: RuntimeState
) -> set[int]:
    try:
        state.last_buttons = [i for i, v in enumerate(rc.buttons) if v]
    except Exception:
        state.last_buttons = []
    try:
        raw_axes = [float(x) for x in list(rc.axes)]
    except Exception:
        raw_axes = []
    state.last_axes = raw_axes[:6]
    axis_pairs: list[str] = []
    for axis_name, axis_idx in sorted(rt.bindings.axes.items()):
        axis_value = None
        if 0 <= axis_idx < len(raw_axes):
            axis_value = raw_axes[axis_idx]
        axis_pairs.append(
            f"{axis_name}@{axis_idx}={axis_value:+.3f}"
            if axis_value is not None
            else f"{axis_name}@{axis_idx}=NA"
        )
    state.last_axis_pairs = axis_pairs
    try:
        return {i for i, v in enumerate(rc.buttons) if v}
    except Exception:
        return set()


def _log_deadman_and_selection(
    *, rt: Joy2IntentRuntime, state: RuntimeState, pressed: set[int]
) -> None:
    dm_btn = rt.bindings.buttons.get("deadman")
    deadman = (dm_btn is not None) and (dm_btn in pressed)
    if rt.ch.changed("deadman", bool(deadman)):
        log.info("deadman=%s", bool(deadman))

    try:
        rig_ids = rt.rig.ordered_winch_ids()
        selected_pairs: list[str] = []
        sel: list[str] = []
        for i, b in enumerate(rt.bindings.select_buttons or []):
            axis_name = rig_ids[i] if i < len(rig_ids) else f"axis[{i}]"
            hit = b in pressed
            selected_pairs.append(f"b{b}->{axis_name}:{'ON' if hit else 'off'}")
            if hit and i < len(rig_ids):
                sel.append(axis_name)
        state.last_selected_axes = list(sel)
        state.last_select_map = list(selected_pairs)
        selected_detail = (
            tuple(sorted(pressed)),
            tuple(sel),
            tuple(selected_pairs),
            tuple(state.last_axis_pairs),
        )
        if rt.ch.changed("selected_detail", selected_detail):
            log.info(
                "buttons=%s select_map=%s selected=%s axes=%s",
                sorted(pressed),
                selected_pairs,
                list(sel),
                state.last_axis_pairs,
            )
    except Exception:
        pass


def _publish_intents(*, rt: Joy2IntentRuntime, intents: list[object]) -> None:
    rt.hb.inc("intent", len(intents))
    for it in intents:
        rt.intent_out.publish_intent(cast(Intent, it))


def _handle_raw_sample(
    *, rt: Joy2IntentRuntime, state: RuntimeState, rc: RawControls, now_ns: int
) -> None:
    state.last_rx_ns = now_ns
    state.sent_stale_zero = False
    pressed = _update_button_axis_snapshots(rc=rc, rt=rt, state=state)
    intents = synthesize_intents(
        rt.state,
        cast(JoyReportLike, rc),
        rt.bindings,
        rt.rig,
        rt.limits,
        hip_id=rt.cfg.hip_id,
        control_context=state.latest_ctx,
    )
    _log_deadman_and_selection(rt=rt, state=state, pressed=pressed)
    _publish_intents(rt=rt, intents=intents)


def _emit_stale_stop(*, rt: Joy2IntentRuntime, state: RuntimeState) -> None:
    if (
        state.latest_ctx is not None
        and str(getattr(state.latest_ctx, "mode", "")) == "independent_axes"
        and str(getattr(state.latest_ctx, "input_mapping", "")) == "axis_rate"
    ):
        axis_ids = tuple(sorted(state.last_selected_axes))
        rt.intent_out.publish_intent(
            LocalAxisManualRequest(axis_ids=axis_ids, enable=False, rate=0.0)
        )
    else:
        rt.intent_out.publish_intent(JogCartesian(vx=0.0, vy=0.0, vz=0.0))
        if rt.rig.winches and rt.state.prev_active_winch_idxs:
            for idx in sorted(rt.state.prev_active_winch_idxs):
                if 0 <= idx < len(rt.rig.winches):
                    rt.intent_out.publish_intent(JogWinch(winch_id=rt.rig.winches[idx], rate=0.0))
            rt.state.prev_active_winch_idxs.clear()
        else:
            wid = rt.rig.winches[rt.state.selected_winch_idx] if rt.rig.winches else "WINCH"
            rt.intent_out.publish_intent(JogWinch(winch_id=wid, rate=0.0))
    state.sent_stale_zero = True


def _handle_stale_input(*, rt: Joy2IntentRuntime, state: RuntimeState, now_ns: int) -> None:
    if state.last_rx_ns is None:
        return
    age_ms = (now_ns - state.last_rx_ns) / 1_000_000.0
    if age_ms > rt.cfg.stale_after_ms and not state.sent_stale_zero:
        _emit_stale_stop(rt=rt, state=state)
        log.warning("raw input stale (age_ms=%.1f) -> emitted stop", age_ms)


def _emit_heartbeat_and_status(*, rt: Joy2IntentRuntime, state: RuntimeState, now_ns: int) -> None:
    rt.hb.set("buttons", list(state.last_buttons))
    rt.hb.set("selected", list(state.last_selected_axes))
    rt.hb.set("ctx_mode", str(getattr(state.latest_ctx, "mode", "")))
    rt.hb.set("select_map", list(state.last_select_map))
    rt.hb.set("axes", list(state.last_axis_pairs))

    if rt.status is not None:
        age_ms_f: float | None = None
        if state.last_rx_ns is not None:
            age_ms_f = (now_ns - state.last_rx_ns) / 1_000_000.0
        payload = build_status_payload(
            mode=rt.state.mode,
            age_ms=age_ms_f,
            stale_stop=state.sent_stale_zero,
            raw_in=rt.cfg.raw_in,
            intent_out=rt.cfg.intent_out,
            winches=list(rt.rig.winches),
            last_buttons=list(state.last_buttons),
            last_axes=list(state.last_axes),
            last_axis_pairs=list(state.last_axis_pairs),
            last_selected_axes=list(state.last_selected_axes),
            last_select_map=list(state.last_select_map),
        )
        emit_status(status=rt.status, payload=payload)

    rt.hb.emit(log)


def run(rt: Joy2IntentRuntime) -> int:
    state = RuntimeState(next_t=time.monotonic())
    log_startup(rt)
    while True:
        now_ns = time.monotonic_ns()
        rc = _update_runtime_inputs(rt=rt, state=state, now_ns=now_ns)
        if rc is not None:
            _handle_raw_sample(rt=rt, state=state, rc=rc, now_ns=now_ns)
        else:
            _handle_stale_input(rt=rt, state=state, now_ns=now_ns)
        _emit_heartbeat_and_status(rt=rt, state=state, now_ns=now_ns)
        state.next_t += rt.dt
        sleep_s = state.next_t - time.monotonic()
        if sleep_s > 0:
            time.sleep(sleep_s)
        else:
            state.next_t = time.monotonic()
