"""Cut marker + stop-metric helpers for DenSiEngine."""

from __future__ import annotations

from .cut_markers import (
    clear_cut_markers as _clear_cut_markers,
    maybe_latch_cut_markers as _maybe_latch_cut_markers,
)
from .types import EStopState


class DenSiCutMarkersMixin:
    # ---------------------------------------------------------------------
    # cut markers
    # ---------------------------------------------------------------------

    def clear_cut_markers(self, *, reset_prev: bool = False) -> None:
        (
            self.cut_valid,
            self.cut_pos_m,
            self.cut_vel_mps,
            self.cut_time_s,
            self.systemtime_tok,
            self.prev_estop_state,
        ) = _clear_cut_markers(
            state=self.state,
            reset_prev=bool(reset_prev),
            prev_estop_state=bool(self.prev_estop_state),
        )

        # Stop metrics are cleared on ReSync together with the cut markers.
        self.stop_valid = False
        self.stop_pos_m = 0.0
        self.stop_time_s = 0.0
        self.posdiff_stop_m = 0.0

        # ReSync / clear also resets the cause edge detector.
        self.prev_cause_active = False
        self.cause_edge = False

    def arm_cut_follow_live(self) -> None:
        """Arm live cut baseline tracking (HiP ReSync)."""
        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        pos = float(getattr(ax0, "pos", 0.0) or 0.0) if ax0 is not None else 0.0
        vel = float(getattr(ax0, "vel", 0.0) or 0.0) if ax0 is not None else 0.0

        self.cut_follow_live = True
        self.cut_valid = True
        self.cut_pos_m = pos
        self.cut_vel_mps = vel
        self.cut_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
        self.systemtime_tok = self._now_token()

        # Clear stop metrics on ReSync.
        self.stop_valid = False
        self.stop_pos_m = 0.0
        self.stop_time_s = 0.0
        self.posdiff_stop_m = 0.0

        # Reset cause-edge detector so the next real cause edge will freeze markers.
        self.prev_cause_active = False
        self.cause_edge = False

        try:
            self.state.params["SystemTime"] = self.systemtime_tok
            self.state.params["CutPos"] = float(self.cut_pos_m)
            self.state.params["CutVel"] = float(self.cut_vel_mps)
            self.state.params["CutTime"] = float(self.cut_time_s)
            # PosDiffFor is reserved for CutMarker diff (pos - CutPos).
            self.state.params["PosDiffFor"] = 0.0
            self.state.params["PosDiffStop"] = 0.0
        except Exception:
            pass

    def update_cut_follow_live(self) -> None:
        """If armed, keep CutPos/CutVel tracking actual axis pos/vel."""
        if not bool(self.cut_follow_live):
            return
        if bool(getattr(self.state, "estop", False)):
            # Freeze immediately on entry into E-Stop (and remain frozen).
            self.cut_follow_live = False
            return

        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        if ax0 is None:
            return

        self.cut_valid = True
        self.cut_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
        self.cut_vel_mps = float(getattr(ax0, "vel", 0.0) or 0.0)
        self.cut_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
        self.systemtime_tok = self._now_token()

        try:
            self.state.params["SystemTime"] = self.systemtime_tok
            self.state.params["CutPos"] = float(self.cut_pos_m)
            self.state.params["CutVel"] = float(self.cut_vel_mps)
            self.state.params["CutTime"] = float(self.cut_time_s)
        except Exception:
            pass

    def maybe_latch_cut_markers(self, estop_edge: bool) -> None:
        (
            self.cut_valid,
            self.cut_pos_m,
            self.cut_vel_mps,
            self.cut_time_s,
            self.systemtime_tok,
        ) = _maybe_latch_cut_markers(
            state=self.state,
            axis_ids=list(self.axis_ids),
            estop_edge=bool(estop_edge),
            cut_valid=bool(self.cut_valid),
            now_token=self._now_token,
            cut_pos_m=float(self.cut_pos_m),
            cut_vel_mps=float(self.cut_vel_mps),
            cut_time_s=float(self.cut_time_s),
            systemtime_tok=str(self.systemtime_tok or ""),
        )

    def maybe_latch_stop_metrics(self) -> None:
        """Latch stop distance once the coastdown reaches v~=0."""

        if (not bool(self.cut_valid)) or bool(self.stop_valid):
            return
        if self.estate != EStopState.STOPPING:
            return

        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        if ax0 is None:
            return

        v = float(getattr(ax0, "vel", 0.0) or 0.0)
        if abs(v) > 1e-3:
            return

        self.stop_valid = True
        self.stop_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
        self.stop_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
        self.posdiff_stop_m = float(self.stop_pos_m) - float(self.cut_pos_m)

        try:
            self.state.params["PosDiffStop"] = float(self.posdiff_stop_m)
            # Keep Hip/legacy panels consistent: PosDiffFor is what they display.
            self.state.params["PosDiffFor"] = float(self.posdiff_stop_m)
        except Exception:
            pass
