from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from steuerung3d.core.telemetry import TelemetrySnapshot

try:
    from steuerung3d.protocol.drive_status import (
        decode_drive_status as _decode_drive_status,  # type: ignore
    )
except Exception:  # pragma: no cover
    _decode_drive_status = None  # type: ignore


decode_drive_status = cast(Callable[[int], Any] | None, _decode_drive_status)


def compute_drive_status_texts(*, snap: TelemetrySnapshot, axis_id: str) -> tuple[str, str]:
    if decode_drive_status is None:
        return "", ""
    if not axis_id:
        return "", ""
    ax = snap.axes.get(axis_id)
    if ax is None:
        return "", ""
    main_word = int(ax.status_word or 0)
    slave_word = int(ax.guide_status_word or 0)
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
    ax = snap.axes.get(axis_id)
    if ax is None:
        return ""
    main_word = int(ax.status_word or 0)
    slave_word = int(ax.guide_status_word or 0)
    try:
        main = decode_drive_status(main_word)
        slave = decode_drive_status(slave_word)
        return f"{main.summary()}|{slave.summary()}"
    except Exception:
        return ""
