from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from steuerung3d.core.telemetry import TelemetrySnapshot

from .param_ui import ParamTxnResult
from .step_phase_presentation_build import build_presentation
from .step_phase_presentation_facts import (
    EstopFacts,
    _HipPresentationEngine,
    build_snap_context,
    derive_attach_state,
    derive_drive_and_readout_facts,
    derive_estop_facts,
    derive_transport_facts,
)
from .types import HipAttachCombo, HipPresentationData


@dataclass(frozen=True)
class HipPresentationPhase:
    presentation: HipPresentationData
    snap_view: TelemetrySnapshot
    params: dict[str, float]
    logical: dict[str, bool]
    estop_word: int
    estate: str
    estop: bool
    fault: bool
    taster: bool
    within_banner: bool
    within_brake: bool
    mode_now: str
    profile: str


def _build_phase_result(
    *,
    presentation: HipPresentationData,
    snap_view: TelemetrySnapshot,
    params: dict[str, float],
    estop_facts: EstopFacts,
    mode_now: str,
    estop: bool,
    fault: bool,
) -> HipPresentationPhase:
    return HipPresentationPhase(
        presentation=presentation,
        snap_view=snap_view,
        params=dict(params or {}),
        logical=dict(estop_facts.logical),
        estop_word=int(estop_facts.estop_word),
        estate=str(estop_facts.estate or ""),
        estop=bool(estop),
        fault=bool(fault),
        taster=bool(estop_facts.taster),
        within_banner=bool(estop_facts.within_banner),
        within_brake=bool(estop_facts.within_brake),
        mode_now=str(mode_now or ""),
        profile=str(estop_facts.profile or ""),
    )


def compute_presentation_phase(
    *,
    engine: _HipPresentationEngine,
    attach_combo: HipAttachCombo,
    attached: bool,
    axis_id: str,
    axis_ids: Sequence[str],
    snap: TelemetrySnapshot,
    now_ns: int,
    last_rx_ns: int | None,
    stale_after_ms: int,
    param_result: ParamTxnResult | None = None,
    update_state: bool = True,
) -> HipPresentationPhase:
    mode_now, snap_view, params, axes, _presentation_axis_id = build_snap_context(
        attached=attached,
        axis_id=axis_id,
        snap=snap,
    )
    estop_facts = derive_estop_facts(
        engine=engine,
        axis_id_for_estate=axis_id or (axis_ids[0] if axis_ids else "X"),
        now_ns=now_ns,
        snap_view=snap_view,
        update_state=update_state,
    )
    estop = bool(getattr(snap, "estop", False))
    fault = bool(getattr(snap, "fault", False))
    state = engine.state
    transport_facts = derive_transport_facts(
        axis_id=axis_id,
        last_rx_ns=last_rx_ns,
        now_ns=now_ns,
        stale_after_ms=stale_after_ms,
        snap=snap,
        snap_view=snap_view,
        state=state,
    )
    drive_facts = derive_drive_and_readout_facts(
        attached=attached,
        axis_id=axis_id,
        axes=axes,
        estate=estop_facts.estate,
        mode_now=mode_now,
        params=params,
        snap=snap,
        snap_view=snap_view,
    )
    attach_state, param_ui = derive_attach_state(
        engine=engine,
        attached=attached,
        mode_now=mode_now,
        estate=estop_facts.estate,
        param_result=param_result,
    )
    presentation = build_presentation(
        attach_combo=attach_combo,
        attach_state=attach_state,
        attached=attached,
        drive_facts=drive_facts,
        estop=estop,
        estop_facts=estop_facts,
        fault=fault,
        param_result=param_result,
        param_ui=param_ui,
        params=params,
        state=state,
        transport_facts=transport_facts,
    )
    if update_state:
        state.prev_device_tick = transport_facts.new_prev
    return _build_phase_result(
        presentation=presentation,
        snap_view=snap_view,
        params=params,
        estop_facts=estop_facts,
        mode_now=mode_now,
        estop=estop,
        fault=fault,
    )
