from __future__ import annotations

from .models import (
    PairAction,
    PairActionSurface,
    PairFacts,
    PairInteractionMode,
    PairPhase,
    PairRef,
    PairStatus,
)


def derive_pair_phase(facts: PairFacts) -> PairPhase:
    if bool(facts.stale):
        return PairPhase.OFFLINE
    if not bool(facts.attached):
        return PairPhase.UNATTACHED
    if bool(facts.fault):
        return PairPhase.FAULT
    if bool(facts.live_motion_active):
        return PairPhase.LIVE
    if bool(facts.ready_actual):
        return PairPhase.READY
    if bool(facts.brake_grace_active):
        return PairPhase.BRAKE_GRACE
    if bool(facts.chk_es_taster_input):
        return PairPhase.ARMED
    if bool(facts.estart_input):
        return PairPhase.IDLE
    return PairPhase.ATTACHED


def derive_interaction_mode(facts: PairFacts) -> PairInteractionMode:
    if bool(facts.param_edit_active):
        return PairInteractionMode.EDITING_PARAMETERS
    return PairInteractionMode.VIEWING


_BLOCKED_REASONS: dict[PairPhase, str] = {
    PairPhase.OFFLINE: "pair offline",
    PairPhase.UNATTACHED: "pair unattached",
    PairPhase.FAULT: "pair faulted",
    PairPhase.LIVE: "pair live",
    PairPhase.ARMED: "no supervisor action in armed phase",
    PairPhase.BRAKE_GRACE: "brake grace active",
    PairPhase.READY: "pair ready",
}


def derive_action_surface(
    phase: PairPhase,
    interaction_mode: PairInteractionMode,
    *,
    estop_reset_input: bool = False,
) -> PairActionSurface:
    if interaction_mode == PairInteractionMode.EDITING_PARAMETERS:
        return PairActionSurface(
            primary_action=None,
            allowed_actions=frozenset({PairAction.WRITE_PARAMETERS, PairAction.CANCEL_EDIT}),
            blocking_reason="edit session active",
        )

    if phase == PairPhase.ATTACHED:
        if estop_reset_input:
            return PairActionSurface(
                primary_action=PairAction.ESTART,
                allowed_actions=frozenset({PairAction.ESTART, PairAction.EDIT_PARAMETERS}),
                blocking_reason="",
            )
        return PairActionSurface(
            primary_action=PairAction.RESET_ESTOP,
            allowed_actions=frozenset({PairAction.RESET_ESTOP, PairAction.EDIT_PARAMETERS}),
            blocking_reason="",
        )

    if phase == PairPhase.IDLE:
        return PairActionSurface(
            primary_action=PairAction.CHECK_ES_TASTER,
            allowed_actions=frozenset({PairAction.CHECK_ES_TASTER, PairAction.EDIT_PARAMETERS}),
            blocking_reason="",
        )

    return PairActionSurface(
        primary_action=None,
        allowed_actions=frozenset(),
        blocking_reason=_BLOCKED_REASONS.get(phase, "not actionable"),
    )


def build_pair_status(ref: PairRef, facts: PairFacts) -> PairStatus:
    phase = derive_pair_phase(facts)
    interaction_mode = derive_interaction_mode(facts)
    actions = derive_action_surface(
        phase,
        interaction_mode,
        estop_reset_input=bool(facts.estop_reset_input),
    )
    return PairStatus(
        ref=ref,
        facts=facts,
        phase=phase,
        interaction_mode=interaction_mode,
        actions=actions,
    )
