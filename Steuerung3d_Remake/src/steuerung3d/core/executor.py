from __future__ import annotations

from typing import Dict, Any

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState

from steuerung3d.core.controllers.legacy_twincat_fsm import LegacyTwinCATAxisFSM, LegacyTwinCATFsmConfig, ST_READY, ST_ENABLING, ST_ACTIVE
from steuerung3d.core.axis_types import AxisRequest, AxisTelemetry as LegacyAxisTelemetry



def build_command_frame(state: MachineState) -> CommandFrame:
    axes: Dict[str, AxisSetpoint] = {
        axis_id: AxisSetpoint(enable=cmd.enable, vel=cmd.vel)
        for axis_id, cmd in state.axis_cmd.items()
    }
    return CommandFrame(
        tick=state.tick,
        t_s=state.t_s,
        estop=state.estop,
        fault=state.fault,
        mode=state.mode.value,
        axes=axes,
    )

def _legacy_tel_or_default(ax, axis_id: str) -> LegacyAxisTelemetry:
    tel = ax.tel
    if isinstance(tel, LegacyAxisTelemetry):
        return tel
    # default until first uplink
    return LegacyAxisTelemetry(
        link_ok=False,
        name=axis_id,
        own_pid_rx="",
        lifetick_tx=0,
        status_word=0,
        guide_status_word=0,
        estop_status_dword=0,
        system_time="",
        pos_ist=ax.pos,
        vel_ist=ax.vel,
        estop_active=False,
        fault_active=ax.fault,
        enabled=ax.enabled,
    )

def drive_legacy_axis_fsms(state: MachineState) -> None:
    for axis_id, cmd_state in state.axis_cmd.items():
        ax = state.ensure_axis(axis_id)

        if getattr(ax, "kind", "generic") != "legacy_twincat":
            ax.meta.setdefault("fsm_state", "skipped_non_legacy")
            continue

        if axis_id not in state.axis_fsm:
            state.axis_fsm[axis_id] = LegacyTwinCATAxisFSM(
                LegacyTwinCATFsmConfig(controller_pid=str(getattr(state, "controller_pid", "4711")))
            )

        tel = _legacy_tel_or_default(ax, axis_id)

        requested_enable = bool(cmd_state.enable),

        # --- no intents yet: safe default request ---
        req = AxisRequest(
            want_claim=True,
            want_enable = requested_enable and (not state.estop) and (not state.fault),
            want_motion=False,
            want_resync=False,
            want_reset_estop=False,
            cmd_speed=0.0,
            cmd_pos=ax.pos,   # nice: keep pos_soll aligned if you later use it
            write_params=False,
        )

        fsm: LegacyTwinCATAxisFSM = state.axis_fsm[axis_id]
        _cmd = fsm.step(tel, req)   # we ignore AxisCommand for now (phase 2)

        # Minimal mapping into existing CommandFrame model:
        # treat "claimed/ready states" as permission to enable (still gated by safety)
        allow_enable = fsm.state in ( ST_READY, ST_ENABLING, ST_ACTIVE)
        cmd_state.enable = bool(req.want_enable and allow_enable)
        cmd_state.vel = float(req.cmd_speed) if cmd_state.enable else 0.0

        # debug visibility
        ax.meta["fsm_state"] = fsm.state
        ax.meta["tel_link_ok"] = bool(tel.link_ok)
        ax.meta["tel_own_pid_rx"] = tel.own_pid_rx
