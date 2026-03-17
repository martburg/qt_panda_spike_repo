from __future__ import annotations

import os
from typing import Any, Callable

from steuerung3d.protocol.udp_plc_coerce import to_bool_token, to_float, to_int
from steuerung3d.protocol.udp_plc_frame_support import (
    PARAM_GROUP_DEFAULTS,
    extract_param_write_values,
    frame_axis_id,
    frame_lifetick_ui_rx,
    frame_param_map,
)

BytesDecoder = Callable[[bytes], Any]
FrameEncoder = Callable[..., bytes]


def load_uplink_decoder() -> BytesDecoder | None:
    try:
        from steuerung3d.protocol.plc_codec import decode_uplink_to_snapshot
    except Exception:
        return None
    return decode_uplink_to_snapshot


def load_downlink_decoder() -> tuple[Any, Any, Any, Any, Any] | None:
    try:
        from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, ParamWriteOp
        from steuerung3d.protocol.plc_codec import _PARAM_KEYMAP, decode_downlink
    except Exception:
        return None
    return AxisSetpoint, CommandFrame, ParamWriteOp, _PARAM_KEYMAP, decode_downlink


def load_downlink_encoder() -> FrameEncoder | None:
    try:
        from steuerung3d.protocol.plc_codec import encode_downlink
    except Exception:
        return None
    return encode_downlink


def iter_decoded_snapshots(raw_items: list[bytes], decoder: BytesDecoder | None) -> list[Any]:
    out: list[Any] = []
    if decoder is None:
        return out
    for raw in raw_items:
        try:
            snap = decoder(raw)
        except Exception:
            continue
        if snap is not None:
            out.append(snap)
    return out


def decode_command_fields(fields: dict[str, Any], *, axis_id: str) -> dict[str, Any]:
    tick_ui_rx = to_int(fields.get("LifetickUIrx", "0"), 0)
    resync = bool(to_bool_token(fields.get("ReSync", "False"), False))
    return {
        "tick_ui_rx": tick_ui_rx,
        "vel": to_float(fields.get("SpeedSollIN", "0"), 0.0),
        "enable": to_bool_token(fields.get("ControlIN", "False"), False),
        "intent": bool(to_bool_token(fields.get("Intent", "True"), True)),
        "resync": resync,
        "gui_not_halt": bool(to_bool_token(fields.get("GUINotHaltIN", "False"), False)),
        "estop_reset": to_bool_token(fields.get("EStopReset", "False"), False),
        "core_mode": str(fields.get("CoreMode", "") or ""),
        "lifetick_echo": {axis_id: tick_ui_rx},
        "resync_by_axis": {axis_id: True} if resync else {},
    }


def extract_param_ops(
    fields: dict[str, Any], *, param_keymap: Any, param_write_op_type: Any
) -> list[Any]:
    param_ops: list[Any] = []
    modus = str(fields.get("Modus", "") or "").strip().lower()
    if modus != "w":
        return param_ops
    for group, values in extract_param_write_values(
        fields,
        group_defaults=PARAM_GROUP_DEFAULTS,
        param_keymap=param_keymap,
    ):
        param_ops.append(param_write_op_type(group=group, values=values))
    return param_ops


def encode_command_payload(frame: Any, *, encode_downlink: FrameEncoder) -> bytes:
    axis_id = frame_axis_id(frame)
    lifetick_ui_rx = frame_lifetick_ui_rx(frame, axis_id)
    params = frame_param_map(frame)
    return encode_downlink(
        axis_id=axis_id,
        frame=frame,
        pid=str(os.getpid()),
        lifetick_ui_rx=int(lifetick_ui_rx),
        params=params or None,
    )
