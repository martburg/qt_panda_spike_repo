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

# -----------------------------
# Downlink: Controller -> PLC
# -----------------------------
# Token order (matches ST parsing order).
DOWNLINK_BASE_FIELDS = [
    "LifetickUIrx",       # 0
    "Modus",              # 1  (e.g. 'E' normal, 'w' write params)
    "OwnPID",             # 2
    "ControlPIDTx",       # 3
    "Intent",             # 4
    "ControlIN",          # 5
    "GuideControlUI",     # 6
    "SpeedSollIN",        # 7
    "GuideSollSpeedUI",   # 8
    "PosSoll",            # 9
    "EStopReset",         # 10
    "ReSync",             # 11
    "GUINotHaltIN",       # 12
]

DOWNLINK_WRITE_FIELDS = [
    "AccIN",              # 13
    "DccIN",              # 14
    "PosMaxHardUI",       # 15
    "PosMaxUserUI",       # 16
    "PosMinUserUI",       # 17
    "PosMinHardUI",       # 18
    "SpeedMaxUI",         # 19
    "AccMaxUI",           # 20
    "DccMaxUI",           # 21
    "AmpMaxUI",           # 22
    "FilterP",            # 23
    "FilterI",            # 24
    "FilterD",            # 25
    "FilterIL",           # 26
    "GuidePitchUI",       # 27
    "GuidePosMaxUI",      # 28
    "GuidePosMinUI",      # 29
    "VelOrPos",           # 30
    "PosWinUI",           # 31
    "VelWinUI",           # 32
    "AccTotUI",           # 33
]

_PARAM_KEYMAP = {
    # internal -> PLC token name (write extension)
    "HardMax": "PosMaxHardUI",
    "UserMax": "PosMaxUserUI",
    "UserMin": "PosMinUserUI",
    "HardMin": "PosMinHardUI",
    "VelMax": "SpeedMaxUI",
    "AccMax": "AccMaxUI",
    "DccMax": "DccMaxUI",
    "MaxAmp": "AmpMaxUI",
    "P": "FilterP",
    "I": "FilterI",
    "D": "FilterD",
    "IL": "FilterIL",
    "Pitch": "GuidePitchUI",
    "PosMax": "GuidePosMaxUI",
    "PosMin": "GuidePosMinUI",
    "PosWin": "PosWinUI",
    "VelWin": "VelWinUI",
    "AccMove": "AccTotUI",
}

def _to_float(s: str, default: float = 0.0) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default

def _to_int(s: str, default: int = 0) -> int:
    try:
        return int(float(str(s).strip()))
    except Exception:
        return default

def _fmt(x: float) -> str:
    # Keep compact but stable formatting.
    # PLC uses LREAL/REAL parsing with '.' decimal.
    return f"{float(x):.6g}"

def encode_downlink(
    *,
    axis_id: str,
    frame: CommandFrame,
    pid: str = "0",
    lifetick_ui_rx: int = 0,
    params: Optional[Dict[str, float]] = None,
) -> bytes:
    """Encode one downlink telegram for one axis (ASCII ';' delimited).

    Note: Many legacy fields exist; we populate what we can and send zeros for the rest.
    """
    params = dict(params or {})
    axis_id = str(axis_id or "")

    sp = frame.axes.get(axis_id)
    vel = float(sp.vel) if isinstance(sp, AxisSetpoint) else 0.0
    # AxisSetpoint currently models velocity setpoints only; older PLC code also had pos.
    # Be defensive so PLC downlink encoding never crashes if the field is absent.
    pos = float(getattr(sp, 'pos', 0.0)) if isinstance(sp, AxisSetpoint) else 0.0

    # crude: treat presence of param_ops as write-mode. Caller can override by setting frame.mode etc later.
    want_write = bool(getattr(frame, "param_ops", None))
    modus = "w" if want_write else "E"

    # base fields
    base: Dict[str, str] = {
        "LifetickUIrx": str(int(lifetick_ui_rx)),
        "Modus": modus,
        "OwnPID": str(pid),
        "ControlPIDTx": str(pid),
        "Intent": "",                 # not yet modeled
        "ControlIN": "0",
        "GuideControlUI": "0",
        "SpeedSollIN": _fmt(vel),
        "GuideSollSpeedUI": "0",
        "PosSoll": _fmt(pos),
        "EStopReset": "1" if bool(getattr(frame, "estop_reset", False)) else "0",
        "ReSync": "1" if bool(getattr(frame, "resync", False)) else "0",
        "GUINotHaltIN": "0",
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
    try:
        msg = payload.decode("utf-8", errors="ignore").strip()
        if not msg:
            return None
        upl = parse_uplink(msg)
        name = upl.fields.get("Name", "") or "X"

        # Time: prefer tail SystemTime if present
        t_s = _to_float(upl.tail.get("SystemTime", ""), default=_to_float(upl.fields.get("SystemTime", ""), 0.0))
        tick = int(round(t_s * 100.0)) if t_s > 0 else _to_int(upl.fields.get("LifetickUItx", "0"), 0)

        # Basic axis state
        pos = _to_float(upl.fields.get("PosIst", "0"), 0.0)
        vel = _to_float(upl.fields.get("SpeedIstUI", "0"), 0.0)

        # Status words
        # EStop status word: primary key is EStopStatus. Some PLC variants place the word
        # in RampenformUI (template-based uplink). Use a conservative fallback when
        # EStopStatus is 0 but another field looks like a large bitmask.
        estop_status = _to_int(upl.fields.get("EStopStatus", "0"), 0)
        if estop_status == 0:
            alt = _to_int(upl.fields.get("RampenformUI", "0"), 0)
            if abs(alt) > 65535:
                estop_status = alt
        status_word = _to_int(upl.fields.get("Status", "0"), 0)
        guide_status_word = _to_int(upl.fields.get("GuideStatus", "0"), 0)

        ax = AxisTelemetry(
            pos=pos,
            vel=vel,
            enabled=False,
            fault=False,
        )
        # Attach extra fields if AxisTelemetry supports them (best effort)
        try:
            setattr(ax, "device_tick", _to_int(upl.fields.get("LifetickUItx", "0"), 0))
            setattr(ax, "status_word", status_word)
            setattr(ax, "guide_status_word", guide_status_word)
            setattr(ax, "lifetick_rx", _to_int(upl.fields.get("LifetickUIrx", "0"), 0))
        except Exception:
            pass

        params: Dict[str, float] = {}
        # Map core/UI parameter keys -> values from uplink
        for k in ("HardMax","UserMax","UserMin","HardMin","PosWin","VelMax","VelWin","AccMax","AccMove","DccMax","MaxAmp",
                  "P","I","D","IL","RampForm","PosMax","PosMin","Pitch"):
            if k in upl.fields:
                params[k] = _to_float(upl.fields.get(k, "0"), 0.0)
        # Also expose UI tail fields that the HiP wants to show
        for k in ("CutPos","CutVel","PosWinUI","VelWinUI","AccTotUI","GuidePosManualMaxUI"):
            if k in upl.tail:
                params[k] = _to_float(upl.tail.get(k, "0"), 0.0)

        snap = TelemetrySnapshot(
            tick=tick,
            t_s=float(t_s),
            mode="IDLE",
            estop=bool(estop_status != 0),
            fault=False,
            axes={name: ax},
            rig_mode="DISCOVERY",
            densis={},
            estop_status_word=int(estop_status),
            param_edit_active=False,
            param_edit_group="",
            params=params,
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
