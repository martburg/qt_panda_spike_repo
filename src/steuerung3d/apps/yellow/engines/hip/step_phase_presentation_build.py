from __future__ import annotations

from typing import Any, cast

from .step_phase_presentation_facts import DriveAndReadoutFacts, EstopFacts, TransportFacts
from .types import HipAttachCombo, HipPresentationData


def build_presentation(
    *,
    attach_combo: object,
    attach_state: Any,
    attached: bool,
    drive_facts: DriveAndReadoutFacts,
    estop: bool,
    estop_facts: EstopFacts,
    fault: bool,
    param_result: object | None,
    param_ui: Any,
    params: dict[str, Any],
    state: object,
    transport_facts: TransportFacts,
) -> HipPresentationData:
    return HipPresentationData(
        tick_text=str(transport_facts.tick_text),
        age_ms=transport_facts.age_ms,
        stale=bool(transport_facts.stale),
        lifetick_age=transport_facts.lifetick_age,
        online_state=transport_facts.online_state,
        estop=bool(estop),
        fault=bool(fault),
        drive_status_summary=str(drive_facts.drive_status_summary or ""),
        drive_status=drive_facts.drive_status,
        estop_word=int(estop_facts.estop_word),
        within_banner=bool(estop_facts.within_banner),
        within_brake=bool(estop_facts.within_brake),
        logical=dict(estop_facts.logical),
        taster=bool(estop_facts.taster),
        attached=bool(attached),
        prev_estop_profile=str(getattr(state, "prev_estop_profile", "") or ""),
        joy_deadman=False,
        joy_select_hip=False,
        joy_soll_speed=0.0,
        readouts=drive_facts.readouts,
        cut_markers=drive_facts.cut_markers,
        attach_state=attach_state,
        attach_combo=cast(HipAttachCombo | None, attach_combo),
        param_ui=param_ui,
        param_values=dict(params or {}),
        param_freeze_group=str(getattr(param_result, "param_freeze_group", "") or ""),
        limit_values=dict(drive_facts.limit_values or {}),
        param_writeback_group=str(getattr(param_result, "param_writeback_group", "") or ""),
        param_writeback_values=dict(getattr(param_result, "param_writeback_values", {}) or {}),
        param_writeback_message=str(getattr(param_result, "param_writeback_message", "") or ""),
        param_commit_dialog=getattr(param_result, "param_commit_dialog", None),
    )
