"""DenSi parameter defaulting.

Lane 1 refactor: centralize the UI/protocol default values so we don't
silently drift between call sites.
"""

from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from typing import Any


# Defaults expected by UI + protocol contract tests.
# NOTE: only add values here that are meant to exist even before any PLC/HiP
# traffic arrives.
DENSI_PARAM_DEFAULTS: dict[str, Any] = {
    "PosChain0": 0.0,
    "PosChain1": 0.0,
    "PosChain2": 0.0,
    "PosChain3": 0.0,
    "GuiderMin": -0.5,
    "GuiderMax": 0.5,
    "AccMax": 1.0,
    "AccMove": 1.0,
    "DccMax": 1.0,
    "VelMax": 1.0,
    "HardMax": 300.0,
    "HardMin": 0.0,
    "UserMax": 300.0,
    "UserMin": 0.0,
    "P": 0.0,
    "I": 0.0,
    "D": 0.0,
    "IL": 0.0,
    "GuideIstSpeed": 0.0,
    "GuidePosIst": 0.0,
    "AxisAmp": 100.0,
    # Latched cut markers start cleared.
    "CutPos": 0.0,
    "CutVel": 0.0,
    "CutTime": 0.0,
    "PosDiffFor": 0.0,
}


def apply_densi_param_defaults(
    params: MutableMapping[str, Any],
    *,
    keys: Iterable[str] | None = None,
) -> None:
    """Apply DenSi defaults using setdefault semantics.

    If *keys* is provided, only those keys are ensured.
    """

    if keys is None:
        for k, v in DENSI_PARAM_DEFAULTS.items():
            params.setdefault(k, v)
        return

    for k in keys:
        if k in DENSI_PARAM_DEFAULTS:
            params.setdefault(k, DENSI_PARAM_DEFAULTS[k])
