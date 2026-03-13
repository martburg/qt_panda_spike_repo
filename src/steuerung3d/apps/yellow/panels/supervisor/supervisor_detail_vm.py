from __future__ import annotations

from dataclasses import dataclass

from ...engines.supervisor.models import PairAction, PairStatus
from .supervisor_presenter import (
    format_interaction_mode,
    format_pair_phase,
    format_position,
    format_primary_action,
    format_velocity,
)


@dataclass(frozen=True)
class SupervisorDetailFieldVM:
    label: str
    value: str


@dataclass(frozen=True)
class SupervisorDetailVM:
    pair_id: str
    title: str
    subtitle: str
    phase_text: str
    interaction_mode_text: str
    primary_action_text: str
    blocking_reason_text: str
    fields: tuple[SupervisorDetailFieldVM, ...]
    available_actions: tuple[str, ...]


_ACTION_LABELS: dict[PairAction, str] = {
    PairAction.RESET_ESTOP: "Reset EStop",
    PairAction.ESTART: "EStart",
    PairAction.CHECK_ES_TASTER: "Check EsTaster",
    PairAction.EDIT_PARAMETERS: "Edit parameters",
    PairAction.WRITE_PARAMETERS: "Write parameters",
    PairAction.CANCEL_EDIT: "Cancel edit",
}


def build_supervisor_detail_vm(pair_status: PairStatus | None) -> SupervisorDetailVM | None:
    if pair_status is None:
        return None
    ref = pair_status.ref
    facts = pair_status.facts
    fields = (
        SupervisorDetailFieldVM("Axis", str(ref.axis_id)),
        SupervisorDetailFieldVM("DenSi", str(ref.densi_id)),
        SupervisorDetailFieldVM("HiP", str(ref.hip_id)),
        SupervisorDetailFieldVM("Position", format_position(facts.position)),
        SupervisorDetailFieldVM("Velocity", format_velocity(facts.velocity)),
        SupervisorDetailFieldVM("Banner estate", str(facts.banner_estate or "—")),
        SupervisorDetailFieldVM("EStop reset input", "On" if facts.estop_reset_input else "Off"),
        SupervisorDetailFieldVM("EStart input", "On" if facts.estart_input else "Off"),
        SupervisorDetailFieldVM("chkEsTaster input", "On" if facts.chk_es_taster_input else "Off"),
    )
    allowed = tuple(
        _ACTION_LABELS[action]
        for action in sorted(pair_status.actions.allowed_actions, key=lambda a: a.value)
    )
    return SupervisorDetailVM(
        pair_id=str(ref.pair_id),
        title=str(ref.pair_id),
        subtitle=f"{ref.axis_id} • {ref.densi_id} • {ref.hip_id}",
        phase_text=format_pair_phase(pair_status.phase),
        interaction_mode_text=format_interaction_mode(pair_status.interaction_mode),
        primary_action_text=format_primary_action(pair_status.actions.primary_action),
        blocking_reason_text=str(pair_status.actions.blocking_reason),
        fields=fields,
        available_actions=allowed,
    )
