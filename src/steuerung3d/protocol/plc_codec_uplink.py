"""Legacy PLC uplink codec (PLC -> Controller).

Split out of plc_codec_impl.py as a Lane-1 refactor (no semantic changes).
"""

from __future__ import annotations

from typing import Dict, Optional

from steuerung3d.core.axis_id import normalize_axis_id
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.protocol.legacy_plc import parse_uplink
from steuerung3d.protocol.plc_codec_utils import (
    fmt as _fmt,
    to_float as _to_float,
    to_int as _to_int,
)

_PLC_TO_INTERNAL_PARAM_KEYS: dict[str, str] = {
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

_TAIL_TO_INTERNAL_PARAM_KEYS: dict[str, str] = {
    "PosWinUI": "PosWin",
    "VelWinUI": "VelWin",
    "AccTotUI": "AccMove",
    "sCutPos": "CutPos",
    "sCutVel": "CutVel",
}

_UPLINK_FIELD_ORDER = [
    "LifetickUIrx",
    "Modus",
    "OwnPID",
    "ControlPIDTx",
    "Intent",
    "ControlIN",
    "GuideControlUI",
    "SpeedSollIN",
    "GuideSollSpeedUI",
    "PosSoll",
    "EStopReset",
    "ReSync",
    "GUINotHaltIN",
    "AccIN",
    "DccIN",
    "PosMaxHardUI",
    "PosMaxUserUI",
    "PosMinUserUI",
    "PosMinHardUI",
    "SpeedMaxUI",
    "AccMaxUI",
    "DccMaxUI",
    "AmpMaxUI",
    "FilterP",
    "FilterI",
    "FilterD",
    "FilterIL",
    "RampForm",
    "GuidePosMaxUI",
    "GuidePosMinUI",
    "GuidePitchUI",
    "VelOrPos",
    "PosWinUI",
    "VelWinUI",
    "AccTotUI",
    "GuidePosManualMaxUI",
    "Name",
    "Status",
    "StatusIst",
    "PosIst",
    "SpeedIstUI",
    "AmpIst",
    "TempIst",
    "EStopStatus",
    "GuideStatus",
]


def _decode_axis_name(upl: object) -> str:
    fields = getattr(upl, "fields", {})
    return normalize_axis_id((fields.get("Name", "") or "X").strip() or "X")


def _decode_raw_uplink_payload(upl: object) -> tuple[dict[str, str], dict[str, str]]:
    return (
        {str(k): str(v) for k, v in dict(getattr(upl, "fields", {})).items()},
        {str(k): str(v) for k, v in dict(getattr(upl, "tail", {})).items()},
    )


def _decode_device_tick(upl: object) -> int:
    return _to_int(getattr(upl, "fields", {}).get("LifetickUItx", "0"), 0) & 0xFFFF


def _decode_timestamp_seconds(upl: object, *, device_tick: int) -> float:
    t_s = _to_float(getattr(upl, "tail", {}).get("SystemTime", ""), default=0.0)
    if t_s <= 0.0:
        t_s = float(device_tick) / 100.0
    return float(t_s)


def _decode_estop_active(estop_status_word: int) -> bool:
    try:
        from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, decode_estop_word

        estop_bits = decode_estop_word(int(estop_status_word))
        return any(bool(estop_bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
    except Exception:
        return bool(int(estop_status_word) != 0)


def _build_axis_telemetry(upl: object, *, device_tick: int) -> tuple[AxisTelemetry, int]:
    fields = getattr(upl, "fields", {})
    pos = _to_float(fields.get("PosIst", "0"), 0.0)
    vel = _to_float(fields.get("SpeedIstUI", "0"), 0.0)
    status_word = _to_int(fields.get("Status", "0"), 0)
    guide_status_word = _to_int(fields.get("GuideStatus", "0"), 0)
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
    estop_status_word = _to_int(fields.get("EStopStatus", "0"), 0)
    return ax, int(estop_status_word)


def _decode_params(upl: object) -> Dict[str, float]:
    fields = getattr(upl, "fields", {})
    tail = getattr(upl, "tail", {})
    params: Dict[str, float] = {}

    for plc_k, internal_k in _PLC_TO_INTERNAL_PARAM_KEYS.items():
        if plc_k in fields:
            params[internal_k] = _to_float(fields.get(plc_k, "0"), 0.0)

    for plc_k, internal_k in _TAIL_TO_INTERNAL_PARAM_KEYS.items():
        if plc_k in tail:
            params[internal_k] = _to_float(tail.get(plc_k, "0"), 0.0)

    return params


def _build_snapshot(
    *,
    axis_name: str,
    axis: AxisTelemetry,
    device_tick: int,
    t_s: float,
    estop_status_word: int,
    estop_active: bool,
    params: Dict[str, float],
    raw_fields: dict[str, str],
    raw_tail: dict[str, str],
) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=int(device_tick),
        t_s=float(t_s),
        core_mode="IDLE",
        estop=bool(estop_active),
        fault=False,
        axes={axis_name: axis},
        rig_mode="DISCOVERY",
        densis={},
        estop_status_word=int(estop_status_word),
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


def decode_uplink_to_snapshot(payload: bytes) -> Optional[TelemetrySnapshot]:
    """Decode one PLC uplink telegram into a TelemetrySnapshot.

    Canonical uplink ordering is defined in protocol/legacy_plc.py (mirrors KommAnton__MAIN.st).
    """
    try:
        msg = payload.decode("utf-8", errors="ignore").strip()
        if not msg:
            return None
        upl = parse_uplink(msg)
        axis_name = _decode_axis_name(upl)
        raw_fields, raw_tail = _decode_raw_uplink_payload(upl)
        device_tick = _decode_device_tick(upl)
        t_s = _decode_timestamp_seconds(upl, device_tick=device_tick)
        axis, estop_status_word = _build_axis_telemetry(upl, device_tick=device_tick)
        estop_active = _decode_estop_active(estop_status_word)
        params = _decode_params(upl)
        return _build_snapshot(
            axis_name=axis_name,
            axis=axis,
            device_tick=device_tick,
            t_s=t_s,
            estop_status_word=estop_status_word,
            estop_active=estop_active,
            params=params,
            raw_fields=raw_fields,
            raw_tail=raw_tail,
        )
    except Exception:
        return None


def _axis_snapshot_values(
    snap: TelemetrySnapshot, *, axis_name: str
) -> tuple[object | None, float, float, float, float]:
    ax = snap.axes.get(axis_name)
    pos = float(getattr(ax, "pos", 0.0)) if ax else 0.0
    vel = float(getattr(ax, "vel", 0.0)) if ax else 0.0
    amp = float(snap.params.get("Amp", 0.0)) if hasattr(snap, "params") else 0.0
    temp = float(snap.params.get("Temp", 0.0)) if hasattr(snap, "params") else 0.0
    return ax, pos, vel, amp, temp


def _status_words(snap: TelemetrySnapshot, *, ax: object | None) -> tuple[int, int, int]:
    estop_status = int(getattr(snap, "estop_status_word", 0) or 0)
    status_word = int(getattr(ax, "status_word", 0) or 0) if ax else 0
    guide_status_word = int(getattr(ax, "guide_status_word", 0) or 0) if ax else 0
    return estop_status, status_word, guide_status_word


def _put_uplink_fields(
    *,
    snap: TelemetrySnapshot,
    axis_name: str,
    pos: float,
    vel: float,
    amp: float,
    temp: float,
    status_word: int,
    guide_status_word: int,
    estop_status: int,
) -> Dict[str, str]:
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
    return f


def _encode_tail_fields(snap: TelemetrySnapshot) -> list[str]:
    t_s = float(getattr(snap, "t_s", 0.0) or 0.0)
    return [
        _fmt(t_s),
        _fmt(float(snap.params.get("CutPos", 0.0))),
        _fmt(float(snap.params.get("CutVel", 0.0))),
        _fmt(float(snap.params.get("PosWin", 0.0))),
        _fmt(float(snap.params.get("VelWin", 0.0))),
        _fmt(float(snap.params.get("AccMove", 0.0))),
        _fmt(float(snap.params.get("GuidePosManualMaxUI", 0.0))),
    ]


def encode_uplink_from_snapshot(snap: TelemetrySnapshot, *, axis_name: str) -> bytes:
    """Encode a minimal but ST-compatible uplink telegram from a TelemetrySnapshot.

    This is primarily for DenSi SIM. Real PLCs generate this string in ST.
    """
    axis_name = normalize_axis_id(axis_name or "X") or "X"
    ax, pos, vel, amp, temp = _axis_snapshot_values(snap, axis_name=axis_name)
    estop_status, status_word, guide_status_word = _status_words(snap, ax=ax)
    fields = _put_uplink_fields(
        snap=snap,
        axis_name=axis_name,
        pos=pos,
        vel=vel,
        amp=amp,
        temp=temp,
        status_word=status_word,
        guide_status_word=guide_status_word,
        estop_status=estop_status,
    )
    parts = [fields.get(k, "0") for k in _UPLINK_FIELD_ORDER]
    line = ";".join(parts) + ";EOD\\;"
    line += ";".join(_encode_tail_fields(snap)) + ";"
    return line.encode("utf-8", errors="strict")
