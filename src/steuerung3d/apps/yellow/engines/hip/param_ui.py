"""Param edit session orchestration for HipEngine (Qt-free)."""

from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.telemetry import TelemetrySnapshot

from ...domain.param_txn import ParamEditTxnClient, RetryEvent
from .types import (
    HipParamButtons,
    HipParamCommitDialog,
    HipParamGroup,
    HipParamUiState,
    HipState,
    HipUiInputs,
)


@dataclass(frozen=True)
class ParamTxnResult:
    param_ui: HipParamUiState
    param_freeze_group: str
    param_writeback_group: str
    param_writeback_values: dict[str, float]
    param_writeback_message: str
    param_commit_dialog: HipParamCommitDialog | None
    txn_events: list[RetryEvent]


def run_param_txn(
    *,
    txn: ParamEditTxnClient,
    state: HipState,
    ui: HipUiInputs,
    axis_id: str,
    now_ns: int,
    estate: str,
    snap: TelemetrySnapshot,
    intents: list[object],
    core_acks: list[str],
) -> ParamTxnResult:
    param_writeback_group = ""
    param_writeback_values: dict[str, float] = {}
    param_writeback_message = ""

    txn.handle_core_acks(list(core_acks or []))

    for action in list(ui.param_actions or []):
        if not axis_id:
            continue
        group = str(action.group or "")
        kind = str(action.kind or "")
        if kind == "edit":
            txn.start_local_edit(group)
            intent = txn.make_begin_intent(axis_id=axis_id, group=group)
            txn.send(intent, group=group, kind="begin", publish=intents.append, now_ns=int(now_ns))
        elif kind == "write":
            vals = dict(ui.param_values.get(group, {}) if isinstance(ui.param_values, dict) else {})
            fixed = dict(vals)
            if group == "pos":
                fixed = _normalize_pos_chain(fixed)
            elif group == "guider":
                fixed = _normalize_guider_range(fixed)

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

            intent = txn.make_write_intent(axis_id=axis_id, group=group, values=fixed)
            txn.send(intent, group=group, kind="write", publish=intents.append, now_ns=int(now_ns))
            txn.end_local_edit(now_ns=int(now_ns))

            state.pending_commit_req_id = str(getattr(intent, "req_id", "") or "")
            state.pending_commit_group = str(getattr(intent, "group", "") or "")
            state.pending_commit_values = dict(getattr(intent, "values", {}) or {})
        elif kind == "cancel":
            intent = txn.make_cancel_intent(axis_id=axis_id, group=group)
            txn.send(intent, group=group, kind="cancel", publish=intents.append, now_ns=int(now_ns))
            txn.end_local_edit(now_ns=int(now_ns))

    txn_events = txn.retry_pending(int(now_ns), publish=intents.append)

    edit_active, edit_group = txn.effective_remote_edit_state(
        remote_active=bool(getattr(snap, "param_edit_active", False)),
        remote_group=str(getattr(snap, "param_edit_group", "") or ""),
        now_ns=int(now_ns),
    )
    param_ui = compute_param_ui_state(
        txn=txn,
        edit_active=bool(edit_active),
        edit_group=str(edit_group or ""),
        estate=str(estate or ""),
    )

    param_freeze_group = txn.local_edit_group if txn.local_edit_active else ""
    param_commit_dialog = maybe_build_param_commit_dialog(state=state, snap=snap)

    return ParamTxnResult(
        param_ui=param_ui,
        param_freeze_group=str(param_freeze_group or ""),
        param_writeback_group=str(param_writeback_group or ""),
        param_writeback_values=dict(param_writeback_values or {}),
        param_writeback_message=str(param_writeback_message or ""),
        param_commit_dialog=param_commit_dialog,
        txn_events=list(txn_events or []),
    )


def compute_param_ui_state(
    *,
    txn: ParamEditTxnClient,
    edit_active: bool,
    edit_group: str,
    estate: str,
) -> HipParamUiState:
    groups = ("pos", "vel", "filter", "guider")
    state_groups: dict[str, HipParamGroup] = {}
    estate = str(estate or "").upper()
    edits_allowed = estate not in ("ARMED", "READY")

    if edit_active:
        for g in groups:
            if g == edit_group:
                busy = txn.is_group_busy(g)
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
        busy = txn.is_group_busy(g)
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


def maybe_build_param_commit_dialog(
    *,
    state: HipState,
    snap: TelemetrySnapshot,
) -> HipParamCommitDialog | None:
    rid = str(getattr(snap, "param_commit_req_id", "") or "")
    status = str(getattr(snap, "param_commit_status", "idle") or "idle")
    group = str(getattr(snap, "param_commit_group", "") or "")

    if not rid or rid != str(state.pending_commit_req_id or ""):
        return None
    if rid in state.commit_dialog_shown_for:
        return None
    if status not in ("applied", "timeout"):
        return None

    state.commit_dialog_shown_for.add(rid)

    if status == "applied":
        msg = f"{group} parameters were applied (observed in telemetry)."
        dialog = HipParamCommitDialog(level="info", title="Parameters applied", message=msg)
    else:
        unmatched = list(getattr(snap, "param_commit_unmatched", []) or [])
        params = dict(getattr(snap, "params", {}) or {})
        want = dict(state.pending_commit_values or {})

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

    state.pending_commit_req_id = ""
    state.pending_commit_group = ""
    state.pending_commit_values = {}
    return dialog


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
