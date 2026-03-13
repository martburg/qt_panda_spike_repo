from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairAction,
    PairInteractionMode,
    PairPhase,
)
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import derive_action_surface


def test_attached_without_reset_input_requires_reset_estop() -> None:
    got = derive_action_surface(
        PairPhase.ATTACHED,
        PairInteractionMode.VIEWING,
        estop_reset_input=False,
    )
    assert got.primary_action == PairAction.RESET_ESTOP
    assert got.allowed_actions == frozenset({PairAction.RESET_ESTOP, PairAction.EDIT_PARAMETERS})


def test_attached_with_reset_input_exposes_estart_next() -> None:
    got = derive_action_surface(
        PairPhase.ATTACHED,
        PairInteractionMode.VIEWING,
        estop_reset_input=True,
    )
    assert got.primary_action == PairAction.ESTART
    assert got.allowed_actions == frozenset({PairAction.ESTART, PairAction.EDIT_PARAMETERS})
