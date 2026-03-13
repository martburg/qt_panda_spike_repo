from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairAction,
    PairInteractionMode,
    PairPhase,
)
from steuerung3d.apps.yellow.panels.supervisor.supervisor_presenter import (
    format_interaction_mode,
    format_pair_phase,
    format_position,
    format_primary_action,
    format_velocity,
)


def test_phase_formatting_is_human_friendly() -> None:
    assert format_pair_phase(PairPhase.BRAKE_GRACE) == "Brake Grace"


def test_interaction_mode_formatting_is_human_friendly() -> None:
    assert format_interaction_mode(PairInteractionMode.EDITING_PARAMETERS) == "Editing Parameters"


def test_position_and_velocity_handle_missing_values() -> None:
    assert format_position(None) == "—"
    assert format_velocity(None) == "—"


def test_position_and_velocity_format_units() -> None:
    assert format_position(12.345) == "12.35 m"
    assert format_velocity(0.2) == "0.20 m/s"


def test_primary_action_formatting_uses_domain_labels() -> None:
    assert format_primary_action(PairAction.CHECK_ES_TASTER) == "Check EsTaster"
    assert format_primary_action(None) == ""
