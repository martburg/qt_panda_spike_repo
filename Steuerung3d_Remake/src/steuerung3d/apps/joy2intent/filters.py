from __future__ import annotations


def deadzone_expo(x: float, deadzone: float, expo: float) -> float:
    """Apply deadzone and an expo curve (cubic blend).

    deadzone: 0..1 (values inside become 0)
    expo: 0..1 (0=linear, 1=strong cubic around center)
    """
    ax = abs(x)
    if ax <= deadzone:
        return 0.0
    s = 1.0 if x >= 0 else -1.0
    u = (ax - deadzone) / max(1e-9, (1.0 - deadzone))
    u = max(0.0, min(1.0, u))
    u2 = (1.0 - expo) * u + expo * (u * u * u)
    return s * u2


def clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x
