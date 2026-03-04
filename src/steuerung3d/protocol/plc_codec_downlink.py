"""Legacy PLC downlink codec (Controller -> PLC).

Split out of plc_codec_impl.py as a Lane-1 refactor (no semantic changes).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from steuerung3d.core.axis_id import normalize_axis_id
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.protocol.plc_codec_fields import (
    DOWNLINK_BASE_FIELDS,
    DOWNLINK_WRITE_FIELDS,
    PARAM_KEYMAP as _PARAM_KEYMAP,
)
from steuerung3d.protocol.plc_codec_utils import bool_token as _bool_token, fmt as _fmt


def encode_downlink(
    *,
    axis_id: str,
    frame: CommandFrame,
    pid: str = "0",
    lifetick_ui_rx: int = 0,
    params: Optional[Dict[str, float]] = None,
    true_token: str = "True",
    false_token: str = "False",
) -> bytes:
    """Encode one downlink telegram for one axis (ASCII ';' delimited).

    Note: Many legacy fields exist; we populate what we can and send zeros for the rest.
    """
    params = dict(params or {})
    axis_id = normalize_axis_id(axis_id)

    sp = frame.axes.get(axis_id)
    enable_cmd = bool(sp.enable) if isinstance(sp, AxisSetpoint) else False
    vel = float(sp.vel) if isinstance(sp, AxisSetpoint) else 0.0
    # AxisSetpoint currently models velocity setpoints only; older PLC code also had pos.
    # Be defensive so PLC downlink encoding never crashes if the field is absent.
    pos = float(getattr(sp, "pos", 0.0)) if isinstance(sp, AxisSetpoint) else 0.0
    # Write-mode is entered only when we actually have write values to send.
    # (HiP may send other param-related intents that should NOT switch the PLC parser into write mode.)
    want_write = bool(params)
    modus = "w" if want_write else "E"

    # base fields
    # Apply global safety gating to the legacy ControlIN and setpoints.
    enable = bool(enable_cmd) and (not bool(frame.estop)) and (not bool(frame.fault))
    vel_eff = float(vel) if enable else 0.0

    intent = bool(getattr(frame, "intent", True))

    main_reset = False
    guider_reset = False
    try:
        main_reset = bool(getattr(frame, "main_reset_by_axis", {}).get(axis_id, False))
    except Exception:
        main_reset = False
    try:
        guider_reset = bool(getattr(frame, "guider_reset_by_axis", {}).get(axis_id, False))
    except Exception:
        guider_reset = False

    # Legacy bitfields (mirrors ST extract):
    #   ControlIN bit0 = enable; bit6 = main amplifier reset
    #   GuideControlUI bit2 = guider amplifier reset
    control_word = (1 if enable else 0) | (64 if main_reset else 0)
    guide_word = 4 if guider_reset else 0

    base: Dict[str, str] = {
        "LifetickUIrx": str(int(lifetick_ui_rx)),
        "Modus": modus,
        "OwnPID": str(pid),
        "ControlPIDTx": str(pid),
        "Intent": _bool_token(intent, true_token, false_token),
        "ControlIN": str(int(control_word)),
        "GuideControlUI": str(int(guide_word)),
        "SpeedSollIN": _fmt(vel_eff),
        "GuideSollSpeedUI": "0",
        "PosSoll": _fmt(pos),
        "EStopReset": _bool_token(
            bool(getattr(frame, "estop_reset", False)), true_token, false_token
        ),
        "ReSync": _bool_token(bool(getattr(frame, "resync", False)), true_token, false_token),
        "GUINotHaltIN": _bool_token(
            bool(getattr(frame, "gui_not_halt", False)), true_token, false_token
        ),
    }

    parts: List[str] = [base.get(k, "0") for k in DOWNLINK_BASE_FIELDS]

    if modus == "w":
        # start with defaults
        w: Dict[str, str] = {k: "0" for k in DOWNLINK_WRITE_FIELDS}
        # add writes from params
        for internal_k, val in params.items():
            plc_k = _PARAM_KEYMAP.get(internal_k)
            if plc_k and plc_k in w:
                w[plc_k] = _fmt(float(val))
        # typical live UI fields
        w["AccIN"] = _fmt(float(params.get("AccIN", 0.0)))
        w["DccIN"] = _fmt(float(params.get("DccIN", 0.0)))
        w["VelOrPos"] = str(int(params.get("VelOrPos", 0)))
        parts.extend([w.get(k, "0") for k in DOWNLINK_WRITE_FIELDS])

    line = ";".join(parts) + ";"
    return line.encode("utf-8", errors="strict")


@dataclass
class DecodedDownlink:
    tokens: List[str]
    fields: Dict[str, str]
    is_write: bool


def decode_downlink(payload: bytes) -> Optional[DecodedDownlink]:
    """Parse a downlink telegram into a dict of fields."""
    try:
        s = payload.decode("utf-8", errors="ignore").strip()
        if not s:
            return None
        toks = [t.strip() for t in s.split(";")]
        if toks and toks[-1] == "":
            toks = toks[:-1]
        fields: Dict[str, str] = {}
        for i, k in enumerate(DOWNLINK_BASE_FIELDS):
            if i < len(toks):
                fields[k] = toks[i]
        is_write = fields.get("Modus", "") == "w"
        if is_write:
            offset = len(DOWNLINK_BASE_FIELDS)
            for j, k in enumerate(DOWNLINK_WRITE_FIELDS):
                idx = offset + j
                if idx < len(toks):
                    fields[k] = toks[idx]
        return DecodedDownlink(tokens=toks, fields=fields, is_write=is_write)
    except Exception:
        return None
