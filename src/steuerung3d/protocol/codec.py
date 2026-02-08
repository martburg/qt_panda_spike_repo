from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Union

from steuerung3d.protocol.raw_controls import RawControls

from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    Intent,
    JogAxis,
    JogWinch,
    JogCartesian,
    SetControlMode,
    SmoothStop,
    ClaimAxis,
    ReleaseAxis,
    SetEstop,
    RequestEstopReset,   # NEW
    ParamEditBegin,
    ParamWrite,
    ParamCancel,
    EchoLifeTick,
)

from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, ParamOp, decode_param_ops



# ---------------------------
# Intents
# ---------------------------

_INTENT_TYPE_MAP = {
    "enable_axis": EnableAxis,
    "jog_axis": JogAxis,
    "jog_winch": JogWinch,
    "jog_cartesian": JogCartesian,
    "set_control_mode": SetControlMode,
    "smooth_stop": SmoothStop,
    "claim_axis": ClaimAxis,
    "release_axis": ReleaseAxis,
    "set_estop": SetEstop,
    "estop_reset": RequestEstopReset,   # NEW
    "arm_live_mode": ArmLiveMode,
    "disarm_to_idle": DisarmToIdle,
    "clear_fault": ClearFault,
    # parameters (axis-agnostic)
    "param_edit_begin": ParamEditBegin,
    "param_write": ParamWrite,
    "param_cancel": ParamCancel,
    "echo_lifetick": EchoLifeTick,
}


def encode_intent(intent: Intent) -> Dict[str, Any]:
    return asdict(intent)


def decode_intent(payload: Dict[str, Any]) -> Intent:
    t = payload.get("type")
    if not isinstance(t, str):
        raise ValueError("intent payload missing 'type'")
    cls = _INTENT_TYPE_MAP.get(t)
    if cls is None:
        raise ValueError(f"unknown intent type: {t}")
    # dataclass ctor matches keys (including 'type')
    return cls(**payload)


# ---------------------------
# Telemetry
# ---------------------------

def encode_telemetry(snap: TelemetrySnapshot) -> Dict[str, Any]:
    return asdict(snap)


def decode_telemetry(payload: Dict[str, Any]) -> TelemetrySnapshot:
    # Axes
    axes_in = payload.get("axes", {})
    axes_out = {
        str(axis_id): AxisTelemetry(**ax) for axis_id, ax in dict(axes_in).items()
        if isinstance(ax, dict)
    }

    # DenSi registry (optional)
    densis_out: Dict[str, DensiTelemetry] = {}
    densis_in = payload.get("densis", {})
    if isinstance(densis_in, dict):
        for dev_id, d in densis_in.items():
            if isinstance(d, dict):
                try:
                    densis_out[str(dev_id)] = DensiTelemetry(**d)
                except Exception:
                    continue

    return TelemetrySnapshot(
        tick=int(payload.get("tick", 0)),
        t_s=float(payload.get("t_s", 0.0)),
        mode=str(payload.get("mode", "IDLE")),
        estop=bool(payload.get("estop", False)),
        fault=bool(payload.get("fault", False)),
        axes=axes_out,
        # rig workflow (optional)
        rig_mode=str(payload.get("rig_mode", "DISCOVERY")),
        densis=densis_out,
        # NEW
        estop_status_word=int(payload.get("estop_status_word", 0)),
        # parameters (optional)
        param_edit_active=bool(payload.get("param_edit_active", False)),
        param_edit_group=str(payload.get("param_edit_group", "")),
        params={k: float(v) for k, v in dict(payload.get("params", {})).items()},
        core_acks=[str(x) for x in list(payload.get("core_acks", []))],
        # observed param commit status (optional)
        param_commit_req_id=str(payload.get("param_commit_req_id", "")),
        param_commit_group=str(payload.get("param_commit_group", "")),
        param_commit_status=str(payload.get("param_commit_status", "idle")),
        param_commit_age_ticks=int(payload.get("param_commit_age_ticks", 0)),
        param_commit_unmatched=[str(x) for x in list(payload.get("param_commit_unmatched", []))],
    )


# ---------------------------
# RawControls (human input seam)
# ---------------------------

def encode_raw_controls(rc: RawControls) -> Dict[str, Any]:
    return asdict(rc)


def decode_raw_controls(payload: Dict[str, Any]) -> RawControls:
    # keep decoding resilient (older logs / missing keys)
    axes_in = payload.get("axes", [])
    buttons_in = payload.get("buttons", [])
    return RawControls(
        type=str(payload.get("type", "raw_controls")),
        t_ns=int(payload.get("t_ns", 0)),
        src=str(payload.get("src", "")),
        axes=[float(x) for x in list(axes_in)],
        buttons=[int(x) for x in list(buttons_in)],
    )

# ---------------------------
# CommandFrame
# ---------------------------

def encode_command_frame(frame: CommandFrame) -> Dict[str, Any]:
    # Custom encode to keep regression hashes stable when new optional fields
    # are empty (e.g. lifetick_echo).
    d = asdict(frame)
    # omit empty optional keys
    if not d.get("lifetick_echo"):
        d.pop("lifetick_echo", None)
    return d


def decode_command_frame(payload: Dict[str, Any]) -> CommandFrame:
    axes_in = payload["axes"]
    axes_out: Dict[str, AxisSetpoint] = {
        axis_id: AxisSetpoint(**ax) for axis_id, ax in axes_in.items()
    }
    return CommandFrame(
        tick=int(payload["tick"]),
        t_s=float(payload["t_s"]),
        estop=bool(payload["estop"]),
        fault=bool(payload["fault"]),
        mode=str(payload["mode"]),
        axes=axes_out,
        estop_reset=bool(payload.get("estop_reset", False)),  # NEW
        param_ops=decode_param_ops(payload.get("param_ops", [])),
        lifetick_echo={k: int(v) for k, v in dict(payload.get("lifetick_echo", {})).items()},
    )