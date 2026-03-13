from __future__ import annotations

from typing import Protocol

from .models import PairStatus, SupervisorPose


class SupervisorKinematics(Protocol):
    def pose_from_pairs(self, pair_statuses: dict[str, PairStatus]) -> SupervisorPose: ...
