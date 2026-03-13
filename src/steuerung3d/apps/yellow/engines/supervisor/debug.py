from __future__ import annotations

from .models import (
    BatchResetEstopResult,
    PairResetEstopEligibility,
    PairStatus,
    SupervisorPose,
    SupervisorSpec,
)


def build_supervisor_debug_snapshot(
    *,
    spec: SupervisorSpec,
    statuses: dict[str, PairStatus],
    pose: SupervisorPose,
) -> dict[str, object]:
    pairs: list[dict[str, object]] = []
    for pair_id, status in sorted(statuses.items()):
        facts = status.facts
        pairs.append(
            {
                "pair_id": pair_id,
                "axis_id": status.ref.axis_id,
                "densi_id": status.ref.densi_id,
                "hip_id": status.ref.hip_id,
                "phase": status.phase.value,
                "interaction_mode": status.interaction_mode.value,
                "primary_action": (
                    None
                    if status.actions.primary_action is None
                    else status.actions.primary_action.value
                ),
                "allowed_actions": sorted(a.value for a in status.actions.allowed_actions),
                "blocking_reason": status.actions.blocking_reason,
                "estop_reset_input": bool(facts.estop_reset_input),
                "estart_input": bool(facts.estart_input),
                "chk_es_taster_input": bool(facts.chk_es_taster_input),
                "position": facts.position,
                "velocity": facts.velocity,
                "banner_estate": str(facts.banner_estate or ""),
            }
        )

    return {
        "supervisor_id": spec.supervisor_id,
        "name": spec.name,
        "members": [
            {
                "member_id": m.member_id,
                "member_kind": m.member_kind,
                "target_id": m.target_id,
                "order_key": m.order_key,
            }
            for m in spec.members
        ],
        "pairs": pairs,
        "pose": {
            "position": dict(pose.position),
            "velocity": dict(pose.velocity),
            "dofs": dict(pose.dofs),
            "valid": bool(pose.valid),
            "summary": str(pose.summary),
        },
    }


def build_reset_estop_debug_entry(
    status: PairStatus,
    eligibility: PairResetEstopEligibility,
) -> dict[str, object]:
    facts = status.facts
    return {
        "pair_id": status.ref.pair_id,
        "phase": status.phase.value,
        "interaction_mode": status.interaction_mode.value,
        "estop_reset_input": bool(facts.estop_reset_input),
        "estart_input": bool(facts.estart_input),
        "eligible": bool(eligibility.eligible),
        "reason": str(eligibility.reason),
    }


def build_reset_estop_batch_debug_summary(
    batch_result: BatchResetEstopResult,
) -> dict[str, object]:
    return {
        "requested_pair_ids": list(batch_result.requested_pair_ids),
        "issued_pair_ids": list(batch_result.issued_pair_ids),
        "blocked_pair_ids": list(batch_result.blocked_pair_ids),
        "results": [
            {
                "pair_id": result.pair_id,
                "issued": bool(result.issued),
                "eligible": bool(result.eligible),
                "reason": str(result.reason),
                "source": result.source.value,
            }
            for result in batch_result.results
        ],
    }
