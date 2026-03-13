from __future__ import annotations

from dataclasses import dataclass

from .models import PairStatus, SupervisorPose


@dataclass(frozen=True)
class OnePairOneDofKinematics:
    dof_by_pair_id: dict[str, str]

    def pose_from_pairs(self, pair_statuses: dict[str, PairStatus]) -> SupervisorPose:
        position: dict[str, float] = {}
        velocity: dict[str, float] = {}
        dofs: dict[str, float] = {}
        missing: list[str] = []

        for pair_id, dof_name in dict(self.dof_by_pair_id).items():
            status = pair_statuses.get(pair_id)
            if status is None:
                missing.append(pair_id)
                continue
            pos = status.facts.position
            vel = status.facts.velocity
            if pos is None or vel is None:
                missing.append(pair_id)
                continue
            position[dof_name] = float(pos)
            velocity[dof_name] = float(vel)
            dofs[dof_name] = float(pos)

        valid = not missing
        summary = "ok" if valid else f"missing pair data: {', '.join(sorted(missing))}"
        return SupervisorPose(
            position=position,
            velocity=velocity,
            dofs=dofs,
            valid=valid,
            summary=summary,
        )
