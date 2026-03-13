from __future__ import annotations

from dataclasses import dataclass

from ...engines.supervisor.models import PairStatus, SupervisorSpec
from .supervisor_presenter import (
    SupervisorRowActionFlags,
    derive_row_action_flags,
    format_interaction_mode,
    format_pair_phase,
    format_position,
    format_primary_action,
    format_velocity,
)


@dataclass(frozen=True)
class SupervisorTableRowVM:
    pair_id: str
    axis_id: str
    densi_id: str
    hip_id: str
    label: str
    phase_text: str
    phase_key: str
    position_text: str
    velocity_text: str
    interaction_mode_text: str
    primary_action_text: str
    blocking_reason_text: str
    estop_reset_input: bool
    estart_input: bool
    chk_es_taster_input: bool
    selected: bool
    member_order: int
    actions: SupervisorRowActionFlags


@dataclass(frozen=True)
class SupervisorTableVM:
    supervisor_id: str
    title: str
    rows: tuple[SupervisorTableRowVM, ...]
    selected_pair_id: str | None


def build_supervisor_table_vm(
    *,
    spec: SupervisorSpec,
    statuses: dict[str, PairStatus],
    selected_pair_id: str | None = None,
) -> SupervisorTableVM:
    rows: list[SupervisorTableRowVM] = []
    for member in sorted(spec.members, key=lambda m: (int(m.order_key), str(m.target_id))):
        if member.member_kind != "pair":
            continue
        pair_id = str(member.target_id)
        status = statuses.get(pair_id)
        if status is None:
            continue
        ref = status.ref
        facts = status.facts
        actions = derive_row_action_flags(status)
        rows.append(
            SupervisorTableRowVM(
                pair_id=ref.pair_id,
                axis_id=ref.axis_id,
                densi_id=ref.densi_id,
                hip_id=ref.hip_id,
                label=f"{ref.pair_id} ({ref.axis_id})",
                phase_text=format_pair_phase(status.phase),
                phase_key=str(status.phase.value),
                position_text=format_position(facts.position),
                velocity_text=format_velocity(facts.velocity),
                interaction_mode_text=format_interaction_mode(status.interaction_mode),
                primary_action_text=format_primary_action(status.actions.primary_action),
                blocking_reason_text=str(status.actions.blocking_reason),
                estop_reset_input=bool(facts.estop_reset_input),
                estart_input=bool(facts.estart_input),
                chk_es_taster_input=bool(facts.chk_es_taster_input),
                selected=(pair_id == selected_pair_id),
                member_order=int(member.order_key),
                actions=actions,
            )
        )
    return SupervisorTableVM(
        supervisor_id=spec.supervisor_id,
        title=str(spec.name),
        rows=tuple(rows),
        selected_pair_id=selected_pair_id,
    )
