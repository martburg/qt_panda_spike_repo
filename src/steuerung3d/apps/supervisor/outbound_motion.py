from __future__ import annotations

from collections.abc import Iterable

from steuerung3d.core.intents import EchoLifeTick, Intent, JoyStateUpdate, LocalAxisManualRequest
from steuerung3d.core.telemetry import JoyState

from .models import AxisConfig, AxisRow


def sync_manual_motion(
    *,
    intents: list[Intent],
    locked: bool,
    joy: JoyState,
    selected_axis_ids: tuple[str, ...],
    manual_active_axis_ids: set[str],
) -> set[str]:
    desired_manual_axis_ids = set() if locked else set(selected_axis_ids)
    if (not bool(joy.deadman)) or locked:
        disable_axis_ids = sorted(manual_active_axis_ids)
        if disable_axis_ids:
            intents.append(
                LocalAxisManualRequest(axis_ids=tuple(disable_axis_ids), enable=False, rate=0.0)
            )
        return set()

    disable_axis_ids = sorted(manual_active_axis_ids - desired_manual_axis_ids)
    if disable_axis_ids:
        intents.append(
            LocalAxisManualRequest(axis_ids=tuple(disable_axis_ids), enable=False, rate=0.0)
        )
    if desired_manual_axis_ids:
        intents.append(
            LocalAxisManualRequest(
                axis_ids=tuple(sorted(desired_manual_axis_ids)),
                enable=True,
                rate=float(joy.soll_speed),
            )
        )
    return desired_manual_axis_ids


def append_lifetick_echoes(
    *,
    intents: list[Intent],
    profile_axes: Iterable[AxisConfig],
    rows_by_unit: dict[str, AxisRow],
    hip_open_counts: dict[str, int],
    supervisor_id: str,
) -> None:
    for axis in profile_axes:
        row = rows_by_unit.get(axis.unit_id)
        if row is None:
            continue
        if int(hip_open_counts.get(axis.unit_id, 0)) > 0:
            continue
        intents.append(
            EchoLifeTick(
                axis_id=axis.axis_id,
                value=int(getattr(row, "livetick", 0)) & 0xFFFF,
                hip_id=supervisor_id,
            )
        )


def build_joy_update(
    *, joy: JoyState, locked: bool, selected_axis_ids: tuple[str, ...]
) -> JoyState:
    motion_blocked = locked
    return JoyState(
        deadman=(False if motion_blocked else bool(joy.deadman)),
        soll_speed=(0.0 if motion_blocked else float(joy.soll_speed)),
        selected_axes=(() if motion_blocked else selected_axis_ids),
    )


def append_joy_update_if_changed(
    *,
    intents: list[Intent],
    joy_update: JoyState,
    last_joy_sent: JoyState | None,
) -> bool:
    changed = last_joy_sent != joy_update
    if changed:
        intents.append(
            JoyStateUpdate(
                deadman=joy_update.deadman,
                soll_speed=joy_update.soll_speed,
                selected_axes=joy_update.selected_axes,
            )
        )
    return changed
