from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.kinematics_simple import OnePairOneDofKinematics
from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairActionSurface,
    PairFacts,
    PairInteractionMode,
    PairPhase,
    PairRef,
    PairStatus,
)


def _status(pair_id: str, *, position: float | None, velocity: float | None) -> PairStatus:
    return PairStatus(
        ref=PairRef(
            pair_id=pair_id, axis_id=pair_id, densi_id=f"d-{pair_id}", hip_id=f"h-{pair_id}"
        ),
        facts=PairFacts(
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
            position=position,
            velocity=velocity,
            banner_estate="",
        ),
        phase=PairPhase.ATTACHED,
        interaction_mode=PairInteractionMode.VIEWING,
        actions=PairActionSurface(
            primary_action=None, allowed_actions=frozenset(), blocking_reason=""
        ),
    )


def test_one_pair_one_dof_maps_position_velocity_and_dofs() -> None:
    kin = OnePairOneDofKinematics({"pair_x": "x"})
    pose = kin.pose_from_pairs({"pair_x": _status("pair_x", position=12.5, velocity=-0.25)})
    assert pose.valid is True
    assert pose.position == {"x": 12.5}
    assert pose.velocity == {"x": -0.25}
    assert pose.dofs == {"x": 12.5}


def test_missing_pair_data_marks_pose_invalid() -> None:
    kin = OnePairOneDofKinematics({"pair_x": "x", "pair_y": "y"})
    pose = kin.pose_from_pairs({"pair_x": _status("pair_x", position=1.0, velocity=0.0)})
    assert pose.valid is False
    assert "pair_y" in pose.summary
