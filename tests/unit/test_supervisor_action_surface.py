from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairAction,
    PairInteractionMode,
    PairPhase,
)
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import derive_action_surface


def test_attached_allows_reset_and_edit() -> None:
    got = derive_action_surface(
        PairPhase.ATTACHED, PairInteractionMode.VIEWING, estop_reset_input=False
    )
    assert got.primary_action == PairAction.RESET_ESTOP
    assert got.allowed_actions == frozenset({PairAction.RESET_ESTOP, PairAction.EDIT_PARAMETERS})


def test_idle_allows_check_and_edit() -> None:
    got = derive_action_surface(PairPhase.IDLE, PairInteractionMode.VIEWING)
    assert got.primary_action == PairAction.CHECK_ES_TASTER
    assert got.allowed_actions == frozenset(
        {PairAction.CHECK_ES_TASTER, PairAction.EDIT_PARAMETERS}
    )


def test_editing_mode_switches_to_write_cancel_surface() -> None:
    got = derive_action_surface(PairPhase.IDLE, PairInteractionMode.EDITING_PARAMETERS)
    assert got.primary_action is None
    assert got.allowed_actions == frozenset({PairAction.WRITE_PARAMETERS, PairAction.CANCEL_EDIT})
    assert got.blocking_reason == "edit session active"


def test_armed_and_ready_block_edit_actions_in_first_slice() -> None:
    armed = derive_action_surface(PairPhase.ARMED, PairInteractionMode.VIEWING)
    ready = derive_action_surface(PairPhase.READY, PairInteractionMode.VIEWING)
    assert armed.allowed_actions == frozenset()
    assert ready.allowed_actions == frozenset()


def test_non_actionable_phases_have_reasons() -> None:
    for phase in (PairPhase.OFFLINE, PairPhase.FAULT, PairPhase.LIVE):
        got = derive_action_surface(phase, PairInteractionMode.VIEWING)
        assert got.primary_action is None
        assert got.allowed_actions == frozenset()
        assert got.blocking_reason
