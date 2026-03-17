from __future__ import annotations

from steuerung3d.core.telemetry import TelemetrySnapshot

DEFAULT_DENSI_AGE_TICK_MS = 50


def axis_is_stale(
    *, snap: TelemetrySnapshot, axis_id: str, densi: object, stale_after_ms: int
) -> bool:
    """Return whether the axis row should be treated as stale."""

    if densi is not None and bool(getattr(densi, "last_seen_age_ticks", 0) or 0):
        age_ticks = int(getattr(densi, "last_seen_age_ticks", 0) or 0)
        return age_ticks * DEFAULT_DENSI_AGE_TICK_MS >= int(stale_after_ms)
    ax = snap.axes.get(axis_id)
    if ax is None:
        return True
    age = int(getattr(ax, "lifetick_age", 0) or 0)
    return age >= int(stale_after_ms)
