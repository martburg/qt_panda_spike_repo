"""PLC wire helpers.

This module exists primarily for DenSi/PLCSim so we can emit *ST-compatible*
uplink frames that Wireshark, legacy tooling, and our own :mod:`legacy_plc`
parser agree on.

The canonical ordering is defined by :mod:`steuerung3d.protocol.legacy_plc`
and ultimately by the Beckhoff ST program (KommAnton__MAIN.st).

Key rule:
  - token #36 is **RampenformUI**
  - token #37 is **EStopStatus**

We previously had an off-by-one there, which breaks E-stop decoding and
enables/disables the HiP's E-stop reset incorrectly.
"""

from __future__ import annotations

from typing import Any, Dict

from steuerung3d.protocol.legacy_plc import encode_uplink


def _f(x: object, default: float = 0.0) -> float:
    try:
        return float(x)  # type: ignore[arg-type]
    except Exception:
        return float(default)


def _i(x: object, default: int = 0) -> int:
    try:
        # tolerate "12.0"
        return int(float(x))  # type: ignore[arg-type]
    except Exception:
        return int(default)


def encode_plc_telemetry(snapshot: Any) -> str:
    """Encode a TelemetrySnapshot-like object into a canonical PLC uplink line."""

    # Choose first axis entry
    axes = getattr(snapshot, "axes", {}) or {}
    if isinstance(axes, dict) and axes:
        axis_id, ax = next(iter(axes.items()))
    else:
        axis_id, ax = ("X", None)

    # Params dict
    params = getattr(snapshot, "params", {}) or {}
    if not isinstance(params, dict):
        params = {}

    def p(name: str, default: float = 0.0) -> float:
        return _f(params.get(name, default), default)

    def p_any(names: list[str], default: float = 0.0) -> float:
        for n in names:
            if n in params:
                return _f(params.get(n, default), default)
        return float(default)

    def ax_meta(name: str, default: int = 0) -> int:
        if ax is None:
            return int(default)
        meta = getattr(ax, "meta", None)
        if isinstance(meta, dict) and name in meta:
            return _i(meta.get(name, default), default)
        return _i(getattr(ax, name, default), default)

    # Device ticks (DenSi uses meta; real devices might attach attributes)
    lifetick_tx = ax_meta("lifetick_tx", ax_meta("device_tick", 0)) & 0xFFFF

    # Downlink echo is stored as lifetick_rx in our sim
    lifetick_rx = ax_meta("lifetick_rx", 0) & 0xFFFF

    status_word = ax_meta("status_word", 0)
    guide_status_word = ax_meta("guide_status_word", 0)

    # Measured values
    pos = _f(getattr(ax, "pos", 0.0) if ax is not None else 0.0)
    vel = _f(getattr(ax, "vel", 0.0) if ax is not None else 0.0)
    amp = p_any(["ActCur", "Amp", "ActCurUI"], 0.0)
    temp = p_any(["Temp", "CabTemperatureUI"], 20.0)

    estop_word = _i(getattr(snapshot, "estop_status_word", 0))

    # Base fields (0..37) — names must match legacy_plc.UPLINK_BASE_FIELDS
    fields: Dict[str, object] = {
        "OwnPID": "0",
        "LifetickUItx": str(int(lifetick_tx)),
        "Status": str(int(status_word)),
        "GuideStatus": str(int(guide_status_word)),
        "PosIst": pos,
        "SpeedIstUI": vel,
        "MasterMomentUI": 0,
        "CabTemperatureUI": temp,
        "Name": str(axis_id),
        "GearToUI": str(int(lifetick_rx)),
        "PosMaxHardUI": p("HardMax", 300.0),
        "PosMaxUserUI": p("UserMax", 300.0),
        "PosMinUserUI": p("UserMin", -10.0),
        "PosMinHardUI": p("HardMin", -10.0),
        "SpeedMaxUI": p("VelMax", 6.0),
        "AccMaxUI": p("AccMax", 1.5),
        "DccMaxUI": p("DccMax", 1.5),
        "AmpMaxUI": p("MaxAmp", 0.0),
        "FilterP": p("P", 1.0),
        "FilterI": p("I", 0.0),
        "FilterD": p("D", 0.0),
        "FilterIL": p("IL", 300.0),
        "RopeSWLL": p("RopeSWLL", 0.0),
        "RopeDiameter": p("RopeDiameter", 0.0),
        "RopeType": p("RopeType", 0.0),
        "RopeNumber": p("RopeNumber", 0.0),
        "RopeLength": p("RopeLength", 0.0),
        "GuidePitchUI": p("Pitch", 6.3),
        "GuidePosMaxUI": p("PosMax", 0.0),
        "GuidePosMinUI": p("PosMin", 0.0),
        "GuidePosIstUI": p("GuidePosIst", 0.0),
        "GuideIstSpeedUI": p("GuideIstSpeed", 0.0),
        "MotAuslastUI": p("MotAuslast", 0.0),
        "ActCurUI": amp,
        "SpeedMaxforUI": p("SpeedMaxfor", 0.0),
        "PosDiffForUI": p("PosDiffFor", 0.0),
        # IMPORTANT: #36 RampenformUI, #37 EStopStatus
        "RampenformUI": _i(p("RampForm", 0.0)),
        "EStopStatus": str(int(estop_word)),
    }

    # Tail fields (after EOD\)
    t_s = _f(getattr(snapshot, "t_s", 0.0))
    tail: Dict[str, object] = {
        # For SIM we keep it numeric so our decoder can derive t_s.
        # Real PLC uses N_/L_ prefixed strings; our decoder should not rely on parsing this.
        "SystemTime": (
            str(snapshot.params.get("SystemTime", ""))
            if isinstance(getattr(snapshot, "params", None), dict)
            and str(snapshot.params.get("SystemTime", ""))
            else f"{t_s:.3f}"
        ),
        "sCutPos": p("CutPos", 0.0),
        "sCutVel": p("CutVel", 0.0),
        "PosWinUI": p("PosWin", 0.01),
        "VelWinUI": p("VelWin", 0.01),
        "AccTotUI": p("AccMove", 5.0),
        "GuidePosManualMaxUI": p("GuidePosManualMaxUI", 0.0),
    }

    return encode_uplink(fields, tail)
