from __future__ import annotations

from collections.abc import Iterable

from steuerung3d.apps.yellow.engines.hip.presentation_extract import (
    parse_estop_word_from_snapshot,
)
from steuerung3d.core.intents import JoyStateUpdate, RequestEstopReset, RequestResync
from steuerung3d.core.telemetry import JoyState, TelemetrySnapshot
from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot
from steuerung3d.protocol.banner_estate import BANNER_DYNAMIC_EXCLUDE
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS, decode_estop_word

from .models import (
    DensiRemoteAction,
    OutboundBatch,
    PairConfig,
    PairPhase,
    PairRow,
    SupervisorProfile,
    SupervisorSnapshot,
)


class SupervisorEngine:
    def __init__(self, profile: SupervisorProfile) -> None:
        self.profile = profile
        self._selected: dict[str, bool] = {p.pair_id: bool(p.selected) for p in profile.pairs}
        self._last_snapshot: TelemetrySnapshot | None = None
        self._rows: dict[str, PairRow] = {}
        self._pending_reset_estop = False
        self._pending_estart = False
        self._pending_resync = False
        self._pending_recover = False
        self._chk_requested = False
        self._joy_sent: JoyState | None = None

    def ingest(self, snap: TelemetrySnapshot) -> None:
        self._last_snapshot = snap
        rows: dict[str, PairRow] = {}
        for pair in self.profile.pairs:
            row = self._build_row(pair, snap)
            if row is not None:
                rows[pair.pair_id] = row
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

    @property
    def recover_requested(self) -> bool:
        return self._pending_recover

    def clear_recover_requested(self) -> None:
        self._pending_recover = False

    def snapshot(self) -> SupervisorSnapshot:
        rows = tuple(sorted(self._rows.values(), key=lambda r: r.pair_id))
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
        )

    def consume_outbound(self) -> OutboundBatch:
        intents = []
        densi_actions: dict[str, list[DensiRemoteAction]] = {}
        if self._pending_reset_estop:
            for pair in self.profile.pairs:
                if pair.pair_id in self._rows:
                    intents.append(RequestEstopReset(axis_id=pair.axis_id, hip_id=pair.hip_id))
            self._pending_reset_estop = False
        if self._pending_resync:
            for pair in self.profile.pairs:
                if pair.pair_id in self._rows:
                    intents.append(RequestResync(axis_id=pair.axis_id, hip_id=pair.hip_id))
            self._pending_resync = False
        if self._pending_estart:
            for pair in self.profile.pairs:
                if pair.pair_id in self._rows and pair.densi_action_out:
                    densi_actions.setdefault(pair.pair_id, []).append(DensiRemoteAction("estart"))
            self._pending_estart = False

        for pair in self.profile.pairs:
            if pair.pair_id in self._rows and pair.densi_action_out:
                densi_actions.setdefault(pair.pair_id, []).append(
                    DensiRemoteAction("chk_es_taster", value=bool(self._chk_requested))
                )

        joy = (
            getattr(self._last_snapshot, "joy", JoyState())
            if self._last_snapshot is not None
            else JoyState()
        )
        selected_axes = tuple(
            pair.axis_id
            for pair in self.profile.pairs
            if pair.pair_id in self._rows and self._selected.get(pair.pair_id, True)
        )
        joy_update = JoyState(
            deadman=bool(joy.deadman),
            soll_speed=float(joy.soll_speed),
            selected_axes=selected_axes,
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

    def _build_row(self, pair: PairConfig, snap: TelemetrySnapshot) -> PairRow | None:
        ax = snap.axes.get(pair.axis_id)
        densi = snap.densis.get(pair.densi_id)
        if ax is None and densi is None:
            return None
        attached = bool(densi.online) if densi is not None else ax is not None
        if not attached:
            return None
        scoped = axis_scoped_snapshot(snap, pair.axis_id)
        estop_word = int(parse_estop_word_from_snapshot(scoped))
        estate = self._estate_from_word(estop_word)
        stale = self._is_stale(snap=snap, axis_id=pair.axis_id, densi=densi)
        phase = self._phase_from(
            estate=estate,
            stale=stale,
            live_motion=self._is_live(ax=ax, joy=getattr(snap, "joy", JoyState())),
        )
        return PairRow(
            pair_id=pair.pair_id,
            axis_id=pair.axis_id,
            densi_id=pair.densi_id,
            hip_id=pair.hip_id,
            selected=bool(self._selected.get(pair.pair_id, True)),
            phase=phase,
            estop=(phase == PairPhase.ESTOP),
            livetick=int(getattr(ax, "device_tick", 0) or 0),
            pos=float(getattr(ax, "pos", 0.0) or 0.0),
            vel=float(getattr(ax, "vel", 0.0) or 0.0),
            stale=stale,
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
    def _phase_from(*, estate: str, stale: bool, live_motion: bool) -> PairPhase:
        if stale:
            return PairPhase.STALE
        if live_motion:
            return PairPhase.LIVE
        estate_s = str(estate or "").upper()
        if estate_s == "READY":
            return PairPhase.READY
        if estate_s == "ARMED":
            return PairPhase.ARMED
        if estate_s == "IDLE":
            return PairPhase.IDLE
        return PairPhase.ESTOP

    @staticmethod
    def _is_live(*, ax, joy: JoyState) -> bool:
        if ax is None:
            return False
        if not bool(joy.deadman):
            return False
        return (
            abs(float(getattr(ax, "vel", 0.0) or 0.0)) > 1e-6 or abs(float(joy.soll_speed)) > 1e-6
        )

    def _build_status_text(self, *, rows: Iterable[PairRow], joy: JoyState) -> str:
        rows_t = tuple(rows)
        phases = {row.phase for row in rows_t}
        if not rows_t:
            state = "NO PAIRS"
        elif PairPhase.ESTOP in phases:
            state = "ESTOP"
        elif PairPhase.STALE in phases:
            state = "DEGRADED"
        elif PairPhase.LIVE in phases:
            state = "LIVE"
        elif rows_t and all(row.phase == PairPhase.READY for row in rows_t):
            state = "READY"
        elif PairPhase.ARMED in phases:
            state = "ARMING"
        else:
            state = "IDLE"
        joy_state = "active" if bool(joy.deadman) else "online"
        return f"System: {state} | pairs: {len(rows_t)} | joystick: {joy_state}"
