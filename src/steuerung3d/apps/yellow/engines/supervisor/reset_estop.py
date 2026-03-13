from __future__ import annotations

from dataclasses import replace
from typing import Iterable

from .models import (
    BatchResetEstopResult,
    ControlSource,
    PairFacts,
    PairInteractionMode,
    PairPhase,
    PairResetEstopEligibility,
    PairResetEstopIssueResult,
    PairStatus,
)


def evaluate_reset_estop_eligibility(status: PairStatus) -> PairResetEstopEligibility:
    pair_id = str(status.ref.pair_id)
    if status.phase == PairPhase.OFFLINE:
        return PairResetEstopEligibility(pair_id=pair_id, eligible=False, reason="pair offline")
    if status.phase == PairPhase.UNATTACHED:
        return PairResetEstopEligibility(pair_id=pair_id, eligible=False, reason="pair unattached")
    if status.phase == PairPhase.FAULT:
        return PairResetEstopEligibility(pair_id=pair_id, eligible=False, reason="pair faulted")
    if status.interaction_mode == PairInteractionMode.EDITING_PARAMETERS:
        return PairResetEstopEligibility(
            pair_id=pair_id, eligible=False, reason="edit session active"
        )
    if status.phase != PairPhase.ATTACHED:
        return PairResetEstopEligibility(
            pair_id=pair_id,
            eligible=False,
            reason="pair not in reset-estop-capable phase",
        )
    if bool(status.facts.estop_reset_input):
        return PairResetEstopEligibility(
            pair_id=pair_id,
            eligible=False,
            reason="estop reset already present",
        )
    return PairResetEstopEligibility(pair_id=pair_id, eligible=True, reason="")


def issue_reset_estop_for_pair(
    *,
    status: PairStatus,
    source: ControlSource,
) -> PairResetEstopIssueResult:
    eligibility = evaluate_reset_estop_eligibility(status)
    return PairResetEstopIssueResult(
        pair_id=str(status.ref.pair_id),
        issued=bool(eligibility.eligible),
        eligible=bool(eligibility.eligible),
        reason=str(eligibility.reason),
        source=source,
    )


def apply_reset_estop_to_pair_facts(
    facts: PairFacts,
    *,
    issued: bool,
) -> PairFacts:
    if not issued:
        return facts
    return replace(facts, estop_reset_input=True)


def issue_reset_estop_batch(
    *,
    statuses: dict[str, PairStatus],
    pair_ids: Iterable[str],
    source: ControlSource,
) -> BatchResetEstopResult:
    results: list[PairResetEstopIssueResult] = []
    requested_pair_ids = tuple(str(pair_id) for pair_id in pair_ids)
    for pair_id in requested_pair_ids:
        status = statuses.get(pair_id)
        if status is None:
            results.append(
                PairResetEstopIssueResult(
                    pair_id=pair_id,
                    issued=False,
                    eligible=False,
                    reason="unknown pair id",
                    source=source,
                )
            )
            continue
        results.append(issue_reset_estop_for_pair(status=status, source=source))
    return BatchResetEstopResult(requested_pair_ids=requested_pair_ids, results=tuple(results))
