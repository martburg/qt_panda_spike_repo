"""HiP drive status helpers (compat shim)."""

from __future__ import annotations

from .engine import HipDriveStatusState, HipEngine


def compute_drive_status_texts(*, snap, axis_id: str) -> tuple[str, str]:
    return HipEngine._compute_drive_status_texts(snap=snap, axis_id=axis_id)


__all__ = [
    "HipDriveStatusState",
    "compute_drive_status_texts",
    "HipEngine",
]
