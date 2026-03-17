from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .models import AxisConfig
from .outbound_device_actions import append_reset_and_resync_intents, build_densi_actions
from .outbound_leases import sync_leases
from .outbound_motion import (
    append_joy_update_if_changed,
    append_lifetick_echoes,
    build_joy_update,
    sync_manual_motion,
)


@dataclass(frozen=True)
class OutboundContext:
    locked: bool
    selected_axes: tuple[AxisConfig, ...]
    selected_axis_ids: tuple[str, ...]


def build_outbound_context(*, locked: bool, selected_axes: Sequence[AxisConfig]) -> OutboundContext:
    axis_tuple = tuple(selected_axes)
    return OutboundContext(
        locked=locked,
        selected_axes=axis_tuple,
        selected_axis_ids=tuple(axis.axis_id for axis in axis_tuple),
    )


__all__ = [
    "OutboundContext",
    "append_joy_update_if_changed",
    "append_lifetick_echoes",
    "append_reset_and_resync_intents",
    "build_densi_actions",
    "build_joy_update",
    "build_outbound_context",
    "sync_leases",
    "sync_manual_motion",
]
