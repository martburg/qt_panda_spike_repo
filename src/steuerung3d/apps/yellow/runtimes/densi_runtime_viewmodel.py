"""DenSi runtime view-model assembly.

Split out of densi_runtime_impl.py to keep the runtime orchestrator readable.

Semantics note: this module intentionally contains a small amount of engine
state write-back (SystemTime / PosDiffFor) to preserve legacy behavior.
"""

from __future__ import annotations

import time

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot

from ..domain.taster_edge_state import TasterEdgeState, update_taster_edge_state, within_brake_grace
from ..engines.densi.engine_types import DenSiTickResult
from ..engines.densi.viewmodel import DensiViewModel
from ..panels.densi.densi_banner_vm import compute_densi_banner_vm
from ..panels.densi.densi_cut_markers_vm import compute_densi_cut_markers_vm
from ..panels.densi.densi_estop_dots_vm import compute_densi_estop_dots_vm
from ..panels.densi.densi_header_online_vm import compute_densi_header_online_vm
from ..panels.densi.densi_lifetick_vm import compute_densi_lifetick_vm
from ..panels.densi.densi_readouts_vm import compute_densi_readouts_vm


def compute_densi_view_model(
    *,
    engine,
    axis_ids: list[str],
    force_refresh_checkboxes: bool,
    now_ns: int,
    tick_result: DenSiTickResult,
    snap: TelemetrySnapshot,
    last_cmd: CommandFrame | None,
    last_cmd_ns: int | None,
    seen_first_cmd: bool,
) -> DensiViewModel:
    """Assemble the DenSi view model.

    The signature is intentionally explicit to keep densi_runtime_impl.py small
    and to make this logic testable without a runtime instance.
    """

    axis_id = axis_ids[0] if axis_ids else ""

    header_online = compute_densi_header_online_vm(
        seen_first_cmd=bool(seen_first_cmd),
        now_ns=int(now_ns),
        last_cmd_ns=last_cmd_ns,
        good_max_s=1.0,
    )

    lifetick_vm = compute_densi_lifetick_vm(state=engine.state, axis_id=axis_id)
    readouts_vm = compute_densi_readouts_vm(state=engine.state, axis_id=axis_id, last_cmd=last_cmd)

    # Cut markers: compute VM + apply effects (state.params + engine token)
    try:
        now_token = engine._now_token()  # pylint: disable=protected-access
    except Exception:
        now_token = ""
    cut_vm = compute_densi_cut_markers_vm(
        cut_valid=bool(getattr(engine, "cut_valid", False)),
        estop_now=bool(getattr(engine.state, "estop", False)),
        now_token=str(now_token),
        systemtime_tok=str(getattr(engine, "systemtime_tok", "") or "") or None,
        systemtime_param=str(engine.state.params.get("SystemTime", "") or "") or None,
        cut_pos_m=float(getattr(engine, "cut_pos_m", 0.0) or 0.0)
        if bool(getattr(engine, "cut_valid", False))
        else None,
        cut_vel_mps=float(getattr(engine, "cut_vel_mps", 0.0) or 0.0)
        if bool(getattr(engine, "cut_valid", False))
        else None,
        pos_m=float(readouts_vm.pos_m) if readouts_vm is not None else None,
    )
    if cut_vm.effects.systemtime_tok is not None:
        engine.systemtime_tok = cut_vm.effects.systemtime_tok
        engine.state.params["SystemTime"] = cut_vm.effects.systemtime_tok
    if cut_vm.effects.posdiff_for is not None:
        try:
            engine.state.params["PosDiffFor"] = float(cut_vm.effects.posdiff_for)
        except Exception:
            pass

    # Estop dots + banner (display grace tracking)
    bits = dict(getattr(tick_result, "estop_bits", {}) or {})
    taster = bool(bits.get("taster", False))
    ready = bool(bits.get("ready", False))

    prev = bool(getattr(engine, "taster_prev_disp", taster))
    pressed_s = getattr(engine, "taster_pressed_s", None)
    st0 = TasterEdgeState(prev=prev, pressed_s=pressed_s if pressed_s is None else float(pressed_s))
    st1 = update_taster_edge_state(state=st0, taster=taster, now_s=float(time.monotonic()))
    engine.taster_prev_disp = bool(st1.prev)
    engine.taster_pressed_s = st1.pressed_s

    within_grace = within_brake_grace(
        state=st1,
        now_s=float(time.monotonic()),
        grace_s=float(getattr(engine, "brake_handoff_grace_s", 2.0)),
    )

    banner_vm = compute_densi_banner_vm(
        estop_word=int(tick_result.estop_word), within_brake_grace=within_grace
    )
    estop_dots_vm = compute_densi_estop_dots_vm(
        bits=bits,
        taster=taster,
        ready=ready,
        within_brake_grace=within_grace,
    )

    return DensiViewModel(
        header_online=header_online,
        banner=banner_vm,
        estop_dots=estop_dots_vm,
        readouts=readouts_vm,
        cut_markers=cut_vm,
        lifetick=lifetick_vm,
        estop_word=int(tick_result.estop_word),
        refresh_checkboxes=bool(getattr(tick_result, "reset_able_changed", False))
        or bool(force_refresh_checkboxes),
        applied_param_values=dict(getattr(tick_result, "applied_param_values", {}) or {}),
    )
