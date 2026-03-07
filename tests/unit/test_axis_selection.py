from __future__ import annotations

from steuerung3d.core.axis_selection import (
    authoritative_selected_axis,
    resolve_motion_axis_id,
    visible_axis_ids_for_hip,
)
from steuerung3d.core.telemetry import DensiTelemetry


def test_visible_axis_ids_for_hip_filters_foreign_claims() -> None:
    densis = {
        "Anton": DensiTelemetry(device_id="Anton", online=True, claimed_by_hip=""),
        "Debby": DensiTelemetry(device_id="Debby", online=True, claimed_by_hip="other"),
        "Cecil": DensiTelemetry(device_id="Cecil", online=True, claimed_by_hip="hip-a"),
    }

    assert visible_axis_ids_for_hip(densis=densis, hip_id="hip-a", prev_selected="") == [
        "Anton",
        "Cecil",
    ]


def test_authoritative_selected_axis_keeps_claimed_previous_axis() -> None:
    densis = {
        "Anton": DensiTelemetry(device_id="Anton", online=True, claimed_by_hip="other"),
        "Cecil": DensiTelemetry(device_id="Cecil", online=True, claimed_by_hip="hip-a"),
    }

    assert (
        authoritative_selected_axis(
            densis=densis,
            hip_id="hip-a",
            selected_axis="Anton",
            prev_selected="Cecil",
        )
        == "Cecil"
    )


def test_resolve_motion_axis_id_single_axis_bringup_remains_unambiguous() -> None:
    axes = {"Anton": type("Axis", (), {"in_scope": True, "fault": False})()}

    assert (
        resolve_motion_axis_id(
            axis_id="",
            axis_ids=["Anton"],
            joy_deadman=True,
            joy_select_hip=True,
            axes=axes,
        )
        == "Anton"
    )
