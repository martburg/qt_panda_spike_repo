from __future__ import annotations


def apply_deadzone_and_expo(x: float, deadzone: float, expo: float) -> float:
    if deadzone < 0:
        deadzone = 0.0
    if deadzone > 0.95:
        deadzone = 0.95

    ax = abs(x)
    if ax <= deadzone:
        return 0.0

    y = (ax - deadzone) / (1.0 - deadzone)
    if expo <= 0:
        expo = 1.0
    y = y**expo
    return y if x >= 0 else -y


def apply_deadzone_only(x: float, deadzone: float) -> float:
    if deadzone < 0:
        deadzone = 0.0
    if deadzone > 0.95:
        deadzone = 0.95
    if abs(x) <= deadzone:
        return 0.0
    return x
