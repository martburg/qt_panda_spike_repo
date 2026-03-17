from __future__ import annotations

from typing import Literal, TypeAlias

ParamGroup: TypeAlias = Literal["pos", "vel", "filter", "guider"]


def coerce_param_group(group: object, default: ParamGroup = "pos") -> ParamGroup:
    """Return a canonical parameter-group literal.

    Unknown or empty values fall back to ``default``.
    """

    g = str(group or "").strip()
    if g == "pos":
        return "pos"
    if g == "vel":
        return "vel"
    if g == "filter":
        return "filter"
    if g == "guider":
        return "guider"
    if default == "vel":
        return "vel"
    if default == "filter":
        return "filter"
    if default == "guider":
        return "guider"
    return "pos"
