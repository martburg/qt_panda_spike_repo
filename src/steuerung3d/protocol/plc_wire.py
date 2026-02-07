
"""PLC wire codec: encode/decode semicolon-delimited telegrams.

For now we only implement telemetry encoding for DenSi simulation so that
Wireshark shows valid PLC-style uplink frames.

The field order is based on the legacy Beckhoff ST program (KommAnton__MAIN.st).
This encoder is deliberately conservative: unknown fields are filled with 0.
"""
from __future__ import annotations

from typing import Any

# Template from user-provided example; axis name will be substituted.
# NOTE: keep escaping for EOD\; literal.
_TEMPLATE_FIELDS = [
    "0",          # 0: ??? (legacy prefix)
    "{device_tick}",  # 1: device tick (16-bit)
    "{status_word}",  # 2: status word
    "{guide_status_word}",  # 3: guide status word
    "{pos}",      # 4
    "{vel}",      # 5
    "{amp}",      # 6
    "{temp}",     # 7
    "{axis}",     # 8 axis name
    "{lifetick}", # 9 livetick rx? (legacy had something here)
    "{HardMax}",  # 10
    "{UserMax}",  # 11
    "{UserMin}",  # 12
    "{HardMin}",  # 13
    "{VelMax}",   # 14
    "{AccMax}",   # 15
    "{DccMax}",   # 16
    "{MaxAmp}",   # 17
    "{VelMaxMot}",# 18
    "{P}", "{I}", "{D}", "{IL}",  # 19-22
    "{RampForm}", # 23
    "{PosMax}", "{PosMin}",       # 24-25
    "0", "0",     # 26-27 reserved
    "{Pitch}",    # 28
    "0", "0",     # 29-30
    "{PosWin}",   # 31
    "{VelWin}",   # 32
    "{AccMove}",  # 33
    "0",          # 34
    "0",          # 35
    "{estop_status_word}",  # 36
    "0",          # 37
    "EOD\\",     # 38 marker
    "{t_s}",      # 39 time seconds
    "0", "0",     # 40-41
    "{PosWin}",   # 42 repeat?
    "{VelWin}",   # 43 repeat?
    "{AccMove}",  # 44 repeat?
    "0",          # 45
]

def encode_plc_telemetry(snapshot: Any) -> str:
    """Encode a TelemetrySnapshot-like object into a PLC telemetry telegram line."""
    # Choose first axis entry
    axes = getattr(snapshot, "axes", {}) or {}
    if isinstance(axes, dict) and axes:
        axis_id, ax = next(iter(axes.items()))
    else:
        axis_id, ax = ("X", None)

    # Params dict
    params = getattr(snapshot, "params", {}) or {}
    def p(name: str, default: float = 0.0) -> float:
        try:
            return float(params.get(name, default))
        except Exception:
            return float(default)

    # Axis telemetry fields
    def axf(attr: str, default: float = 0.0) -> float:
        if ax is None:
            return float(default)
        try:
            return float(getattr(ax, attr))
        except Exception:
            return float(default)

    device_tick = int(getattr(ax, "device_tick", 0) if ax is not None else 0) & 0xFFFF
    status_word = int(getattr(ax, "status_word", 0) if ax is not None else 0)
    guide_status_word = int(getattr(ax, "guide_status_word", 0) if ax is not None else 0)
    lifetick = int(getattr(ax, "lifetick_rx", 0) if ax is not None else 0)

    estop_word = int(getattr(snapshot, "estop_status_word", 0))

    values = {
        "device_tick": device_tick,
        "status_word": status_word,
        "guide_status_word": guide_status_word,
        "pos": axf("pos", 0.0),
        "vel": axf("vel", 0.0),
        "amp": axf("amp", 0.0),
        "temp": axf("temp", 0.0),
        "axis": str(axis_id),
        "lifetick": lifetick,
        "HardMax": p("HardMax", 300.0),
        "UserMax": p("UserMax", 300.0),
        "UserMin": p("UserMin", -10.0),
        "HardMin": p("HardMin", -10.0),
        "VelMax": p("VelMax", 6.0),
        "AccMax": p("AccMax", 1.5),
        "DccMax": p("DccMax", 1.5),
        "MaxAmp": p("MaxAmp", 0.0),
        "VelMaxMot": p("VelMaxMot", 0.0),
        "P": p("P", 0.0),
        "I": p("I", 0.0),
        "D": p("D", 0.0),
        "IL": p("IL", 0.0),
        "RampForm": p("RampForm", 0.0),
        "PosMax": p("PosMax", 0.0),
        "PosMin": p("PosMin", 0.0),
        "Pitch": p("Pitch", 6.3),
        "PosWin": p("PosWin", 0.01),
        "VelWin": p("VelWin", 0.01),
        "AccMove": p("AccMove", 5.0),
        "estop_status_word": estop_word,
        "t_s": float(getattr(snapshot, "t_s", 0.0)),
    }

    fields=[]
    for f in _TEMPLATE_FIELDS:
        if f.startswith("{") and f.endswith("}"):
            key=f[1:-1]
            fields.append(str(values.get(key, 0)))
        else:
            fields.append(f)
    return ";".join(fields) + ";"
