from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairFacts,
    PairRef,
    SupervisorMember,
    SupervisorSpec,
)
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import build_pair_status
from steuerung3d.apps.yellow.panels.supervisor.supervisor_node_vm import build_supervisor_node_vm


def _status(pair_id: str, order: int, **overrides: object):
    facts = PairFacts(
        attached=True,
        stale=False,
        fault=False,
        estop_reset_input=False,
        estart_input=False,
        chk_es_taster_input=False,
        brake_grace_active=False,
        ready_actual=False,
        deadman_active=False,
        live_motion_active=False,
        param_edit_active=False,
        position=1.0 + order,
        velocity=0.0,
        banner_estate="",
    )
    facts = PairFacts(**(facts.__dict__ | dict(overrides)))
    ref = PairRef(pair_id=pair_id, axis_id=f"A{order}", densi_id=f"D{order}", hip_id=f"H{order}")
    return build_pair_status(ref, facts)


def test_node_model_preserves_supervisor_title_and_order() -> None:
    spec = SupervisorSpec(
        supervisor_id="sup-1",
        name="Supervisor One",
        members=(
            SupervisorMember(member_id="m2", member_kind="pair", target_id="p2", order_key=2),
            SupervisorMember(member_id="m1", member_kind="pair", target_id="p1", order_key=1),
        ),
    )
    statuses = {"p1": _status("p1", 1), "p2": _status("p2", 2, estart_input=True)}
    vm = build_supervisor_node_vm(spec=spec, statuses=statuses, selected_pair_id="p2")
    assert vm.title == "Supervisor One"
    assert [child.pair_id for child in vm.children] == ["p1", "p2"]
    assert vm.children[1].selected is True


def test_node_model_generates_compact_badges_and_primary_action() -> None:
    spec = SupervisorSpec(
        supervisor_id="sup-1",
        name="Supervisor One",
        members=(
            SupervisorMember(member_id="m1", member_kind="pair", target_id="p1", order_key=1),
        ),
    )
    statuses = {"p1": _status("p1", 1, estart_input=True)}
    vm = build_supervisor_node_vm(spec=spec, statuses=statuses)
    child = vm.children[0]
    assert child.primary_action_text == "Check EsTaster"
    badge_texts = [badge.text for badge in child.badges]
    assert "Idle" in badge_texts
    assert "EStart" in badge_texts
