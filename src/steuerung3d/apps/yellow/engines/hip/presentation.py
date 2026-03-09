"""Presentation helpers for HipEngine (Qt-free).

Typing note:
These helpers are used across the Qt-free HiP pipeline. Keep annotations precise
so Pylance/Pyright can follow the `TelemetrySnapshot` / `AxisTelemetry` surface.
"""

from __future__ import annotations

from ...domain.banner_facts import derive_banner_estate_from_word
from .presentation_cut_markers import compute_cut_markers_state
from .presentation_drive_status import compute_drive_status_summary, compute_drive_status_texts
from .presentation_extract import (
    compute_tick_text,
    get_lifetick_age,
    parse_estop_word_from_snapshot,
    raw_tail_token,
    raw_uplink_float,
    read_amp_and_temp,
    read_axis_pos_vel,
)
from .presentation_readouts import compute_readouts_state


def compute_banner_estate(*, estop_word: int, within_brake_grace: bool) -> str:
    return derive_banner_estate_from_word(
        int(estop_word),
        within_brake_grace=lambda: bool(within_brake_grace),
    )


__all__ = [
    "compute_banner_estate",
    "compute_cut_markers_state",
    "compute_drive_status_summary",
    "compute_drive_status_texts",
    "compute_readouts_state",
    "compute_tick_text",
    "get_lifetick_age",
    "parse_estop_word_from_snapshot",
    "raw_tail_token",
    "raw_uplink_float",
    "read_amp_and_temp",
    "read_axis_pos_vel",
]
