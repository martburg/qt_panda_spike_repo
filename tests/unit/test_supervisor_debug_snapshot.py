from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.debug import build_supervisor_debug_snapshot
from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairAction,
    PairActionSurface,
    PairFacts,
    PairInteractionMode,
    PairPhase,
    PairRef,
    PairStatus,
    SupervisorMember,
    SupervisorPose,
    SupervisorSpec,
)


def test_debug_snapshot_contains_pair_inputs_and_pose() -> None:
    spec = SupervisorSpec(
        supervisor_id="sup-main",
        name="Main Supervisor",
        members=(SupervisorMember(member_id="m1", member_kind="pair", target_id="pair-a"),),
    )
    statuses = {
        "pair-a": PairStatus(
            ref=PairRef(pair_id="pair-a", axis_id="Anton", densi_id="d1", hip_id="h1"),
            facts=PairFacts(
                attached=True,
                stale=False,
                fault=False,
                estop_reset_input=True,
                estart_input=False,
                chk_es_taster_input=True,
                brake_grace_active=False,
                ready_actual=False,
                deadman_active=False,
                live_motion_active=False,
                param_edit_active=False,
                position=3.5,
                velocity=0.1,
                banner_estate="IDLE",
            ),
            phase=PairPhase.ARMED,
            interaction_mode=PairInteractionMode.VIEWING,
            actions=PairActionSurface(
                primary_action=PairAction.CHECK_ES_TASTER,
                allowed_actions=frozenset({PairAction.CHECK_ES_TASTER}),
                blocking_reason="",
            ),
        )
    }
    pose = SupervisorPose(
        position={"x": 3.5}, velocity={"x": 0.1}, dofs={"x": 3.5}, valid=True, summary="ok"
    )

    got = build_supervisor_debug_snapshot(spec=spec, statuses=statuses, pose=pose)
    assert got["supervisor_id"] == "sup-main"
    pair0 = got["pairs"][0]
    assert pair0["phase"] == "armed"
    assert pair0["estop_reset_input"] is True
    assert pair0["chk_es_taster_input"] is True
    assert got["pose"]["position"] == {"x": 3.5}
    assert got["pose"]["velocity"] == {"x": 0.1}
    assert got["pose"]["dofs"] == {"x": 3.5}
