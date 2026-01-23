# src/steuerung3d/protocol/estop_bits.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional


@dataclass(frozen=True)
class EstopBitSpec:
    key: str
    bit: int
    invert: bool = False                 # True => raw bit means "bad", so logical = not raw
    checkbox: Optional[str] = None       # Diagnostics tab QCheckBox objectName
    dot: Optional[str] = None            # QFrame dot objectName (or header LED)


# ---- Canonical mapping (legacy DecodeEStopStatus) ----
# NOTE on semantics:
#   - invert=True for guider lines (legacy did: if bit set => flag False)
#   - for non-inverted bits: raw bit set => logical True
ESTOP_SPECS: Dict[str, EstopBitSpec] = {
    # --- Guider channel bits (INVERTED in legacy) ---
    # G3
    "g3_fb":  EstopBitSpec("g3_fb",  0, invert=True, checkbox="chkEsG3Fb",  dot="g3_fb_dot"),
    "g3_com": EstopBitSpec("g3_com", 1, invert=True, checkbox="chkEsG3Com", dot="g3_com_dot"),
    "g3_out": EstopBitSpec("g3_out", 2, invert=True, checkbox="chkEsG3Out", dot="g3_out_dot"),
    # G2
    "g2_fb":  EstopBitSpec("g2_fb",  3, invert=True, checkbox="chkEsG2Fb",  dot="g2_fb_dot"),
    "g2_com": EstopBitSpec("g2_com", 4, invert=True, checkbox="chkEsG2Com", dot="g2_com_dot"),
    "g2_out": EstopBitSpec("g2_out", 5, invert=True, checkbox="chkEsG2Out", dot="g2_out_dot"),
    # G1
    "g1_fb":  EstopBitSpec("g1_fb",  6, invert=True, checkbox="chkEsG1Fb",  dot="g1_fb_dot"),
    "g1_com": EstopBitSpec("g1_com", 7, invert=True, checkbox="chkEsG1Com", dot="g1_com_dot"),
    "g1_out": EstopBitSpec("g1_out", 8, invert=True, checkbox="chkEsG1Out", dot="g1_out_dot"),

    # --- Core / safety bits (not inverted) ---
    "master":      EstopBitSpec("master",      9,  checkbox="chkEStopMaster",  dot="dotMaster"),
    "guider":      EstopBitSpec("guider",      10, checkbox="chkEStopGuider",  dot="dotGuider"),   # legacy: EsSlave
    "network":     EstopBitSpec("network",     11, checkbox="chkEStopNetwork", dot="dotNetwork"),
    "reset_able":  EstopBitSpec("reset_able",  12, checkbox="chkEsResetAble",  dot=None),
    "estop1":      EstopBitSpec("estop1",      13, checkbox="chkEStop1",       dot="dotEStop1"),
    "estop2":      EstopBitSpec("estop2",      14, checkbox="chkEStop2",       dot="dotEStop2"),
    "steuerwort":  EstopBitSpec("steuerwort",  15, checkbox="chkEsSteuerwort", dot=None),

    "kw30_ok":     EstopBitSpec("kw30_ok",     16, checkbox="chkEs30kWOK",     dot="dot30kw"),
    "kw05_ok":     EstopBitSpec("kw05_ok",     17, checkbox="chkEs05kWOK",     dot="dot05kw"),

    "brk1_ok":     EstopBitSpec("brk1_ok",     18, checkbox="chkEsBRK1OK",     dot="dotBRK1"),
    "brk2_ok":     EstopBitSpec("brk2_ok",     19, checkbox="chkEsBRK2OK",     dot="dotBRK2"),
    "dcs_ok":      EstopBitSpec("dcs_ok",      20, checkbox="chkEsDCSOK",      dot="dotENC"),
    "sps_ok":      EstopBitSpec("sps_ok",      21, checkbox="chkEsSPSOK",      dot="dotSPS"),
    "brk2kb_ok":   EstopBitSpec("brk2kb_ok",   22, checkbox="chkEsBRK2KB",     dot="dotBRK2KB"),
    "fbt_ok":      EstopBitSpec("fbt_ok",      23, checkbox="chkEsRed",        dot="dotRed"),      # legacy: EsFTBOK; QSS shows dotRed

    "pos_win":     EstopBitSpec("pos_win",     24, checkbox="chkEsPosWin",     dot="dotPosWin"),
    "vel_win":     EstopBitSpec("vel_win",     25, checkbox="chkEsVelWin",     dot="dotVelWin"),
    "endlage":     EstopBitSpec("endlage",     26, checkbox="chkEsEndlage",    dot="dotEndlage"),

    "taster":      EstopBitSpec("taster",      27, checkbox="chkEsTaster",     dot=None),
    "schuetz":     EstopBitSpec("schuetz",     28, checkbox="chkEsSchuetz",    dot=None),
    "ready":       EstopBitSpec("ready",       29, checkbox="chkEsReady",      dot=None),  # header LED objectName differs; see QSS
    "schluessel1": EstopBitSpec("schluessel1", 30, checkbox="chkEsKey1",       dot=None),
    "schluessel2": EstopBitSpec("schluessel2", 31, checkbox="chkEsKey2",       dot=None),
}

# Bits that mean "E-Stop is ACTIVE / cause present" (trip sources)
ESTOP_CAUSE_KEYS = {"master", "guider", "network", "estop1", "estop2"}

# Bits that mean "OK / healthy" when True (status chain)
ESTOP_OK_KEYS = {
    k
    for k, spec in ESTOP_SPECS.items()
    if spec.invert
       or k.endswith("_ok")
       or k in {"pos_win", "vel_win", "reset_able", "steuerwort", "ready"}
}

# Backwards-compatible: plain bit index map (some code already expects this)
#ESTOP_BITS: Dict[str, int] = {k: spec.bit for k, spec in ESTOP_SPECS.items()}


def iter_specs() -> Iterable[EstopBitSpec]:
    return ESTOP_SPECS.values()


def get_bit(word: int, bit: int) -> bool:
    return bool((int(word) >> int(bit)) & 1)


def set_bit(word: int, bit: int, value: bool) -> int:
    if value:
        return int(word) | (1 << int(bit))
    return int(word) & ~(1 << int(bit))


def decode_estop_word(word: int) -> Dict[str, bool]:
    """Return LOGICAL booleans per key (invert applied where required)."""
    w = int(word or 0)
    out: Dict[str, bool] = {}
    for key, spec in ESTOP_SPECS.items():
        raw = bool((w >> spec.bit) & 1)
        out[key] = (not raw) if spec.invert else raw
    return out


def encode_estop_word(bits: Dict[str, bool], *, base: int = 0) -> int:
    """Encode LOGICAL booleans into a word (invert applied where required)."""
    w = int(base or 0)
    for key, spec in ESTOP_SPECS.items():
        logical = bool(bits.get(key, False))
        raw = (not logical) if spec.invert else logical
        w = set_bit(w, spec.bit, raw)
    return w


def checkbox_name(key: str) -> Optional[str]:
    spec = ESTOP_SPECS.get(key)
    return None if spec is None else spec.checkbox


def dot_name(key: str) -> Optional[str]:
    spec = ESTOP_SPECS.get(key)
    return None if spec is None else spec.dot
