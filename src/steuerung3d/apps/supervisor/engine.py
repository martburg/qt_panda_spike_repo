from __future__ import annotations

from collections.abc import Iterable

from steuerung3d.apps.yellow.engines.hip.presentation_extract import (
    parse_estop_word_from_snapshot,
)
from steuerung3d.core.intents import EchoLifeTick, JoyStateUpdate, RequestEstopReset, RequestResync
from steuerung3d.core.telemetry import JoyState, TelemetrySnapshot
from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot
from steuerung3d.protocol.banner_estate import BANNER_DYNAMIC_EXCLUDE
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS, decode_estop_word

from .models import (
    AxisConfig,
    AxisPhase,
    AxisRow,
    DensiRemoteAction,
    OutboundBatch,
    SupervisorProfile,
    SupervisorSnapshot,
)


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
        value = max(0, int(count))
        if value <= 0:
            self._hip_open_counts.pop(str(unit_id), None)
            return
        self._hip_open_counts[str(unit_id)] = value

    @property
    def hip_open_total(self) -> int:
        return sum(int(v) for v in self._hip_open_counts.values())

    @property
    def recover_requested(self) -> bool:
        return self._pending_recover

    def clear_recover_requested(self) -> None:
        self._pending_recover = False

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
        joy = (
            getattr(self._last_snapshot, "joy", JoyState())
            if self._last_snapshot is not None
            else JoyState()
        )
        return SupervisorSnapshot(
            title=self.profile.title,
            status_text=self._build_status_text(rows=rows, joy=joy),
            rows=rows,
            joy=joy,
            hip_open_total=self.hip_open_total,
        )

    def consume_outbound(self) -> OutboundBatch:
        intents = []
        densi_actions: dict[str, list[DensiRemoteAction]] = {}
        if self._pending_reset_estop:
            for axis in self.profile.axes:
                if axis.unit_id in self._rows:
                    intents.append(RequestEstopReset(axis_id=axis.axis_id, hip_id=axis.hip_id))
            self._pending_reset_estop = False
        if self._pending_resync:
            for axis in self.profile.axes:
                if axis.unit_id in self._rows:
                    intents.append(RequestResync(axis_id=axis.axis_id, hip_id=axis.hip_id))
            self._pending_resync = False
        if self._pending_estart:
            for axis in self.profile.axes:
                if axis.unit_id in self._rows and axis.densi_action_out:
                    densi_actions.setdefault(axis.unit_id, []).append(DensiRemoteAction("estart"))
            self._pending_estart = False

        for axis in self.profile.axes:
            if axis.unit_id in self._rows and axis.densi_action_out:
                densi_actions.setdefault(axis.unit_id, []).append(
                    DensiRemoteAction("chk_es_taster", value=bool(self._chk_requested))
                )

        joy = (
            getattr(self._last_snapshot, "joy", JoyState())
            if self._last_snapshot is not None
            else JoyState()
        )
        selected_axes = tuple(
            axis.axis_id
            for axis in self.profile.axes
            if axis.unit_id in self._rows and self._selected.get(axis.unit_id, True)
        )
        for axis in self.profile.axes:
            if axis.unit_id not in self._rows:
                continue
            if int(self._hip_open_counts.get(axis.unit_id, 0)) > 0:
                continue
            self._echo_tick = (int(self._echo_tick) + 1) & 0xFFFF
            intents.append(
                EchoLifeTick(
                    axis_id=axis.axis_id,
                    value=int(self._echo_tick),
                    hip_id=str(self.profile.supervisor_id),
                )
            )
        motion_blocked = self.hip_open_total > 0
        joy_update = JoyState(
            deadman=(False if motion_blocked else bool(joy.deadman)),
            soll_speed=(0.0 if motion_blocked else float(joy.soll_speed)),
            selected_axes=(() if motion_blocked else selected_axes),
        )
        changed = self._joy_sent != joy_update
        if changed:
            intents.append(
                JoyStateUpdate(
                    deadman=joy_update.deadman,
                    soll_speed=joy_update.soll_speed,
                    selected_axes=joy_update.selected_axes,
                )
            )
            self._joy_sent = joy_update
        return OutboundBatch(
            intents=tuple(intents),
            densi_actions={k: tuple(v) for k, v in densi_actions.items()},
            joy_update_changed=changed,
        )

    def _build_row(self, axis: AxisConfig, snap: TelemetrySnapshot) -> AxisRow | None:
        ax = snap.axes.get(axis.axis_id)
        densi = snap.densis.get(axis.densi_id)
        if ax is None and densi is None:
            return None
        attached = bool(densi.online) if densi is not None else ax is not None
        if not attached:
            return None
        scoped = axis_scoped_snapshot(snap, axis.axis_id)
        estop_word = int(parse_estop_word_from_snapshot(scoped))
        estate = self._estate_from_word(estop_word)
        stale = self._is_stale(snap=snap, axis_id=axis.axis_id, densi=densi)
        phase = self._phase_from(
            estate=estate,
            stale=stale,
            live_motion=self._is_live(ax=ax, joy=getattr(snap, "joy", JoyState())),
        )
        return AxisRow(
            unit_id=axis.unit_id,
            axis_id=axis.axis_id,
            densi_id=axis.densi_id,
            hip_id=axis.hip_id,
            selected=bool(self._selected.get(axis.unit_id, True)),
            phase=phase,
            estop=(phase == AxisPhase.ESTOP),
            livetick=int(getattr(ax, "device_tick", 0) or 0),
            livetick_diff=int(getattr(ax, "lifetick_age", 0) or 0),
            pos=float(getattr(ax, "pos", 0.0) or 0.0),
            vel=float(getattr(ax, "vel", 0.0) or 0.0),
            stale=stale,
            hip_open_count=int(self._hip_open_counts.get(axis.unit_id, 0)),
        )

    def _is_stale(self, *, snap: TelemetrySnapshot, axis_id: str, densi) -> bool:
        if densi is not None and bool(getattr(densi, "last_seen_age_ticks", 0) or 0):
            return int(getattr(densi, "last_seen_age_ticks", 0) or 0) * 50 >= int(
                self.profile.stale_after_ms
            )
        ax = snap.axes.get(axis_id)
        if ax is None:
            return True
        age = int(getattr(ax, "lifetick_age", 0) or 0)
        return age >= int(self.profile.stale_after_ms)

    @staticmethod
    def _estate_from_word(word: int) -> str:
        w = int(word) & 0xFFFFFFFF
        if w == 0:
            return "ESTOP"
        bits = decode_estop_word(w)
        trip_cause = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
        ok_keys = [
            k
            for k in ESTOP_OK_KEYS
            if (k not in BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))
        ]
        ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)
        taster = bool(bits.get("taster", False))
        schuetz = bool(bits.get("schuetz", False))
        brk_ok = bool(bits.get("brk1_ok", True)) and bool(bits.get("brk2_ok", True))
        if trip_cause or ok_chain_fault or not schuetz:
            return "ESTOP"
        if not taster:
            return "IDLE"
        return "READY" if brk_ok else "ARMED"

    @staticmethod
    def _phase_from(*, estate: str, stale: bool, live_motion: bool) -> AxisPhase:
        if stale:
            return AxisPhase.STALE
        if live_motion:
            return AxisPhase.LIVE
        estate_s = str(estate or "").upper()
        if estate_s == "READY":
            return AxisPhase.READY
        if estate_s == "ARMED":
            return AxisPhase.ARMED
        if estate_s == "IDLE":
            return AxisPhase.IDLE
        return AxisPhase.ESTOP

    @staticmethod
    def _is_live(*, ax, joy: JoyState) -> bool:
        if ax is None:
            return False
        if not bool(joy.deadman):
            return False
        return (
            abs(float(getattr(ax, "vel", 0.0) or 0.0)) > 1e-6 or abs(float(joy.soll_speed)) > 1e-6
        )

    def _build_status_text(self, *, rows: Iterable[AxisRow], joy: JoyState) -> str:
        rows_t = tuple(rows)
        phases = {row.phase for row in rows_t}
        if not rows_t:
            state = "NO AXES"
        elif AxisPhase.ESTOP in phases:
            state = "ESTOP"
        elif AxisPhase.STALE in phases:
            state = "DEGRADED"
        elif AxisPhase.LIVE in phases:
            state = "LIVE"
        elif rows_t and all(row.phase == AxisPhase.READY for row in rows_t):
            state = "READY"
        elif AxisPhase.ARMED in phases:
            state = "ARMING"
        else:
            state = "IDLE"
        joy_state = "active" if bool(joy.deadman) and self.hip_open_total <= 0 else "online"
        status = f"System: {state} | axes: {len(rows_t)} | joystick: {joy_state}"
        if self.hip_open_total > 0:
            status += f" | hip: {self.hip_open_total} open"
        return status
