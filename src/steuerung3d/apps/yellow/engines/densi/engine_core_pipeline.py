"""Tick pipeline helpers for DenSiEngine.

Most semantics live in :mod:`step_impl` and are invoked via :meth:`DenSiEngine.step`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from steuerung3d.core.command_frame import CommandFrame

from .engine_host_protocols import DenSiEngineHost
from .motion_clamp import apply_estop_clamp_to_state, compute_moving_guard
from .param_ops import apply_densi_param_ops
from .plc_anton_vel_cmd import step_plc_anton_vel_cmd
from .resync import handle_resync_cmd as _handle_resync_cmd
from .setpoint_semantics import normalize_cmd_for_plant
from .step_impl import step as _step
from .types import L0Sub, L0Top

ParamValue = float | str


def _identity_param_map(values: Mapping[str, float]) -> dict[str, float]:
    return {str(k): float(v) for k, v in values.items()}


def _state_params_store(host: DenSiEngineHost) -> dict[str, ParamValue]:
    return cast(dict[str, ParamValue], host.state.params)


class DenSiPipelineMixin:
    def _host(self) -> DenSiEngineHost:
        return cast(DenSiEngineHost, self)

    # ---------------------------------------------------------------------
    # step pipeline
    # ---------------------------------------------------------------------

    def ensure_last_cmd(self) -> CommandFrame:
        host = self._host()
        if host.last_cmd is None:
            host.last_cmd = CommandFrame(
                tick=int(host.state.tick),
                t_s=float(host.state.t_s),
                estop=False,
                fault=False,
                core_mode=getattr(host.state, "core_mode", ""),
                axes={},
                estop_reset=False,
            )
        return host.last_cmd

    def rx_command_frames(self, frames: list[CommandFrame], now_ns: int) -> int:
        host = self._host()
        if frames:
            host.last_cmd = frames[-1]
            host.last_cmd_ns = int(now_ns)
            host.seen_first_cmd = True
        return int(len(frames))

    def update_l0_connection_state(self, now_ns: int) -> None:
        host = self._host()
        if not bool(host.seen_first_cmd):
            host.l0_top = L0Top.START
            host.l0_sub = L0Sub.IDLE
        else:
            if host.last_cmd_ns is not None:
                age_s = (int(now_ns) - int(host.last_cmd_ns)) / 1e9
                if age_s > float(host.disconnect_after_s):
                    host.l0_top = L0Top.START
                    host.l0_sub = L0Sub.IDLE
                else:
                    host.l0_top = L0Top.CONNECTED
            else:
                host.l0_top = L0Top.CONNECTED

        try:
            params = _state_params_store(host)
            params["DenSiL0Top"] = host.l0_top.name
            params["DenSiL0Sub"] = host.l0_sub.name
        except Exception:
            pass

    def compute_moving_guard(self) -> bool:
        host = self._host()
        return compute_moving_guard(state=host.state, axis_ids=list(host.axis_ids))

    def handle_resync_cmd(self) -> None:
        host = self._host()
        cmd = host.ensure_last_cmd()
        _handle_resync_cmd(
            cmd=cmd,
            l0_top=host.l0_top,
            clear_cut_markers=lambda reset_prev: host.clear_cut_markers(reset_prev=reset_prev),
            arm_cut_follow_live=host.arm_cut_follow_live,
        )

    def apply_param_ops(self, ready_for_sollvel: bool, moving: bool) -> dict[str, float]:
        host = self._host()
        cmd = host.ensure_last_cmd()
        allow_param_ops = (
            host.l0_top == L0Top.CONNECTED and (not bool(ready_for_sollvel)) and (not bool(moving))
        )

        normalize_pos_chain = host.normalize_pos_chain or _identity_param_map
        normalize_guider_range = host.normalize_guider_range or _identity_param_map
        enforce_pos_chain = host.enforce_pos_chain or _identity_param_map
        enforce_guider_minmax = host.enforce_guider_minmax or _identity_param_map

        res = apply_densi_param_ops(
            state=host.state,
            param_ops=getattr(cmd, "param_ops", []) or [],
            allow=allow_param_ops,
            normalize_pos_chain=normalize_pos_chain,
            normalize_guider_range=normalize_guider_range,
            enforce_pos_chain=enforce_pos_chain,
            enforce_guider_minmax=enforce_guider_minmax,
        )
        return dict(res.applied_values or {})

    def step_plant_with_clamp(self) -> None:
        """PLC-faithful DenSi behavior (Anton): see docs/anton_vel_cmd_implementation_step.md"""

        host = self._host()
        cmd = host.ensure_last_cmd()
        cmd_for_plant = normalize_cmd_for_plant(
            cmd,
            state=host.state,
            dt_s=float(host.tb.dt_s),
            axis_ids=list(host.axis_ids),
            drive_ready=bool(host.drive_ready),
        )
        params = dict(getattr(host.state, "params", {}) or {})
        ramp_mode_ok = bool(int(params.get("RampModeOk", params.get("DriveModeOk", 1)) or 0))
        deadman_active = bool(getattr(getattr(host.state, "joy", None), "deadman", False))

        step_plc_anton_vel_cmd(
            state=host.state,
            cmd=cmd_for_plant,
            dt_s=float(host.tb.dt_s),
            axis_ids=list(host.axis_ids),
            ready_for_sollvel=bool(host.drive_ready),
            lifetick_stale_after_ticks_active=int(host.lifetick_stale_after_ticks_active),
            lifetick_stale_after_ticks_idle=int(host.lifetick_stale_after_ticks_idle),
            deadman_active=bool(deadman_active),
            ramp_mode_ok=bool(ramp_mode_ok),
        )

    def apply_estop_clamp_to_state(self) -> None:
        host = self._host()
        apply_estop_clamp_to_state(state=host.state)

    def advance_tick(self) -> None:
        host = self._host()
        host.state.tick += 1
        host.state.t_s += float(host.tb.dt_s)
        host.prev_estop_state = bool(host.state.estop)

    def step(self, *, frames: list[CommandFrame], now_ns: int) -> object:
        return _step(engine=self, frames=frames, now_ns=now_ns)
