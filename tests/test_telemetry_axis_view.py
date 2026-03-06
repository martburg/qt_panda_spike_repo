from __future__ import annotations

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.core.telemetry_axis_view import axis_scoped_snapshot


def _fanout_snap() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=1.0, vel=0.1, enabled=True, fault=False),
            "Debby": AxisTelemetry(pos=2.0, vel=0.2, enabled=True, fault=False),
        },
        estop_status_word=55,
        params={"VelMax": 9.9},
        plc_uplink_fields={"Axis": "Anton"},
        axis_estop_status_word={"Anton": 11, "Debby": 22},
        axis_params={"Anton": {"VelMax": 1.1}, "Debby": {"VelMax": 2.2}},
        axis_plc_uplink_fields={"Anton": {"Axis": "Anton"}, "Debby": {"Axis": "Debby"}},
        axis_param_edit_active={"Anton": True, "Debby": False},
        axis_param_edit_group={"Anton": "filter", "Debby": ""},
        axis_param_commit_status={"Anton": "applied", "Debby": "idle"},
    )


def test_axis_scoped_snapshot_projects_axis_specific_surface() -> None:
    got = axis_scoped_snapshot(_fanout_snap(), "Debby")
    assert got.estop_status_word == 22
    assert got.params == {"VelMax": 2.2}
    assert got.plc_uplink_fields == {"Axis": "Debby"}
    assert got.param_edit_active is False
    assert got.param_edit_group == ""
    assert got.param_commit_status == "idle"


def test_axis_scoped_snapshot_blanks_surface_when_unattached() -> None:
    got = axis_scoped_snapshot(_fanout_snap(), "")
    assert got.estop_status_word == 0
    assert got.params == {}
    assert got.plc_uplink_fields == {}
    assert got.param_edit_active is False
    assert got.param_edit_group == ""
    assert got.param_commit_status == "idle"
