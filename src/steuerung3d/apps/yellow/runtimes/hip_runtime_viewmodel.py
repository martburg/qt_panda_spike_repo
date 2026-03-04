"""HiP runtime view-model assembly.

Split out of hip_runtime_impl.py to keep the runtime orchestrator readable.
"""

from __future__ import annotations

from ..domain.ui_estop import infer_estop_profile
from ..engines.hip.types import HipPresentationData
from ..engines.hip.viewmodel import HipViewModel
from ..panels.hip.hip_banner_vm import compute_hip_banner_vm
from ..panels.hip.hip_estop_vm import compute_hip_estop_vm
from ..panels.hip.hip_header_dots_vm import compute_hip_header_dots_vm


def assemble_legacy_view_model(pres: HipPresentationData) -> HipViewModel:
    return HipViewModel(
        tick_text=str(pres.tick_text),
        age_ms=pres.age_ms,
        stale=bool(pres.stale),
        lifetick_age=pres.lifetick_age,
        online_state=pres.online_state,
        estop=bool(pres.estop),
        fault=bool(pres.fault),
        drive_status_summary=str(pres.drive_status_summary or ""),
    )


def assemble_view_model(pres: HipPresentationData) -> HipViewModel:
    banner = compute_hip_banner_vm(
        estop_word=int(pres.estop_word),
        within_brake_grace=bool(pres.within_banner),
    )

    def _brake_ok_display(raw: bool) -> bool:
        if bool(pres.taster) and bool(pres.within_brake):
            return True
        return bool(raw)

    header_dots = compute_hip_header_dots_vm(
        online_state=pres.online_state,
        taster=bool(pres.taster),
        ready=bool(pres.logical.get("ready", False)),
        brk1_raw=bool(pres.logical.get("brk1_ok", False)),
        brk2_raw=bool(pres.logical.get("brk2_ok", False)),
        brake_ok_display=_brake_ok_display,
    )

    profile = infer_estop_profile(pres.logical)
    estop_state = compute_hip_estop_vm(
        logical=pres.logical,
        taster=bool(pres.taster),
        attached=bool(pres.attached),
        brake_ok_display=_brake_ok_display,
        profile=profile,
        prev_profile=str(pres.prev_estop_profile or ""),
    )

    return HipViewModel(
        tick_text=str(pres.tick_text),
        age_ms=pres.age_ms,
        stale=bool(pres.stale),
        lifetick_age=pres.lifetick_age,
        online_state=pres.online_state,
        estop=bool(pres.estop),
        fault=bool(pres.fault),
        drive_status_summary=str(pres.drive_status_summary or ""),
        joy_deadman=bool(pres.joy_deadman),
        joy_select_hip=bool(pres.joy_select_hip),
        joy_soll_speed=float(pres.joy_soll_speed),
        banner=banner,
        header_dots=header_dots,
        drive_status=pres.drive_status,
        estop_state=estop_state,
        readouts=pres.readouts,
        cut_markers=pres.cut_markers,
        attach_state=pres.attach_state,
        attach_combo=pres.attach_combo,
        param_ui=pres.param_ui,
        param_values=dict(pres.param_values or {}),
        param_freeze_group=str(pres.param_freeze_group or ""),
        limit_values=dict(pres.limit_values or {}),
        param_writeback_group=str(pres.param_writeback_group or ""),
        param_writeback_values=dict(pres.param_writeback_values or {}),
        param_writeback_message=str(pres.param_writeback_message or ""),
        param_commit_dialog=pres.param_commit_dialog,
    )
