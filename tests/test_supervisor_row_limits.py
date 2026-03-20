from __future__ import annotations

from steuerung3d.apps.supervisor.models import AxisConfig
from steuerung3d.apps.supervisor.rows import build_axis_row
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


def test_build_axis_row_projects_user_position_limits_from_axis_params() -> None:
    row = build_axis_row(
        axis=AxisConfig(axis_id="Anton", unit_id="Anton", densi_id="Anton", hip_id="hip-A"),
        snap=TelemetrySnapshot(
            tick=1,
            t_s=0.0,
            core_mode="IDLE",
            estop=False,
            fault=False,
            axes={
                "Anton": AxisTelemetry(
                    pos=12.5,
                    vel=0.0,
                    enabled=True,
                    fault=False,
                )
            },
            densis={"Anton": DensiTelemetry(device_id="Anton", online=True)},
            axis_params={"Anton": {"UserMin": -20.0, "UserMax": 80.0}},
        ),
        selected=True,
        stale_after_ms=800,
        hip_open_count=0,
    )
    assert row is not None
    assert row.pos == 12.5
    assert row.pos_user_min == -20.0
    assert row.pos_user_max == 80.0


def test_build_axis_row_orders_inverted_user_position_limits() -> None:
    row = build_axis_row(
        axis=AxisConfig(axis_id="Anton", unit_id="Anton", densi_id="Anton", hip_id="hip-A"),
        snap=TelemetrySnapshot(
            tick=1,
            t_s=0.0,
            core_mode="IDLE",
            estop=False,
            fault=False,
            axes={
                "Anton": AxisTelemetry(
                    pos=12.5,
                    vel=0.0,
                    enabled=True,
                    fault=False,
                )
            },
            densis={"Anton": DensiTelemetry(device_id="Anton", online=True)},
            axis_params={"Anton": {"UserMin": 80.0, "UserMax": -20.0}},
        ),
        selected=True,
        stale_after_ms=800,
        hip_open_count=0,
    )
    assert row is not None
    assert row.pos_user_min == -20.0
    assert row.pos_user_max == 80.0


def test_build_axis_row_projects_diagnostics_from_axis_scoped_uplink() -> None:
    row = build_axis_row(
        axis=AxisConfig(axis_id="Anton", unit_id="Anton", densi_id="Anton", hip_id="hip-A"),
        snap=TelemetrySnapshot(
            tick=1,
            t_s=0.0,
            core_mode="IDLE",
            estop=False,
            fault=False,
            axes={
                "Anton": AxisTelemetry(
                    pos=12.5,
                    vel=0.0,
                    enabled=True,
                    fault=False,
                )
            },
            densis={"Anton": DensiTelemetry(device_id="Anton", online=True)},
            axis_params={
                "Anton": {
                    "UserMin": -20.0,
                    "UserMax": 80.0,
                    "MotAuslast": 135.0,
                    "Temp": 42.5,
                    "PosDiffFor": 0.03125,
                }
            },
            axis_plc_uplink_tail={"Anton": {"SystemTime": "N_2026-03-19-19:20:31.123"}},
        ),
        selected=True,
        stale_after_ms=800,
        hip_open_count=0,
    )
    assert row is not None
    assert row.load_pct == 135.0
    assert row.temp_c == 42.5
    assert row.pos_diff_m == 0.03125
    assert row.system_time_token == "N_2026-03-19-19:20:31.123"
