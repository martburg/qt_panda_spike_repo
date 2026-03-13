from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.membership import (
    add_pair_member,
    remove_pair_member,
)
from steuerung3d.apps.yellow.engines.supervisor.models import SupervisorMember, SupervisorSpec


def test_add_pair_member_to_empty_supervisor() -> None:
    spec = SupervisorSpec(supervisor_id="sup-1", name="Sup", members=())
    got = add_pair_member(spec, "p1")
    assert [m.target_id for m in got.members] == ["p1"]
    assert got.members[0].order_key == 0


def test_add_pair_member_is_idempotent_for_duplicates() -> None:
    spec = SupervisorSpec(
        supervisor_id="sup-1",
        name="Sup",
        members=(
            SupervisorMember(member_id="pair:p1", member_kind="pair", target_id="p1", order_key=0),
        ),
    )
    got = add_pair_member(spec, "p1")
    assert got == spec


def test_remove_existing_pair_member() -> None:
    spec = SupervisorSpec(
        supervisor_id="sup-1",
        name="Sup",
        members=(
            SupervisorMember(member_id="pair:p1", member_kind="pair", target_id="p1", order_key=0),
            SupervisorMember(member_id="pair:p2", member_kind="pair", target_id="p2", order_key=1),
        ),
    )
    got = remove_pair_member(spec, "p1")
    assert [m.target_id for m in got.members] == ["p2"]


def test_remove_missing_pair_member_is_idempotent() -> None:
    spec = SupervisorSpec(supervisor_id="sup-1", name="Sup", members=())
    got = remove_pair_member(spec, "p9")
    assert got == spec


def test_add_pair_member_appends_with_stable_order_key() -> None:
    spec = SupervisorSpec(
        supervisor_id="sup-1",
        name="Sup",
        members=(
            SupervisorMember(member_id="pair:p1", member_kind="pair", target_id="p1", order_key=4),
        ),
    )
    got = add_pair_member(spec, "p2")
    assert [m.target_id for m in got.members] == ["p1", "p2"]
    assert got.members[-1].order_key == 5
