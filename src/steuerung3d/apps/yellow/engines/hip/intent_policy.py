"""Intent policy helpers for HipEngine (Qt-free)."""

from __future__ import annotations

from typing import Iterable

from steuerung3d.core.attach_targets import claim_owner_from_snapshot
from steuerung3d.core.intents import EnableAxis, JogAxis, JogCartesian, JogWinch, SmoothStop
from steuerung3d.core.telemetry import TelemetrySnapshot


def is_motion_intent(intent: object) -> bool:
    return isinstance(intent, (EnableAxis, JogAxis, JogWinch, JogCartesian, SmoothStop))


def _is_safe_release_intent(intent: object) -> bool:
    if isinstance(intent, EnableAxis):
        return not bool(getattr(intent, "enable", False))
    if isinstance(intent, JogWinch):
        return float(getattr(intent, "rate", 0.0) or 0.0) == 0.0
    if isinstance(intent, JogAxis):
        return float(getattr(intent, "vel", 0.0) or 0.0) == 0.0
    return False


def gate_motion_intents(intents: Iterable[object], *, deadman: bool) -> list[object]:
    if bool(deadman):
        return list(intents)
    return [i for i in intents if (not is_motion_intent(i)) or _is_safe_release_intent(i)]


def claim_allowed(
    last_claim_attempt_ns_by_axis: dict[str, int],
    axis_id: str,
    now_ns: int,
    *,
    min_interval_ns: int = 500_000_000,
) -> bool:
    last = int(last_claim_attempt_ns_by_axis.get(axis_id, -(10**18)))
    if int(now_ns) - last < int(min_interval_ns):
        return False
    last_claim_attempt_ns_by_axis[axis_id] = int(now_ns)
    return True


def should_emit_speed(
    last_sent_speed_by_axis: dict[str, float],
    axis_id: str,
    speed: float,
    *,
    eps: float = 1e-3,
) -> bool:
    last = last_sent_speed_by_axis.get(axis_id)
    if last is None or abs(float(speed) - float(last)) > float(eps):
        last_sent_speed_by_axis[axis_id] = float(speed)
        return True
    return False


def should_emit_enable(
    last_sent_enable_by_axis: dict[str, bool],
    axis_id: str,
    enable: bool,
) -> bool:
    last = last_sent_enable_by_axis.get(axis_id)
    if last is None or bool(enable) != bool(last):
        last_sent_enable_by_axis[axis_id] = bool(enable)
        return True
    return False


def get_claim_owner(snap: TelemetrySnapshot, axis_id: str) -> str:
    return claim_owner_from_snapshot(snap, axis_id)
