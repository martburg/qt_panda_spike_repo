from __future__ import annotations

from steuerung3d.core.telemetry import TelemetrySnapshot

try:
    from steuerung3d.protocol.drive_status import decode_drive_status  # type: ignore
except Exception:  # pragma: no cover
    decode_drive_status = None  # type: ignore


def compute_drive_status_texts(*, snap: TelemetrySnapshot, axis_id: str) -> tuple[str, str]:
    if decode_drive_status is None:
        return "", ""
    if not axis_id:
        return "", ""
    ax = snap.axes.get(axis_id)
    if ax is None:
        return "", ""
    main_word = int(getattr(ax, "status_word", 0) or 0)
    slave_word = int(getattr(ax, "guide_status_word", 0) or 0)
    try:
        main = decode_drive_status(main_word)
        slave = decode_drive_status(slave_word)
        return str(main.summary()), str(slave.summary())
    except Exception:
        return "", ""


def compute_drive_status_summary(*, snap: TelemetrySnapshot, axis_id: str) -> str:
    if decode_drive_status is None:
        return ""
    if not axis_id:
        return ""
    axes = getattr(snap, "axes", None)
    if not isinstance(axes, dict):
        return ""
    ax = axes.get(axis_id)
    if ax is None:
        return ""
    main_word = int(getattr(ax, "status_word", 0) or 0)
    slave_word = int(getattr(ax, "guide_status_word", 0) or 0)
    try:
        main = decode_drive_status(main_word)
        slave = decode_drive_status(slave_word)
        return f"{main.summary()}|{slave.summary()}"
    except Exception:
        return ""
