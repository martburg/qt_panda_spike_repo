from __future__ import annotations

from dataclasses import dataclass

from ...engines.supervisor.models import PairStatus, SupervisorSpec
from .supervisor_presenter import format_pair_phase, format_primary_action


@dataclass(frozen=True)
class SupervisorNodeBadgeVM:
    text: str
    kind: str


@dataclass(frozen=True)
class PairNodeVM:
    pair_id: str
    title: str
    subtitle: str
    selected: bool
    phase_text: str
    badges: tuple[SupervisorNodeBadgeVM, ...]
    primary_action_text: str


@dataclass(frozen=True)
class SupervisorNodeVM:
    supervisor_id: str
    title: str
    subtitle: str
    children: tuple[PairNodeVM, ...]


def build_supervisor_node_vm(
    *,
    spec: SupervisorSpec,
    statuses: dict[str, PairStatus],
    selected_pair_id: str | None = None,
) -> SupervisorNodeVM:
    children: list[PairNodeVM] = []
    for member in sorted(spec.members, key=lambda m: (int(m.order_key), str(m.target_id))):
        if member.member_kind != "pair":
            continue
        pair_id = str(member.target_id)
        status = statuses.get(pair_id)
        if status is None:
            continue
        ref = status.ref
        facts = status.facts
        badges: list[SupervisorNodeBadgeVM] = [
            SupervisorNodeBadgeVM(text=format_pair_phase(status.phase), kind="phase")
        ]
        if facts.param_edit_active:
            badges.append(SupervisorNodeBadgeVM(text="Editing", kind="mode"))
        if facts.estart_input:
            badges.append(SupervisorNodeBadgeVM(text="EStart", kind="input"))
        if facts.chk_es_taster_input:
            badges.append(SupervisorNodeBadgeVM(text="EsTaster", kind="input"))
        if facts.estop_reset_input:
            badges.append(SupervisorNodeBadgeVM(text="EStop reset", kind="input"))
        children.append(
            PairNodeVM(
                pair_id=ref.pair_id,
                title=ref.pair_id,
                subtitle=f"{ref.axis_id} • {ref.densi_id} • {ref.hip_id}",
                selected=(pair_id == selected_pair_id),
                phase_text=format_pair_phase(status.phase),
                badges=tuple(badges),
                primary_action_text=format_primary_action(status.actions.primary_action),
            )
        )
    return SupervisorNodeVM(
        supervisor_id=spec.supervisor_id,
        title=str(spec.name),
        subtitle=f"{len(children)} pairs",
        children=tuple(children),
    )
