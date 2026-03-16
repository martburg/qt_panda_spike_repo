from __future__ import annotations

from steuerung3d.apps.supervisor.merge import merge_snapshots
from steuerung3d.core.telemetry import AxisTelemetry, DensiTelemetry, TelemetrySnapshot


def _snap(*, tick: int, axis_id: str) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=tick,
        t_s=0.01 * tick,
        core_mode="ESTOP",
        estop=True,
        fault=False,
        axes={
            axis_id: AxisTelemetry(
                pos=float(tick),
                vel=0.0,
                enabled=False,
                fault=False,
                device_tick=tick,
                lifetick_age=0,
            )
        },
        densis={axis_id: DensiTelemetry(device_id=axis_id, online=True, last_seen_age_ticks=0)},
        axis_estop_status_word={axis_id: 1},
    )


def test_merge_snapshots_preserves_multiple_axes() -> None:
    merged = merge_snapshots(None, [_snap(tick=1, axis_id="Anton"), _snap(tick=2, axis_id="Debby")])
    assert merged is not None
    assert set(merged.axes.keys()) == {"Anton", "Debby"}
    assert set(merged.densis.keys()) == {"Anton", "Debby"}
    assert set(merged.axis_estop_status_word.keys()) == {"Anton", "Debby"}
