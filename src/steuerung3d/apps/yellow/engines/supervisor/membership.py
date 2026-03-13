from __future__ import annotations

from .models import SupervisorMember, SupervisorSpec


def add_pair_member(spec: SupervisorSpec, pair_id: str) -> SupervisorSpec:
    pair_id = str(pair_id)
    existing = tuple(spec.members)
    for member in existing:
        if member.member_kind == "pair" and str(member.target_id) == pair_id:
            return spec
    max_order = max((int(member.order_key) for member in existing), default=-1)
    new_member = SupervisorMember(
        member_id=f"pair:{pair_id}",
        member_kind="pair",
        target_id=pair_id,
        order_key=max_order + 1,
    )
    return SupervisorSpec(
        supervisor_id=spec.supervisor_id,
        name=spec.name,
        members=existing + (new_member,),
        kinematics_id=spec.kinematics_id,
    )


def remove_pair_member(spec: SupervisorSpec, pair_id: str) -> SupervisorSpec:
    pair_id = str(pair_id)
    kept = tuple(
        member
        for member in spec.members
        if not (member.member_kind == "pair" and str(member.target_id) == pair_id)
    )
    if kept == spec.members:
        return spec
    return SupervisorSpec(
        supervisor_id=spec.supervisor_id,
        name=spec.name,
        members=kept,
        kinematics_id=spec.kinematics_id,
    )
