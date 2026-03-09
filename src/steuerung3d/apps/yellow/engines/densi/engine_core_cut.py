"""Cut marker + stop-metric helpers for DenSiEngine."""

from __future__ import annotations

from typing import cast

from .cut_markers import (
    clear_cut_markers as _clear_cut_markers,
    maybe_latch_cut_markers as _maybe_latch_cut_markers,
)
from .engine_host_protocols import DenSiEngineHost
from .types import EStopState

ParamValue = float | str


def _state_params_store(host: DenSiEngineHost) -> dict[str, ParamValue]:
    return cast(dict[str, ParamValue], host.state.params)


class DenSiCutMarkersMixin:
    def _host(self) -> DenSiEngineHost:
        return cast(DenSiEngineHost, self)

    # ---------------------------------------------------------------------
    # cut markers
    # ---------------------------------------------------------------------

    def clear_cut_markers(self, *, reset_prev: bool = False) -> None:
        host = self._host()
        (
            host.cut_valid,
            host.cut_pos_m,
            host.cut_vel_mps,
            host.cut_time_s,
            host.systemtime_tok,
            host.prev_estop_state,
        ) = _clear_cut_markers(
            state=host.state,
            reset_prev=bool(reset_prev),
            prev_estop_state=bool(host.prev_estop_state),
        )

        host.stop_valid = False
        host.stop_pos_m = 0.0
        host.stop_time_s = 0.0
        host.posdiff_stop_m = 0.0
        host.prev_cause_active = False
        host.cause_edge = False

    def arm_cut_follow_live(self) -> None:
        host = self._host()
        axis_id = host.axis_ids[0] if host.axis_ids else ""
        ax0 = host.state.axes.get(axis_id) if axis_id else None
        pos = float(getattr(ax0, "pos", 0.0) or 0.0) if ax0 is not None else 0.0
        vel = float(getattr(ax0, "vel", 0.0) or 0.0) if ax0 is not None else 0.0

        host.cut_follow_live = True
        host.cut_valid = True
        host.cut_pos_m = pos
        host.cut_vel_mps = vel
        host.cut_time_s = float(getattr(host.state, "t_s", 0.0) or 0.0)
        host.systemtime_tok = host._now_token()

        host.stop_valid = False
        host.stop_pos_m = 0.0
        host.stop_time_s = 0.0
        host.posdiff_stop_m = 0.0
        host.prev_cause_active = False
        host.cause_edge = False

        try:
            params = _state_params_store(host)
            params["SystemTime"] = host.systemtime_tok
            params["CutPos"] = float(host.cut_pos_m)
            params["CutVel"] = float(host.cut_vel_mps)
            params["CutTime"] = float(host.cut_time_s)
            params["PosDiffFor"] = 0.0
            params["PosDiffStop"] = 0.0
        except Exception:
            pass

    def update_cut_follow_live(self) -> None:
        host = self._host()
        if not bool(host.cut_follow_live):
            return
        if bool(getattr(host.state, "estop", False)):
            host.cut_follow_live = False
            return

        axis_id = host.axis_ids[0] if host.axis_ids else ""
        ax0 = host.state.axes.get(axis_id) if axis_id else None
        if ax0 is None:
            return

        host.cut_valid = True
        host.cut_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
        host.cut_vel_mps = float(getattr(ax0, "vel", 0.0) or 0.0)
        host.cut_time_s = float(getattr(host.state, "t_s", 0.0) or 0.0)
        host.systemtime_tok = host._now_token()

        try:
            params = _state_params_store(host)
            params["SystemTime"] = host.systemtime_tok
            params["CutPos"] = float(host.cut_pos_m)
            params["CutVel"] = float(host.cut_vel_mps)
            params["CutTime"] = float(host.cut_time_s)
        except Exception:
            pass

    def maybe_latch_cut_markers(self, estop_edge: bool) -> None:
        host = self._host()
        (
            host.cut_valid,
            host.cut_pos_m,
            host.cut_vel_mps,
            host.cut_time_s,
            host.systemtime_tok,
        ) = _maybe_latch_cut_markers(
            state=host.state,
            axis_ids=list(host.axis_ids),
            estop_edge=bool(estop_edge),
            cut_valid=bool(host.cut_valid),
            now_token=host._now_token,
            cut_pos_m=float(host.cut_pos_m),
            cut_vel_mps=float(host.cut_vel_mps),
            cut_time_s=float(host.cut_time_s),
            systemtime_tok=str(host.systemtime_tok or ""),
        )

    def maybe_latch_stop_metrics(self) -> None:
        host = self._host()
        if (not bool(host.cut_valid)) or bool(host.stop_valid):
            return
        if host.estate != EStopState.STOPPING:
            return

        axis_id = host.axis_ids[0] if host.axis_ids else ""
        ax0 = host.state.axes.get(axis_id) if axis_id else None
        if ax0 is None:
            return

        v = float(getattr(ax0, "vel", 0.0) or 0.0)
        if abs(v) > 1e-3:
            return

        host.stop_valid = True
        host.stop_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
        host.stop_time_s = float(getattr(host.state, "t_s", 0.0) or 0.0)
        host.posdiff_stop_m = float(host.stop_pos_m) - float(host.cut_pos_m)

        try:
            params = _state_params_store(host)
            params["PosDiffStop"] = float(host.posdiff_stop_m)
            params["PosDiffFor"] = float(host.posdiff_stop_m)
        except Exception:
            pass
