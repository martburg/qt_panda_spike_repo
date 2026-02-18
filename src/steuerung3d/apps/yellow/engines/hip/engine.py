"""Qt-free HiP engine (minimal seam).

Purpose: provide a stable place to compute attach-state enablement and banner
estate without changing controller behavior. This is used for shadow-mode
comparison before cutover.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any, Iterable

from steuerung3d.core.intents import (
    ClaimAxis,
    EchoLifeTick,
    ReleaseAxis,
    RequestEstopReset,
    RequestResync,
)
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.estop_bits import ESTOP_SPECS, decode_estop_word
from steuerung3d.util.tick import compute_time_tick

from ...domain.param_txn import ParamEditTxnClient, RetryEvent
from ...domain.ui_estop import (
    age_to_online_state,
    compute_estop_dot_states,
    compute_header_estop_dot_states,
    infer_estop_profile,
    active_estop_keys_for_profile,
)
from ...domain.ui_banner import BANNER_COLORS, derive_banner_estate_from_word
from ...domain.ui_format import fmt_f_unit, fmt_i_unit
from ...domain.yellow_maps import PARAM_WIDGETS as _PARAM_WIDGETS, LIMIT_WIDGETS as _LIMIT_WIDGETS

# NOTE: drive status decoder is optional.
try:
    from steuerung3d.protocol.drive_status import decode_drive_status  # type: ignore
except Exception:  # pragma: no cover
    decode_drive_status = None  # type: ignore


NOT_ATTACHED = "NotAttached"


@dataclass(frozen=True)
class HipAttachInputs:
    attached: bool
    modal_locked: bool
    last_mode: str
    last_estate: str


@dataclass(frozen=True)
class HipAttachState:
    attached: bool
    tabs_enabled: bool | None
    setup_enabled: bool
    main_amp_reset_enabled: bool
    resync_enabled: bool
    estop_reset_enabled: bool | None


@dataclass(frozen=True)
class HipBannerInputs:
    estop_word: int
    within_brake_grace: bool


@dataclass(frozen=True)
class HipAttachCombo:
    items: list[str]
    current: str
    enabled: bool
    fixed_axis_applied: bool


@dataclass(frozen=True)
class HipParamAction:
    kind: str  # edit|write|cancel
    group: str


@dataclass(frozen=True)
class HipUiInputs:
    axis_selected: str
    axis_selection_changed: bool
    estop_reset_clicked: bool
    resync_clicked: bool
    param_actions: list[HipParamAction]
    param_values: dict[str, dict[str, float]]


@dataclass(frozen=True)
class HipParamButtons:
    edit_enabled: bool
    write_enabled: bool
    cancel_enabled: bool


@dataclass(frozen=True)
class HipParamGroup:
    fields_enabled: bool
    buttons: HipParamButtons


@dataclass(frozen=True)
class HipParamUiState:
    modal_lock_active: bool
    modal_lock_group: str
    groups: dict[str, HipParamGroup]


@dataclass(frozen=True)
class HipParamCommitDialog:
    level: str  # "info" | "warning"
    title: str
    message: str


@dataclass(frozen=True)
class HipBannerState:
    estate: str
    bg: str
    fg: str
    left_text: str
    right_text: str


@dataclass(frozen=True)
class HipHeaderDots:
    online_state: str | None
    ready_state: str | None
    fbt_state: str | None
    brk1_state: str | None
    brk2_state: str | None


@dataclass(frozen=True)
class HipDriveStatusState:
    main_text: str
    slave_text: str


@dataclass(frozen=True)
class HipEstopState:
    dots: dict[str, str | None]
    reset_enabled: bool
    checkbox_states: dict[str, bool]
    active_keys: set[str]
    profile_changed: bool


@dataclass(frozen=True)
class HipReadoutsState:
    pos_text: str
    vel_text: str
    amp_text: str
    temp_text: str
    guider_min_text: str
    guider_max_text: str
    guider_val_text: str
    guider_speed_text: str
    vel_cmd_min: int
    vel_cmd_max: int
    vel_cmd_val: int
    limit_min: int
    limit_max: int
    limit_val: int
    guider_range_min: int
    guider_range_max: int
    guider_range_val: int
    guider_speed_min: int
    guider_speed_max: int
    guider_speed_val: int


@dataclass(frozen=True)
class HipCutMarkersState:
    cut_time_text: str
    cut_pos_text: str
    cut_vel_text: str
    posdiff_text: str


@dataclass(frozen=True)
class HipViewModel:
    tick_text: str
    age_ms: int | None
    stale: bool
    lifetick_age: int | None
    online_state: str | None
    estop: bool
    fault: bool
    drive_status_summary: str
    banner: HipBannerState | None = None
    header_dots: HipHeaderDots | None = None
    drive_status: HipDriveStatusState | None = None
    estop_state: HipEstopState | None = None
    readouts: HipReadoutsState | None = None
    cut_markers: HipCutMarkersState | None = None
    attach_state: HipAttachState | None = None
    attach_combo: HipAttachCombo | None = None
    param_ui: HipParamUiState | None = None
    param_values: dict[str, float] = field(default_factory=dict)
    param_freeze_group: str = ""
    limit_values: dict[str, float] = field(default_factory=dict)
    param_writeback_group: str = ""
    param_writeback_values: dict[str, float] = field(default_factory=dict)
    param_writeback_message: str = ""
    param_commit_dialog: HipParamCommitDialog | None = None


@dataclass
class HipState:
    prev_device_tick: int | None = None
    last_lifetick_echo_sent: dict[str, int] = field(default_factory=dict)
    selected_axis: str = ""
    fixed_axis_applied: bool = False
    last_ui_axis_selected: str = ""
    prev_estop_profile: str = ""
    pending_commit_req_id: str = ""
    pending_commit_group: str = ""
    pending_commit_values: dict[str, float] = field(default_factory=dict)
    commit_dialog_shown_for: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class HipStepInputs:
    snap: TelemetrySnapshot
    hip_id: str
    last_rx_ns: int | None
    now_ns: int
    stale_after_ms: int
    fixed_axis: str
    lock_axis_combo: bool
    last_mode: str
    last_estate: str
    ui: HipUiInputs
    core_acks: list[str]


@dataclass(frozen=True)
class HipStepResult:
    view_model: HipViewModel
    legacy_view_model: HipViewModel
    intents: list[object]
    resync_ignored: bool
    resync_block_reason: str
    txn_events: list[RetryEvent] = field(default_factory=list)


class HipEngine:
    """Minimal HipEngine surface (shadow-mode only)."""

    def __init__(self, *, hip_id: str = "") -> None:
        self._param_txn = ParamEditTxnClient(hip_id=str(hip_id or ""))
        self._taster_prev: dict[str, bool] = {}
        self._taster_pressed_s: dict[str, float] = {}
        self.state = HipState()

    def _update_taster_edge(self, axis_id: str, taster: bool, now_s: float) -> None:
        prev = self._taster_prev.get(axis_id, taster)
        if (not prev) and taster:
            self._taster_pressed_s[axis_id] = float(now_s)
        self._taster_prev[axis_id] = bool(taster)

    def _within_brake_grace(self, axis_id: str, now_s: float, grace_s: float) -> bool:
        t0 = self._taster_pressed_s.get(axis_id)
        if t0 is None:
            return False
        return (float(now_s) - float(t0)) <= float(grace_s)

    def compute_attach_state(self, inputs: HipAttachInputs) -> HipAttachState:
        attached = bool(inputs.attached)
        modal_locked = bool(inputs.modal_locked)
        last_mode = str(inputs.last_mode or "").upper()
        last_estate = str(inputs.last_estate or "").upper()

        # Preserve legacy behavior: when modal-locked and attached, do not
        # force tabs enabled/disabled.
        if attached and modal_locked:
            tabs_enabled: bool | None = None
        else:
            tabs_enabled = bool(attached) and (not modal_locked)

        setup_enabled = bool(attached) and (not modal_locked)
        main_amp_reset_enabled = bool(attached) and (not modal_locked)

        resync_enabled = (
            bool(attached)
            and (not modal_locked)
            and (last_mode == "IDLE")
            and (last_estate == "IDLE")
        )

        # Preserve legacy behavior: only force-disable when unattached.
        estop_reset_enabled: bool | None = None if attached else False

        return HipAttachState(
            attached=attached,
            tabs_enabled=tabs_enabled,
            setup_enabled=setup_enabled,
            main_amp_reset_enabled=main_amp_reset_enabled,
            resync_enabled=resync_enabled,
            estop_reset_enabled=estop_reset_enabled,
        )

    def compute_banner_estate(self, inputs: HipBannerInputs) -> str:
        return derive_banner_estate_from_word(
            int(inputs.estop_word),
            within_brake_grace=lambda: bool(inputs.within_brake_grace),
        )

    def step(self, inputs: HipStepInputs) -> HipStepResult:
        snap = inputs.snap
        ui = inputs.ui
        hip_id = str(inputs.hip_id or "")
        if getattr(self._param_txn, "hip_id", "") != hip_id:
            self._param_txn.hip_id = hip_id

        axes = getattr(snap, "axes", None)
        axes = axes if isinstance(axes, dict) else {}
        axis_ids = sorted(list(axes.keys()))

        ui_axis = str(ui.axis_selected or "").strip()
        if ui.axis_selection_changed:
            self.state.last_ui_axis_selected = ui_axis
        elif self.state.last_ui_axis_selected:
            ui_axis = self.state.last_ui_axis_selected

        fixed_axis = str(inputs.fixed_axis or "").strip()
        prev_selected = str(self.state.selected_axis or "").strip()
        fixed_applied = bool(self.state.fixed_axis_applied)

        items = [NOT_ATTACHED] + axis_ids
        combo_enabled = True
        combo_current = NOT_ATTACHED
        if fixed_axis and fixed_axis in axis_ids:
            selected_axis = fixed_axis
            combo_current = fixed_axis
            fixed_applied = True
            combo_enabled = not (bool(inputs.lock_axis_combo) and fixed_applied)
        else:
            if ui_axis in axis_ids:
                selected_axis = ui_axis
            elif ui_axis == NOT_ATTACHED or not ui_axis:
                selected_axis = ""
            else:
                selected_axis = ""

            if ui_axis in items:
                combo_current = ui_axis
            elif prev_selected in axis_ids:
                combo_current = prev_selected
            else:
                combo_current = NOT_ATTACHED

        attach_combo = HipAttachCombo(
            items=items,
            current=combo_current,
            enabled=bool(combo_enabled),
            fixed_axis_applied=bool(fixed_applied),
        )

        intents: list[object] = []
        if ui.axis_selection_changed:
            if prev_selected and (not selected_axis or prev_selected != selected_axis):
                intents.append(ReleaseAxis(axis_id=prev_selected, hip_id=hip_id))
            if selected_axis and selected_axis != prev_selected:
                intents.append(ClaimAxis(axis_id=selected_axis, hip_id=hip_id))

        axis_id = str(selected_axis or fixed_axis or "").strip()
        attached = bool(selected_axis or fixed_axis)

        prev_device_tick = self.state.prev_device_tick
        tick_text, new_prev = self._compute_tick_text(
            snap=snap,
            axis_id=axis_id,
            prev_device_tick=prev_device_tick,
        )

        lifetick_age = self._get_lifetick_age(snap=snap, axis_id=axis_id)
        online_state = None
        if lifetick_age is not None:
            online_state = age_to_online_state(age=float(lifetick_age), good_max=30.0, warn_max=500.0)

        age_ms: int | None
        if inputs.last_rx_ns is None:
            age_ms = None
        else:
            age_ms = int((int(inputs.now_ns) - int(inputs.last_rx_ns)) / 1_000_000.0)
        stale = (age_ms is None) or (age_ms >= int(inputs.stale_after_ms))

        estop = bool(getattr(snap, "estop", False))
        fault = bool(getattr(snap, "fault", False))

        main_text, slave_text = self._compute_drive_status_texts(snap=snap, axis_id=axis_id)
        drive_status_summary = f"{main_text}|{slave_text}" if (main_text or slave_text) else ""
        drive_status = HipDriveStatusState(main_text=str(main_text), slave_text=str(slave_text))

        now_s = float(inputs.now_ns) / 1e9
        estop_word = int(self._parse_estop_word_from_snapshot(snap))
        logical = decode_estop_word(estop_word)

        mode_now = str(getattr(snap, "mode", "") or "")

        axis_id_for_estate = axis_id
        if not axis_id_for_estate:
            if axis_ids:
                axis_id_for_estate = axis_ids[0]
            else:
                axis_id_for_estate = "X"

        taster = bool(logical.get("taster", False))
        self._update_taster_edge(axis_id_for_estate, taster, now_s)
        within_banner = self._within_brake_grace(axis_id_for_estate, now_s, 2.0)
        within_brake = self._within_brake_grace(axis_id_for_estate, now_s, 3.0)

        estate = derive_banner_estate_from_word(
            int(estop_word),
            within_brake_grace=(lambda: bool(within_banner)),
        )
        bg, fg = BANNER_COLORS.get(estate, ("#F9E547", "#000000"))
        banner = HipBannerState(
            estate=str(estate),
            bg=str(bg),
            fg=str(fg),
            left_text=str(estate),
            right_text=str(estate),
        )

        def _brake_ok_display(raw: bool) -> bool:
            if bool(taster) and bool(within_brake):
                return True
            return bool(raw)

        hdr_states = compute_header_estop_dot_states(
            taster=bool(taster),
            ready=bool(logical.get("ready", False)),
            brk1_raw=bool(logical.get("brk1_ok", False)),
            brk2_raw=bool(logical.get("brk2_ok", False)),
            brake_ok_display=_brake_ok_display,
        )
        header_dots = HipHeaderDots(
            online_state=online_state,
            ready_state=hdr_states.get("dotHdrReady"),
            fbt_state=hdr_states.get("dotHdrFbt"),
            brk1_state=hdr_states.get("dotHdrBrake1"),
            brk2_state=hdr_states.get("dotHdrBrake2"),
        )

        profile = infer_estop_profile(logical)
        active_keys = active_estop_keys_for_profile(profile, ESTOP_SPECS.keys())
        profile_changed = str(profile) != str(self.state.prev_estop_profile or "")

        estop_dots = compute_estop_dot_states(
            bits=logical,
            taster=bool(taster),
            specs=ESTOP_SPECS.values(),
            brake_ok_display=_brake_ok_display,
        )
        checkbox_states = {spec.key: bool(logical.get(spec.key, False)) for spec in ESTOP_SPECS.values()}
        reset_enabled = bool(logical.get("reset_able", False)) if attached else False
        estop_state = HipEstopState(
            dots=estop_dots,
            reset_enabled=bool(reset_enabled),
            checkbox_states=checkbox_states,
            active_keys=set(active_keys),
            profile_changed=bool(profile_changed),
        )

        legacy_vm = HipViewModel(
            tick_text=str(tick_text),
            age_ms=age_ms,
            stale=bool(stale),
            lifetick_age=lifetick_age,
            online_state=online_state,
            estop=bool(estop),
            fault=bool(fault),
            drive_status_summary=str(drive_status_summary or ""),
        )

        readouts = None
        cut_markers = None
        params = getattr(snap, "params", {}) or {}
        if attached and axis_id and axis_id in axes:
            ax = axes.get(axis_id)
            pos, vel = self._read_axis_pos_vel(ax)
            amp, tmp = self._read_amp_and_temp(params=params, snap=snap)
            readouts = self._compute_readouts_state(
                ax=ax,
                pos=pos,
                vel=vel,
                amp=amp,
                temp=tmp,
                params=params,
                snap=snap,
            )
            cut_markers = self._compute_cut_markers_state(
                snap=snap,
                params=params,
                estate=estate,
            )

        param_writeback_group = ""
        param_writeback_values: dict[str, float] = {}
        param_writeback_message = ""

        # --- UI actions -> intents (param ops, estop reset, resync) ---
        if ui.estop_reset_clicked and axis_id:
            intents.append(RequestEstopReset(axis_id=axis_id, hip_id=hip_id))

        resync_ignored = False
        resync_reason = ""
        if ui.resync_clicked:
            if (str(mode_now).upper() != "IDLE") or (str(estate).upper() != "IDLE"):
                resync_ignored = True
                resync_reason = f"mode={str(mode_now)} estate={str(estate)}"
            else:
                intents.append(RequestResync(axis_id=str(axis_id or ""), hip_id=hip_id))
                if readouts is not None:
                    cut_markers = HipCutMarkersState("--", "--", "--", "--")

        # Apply core acks before param txn decisions
        self._param_txn.handle_core_acks(list(inputs.core_acks or []))

        for action in list(ui.param_actions or []):
            if not axis_id:
                continue
            group = str(action.group or "")
            kind = str(action.kind or "")
            if kind == "edit":
                self._param_txn.start_local_edit(group)
                intent = self._param_txn.make_begin_intent(axis_id=axis_id, group=group)
                self._param_txn.send(intent, group=group, kind="begin", publish=intents.append, now_ns=int(inputs.now_ns))
            elif kind == "write":
                vals = dict(ui.param_values.get(group, {}) if isinstance(ui.param_values, dict) else {})
                fixed = dict(vals)
                if group == "pos":
                    fixed = self._normalize_pos_chain(fixed)
                elif group == "guider":
                    fixed = self._normalize_guider_range(fixed)

                if fixed != vals:
                    param_writeback_group = group
                    param_writeback_values = dict(fixed)
                    if group == "pos":
                        lines = []
                        for k in ("HardMax", "UserMax", "UserMin", "HardMin"):
                            if k in vals and k in fixed and float(vals[k]) != float(fixed[k]):
                                lines.append(f"{k}: {float(vals[k]):g} → {float(fixed[k]):g}")
                        if lines:
                            param_writeback_message = (
                                "The rule HardMax ≥ UserMax ≥ UserMin ≥ HardMin was enforced.\n\n"
                                + "\n".join(lines)
                            )

                intent = self._param_txn.make_write_intent(axis_id=axis_id, group=group, values=fixed)
                self._param_txn.send(intent, group=group, kind="write", publish=intents.append, now_ns=int(inputs.now_ns))
                self._param_txn.end_local_edit(now_ns=int(inputs.now_ns))

                self.state.pending_commit_req_id = str(getattr(intent, "req_id", "") or "")
                self.state.pending_commit_group = str(getattr(intent, "group", "") or "")
                self.state.pending_commit_values = dict(getattr(intent, "values", {}) or {})
            elif kind == "cancel":
                intent = self._param_txn.make_cancel_intent(axis_id=axis_id, group=group)
                self._param_txn.send(intent, group=group, kind="cancel", publish=intents.append, now_ns=int(inputs.now_ns))
                self._param_txn.end_local_edit(now_ns=int(inputs.now_ns))

        txn_events = self._param_txn.retry_pending(int(inputs.now_ns), publish=intents.append)

        # Compute param UI state
        now_ns = int(inputs.now_ns)
        edit_active, edit_group = self._param_txn.effective_remote_edit_state(
            remote_active=bool(getattr(snap, "param_edit_active", False)),
            remote_group=str(getattr(snap, "param_edit_group", "") or ""),
            now_ns=now_ns,
        )
        param_ui = self._compute_param_ui_state(
            edit_active=bool(edit_active),
            edit_group=str(edit_group or ""),
            estate=str(estate or ""),
        )

        attach_state = self.compute_attach_state(
            HipAttachInputs(
                attached=bool(attached),
                modal_locked=bool(param_ui.modal_lock_active),
                last_mode=str(mode_now or ""),
                last_estate=str(estate or ""),
            )
        )

        limit_values: dict[str, float] = {}
        try:
            for k in ("HardMin", "UserMin", "UserMax", "HardMax"):
                if k in params:
                    limit_values[k] = float(params[k])
        except Exception:
            limit_values = {}

        param_freeze_group = self._param_txn.local_edit_group if self._param_txn.local_edit_active else ""

        lifetick_intents, echo_map = self._compute_lifetick_echo_intents(
            snap=snap,
            hip_id=hip_id,
            last_lifetick_echo_sent=dict(self.state.last_lifetick_echo_sent or {}),
        )
        intents.extend(lifetick_intents)

        param_commit_dialog = self._maybe_build_param_commit_dialog(snap)

        vm = HipViewModel(
            tick_text=str(tick_text),
            age_ms=age_ms,
            stale=bool(stale),
            lifetick_age=lifetick_age,
            online_state=online_state,
            estop=bool(estop),
            fault=bool(fault),
            drive_status_summary=str(drive_status_summary or ""),
            banner=banner,
            header_dots=header_dots,
            drive_status=drive_status,
            estop_state=estop_state,
            readouts=readouts,
            cut_markers=cut_markers,
            attach_state=attach_state,
            attach_combo=attach_combo,
            param_ui=param_ui,
            param_values=dict(params or {}),
            param_freeze_group=str(param_freeze_group or ""),
            limit_values=dict(limit_values or {}),
            param_writeback_group=str(param_writeback_group or ""),
            param_writeback_values=dict(param_writeback_values or {}),
            param_writeback_message=str(param_writeback_message or ""),
            param_commit_dialog=param_commit_dialog,
        )

        self.state.prev_device_tick = new_prev
        self.state.last_lifetick_echo_sent = dict(echo_map or {})
        self.state.selected_axis = str(selected_axis or "")
        self.state.fixed_axis_applied = bool(fixed_applied)
        self.state.prev_estop_profile = str(profile or "")

        return HipStepResult(
            view_model=vm,
            legacy_view_model=legacy_vm,
            intents=intents,
            resync_ignored=bool(resync_ignored),
            resync_block_reason=str(resync_reason or ""),
            txn_events=list(txn_events or []),
        )

    def _maybe_build_param_commit_dialog(self, snap: TelemetrySnapshot) -> HipParamCommitDialog | None:
        rid = str(getattr(snap, "param_commit_req_id", "") or "")
        status = str(getattr(snap, "param_commit_status", "idle") or "idle")
        group = str(getattr(snap, "param_commit_group", "") or "")

        if not rid or rid != str(self.state.pending_commit_req_id or ""):
            return None
        if rid in self.state.commit_dialog_shown_for:
            return None
        if status not in ("applied", "timeout"):
            return None

        self.state.commit_dialog_shown_for.add(rid)

        if status == "applied":
            msg = f"{group} parameters were applied (observed in telemetry)."
            dialog = HipParamCommitDialog(level="info", title="Parameters applied", message=msg)
        else:
            unmatched = list(getattr(snap, "param_commit_unmatched", []) or [])
            params = dict(getattr(snap, "params", {}) or {})
            want = dict(self.state.pending_commit_values or {})

            lines = [
                f"{group} parameters were not confirmed (timeout).",
                "",
                "Mismatches:",
            ]
            for k in unmatched:
                w = want.get(k, "?")
                g = params.get(k, "<missing>")
                lines.append(f"- {k}: want {w}  got {g}")
            dialog = HipParamCommitDialog(level="warning", title="Parameters not confirmed", message="\n".join(lines))

        self.state.pending_commit_req_id = ""
        self.state.pending_commit_group = ""
        self.state.pending_commit_values = {}
        return dialog

    @staticmethod
    def normalize_intents(intents: Iterable[object]) -> list[tuple[str, tuple[tuple[str, Any], ...]]]:
        items: list[tuple[str, tuple[tuple[str, Any], ...]]] = []
        for intent in intents:
            name = type(intent).__name__
            raw = {}
            try:
                raw = dict(vars(intent))
            except Exception:
                raw = {}
            norm = {k: _normalize_value(v) for k, v in raw.items() if not str(k).startswith("_")}
            items.append((name, tuple(sorted(norm.items()))))
        items.sort(key=lambda x: (x[0], x[1]))
        return items

    @staticmethod
    def normalize_view_model(vm: HipViewModel) -> dict[str, Any]:
        try:
            data = asdict(vm)
        except Exception:
            data = dict(vars(vm))
        norm = _normalize_value(data)
        try:
            if "age_ms" in norm:
                norm["age_ms"] = None if norm["age_ms"] is None else int(norm["age_ms"])
            if "lifetick_age" in norm:
                norm["lifetick_age"] = None if norm["lifetick_age"] is None else int(norm["lifetick_age"])
        except Exception:
            pass
        return norm

    @staticmethod
    def _compute_tick_text(
        *,
        snap: TelemetrySnapshot,
        axis_id: str,
        prev_device_tick: int | None,
    ) -> tuple[str, int | None]:
        if not axis_id:
            return "--", None

        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return "--", None

        ax = axes.get(axis_id)
        if ax is None:
            return "--", None

        cur_raw = getattr(ax, "device_tick", 0)
        try:
            cur = int(cur_raw)
        except Exception:
            return "--", None

        delta, new_prev = compute_time_tick(prev_device_tick, cur)
        return str(int(delta)), int(new_prev)

    @staticmethod
    def _parse_estop_word_from_snapshot(snap: TelemetrySnapshot) -> int:
        fields = getattr(snap, "plc_uplink_fields", None)
        if isinstance(fields, dict):
            v = fields.get("EStopStatus")
            if v is not None:
                try:
                    return int(str(v).strip())
                except Exception:
                    pass
        return int(getattr(snap, "estop_status_word", 0) or 0)

    @staticmethod
    def _raw_uplink_float(snap: TelemetrySnapshot, key: str, default: float) -> float:
        try:
            raw = getattr(snap, "plc_uplink_fields", None)
            if isinstance(raw, dict) and key in raw:
                return float(raw.get(key, default) or default)
        except Exception:
            pass
        return float(default)

    @staticmethod
    def _raw_tail_token(snap: TelemetrySnapshot, key: str) -> str:
        try:
            tail = getattr(snap, "plc_uplink_tail", {}) or {}
            if isinstance(tail, dict):
                v = tail.get(key, "") or ""
                return str(v)
        except Exception:
            pass
        return ""

    @staticmethod
    def _read_axis_pos_vel(ax) -> tuple[float, float]:
        try:
            pos = float(getattr(ax, "pos", 0.0) or 0.0)
        except Exception:
            pos = 0.0
        try:
            vel = float(getattr(ax, "vel", 0.0) or 0.0)
        except Exception:
            vel = 0.0
        return pos, vel

    @classmethod
    def _read_amp_and_temp(cls, *, params: dict, snap: TelemetrySnapshot) -> tuple[float, float]:
        def _pf(key: str, default: float) -> float:
            try:
                return float(params.get(key, default))
            except Exception:
                return float(default)

        amp = _pf("ActCur", _pf("Amp", 0.0))
        tmp = _pf("Temp", 20.0)

        if "ActCur" not in params:
            amp = cls._raw_uplink_float(snap, "ActCurUI", amp)
        if "Temp" not in params:
            tmp = cls._raw_uplink_float(snap, "CabTemperatureUI", tmp)
        return amp, tmp

    @classmethod
    def _compute_readouts_state(
        cls,
        *,
        ax,
        pos: float,
        vel: float,
        amp: float,
        temp: float,
        params: dict,
        snap: TelemetrySnapshot,
    ) -> HipReadoutsState:
        pos_text = fmt_f_unit(pos, "m", ndigits=2)
        vel_text = f"{vel:.2f} m/s"
        amp_text = fmt_i_unit(int(round(amp)), "A")
        temp_text = f"{int(round(temp))}°"

        try:
            g_pos_min = float(params.get("PosMin", 0.0) or 0.0)
        except Exception:
            g_pos_min = 0.0
        try:
            g_pos_max = float(params.get("PosMax", 0.0) or 0.0)
        except Exception:
            g_pos_max = 0.0
        if g_pos_max < g_pos_min:
            g_pos_min, g_pos_max = g_pos_max, g_pos_min

        try:
            g_pos = float(params.get("GuidePosIst", 0.0) or 0.0)
        except Exception:
            g_pos = 0.0
        if g_pos == 0.0:
            g_pos = cls._raw_uplink_float(snap, "GuidePosIstUI", g_pos)

        guider_min_text = f"{g_pos_min:.3f} m"
        guider_max_text = f"{g_pos_max:.3f} m"
        guider_val_text = f"{g_pos:.3f} m"

        try:
            vel_max = float(params.get("VelMax", 0.0) or 0.0)
        except Exception:
            vel_max = 0.0
        if vel_max <= 0.0:
            vel_max = 1.0

        try:
            vel_cmd = float(getattr(ax, "vel_cmd", vel) if ax is not None else vel)
        except Exception:
            vel_cmd = vel
        scale = 1000.0
        vel_cmd_min = int(round(-vel_max * scale))
        vel_cmd_max = int(round(+vel_max * scale))
        vel_cmd_val = int(round(vel_cmd * scale))

        try:
            user_min = float(params.get("UserMin", 0.0) or 0.0)
        except Exception:
            user_min = 0.0
        try:
            user_max = float(params.get("UserMax", 0.0) or 0.0)
        except Exception:
            user_max = 0.0
        if user_max < user_min:
            user_min, user_max = user_max, user_min
        limit_min = int(round(user_min * scale))
        limit_max = int(round(user_max * scale))
        limit_val = int(round(pos * scale))

        drum_diam = 0.5
        try:
            pitch = float(params.get("Pitch", 0.0) or 0.0)
        except Exception:
            pitch = 0.0
        denom = 3.141592653589793 * drum_diam
        ratio = (pitch / denom) if (denom > 0.0 and pitch > 0.0) else 0.0

        try:
            g_vel_meas = float(params.get("GuideIstSpeed", 0.0) or 0.0)
        except Exception:
            g_vel_meas = 0.0
        if g_vel_meas == 0.0:
            g_vel_meas = cls._raw_uplink_float(snap, "GuideIstSpeedUI", g_vel_meas)

        g_vel_max = abs(vel_max) * ratio
        if g_vel_max <= 0.0:
            g_vel_max = 1.0
        if g_vel_meas > g_vel_max:
            g_vel_meas = g_vel_max
        elif g_vel_meas < -g_vel_max:
            g_vel_meas = -g_vel_max

        guider_speed_min = int(round(-g_vel_max * scale))
        guider_speed_max = int(round(+g_vel_max * scale))
        guider_speed_val = int(round(g_vel_meas * scale))
        guider_speed_text = f"{g_vel_meas:.3f} m/s"

        return HipReadoutsState(
            pos_text=str(pos_text),
            vel_text=str(vel_text),
            amp_text=str(amp_text),
            temp_text=str(temp_text),
            guider_min_text=str(guider_min_text),
            guider_max_text=str(guider_max_text),
            guider_val_text=str(guider_val_text),
            guider_speed_text=str(guider_speed_text),
            vel_cmd_min=int(vel_cmd_min),
            vel_cmd_max=int(vel_cmd_max),
            vel_cmd_val=int(vel_cmd_val),
            limit_min=int(limit_min),
            limit_max=int(limit_max),
            limit_val=int(limit_val),
            guider_range_min=int(round(g_pos_min * scale)),
            guider_range_max=int(round(g_pos_max * scale)),
            guider_range_val=int(round(g_pos * scale)),
            guider_speed_min=int(guider_speed_min),
            guider_speed_max=int(guider_speed_max),
            guider_speed_val=int(guider_speed_val),
        )

    @classmethod
    def _compute_cut_markers_state(
        cls,
        *,
        snap: TelemetrySnapshot,
        params: dict,
        estate: str,
    ) -> HipCutMarkersState:
        try:
            cut_pos = float(params.get("CutPos", 0.0) or 0.0)
            cut_vel = float(params.get("CutVel", 0.0) or 0.0)
            posdiff = float(params.get("PosDiffFor", 0.0) or 0.0)
        except Exception:
            cut_pos = 0.0
            cut_vel = 0.0
            posdiff = 0.0

        in_estop = bool(getattr(snap, "estop", False))
        try:
            word = cls._parse_estop_word_from_snapshot(snap)
            bits = decode_estop_word(int(word))
            in_estop = any(bool(bits.get(k, False)) for k in ("master", "slave", "network", "estop1", "estop2"))
        except Exception:
            pass
        if not in_estop and str(estate or "").upper() == "ESTOP":
            in_estop = True

        if not in_estop:
            cut_pos_text = "--"
            cut_vel_text = "--"
            posdiff_text = "--"
        else:
            cut_pos_text = fmt_f_unit(cut_pos, "m", ndigits=2)
            cut_vel_text = fmt_f_unit(cut_vel, "m/s", ndigits=2)
            posdiff_text = fmt_f_unit(posdiff, "m", ndigits=2)

        t_tok = cls._raw_tail_token(snap, "SystemTime")
        cut_time_text = t_tok if t_tok else "--"
        return HipCutMarkersState(
            cut_time_text=str(cut_time_text),
            cut_pos_text=str(cut_pos_text),
            cut_vel_text=str(cut_vel_text),
            posdiff_text=str(posdiff_text),
        )

    @staticmethod
    def _normalize_pos_chain(values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        need = {"HardMax", "UserMax", "UserMin", "HardMin"}
        if not need.issubset(v.keys()):
            return v

        hard_max = float(v["HardMax"])
        hard_min = float(v["HardMin"])
        user_max = float(v["UserMax"])
        user_min = float(v["UserMin"])

        if hard_max < hard_min:
            hard_max, hard_min = hard_min, hard_max

        user_max = max(min(user_max, hard_max), hard_min)
        user_min = max(min(user_min, user_max), hard_min)

        v["HardMax"] = hard_max
        v["HardMin"] = hard_min
        v["UserMax"] = user_max
        v["UserMin"] = user_min
        return v

    @staticmethod
    def _normalize_guider_range(values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        if "PosMin" not in v or "PosMax" not in v:
            return v
        pos_min = float(v["PosMin"])
        pos_max = float(v["PosMax"])
        if pos_min > pos_max:
            pos_min = pos_max
        v["PosMin"] = pos_min
        v["PosMax"] = pos_max
        return v

    @staticmethod
    def _compute_drive_status_texts(
        *,
        snap: TelemetrySnapshot,
        axis_id: str,
    ) -> tuple[str, str]:
        if decode_drive_status is None:
            return "", ""
        if not axis_id:
            return "", ""
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return "", ""
        ax = axes.get(axis_id)
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

    def _compute_param_ui_state(self, *, edit_active: bool, edit_group: str, estate: str) -> HipParamUiState:
        groups = ("pos", "vel", "filter", "guider")
        state_groups: dict[str, HipParamGroup] = {}
        estate = str(estate or "").upper()
        edits_allowed = estate not in ("ARMED", "READY")

        if edit_active:
            for g in groups:
                if g == edit_group:
                    busy = self._param_txn.is_group_busy(g)
                    buttons = HipParamButtons(
                        edit_enabled=False if edits_allowed else False,
                        write_enabled=bool((not busy) and edits_allowed),
                        cancel_enabled=bool(not busy),
                    )
                    if busy:
                        buttons = HipParamButtons(edit_enabled=False, write_enabled=False, cancel_enabled=False)
                    state_groups[g] = HipParamGroup(fields_enabled=bool(not busy), buttons=buttons)
                else:
                    state_groups[g] = HipParamGroup(
                        fields_enabled=False,
                        buttons=HipParamButtons(edit_enabled=False, write_enabled=False, cancel_enabled=False),
                    )
            return HipParamUiState(
                modal_lock_active=True,
                modal_lock_group=str(edit_group or ""),
                groups=state_groups,
            )

        for g in groups:
            busy = self._param_txn.is_group_busy(g)
            if busy:
                buttons = HipParamButtons(edit_enabled=False, write_enabled=False, cancel_enabled=False)
            else:
                buttons = HipParamButtons(
                    edit_enabled=bool(edits_allowed),
                    write_enabled=False,
                    cancel_enabled=False,
                )
            state_groups[g] = HipParamGroup(fields_enabled=False, buttons=buttons)

        return HipParamUiState(
            modal_lock_active=False,
            modal_lock_group="",
            groups=state_groups,
        )

    @staticmethod
    def _get_lifetick_age(*, snap: TelemetrySnapshot, axis_id: str) -> int | None:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict):
            return None
        ax = axes.get(axis_id)
        if ax is None:
            return None
        try:
            return int(getattr(ax, "lifetick_age", 0) or 0)
        except Exception:
            return None

    @staticmethod
    def _compute_drive_status_summary(*, snap: TelemetrySnapshot, axis_id: str) -> str:
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

    @staticmethod
    def _compute_lifetick_echo_intents(
        *,
        snap: TelemetrySnapshot,
        hip_id: str,
        last_lifetick_echo_sent: dict[str, int],
    ) -> tuple[list[object], dict[str, int]]:
        axes = getattr(snap, "axes", None)
        if not isinstance(axes, dict) or not axes:
            return [], last_lifetick_echo_sent

        intents: list[object] = []
        for axis_id, ax in axes.items():
            try:
                v = int(getattr(ax, "device_tick", 0)) & 0xFFFF
            except Exception:
                v = 0

            prev = last_lifetick_echo_sent.get(axis_id)
            if prev is not None and int(prev) == v:
                continue

            last_lifetick_echo_sent[axis_id] = v
            intents.append(EchoLifeTick(axis_id=axis_id, value=v, hip_id=str(hip_id or "")))

        return intents, last_lifetick_echo_sent


def _normalize_value(val: Any) -> Any:
    if isinstance(val, float):
        return round(val, 6)
    if isinstance(val, (int, str, bool)) or val is None:
        return val
    if isinstance(val, dict):
        return {str(k): _normalize_value(v) for k, v in sorted(val.items(), key=lambda x: str(x[0]))}
    if isinstance(val, set):
        return [_normalize_value(v) for v in sorted(val, key=lambda x: str(x))]
    if isinstance(val, (list, tuple)):
        return [_normalize_value(v) for v in val]
    try:
        return str(val)
    except Exception:
        return "<unrepr>"
