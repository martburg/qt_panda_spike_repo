from __future__ import annotations

from steuerung3d.apps.supervisor.gui.viewport.selection_bridge import (
    RawPickResult,
    ShellSelectionState,
    ViewportSelectionEvent,
    normalize_viewport_object_name,
    selection_event_from_pick_result,
    selection_summary_from_event,
)


def test_normalize_viewport_object_name_strips_whitespace() -> None:
    assert normalize_viewport_object_name("  joint1_axis_base  ") == "joint1_axis_base"


def test_selection_summary_defaults_when_event_missing() -> None:
    assert selection_summary_from_event(None) == ShellSelectionState()


def test_selection_event_from_pick_result_normalizes_fields() -> None:
    event = selection_event_from_pick_result(
        RawPickResult(
            object_name="  actual_aim  ",
            machine_id=" head_a ",
            object_id=" actual_aim ",
            object_kind=" aim_line ",
            hit_point_world=(1.0, 2.0, 3.0),
        )
    )
    assert event == ViewportSelectionEvent(
        object_name="actual_aim",
        machine_id="head_a",
        object_id="actual_aim",
        object_kind="aim_line",
        hit_point_world=(1.0, 2.0, 3.0),
    )


def test_selection_summary_includes_machine_prefix_when_present() -> None:
    state = selection_summary_from_event(
        ViewportSelectionEvent(
            object_name="actual_aim",
            machine_id="head_a",
            object_id="actual_aim",
            object_kind="aim_line",
        )
    )
    assert state.selected_object_name == "actual_aim"
    assert state.selected_machine_id == "head_a"
    assert state.selected_object_id == "actual_aim"
    assert state.selected_object_kind == "aim_line"
    assert state.summary_text == "head_a | actual_aim"
