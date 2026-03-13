from __future__ import annotations

from dataclasses import dataclass

from ...panels.supervisor.supervisor_detail_vm import SupervisorDetailVM, build_supervisor_detail_vm
from ...panels.supervisor.supervisor_node_vm import SupervisorNodeVM, build_supervisor_node_vm
from ...panels.supervisor.supervisor_table_vm import SupervisorTableVM, build_supervisor_table_vm
from .debug import build_supervisor_debug_snapshot
from .kinematics import SupervisorKinematics
from .models import (
    BatchResetEstopResult,
    ControlSource,
    PairFacts,
    PairRef,
    PairResetEstopEligibility,
    PairResetEstopIssueResult,
    PairStatus,
    SupervisorPose,
    SupervisorSpec,
)
from .pair_derivation import build_pair_status
from .reset_estop import (
    apply_reset_estop_to_pair_facts,
    evaluate_reset_estop_eligibility,
    issue_reset_estop_batch as issue_reset_estop_batch_results,
    issue_reset_estop_for_pair,
)


@dataclass
class SupervisorRuntime:
    spec: SupervisorSpec
    pair_refs: dict[str, PairRef]
    kinematics: SupervisorKinematics

    def build_statuses(self, facts_by_pair_id: dict[str, PairFacts]) -> dict[str, PairStatus]:
        statuses: dict[str, PairStatus] = {}
        for member in self.spec.members:
            if member.member_kind != "pair":
                continue
            pair_id = str(member.target_id)
            ref = self.pair_refs.get(pair_id)
            facts = facts_by_pair_id.get(pair_id)
            if ref is None or facts is None:
                continue
            statuses[pair_id] = build_pair_status(ref, facts)
        return statuses

    def build_pose(self, statuses: dict[str, PairStatus]) -> SupervisorPose:
        return self.kinematics.pose_from_pairs(statuses)

    def evaluate_reset_estop(
        self,
        *,
        pair_id: str,
        facts_by_pair_id: dict[str, PairFacts],
    ) -> PairResetEstopEligibility:
        statuses = self.build_statuses(facts_by_pair_id)
        status = statuses.get(str(pair_id))
        if status is None:
            return PairResetEstopEligibility(
                pair_id=str(pair_id), eligible=False, reason="unknown pair id"
            )
        return evaluate_reset_estop_eligibility(status)

    def issue_reset_estop(
        self,
        *,
        pair_id: str,
        facts_by_pair_id: dict[str, PairFacts],
        source: ControlSource = ControlSource.GUI,
    ) -> tuple[PairResetEstopIssueResult, dict[str, PairFacts]]:
        statuses = self.build_statuses(facts_by_pair_id)
        status = statuses.get(str(pair_id))
        if status is None:
            result = PairResetEstopIssueResult(
                pair_id=str(pair_id),
                issued=False,
                eligible=False,
                reason="unknown pair id",
                source=source,
            )
            return result, dict(facts_by_pair_id)
        result = issue_reset_estop_for_pair(status=status, source=source)
        updated = dict(facts_by_pair_id)
        if result.issued:
            updated[str(pair_id)] = apply_reset_estop_to_pair_facts(status.facts, issued=True)
        return result, updated

    def issue_reset_estop_batch(
        self,
        *,
        pair_ids: list[str] | tuple[str, ...],
        facts_by_pair_id: dict[str, PairFacts],
        source: ControlSource = ControlSource.GUI,
    ) -> tuple[BatchResetEstopResult, dict[str, PairFacts]]:
        statuses = self.build_statuses(facts_by_pair_id)
        batch_result = issue_reset_estop_batch_results(
            statuses=statuses,
            pair_ids=pair_ids,
            source=source,
        )
        updated = dict(facts_by_pair_id)
        for result in batch_result.results:
            if not result.issued:
                continue
            status = statuses.get(result.pair_id)
            if status is None:
                continue
            updated[result.pair_id] = apply_reset_estop_to_pair_facts(status.facts, issued=True)
        return batch_result, updated

    def build_table_vm(
        self,
        facts_by_pair_id: dict[str, PairFacts],
        *,
        selected_pair_id: str | None = None,
    ) -> SupervisorTableVM:
        statuses = self.build_statuses(facts_by_pair_id)
        return build_supervisor_table_vm(
            spec=self.spec,
            statuses=statuses,
            selected_pair_id=selected_pair_id,
        )

    def build_node_vm(
        self,
        facts_by_pair_id: dict[str, PairFacts],
        *,
        selected_pair_id: str | None = None,
    ) -> SupervisorNodeVM:
        statuses = self.build_statuses(facts_by_pair_id)
        return build_supervisor_node_vm(
            spec=self.spec,
            statuses=statuses,
            selected_pair_id=selected_pair_id,
        )

    def build_detail_vm(
        self,
        facts_by_pair_id: dict[str, PairFacts],
        *,
        selected_pair_id: str | None = None,
    ) -> SupervisorDetailVM | None:
        statuses = self.build_statuses(facts_by_pair_id)
        return build_supervisor_detail_vm(
            statuses.get(str(selected_pair_id)) if selected_pair_id else None
        )

    def build_debug_snapshot(self, facts_by_pair_id: dict[str, PairFacts]) -> dict[str, object]:
        statuses = self.build_statuses(facts_by_pair_id)
        pose = self.build_pose(statuses)
        return build_supervisor_debug_snapshot(spec=self.spec, statuses=statuses, pose=pose)
