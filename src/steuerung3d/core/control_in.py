"""Legacy ControlIN bitfield helpers.

The legacy TwinCAT protocol exposes a single integer `ControlIN` word.

At the moment we only have high confidence in the *enable* semantics:
- `ControlIN != 0` is interpreted as "enabled" in the legacy simulator/device.

We keep the mapping centralized so future bitfield confirmation (enable vs
motion vs other flags) changes in exactly one place.
"""

from __future__ import annotations


# Known / used today
CONTROL_IN_ENABLE_MASK: int = 0x0001


def compute_control_in(*, enable: bool, motion: bool = False) -> int:
    """Compute the legacy ControlIN word.

    Args:
        enable: Request servo/drive enable.
        motion: Request motion permission (reserved; currently folded into enable).

    Returns:
        Integer control word.
    """

    # Current confirmed behavior: non-zero means enabled.
    # Motion is currently not represented separately.
    return CONTROL_IN_ENABLE_MASK if bool(enable) else 0
