from __future__ import annotations

from steuerung3d.core.intents import Intent
from steuerung3d.core.telemetry import JoyState, TelemetrySnapshot

from .models import AxisConfig, AxisRow, OutboundBatch, SupervisorProfile, SupervisorSnapshot
from .outbound import (
    append_joy_update_if_changed,
    append_lifetick_echoes,
    append_reset_and_resync_intents,
    build_densi_actions,
    build_joy_update,
    build_outbound_context,
    sync_leases,
    sync_manual_motion,
)
from .rows import build_axis_row
from .status import build_status_text


class SupervisorEngine:
    def __init__(self, profile: SupervisorProfile) -> None:
        self.profile = profile
        self._selected: dict[str, bool] = {
            axis.unit_id: bool(axis.selected) for axis in profile.axes
        }
        self._last_snapshot: TelemetrySnapshot | None = None
        self._rows: dict[str, AxisRow] = {}
        self._pending_reset_estop = False
        self._pending_estart = False
        self._pending_resync = False
        self._pending_recover = False
        self._chk_requested = False
        self._joy_sent: JoyState | None = None
        self._hip_open_counts: dict[str, int] = {}
        self._leased_axis_ids: set[str] = set()
        self._manual_active_axis_ids: set[str] = set()
        self._echo_tick: int = 0

    def ingest(self, snap: TelemetrySnapshot) -> None:
        self._last_snapshot = snap
        rows: dict[str, AxisRow] = {}
        for axis in self.profile.axes:
            row = self._build_row(axis, snap)
            if row is not None:
                rows[axis.unit_id] = row
        self._rows = rows

    def set_selected(self, pair_id: str, selected: bool) -> None:
        self._selected[str(pair_id)] = bool(selected)

    def queue_reset_estop(self) -> None:
        self._pending_reset_estop = True

    def queue_estart(self) -> None:
        self._pending_estart = True

    def queue_resync(self) -> None:
        self._pending_resync = True

    def queue_recover(self) -> None:
        self._pending_recover = True

    def set_chk_requested(self, checked: bool) -> None:
        self._chk_requested = bool(checked)

    def set_hip_open_count(self, unit_id: str, count: int) -> None:
        was_locked = self._lock_active()
        value = max(0, int(count))
        if value <= 0:
            self._hip_open_counts.pop(str(unit_id), None)
        else:
            self._hip_open_counts[str(unit_id)] = value
        now_locked = self._lock_active()
        if now_locked and not was_locked:
            self._chk_requested = False
            self._pending_reset_estop = False
            self._pending_estart = False
            self._pending_resync = False

    @property
    def hip_open_total(self) -> int:
        return sum(int(v) for v in self._hip_open_counts.values())

    @property
    def recover_requested(self) -> bool:
        return self._pending_recover

    def clear_recover_requested(self) -> None:
        self._pending_recover = False

    def _lock_active(self) -> bool:
        return self.hip_open_total > 0

    def _selected_units(self) -> tuple[str, ...]:
        return tuple(
            axis.unit_id
            for axis in self.profile.axes
            if axis.unit_id in self._rows and self._selected.get(axis.unit_id, True)
        )

    def _selected_axes(self) -> tuple[AxisConfig, ...]:
        selected = set(self._selected_units())
        return tuple(axis for axis in self.profile.axes if axis.unit_id in selected)

    def snapshot(self) -> SupervisorSnapshot:
        rows = tuple(
            sorted(
                (
                    AxisRow(
                        unit_id=row.unit_id,
                        axis_id=row.axis_id,
                        densi_id=row.densi_id,
                        hip_id=row.hip_id,
                        selected=row.selected,
                        phase=row.phase,
                        estop=row.estop,
                        livetick=row.livetick,
                        livetick_diff=row.livetick_diff,
                        pos=row.pos,
                        vel=row.vel,
                        stale=row.stale,
                        hip_open_count=int(self._hip_open_counts.get(row.unit_id, 0)),
                    )
                    for row in self._rows.values()
                ),
                key=lambda r: r.unit_id,
            )
        )
        joy = self._current_joy()
        return SupervisorSnapshot(
            title=self.profile.title,
            status_text=build_status_text(rows=rows, joy=joy, hip_open_total=self.hip_open_total),
            rows=rows,
            joy=joy,
            hip_open_total=self.hip_open_total,
        )

    def consume_outbound(self) -> OutboundBatch:
        intents: list[Intent] = []
        context = build_outbound_context(
            locked=self._lock_active(),
            selected_axes=self._selected_axes(),
        )

        self._leased_axis_ids = sync_leases(
            intents=intents,
            supervisor_id=str(self.profile.supervisor_id),
            locked=context.locked,
            selected_axes=context.selected_axes,
            leased_axis_ids=self._leased_axis_ids,
        )
        append_reset_and_resync_intents(
            intents=intents,
            supervisor_id=str(self.profile.supervisor_id),
            locked=context.locked,
            selected_axes=context.selected_axes,
            pending_reset_estop=self._pending_reset_estop,
            pending_resync=self._pending_resync,
        )
        self._pending_reset_estop = False
        self._pending_resync = False

        densi_actions = build_densi_actions(
            locked=context.locked,
            selected_axes=context.selected_axes,
            pending_estart=self._pending_estart,
            chk_requested=self._chk_requested,
        )
        self._pending_estart = False

        joy = self._current_joy()
        self._manual_active_axis_ids = sync_manual_motion(
            intents=intents,
            locked=context.locked,
            joy=joy,
            selected_axis_ids=context.selected_axis_ids,
            manual_active_axis_ids=self._manual_active_axis_ids,
        )
        append_lifetick_echoes(
            intents=intents,
            profile_axes=self.profile.axes,
            rows_by_unit=self._rows,
            hip_open_counts=self._hip_open_counts,
            supervisor_id=str(self.profile.supervisor_id),
        )

        joy_update = build_joy_update(
            joy=joy,
            locked=context.locked,
            selected_axis_ids=context.selected_axis_ids,
        )
        changed = append_joy_update_if_changed(
            intents=intents,
            joy_update=joy_update,
            last_joy_sent=self._joy_sent,
        )
        if changed:
            self._joy_sent = joy_update
        return OutboundBatch(
            intents=tuple(intents),
            densi_actions=densi_actions,
            joy_update_changed=changed,
        )

    def _build_row(self, axis: AxisConfig, snap: TelemetrySnapshot) -> AxisRow | None:
        return build_axis_row(
            axis=axis,
            snap=snap,
            selected=bool(self._selected.get(axis.unit_id, True)),
            stale_after_ms=int(self.profile.stale_after_ms),
            hip_open_count=int(self._hip_open_counts.get(axis.unit_id, 0)),
        )

    def _current_joy(self) -> JoyState:
        if self._last_snapshot is None:
            return JoyState()
        return getattr(self._last_snapshot, "joy", JoyState())
