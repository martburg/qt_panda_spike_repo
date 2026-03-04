"""Tick pipeline helpers for DenSiEngine.

Most semantics live in :mod:`step_impl` and are invoked via :meth:`DenSiEngine.step`.
"""

from __future__ import annotations

from steuerung3d.core.command_frame import CommandFrame

from .motion_clamp import apply_estop_clamp_to_state, compute_moving_guard
from .param_ops import apply_densi_param_ops
from .plc_anton_vel_cmd import step_plc_anton_vel_cmd
from .resync import handle_resync_cmd as _handle_resync_cmd
from .setpoint_semantics import normalize_cmd_for_plant
from .step_impl import step as _step
from .types import L0Sub, L0Top


class DenSiPipelineMixin:
    # ---------------------------------------------------------------------
    # step pipeline
    # ---------------------------------------------------------------------

    def ensure_last_cmd(self) -> CommandFrame:
        if self.last_cmd is None:
            self.last_cmd = CommandFrame(
                tick=int(self.state.tick),
                t_s=float(self.state.t_s),
                estop=False,
                fault=False,
                core_mode=getattr(self.state, "core_mode", ""),
                axes={},
                estop_reset=False,
            )
        # last_cmd is always a CommandFrame after first call.
        return self.last_cmd  # type: ignore[return-value]

    def rx_command_frames(self, frames: list[CommandFrame], now_ns: int) -> int:
        if frames:
            self.last_cmd = frames[-1]
            self.last_cmd_ns = int(now_ns)
            self.seen_first_cmd = True
        return int(len(frames))

    def update_l0_connection_state(self, now_ns: int) -> None:
        if not bool(self.seen_first_cmd):
            self.l0_top = L0Top.START
            self.l0_sub = L0Sub.IDLE
        else:
            if self.last_cmd_ns is not None:
                age_s = (int(now_ns) - int(self.last_cmd_ns)) / 1e9
                if age_s > float(self.disconnect_after_s):
                    self.l0_top = L0Top.START
                    self.l0_sub = L0Sub.IDLE
                else:
                    self.l0_top = L0Top.CONNECTED
            else:
                self.l0_top = L0Top.CONNECTED

        try:
            self.state.params["DenSiL0Top"] = self.l0_top.name
            self.state.params["DenSiL0Sub"] = self.l0_sub.name
        except Exception:
            pass

    def compute_moving_guard(self) -> bool:
        return compute_moving_guard(state=self.state, axis_ids=list(self.axis_ids))

    def handle_resync_cmd(self) -> None:
        cmd = self.ensure_last_cmd()
        _handle_resync_cmd(
            cmd=cmd,
            l0_top=self.l0_top,
            clear_cut_markers=lambda reset_prev: self.clear_cut_markers(reset_prev=reset_prev),
            arm_cut_follow_live=self.arm_cut_follow_live,
        )

    def apply_param_ops(self, ready_for_sollvel: bool, moving: bool) -> dict[str, float]:
        cmd = self.ensure_last_cmd()
        allow_param_ops = (
            self.l0_top == L0Top.CONNECTED
            and (not bool(ready_for_sollvel))
            and (not bool(moving))
        )

        res = apply_densi_param_ops(
            state=self.state,
            param_ops=getattr(cmd, "param_ops", []) or [],
            allow=allow_param_ops,
            normalize_pos_chain=self.normalize_pos_chain,
            normalize_guider_range=self.normalize_guider_range,
            enforce_pos_chain=self.enforce_pos_chain,
            enforce_guider_minmax=self.enforce_guider_minmax,
        )
        return dict(res.applied_values or {})

    def step_plant_with_clamp(self) -> None:
        """PLC-faithful DenSi behavior (Anton): see docs/anton_vel_cmd_implementation_step.md"""

        cmd = self.ensure_last_cmd()
        cmd_for_plant = normalize_cmd_for_plant(
            cmd,
            state=self.state,
            dt_s=float(self.tb.dt_s),
            axis_ids=list(self.axis_ids),
            drive_ready=bool(self.drive_ready),
        )
        params = dict(getattr(self.state, "params", {}) or {})
        ramp_mode_ok = bool(int(params.get("RampModeOk", params.get("DriveModeOk", 1)) or 0))
        deadman_active = bool(getattr(getattr(self.state, "joy", None), "deadman", False))

        step_plc_anton_vel_cmd(
            state=self.state,
            cmd=cmd_for_plant,
            dt_s=float(self.tb.dt_s),
            axis_ids=list(self.axis_ids),
            ready_for_sollvel=bool(self.drive_ready),
            lifetick_stale_after_ticks_active=int(self.lifetick_stale_after_ticks_active),
            lifetick_stale_after_ticks_idle=int(self.lifetick_stale_after_ticks_idle),
            deadman_active=bool(deadman_active),
            ramp_mode_ok=bool(ramp_mode_ok),
        )

    def apply_estop_clamp_to_state(self) -> None:
        apply_estop_clamp_to_state(state=self.state)

    def advance_tick(self) -> None:
        self.state.tick += 1
        self.state.t_s += float(self.tb.dt_s)
        self.prev_estop_state = bool(self.state.estop)

    def step(self, *, frames: list[CommandFrame], now_ns: int):
        return _step(engine=self, frames=frames, now_ns=now_ns)
