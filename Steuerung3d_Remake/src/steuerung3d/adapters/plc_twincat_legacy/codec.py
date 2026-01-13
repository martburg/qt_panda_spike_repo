from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Tuple

from steuerung3d.protocol.legacy_plc import parse_uplink as parse_legacy_uplink


def _split_fields(line: str, sep: str = ";") -> List[str]:
    raw = [p.strip() for p in line.strip().split(sep)]
    while raw and raw[-1] == "":
        raw.pop()
    return raw


def parse_int(v: str, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except Exception:
        return default


def parse_float(v: str, default: float = 0.0) -> float:
    try:
        return float(str(v).strip())
    except Exception:
        return default


def parse_bool_str(v: str, default: bool = False) -> bool:
    if v is None:
        return default
    s = str(v).strip().lower()
    if s in ("1", "true", "t", "yes", "y", "on"):
        return True
    if s in ("0", "false", "f", "no", "n", "off"):
        return False
    return default


# -------------------------
# Legacy TwinCAT winch schemas (positional)
# -------------------------

WINCH_DOWN_BASE_FIELDS: Tuple[str, ...] = (
    "LifetickUIrx",       # WORD
    "Modus",              # STRING
    "OwnPID",             # STRING
    "ControlPIDTx",       # UINT
    "Intent",             # STRING "True"/"False"
    "ControlIN",          # UINT
    "GuideControlUI",     # UINT
    "SpeedSollIN",        # REAL
    "GuideSollSpeedUI",   # REAL
    "PosSoll",            # REAL
    "EStopReset",         # DWORD
    "ReSync",             # REAL
    "GUINotHaltIN",       # INT
)

WINCH_DOWN_WRITE_FIELDS: Tuple[str, ...] = (
    "AccIN", "DccIN",
    "PosMaxHardUI", "PosMaxUserUI", "PosMinUserUI", "PosMinHardUI",
    "SpeedMaxUI", "AccMaxUI", "DccMaxUI", "AmpMaxUI",
    "FilterP", "FilterI", "FilterD", "FilterIL",
    "GuidePitchUI", "GuidePosMaxUI", "GuidePosMinUI",
    "VelOrPos", "PosWinUI", "VelWinUI", "AccTotUI",
)

WINCH_UP_FIELDS: Tuple[str, ...] = (
    "OwnPID",
    "LifetickUItx",
    "Status",
    "GuideStatus",
    "PosIst",
    "SpeedIstUI",
    "MasterMomentUI",
    "CabTemperatureUI",
    "Name",
    "GearToUI",
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
    "RopeSWLL",
    "RopeDiameter",
    "RopeType",
    "RopeNumber",
    "RopeLength",
    "GuidePitchUI",
    "GuidePosMaxUI",
    "GuidePosMinUI",
    "GuidePosIstUI",
    "GuideIstSpeedUI",
    "MotAuslastUI",
    "ActCurUI",
    "SpeedMaxforUI",
    "PosDiffForUI",
    "RampenformUI",
    "EStopStatus",
)

WINCH_UP_TAIL_FIELDS: Tuple[str, ...] = (
    "SystemTime",
    "sCutPos",
    "sCutVel",
    "PosWinUI",
    "VelWinUI",
    "AccTotUI",
    "GuidePosManualMaxUI",
)


@dataclass(frozen=True)
class TwinCATLegacyWinchDownlink:
    lifetick: int
    modus: str
    own_pid: str
    control_pid_tx: int
    intent: bool

    control_in: int
    guide_control_ui: int
    speed_soll: float
    guide_soll_speed: float
    pos_soll: float

    estop_reset: int
    resync: float
    gui_not_halt: int

    # only used when modus == 'w'
    write_params: Optional[Mapping[str, object]] = None


@dataclass(frozen=True)
class TwinCATLegacyWinchUplink:
    fields: Dict[str, str]
    tail: Dict[str, str]
    raw_tokens: List[str]


class TwinCATLegacyWinchCodec:
    sep: str = ";"
    eod_token: str = "EOD"

    def encode_downlink(self, d: TwinCATLegacyWinchDownlink) -> str:
        def fmt(x: object) -> str:
            if isinstance(x, bool):
                return "True" if x else "False"
            return str(x)

        base: Dict[str, object] = {
            "LifetickUIrx": int(d.lifetick) & 0xFFFF,
            "Modus": d.modus,
            "OwnPID": d.own_pid,
            "ControlPIDTx": int(d.control_pid_tx),
            "Intent": "True" if d.intent else "False",
            "ControlIN": int(d.control_in),
            "GuideControlUI": int(d.guide_control_ui),
            "SpeedSollIN": float(d.speed_soll),
            "GuideSollSpeedUI": float(d.guide_soll_speed),
            "PosSoll": float(d.pos_soll),
            "EStopReset": int(d.estop_reset),
            "ReSync": float(d.resync),
            "GUINotHaltIN": int(d.gui_not_halt),
        }

        parts = [fmt(base[k]) for k in WINCH_DOWN_BASE_FIELDS]

        if str(d.modus).strip().lower() == "w":
            wp = dict(d.write_params or {})
            for k in WINCH_DOWN_WRITE_FIELDS:
                if k not in wp:
                    raise KeyError(f"Modus 'w' requires write_params['{k}']")
                parts.append(fmt(wp[k]))

        return self.sep.join(parts) + self.sep

    
    def decode_uplink(self, line: str) -> TwinCATLegacyWinchUplink:
        """Parse PLC->controller status line into named fields.

        Delegates the wire-format parsing to `steuerung3d.protocol.legacy_plc`.
        We keep the adapter-local `TwinCATLegacyWinchUplink` wrapper for backward
        compatibility with existing tests and device code.
        """
        parsed = parse_legacy_uplink(line)

        # Keep adapter-local convention: include best-effort extras if someone
        # sends longer frames than expected.
        fields = dict(parsed.fields)
        tail = dict(parsed.tail)

        # Best-effort: if the message had more tokens than we mapped, preserve them
        # under the same keys used before.
        tokens = [t.strip() for t in line.strip().split(self.sep)]
        if tokens and tokens[-1] == "":
            tokens = tokens[:-1]
        try:
            eod_idx = tokens.index("EOD")
        except ValueError:
            try:
                eod_idx = tokens.index("EOD\\")
            except ValueError:
                eod_idx = len(tokens)

        prefix = tokens[:eod_idx]
        tail_tokens = tokens[eod_idx + 1 :] if eod_idx < len(tokens) else []

        if len(prefix) > len(WINCH_UP_FIELDS):
            fields["_extra_prefix"] = self.sep.join(prefix[len(WINCH_UP_FIELDS) :])
        if len(tail_tokens) > len(WINCH_UP_TAIL_FIELDS):
            tail["_extra_tail"] = self.sep.join(tail_tokens[len(WINCH_UP_TAIL_FIELDS) :])

        return TwinCATLegacyWinchUplink(fields=fields, tail=tail, raw_tokens=tokens)
