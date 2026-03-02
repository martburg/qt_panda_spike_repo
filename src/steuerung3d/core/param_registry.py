from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

# NOTE: this module is intentionally small; expand PARAM_SPECS as the PLC contract is mapped.


@dataclass(frozen=True)
class ParamSpec:
    name: str
    group: str
    eps: float = 1e-6


PARAM_SPECS: Dict[str, ParamSpec] = {
    # pos
    "HardMax": ParamSpec("HardMax", "pos"),
    "UserMax": ParamSpec("UserMax", "pos"),
    "UserMin": ParamSpec("UserMin", "pos"),
    "HardMin": ParamSpec("HardMin", "pos"),
    "PosWin": ParamSpec("PosWin", "pos"),
    # vel
    "VelMax": ParamSpec("VelMax", "vel"),
    "VelWin": ParamSpec("VelWin", "vel"),
    "AccMax": ParamSpec("AccMax", "vel"),
    "AccMove": ParamSpec("AccMove", "vel"),
    "DccMax": ParamSpec("DccMax", "vel"),
    "MaxAmp": ParamSpec("MaxAmp", "vel"),
    "VelMaxMot": ParamSpec("VelMaxMot", "vel"),
    # filter
    "P": ParamSpec("P", "filter"),
    "I": ParamSpec("I", "filter"),
    "D": ParamSpec("D", "filter"),
    "IL": ParamSpec("IL", "filter"),
    "RampForm": ParamSpec("RampForm", "filter"),
    # guider
    "PosMin": ParamSpec("PosMin", "guider"),
    "PosMax": ParamSpec("PosMax", "guider"),
    "Pitch": ParamSpec("Pitch", "guider"),
}


def eps_for_param(name: str, default: float = 1e-6) -> float:
    spec = PARAM_SPECS.get(str(name))
    return float(spec.eps) if spec else float(default)


def normalize_group_values(group: str, values: Dict[str, float]) -> Tuple[Dict[str, float], List[str]]:
    """Return (normalized_values, warnings).

    This is a safety net. HiP UI already enforces the same rules; the core repeats them
    so that other future clients (joystick/console) behave identically.
    """
    g = str(group or "")
    v: Dict[str, float] = {str(k): float(val) for k, val in dict(values).items()}
    warnings: List[str] = []

    if g == "pos":
        need = ("HardMax", "UserMax", "UserMin", "HardMin")
        if all(k in v for k in need):
            hard_max0 = float(v["HardMax"])
            hard_min0 = float(v["HardMin"])
            user_max0 = float(v["UserMax"])
            user_min0 = float(v["UserMin"])

            hard_max = hard_max0
            hard_min = hard_min0
            user_max = user_max0
            user_min = user_min0

            if hard_max < hard_min:
                hard_max, hard_min = hard_min, hard_max
                warnings.append("pos: swapped HardMax/HardMin")

            # Enforce chain: HardMax >= UserMax >= UserMin >= HardMin
            user_max = max(min(user_max, hard_max), hard_min)
            user_min = max(min(user_min, user_max), hard_min)

            if user_max != user_max0 or user_min != user_min0:
                warnings.append("pos: clamped UserMax/UserMin into [HardMin, HardMax] and ordered")

            v["HardMax"] = hard_max
            v["HardMin"] = hard_min
            v["UserMax"] = user_max
            v["UserMin"] = user_min

    if g == "guider":
        if "PosMin" in v and "PosMax" in v:
            lo0 = float(v["PosMin"])
            hi0 = float(v["PosMax"])
            lo = lo0
            hi = hi0

            # Clamp so that PosMin <= PosMax without swapping.
            if lo > hi:
                lo = hi
                warnings.append("guider: clamped PosMin to PosMax")

            v["PosMin"] = lo
            v["PosMax"] = hi

    return v, warnings
