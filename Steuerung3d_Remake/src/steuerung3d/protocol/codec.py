from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, Union

from steuerung3d.core.intents import (
    ArmLiveMode,
    ClearFault,
    DisarmToIdle,
    EnableAxis,
    Intent,
    JogAxis,
    SetEstop,
    RequestEstopReset,   # NEW
)

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame



# ---------------------------
# Intents
# ---------------------------

_INTENT_TYPE_MAP = {
    "enable_axis": EnableAxis,
    "jog_axis": JogAxis,
    "set_estop": SetEstop,
    "estop_reset": RequestEstopReset,   # NEW
    "arm_live_mode": ArmLiveMode,
    "disarm_to_idle": DisarmToIdle,
    "clear_fault": ClearFault,
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
    axes_in = payload["axes"]
    axes_out = {axis_id: AxisTelemetry(**ax) for axis_id, ax in axes_in.items()}
    return TelemetrySnapshot(
        tick=int(payload["tick"]),
        t_s=float(payload["t_s"]),
        mode=str(payload["mode"]),
        estop=bool(payload["estop"]),
        fault=bool(payload["fault"]),
        axes=axes_out,
        estop_status_word=int(payload.get("estop_status_word", 0)),  # NEW
    )

# ---------------------------
# CommandFrame
# ---------------------------

def encode_command_frame(frame: CommandFrame) -> Dict[str, Any]:
    # Keep it consistent with encode_intent / encode_telemetry: dict payload
    return asdict(frame)


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
    )