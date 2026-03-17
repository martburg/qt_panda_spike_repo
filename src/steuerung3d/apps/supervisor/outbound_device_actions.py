from __future__ import annotations

from collections.abc import Sequence

from steuerung3d.core.intents import Intent, RequestEstopReset, RequestResync

from .models import AxisConfig, DensiRemoteAction


def append_reset_and_resync_intents(
    *,
    intents: list[Intent],
    supervisor_id: str,
    locked: bool,
    selected_axes: Sequence[AxisConfig],
    pending_reset_estop: bool,
    pending_resync: bool,
) -> None:
    if not locked and pending_reset_estop:
        for axis in selected_axes:
            intents.append(
                RequestEstopReset(
                    axis_id=axis.axis_id,
                    hip_id=supervisor_id,
                    actor_kind="supervisor",
                )
            )
    if not locked and pending_resync:
        for axis in selected_axes:
            intents.append(
                RequestResync(
                    axis_id=axis.axis_id,
                    hip_id=supervisor_id,
                    actor_kind="supervisor",
                )
            )


def build_densi_actions(
    *,
    locked: bool,
    selected_axes: Sequence[AxisConfig],
    pending_estart: bool,
    chk_requested: bool,
) -> dict[str, tuple[DensiRemoteAction, ...]]:
    actions: dict[str, list[DensiRemoteAction]] = {}
    if not locked and pending_estart:
        for axis in selected_axes:
            if axis.densi_action_out:
                actions.setdefault(axis.unit_id, []).append(DensiRemoteAction("estart"))
    if not locked:
        for axis in selected_axes:
            if axis.densi_action_out:
                actions.setdefault(axis.unit_id, []).append(
                    DensiRemoteAction("chk_es_taster", value=bool(chk_requested))
                )
    return {unit_id: tuple(unit_actions) for unit_id, unit_actions in actions.items()}
