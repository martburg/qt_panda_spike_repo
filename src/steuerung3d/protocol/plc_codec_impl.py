from __future__ import annotations

"""
Legacy PLC ';' delimited UDP codec (canonical: KommAnton__MAIN.st).

This codec exists to bridge between:
- wire format emitted/consumed by the Beckhoff PLC ST program (ASCII tokens separated by ';')
- internal Steuerung3D objects (TelemetrySnapshot, CommandFrame)

Design goals:
- tolerant parsing (missing/extra tokens)
- preserve canonical token ordering (see KommAnton__MAIN.st)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from steuerung3d.core.command_frame import CommandFrame, AxisSetpoint
from steuerung3d.core.telemetry import TelemetrySnapshot, AxisTelemetry

from steuerung3d.protocol.legacy_plc import parse_uplink, LegacyPlcUplink
from steuerung3d.protocol.plc_codec_fields import (
    DOWNLINK_BASE_FIELDS,
    DOWNLINK_WRITE_FIELDS,
    PARAM_KEYMAP as _PARAM_KEYMAP,
)
from steuerung3d.protocol.plc_codec_utils import bool_token as _bool_token
from steuerung3d.protocol.plc_codec_utils import fmt as _fmt
from steuerung3d.protocol.plc_codec_utils import to_float as _to_float
from steuerung3d.protocol.plc_codec_utils import to_int as _to_int




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
    axis_id = str(axis_id or "")

    sp = frame.axes.get(axis_id)
    enable_cmd = bool(sp.enable) if isinstance(sp, AxisSetpoint) else False
    vel = float(sp.vel) if isinstance(sp, AxisSetpoint) else 0.0
    # AxisSetpoint currently models velocity setpoints only; older PLC code also had pos.
    # Be defensive so PLC downlink encoding never crashes if the field is absent.
    pos = float(getattr(sp, 'pos', 0.0)) if isinstance(sp, AxisSetpoint) else 0.0
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
    guide_word = (4 if guider_reset else 0)

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
        "EStopReset": _bool_token(bool(getattr(frame, "estop_reset", False)), true_token, false_token),
        "ReSync": _bool_token(bool(getattr(frame, "resync", False)), true_token, false_token),
        "GUINotHaltIN": _bool_token(bool(getattr(frame, "gui_not_halt", False)), true_token, false_token),
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


# -----------------------------
# Uplink: PLC -> Controller
# -----------------------------
# We use the canonical ST ordering from legacy_plc.py. The tail fields include:
# SystemTime; CutPos; CutVel; PosWinUI; VelWinUI; AccTotUI; GuidePosManualMaxUI
# (see the ST send section near 'SystemTime', 'sCutPos', ...)

def decode_uplink_to_snapshot(payload: bytes) -> Optional[TelemetrySnapshot]:
    """Decode one PLC uplink telegram into a TelemetrySnapshot.

    Canonical uplink ordering is defined in protocol/legacy_plc.py (mirrors KommAnton__MAIN.st).
    """
    try:
        msg = payload.decode("utf-8", errors="ignore").strip()
        if not msg:
            return None
        upl = parse_uplink(msg)

        axis_name = (upl.fields.get("Name", "") or "X").strip() or "X"

        # Preserve entire uplink payload so HiP/UI can decide what to use.
        raw_fields = {str(k): str(v) for k, v in dict(upl.fields).items()}
        raw_tail = {str(k): str(v) for k, v in dict(upl.tail).items()}


        # --- Lifetick semantics (legacy) ---
        # Uplink field #1 = LifetickUItx (generated by device/DenSi)
        device_tick = _to_int(upl.fields.get("LifetickUItx", "0"), 0) & 0xFFFF

        # --- Time ---
        # Tail SystemTime is a numeric seconds value in the DenSi/PLC protocol.
        # Use it if present; otherwise fall back to an approximate seconds value from the lifetick.
        t_s = _to_float(upl.tail.get("SystemTime", ""), default=0.0)
        if t_s <= 0.0:
            t_s = float(device_tick) / 100.0

        # Snapshot tick: keep device_tick as the primary monotonically increasing counter from the device.
        tick = int(device_tick)

        # --- Basic axis state ---
        pos = _to_float(upl.fields.get("PosIst", "0"), 0.0)
        vel = _to_float(upl.fields.get("SpeedIstUI", "0"), 0.0)

        status_word = _to_int(upl.fields.get("Status", "0"), 0)
        guide_status_word = _to_int(upl.fields.get("GuideStatus", "0"), 0)

        estop_status_word = _to_int(upl.fields.get("EStopStatus", "0"), 0)

        # Active estop is defined by CAUSE bits (not by "word != 0", because OK/status bits can be set).
        try:
            from steuerung3d.protocol.estop_bits import decode_estop_word, ESTOP_CAUSE_KEYS
            estop_bits = decode_estop_word(int(estop_status_word))
            estop_active = any(bool(estop_bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
        except Exception:
            estop_active = bool(int(estop_status_word) != 0)

        ax = AxisTelemetry(
            pos=pos,
            vel=vel,
            enabled=False,
            fault=False,
            device_tick=int(device_tick),
            lifetick_rx=0,
            lifetick_age=0,
            status_word=int(status_word),
            guide_status_word=int(guide_status_word),
        )

        # --- Parameters ---
        # Map PLC token names -> internal param keys used by UI and param_registry.py
        plc_to_internal = {
            # pos
            "PosMaxHardUI": "HardMax",
            "PosMaxUserUI": "UserMax",
            "PosMinUserUI": "UserMin",
            "PosMinHardUI": "HardMin",
            # vel
            "SpeedMaxUI": "VelMax",
            "AccMaxUI": "AccMax",
            "DccMaxUI": "DccMax",
            "AmpMaxUI": "MaxAmp",
            "SpeedMaxforUI": "VelMaxMot",
            # filter
            "FilterP": "P",
            "FilterI": "I",
            "FilterD": "D",
            "FilterIL": "IL",
            "RampenformUI": "RampForm",
            # guider
            "GuidePitchUI": "Pitch",
            "GuidePosMaxUI": "PosMax",
            "GuidePosMinUI": "PosMin",
                    # measured / diagnostics (forwarded as params for UI convenience)
            "ActCurUI": "ActCur",
            "CabTemperatureUI": "Temp",
            "MotAuslastUI": "MotAuslast",
            "PosDiffForUI": "PosDiffFor",
            "GuidePosIstUI": "GuidePosIst",
            "GuideIstSpeedUI": "GuideIstSpeed",
        }
        tail_to_internal = {
            "PosWinUI": "PosWin",
            "VelWinUI": "VelWin",
            "AccTotUI": "AccMove",
                    "sCutPos": "CutPos",
            "sCutVel": "CutVel",
        }

        params: Dict[str, float] = {}

        for plc_k, internal_k in plc_to_internal.items():
            if plc_k in upl.fields:
                params[internal_k] = _to_float(upl.fields.get(plc_k, "0"), 0.0)

        for plc_k, internal_k in tail_to_internal.items():
            if plc_k in upl.tail:
                params[internal_k] = _to_float(upl.tail.get(plc_k, "0"), 0.0)

        snap = TelemetrySnapshot(
            tick=tick,
            t_s=float(t_s),
            core_mode="IDLE",
            estop=bool(estop_active),
            fault=False,
            axes={axis_name: ax},
            rig_mode="DISCOVERY",
            densis={},
            estop_status_word=int(estop_status_word),
            # parameters
            param_edit_active=False,
            param_edit_group="",
            params=params,
            plc_uplink_fields=raw_fields,
            plc_uplink_tail=raw_tail,
            core_acks=[],
            param_commit_req_id="",
            param_commit_group="",
            param_commit_status="idle",
            param_commit_age_ticks=0,
            param_commit_unmatched=[],
        )
        return snap
    except Exception:
        return None


def encode_uplink_from_snapshot(snap: TelemetrySnapshot, *, axis_name: str) -> bytes:
    """Encode a minimal but ST-compatible uplink telegram from a TelemetrySnapshot.

    This is primarily for DenSi SIM. Real PLCs generate this string in ST.
    """
    axis_name = str(axis_name or "X")
    ax = snap.axes.get(axis_name)
    pos = float(getattr(ax, "pos", 0.0)) if ax else 0.0
    vel = float(getattr(ax, "vel", 0.0)) if ax else 0.0
    amp = float(snap.params.get("Amp", 0.0)) if hasattr(snap, "params") else 0.0
    temp = float(snap.params.get("Temp", 0.0)) if hasattr(snap, "params") else 0.0

    # Basic status: start up in estop fault (caller controls snap.estop_status_word)
    estop_status = int(getattr(snap, "estop_status_word", 0) or 0)
    status_word = int(getattr(ax, "status_word", 0) or 0) if ax else 0
    guide_status_word = int(getattr(ax, "guide_status_word", 0) or 0) if ax else 0

    # Populate uplink fields using keys present in legacy_plc.parse_uplink.
    f: Dict[str, str] = {}
    def put(k: str, v: str) -> None:
        f[k] = v

    put("LifetickUIrx", "0")
    put("Modus", "E")
    put("OwnPID", "0")
    put("ControlPIDTx", "0")
    put("Intent", "")
    put("ControlIN", "0")
    put("GuideControlUI", "0")
    put("SpeedSollIN", _fmt(vel))
    put("GuideSollSpeedUI", "0")
    put("PosSoll", _fmt(pos))
    put("EStopReset", "0")
    put("ReSync", "0")
    put("GUINotHaltIN", "0")
    put("AccIN", "0")
    put("DccIN", "0")
    put("PosMaxHardUI", _fmt(float(snap.params.get("HardMax", 0.0))))
    put("PosMaxUserUI", _fmt(float(snap.params.get("UserMax", 0.0))))
    put("PosMinUserUI", _fmt(float(snap.params.get("UserMin", 0.0))))
    put("PosMinHardUI", _fmt(float(snap.params.get("HardMin", 0.0))))
    put("SpeedMaxUI", _fmt(float(snap.params.get("VelMax", 0.0))))
    put("AccMaxUI", _fmt(float(snap.params.get("AccMax", 0.0))))
    put("DccMaxUI", _fmt(float(snap.params.get("DccMax", 0.0))))
    put("AmpMaxUI", _fmt(float(snap.params.get("MaxAmp", 0.0))))
    put("FilterP", _fmt(float(snap.params.get("P", 0.0))))
    put("FilterI", _fmt(float(snap.params.get("I", 0.0))))
    put("FilterD", _fmt(float(snap.params.get("D", 0.0))))
    put("FilterIL", _fmt(float(snap.params.get("IL", 0.0))))
    put("RampForm", _fmt(float(snap.params.get("RampForm", 0.0))))
    put("GuidePosMaxUI", _fmt(float(snap.params.get("PosMax", 0.0))))
    put("GuidePosMinUI", _fmt(float(snap.params.get("PosMin", 0.0))))
    put("GuidePitchUI", _fmt(float(snap.params.get("Pitch", 0.0))))
    put("VelOrPos", "0")
    put("PosWinUI", _fmt(float(snap.params.get("PosWin", 0.0))))
    put("VelWinUI", _fmt(float(snap.params.get("VelWin", 0.0))))
    put("AccTotUI", _fmt(float(snap.params.get("AccMove", 0.0))))
    put("GuidePosManualMaxUI", "0")
    put("Name", axis_name)
    put("Status", str(status_word))
    put("StatusIst", str(status_word))
    put("PosIst", _fmt(pos))
    put("SpeedIstUI", _fmt(vel))
    put("AmpIst", _fmt(amp))
    put("TempIst", _fmt(temp))
    put("EStopStatus", str(estop_status))
    put("GuideStatus", str(guide_status_word))

    # Construct ordered tokens (same as legacy_plc.UPLINK_FIELDS order)
    upl_order = [
        "LifetickUIrx","Modus","OwnPID","ControlPIDTx","Intent","ControlIN","GuideControlUI",
        "SpeedSollIN","GuideSollSpeedUI","PosSoll","EStopReset","ReSync","GUINotHaltIN","AccIN","DccIN",
        "PosMaxHardUI","PosMaxUserUI","PosMinUserUI","PosMinHardUI","SpeedMaxUI","AccMaxUI","DccMaxUI","AmpMaxUI",
        "FilterP","FilterI","FilterD","FilterIL","RampForm","GuidePosMaxUI","GuidePosMinUI","GuidePitchUI","VelOrPos",
        "PosWinUI","VelWinUI","AccTotUI","GuidePosManualMaxUI","Name","Status","StatusIst","PosIst","SpeedIstUI","AmpIst",
        "TempIst","EStopStatus","GuideStatus",
    ]
    parts = [f.get(k, "0") for k in upl_order]
    # EOD marker and tail
    # In ST, EOD\ is embedded and then a ';' and tail fields are appended.
    line = ";".join(parts) + ";EOD\\;"
    # tail fields as in ST send: SystemTime; CutPos; CutVel; PosWinUI; VelWinUI; AccTotUI; GuidePosManualMaxUI;
    t_s = float(getattr(snap, "t_s", 0.0) or 0.0)
    tail = [
        _fmt(t_s),
        _fmt(float(snap.params.get("CutPos", 0.0))),
        _fmt(float(snap.params.get("CutVel", 0.0))),
        _fmt(float(snap.params.get("PosWin", 0.0))),
        _fmt(float(snap.params.get("VelWin", 0.0))),
        _fmt(float(snap.params.get("AccMove", 0.0))),
        _fmt(float(snap.params.get("GuidePosManualMaxUI", 0.0))),
    ]
    line += ";".join(tail) + ";"
    return line.encode("utf-8", errors="strict")
