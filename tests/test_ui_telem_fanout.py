from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.protocol.axis_router import AxisRouter


@dataclass
class _Sink:
    snaps: list[TelemetrySnapshot] | None = None

    def __post_init__(self) -> None:
        if self.snaps is None:
            self.snaps = []

    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.snaps.append(snap)


def test_axis_router_fanout_publishes_full_snapshot_to_every_sink() -> None:
    s1 = _Sink()
    s2 = _Sink()
    router = AxisRouter(
        axis_ids=["Anton", "Debby"],
        dev_cmd_out_by_axis={},
        ui_telem_out_by_axis={},
        ui_telem_fanout=[s1, s2],
    )
    snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=1.0, vel=0.1, enabled=True, fault=False),
            "Debby": AxisTelemetry(pos=2.0, vel=0.2, enabled=False, fault=False),
        },
    )
    assert router.publish_ui_snapshot(snap) == 2
    assert set(s1.snaps[0].axes.keys()) == {"Anton", "Debby"}
    assert set(s2.snaps[0].axes.keys()) == {"Anton", "Debby"}


def test_axis_router_fanout_includes_axis_scoped_device_caches() -> None:
    s = _Sink()
    router = AxisRouter(
        axis_ids=["Anton", "Debby"],
        dev_cmd_out_by_axis={},
        ui_telem_out_by_axis={},
        ui_telem_fanout=[s],
    )
    dev_snap = TelemetrySnapshot(
        tick=1,
        t_s=0.0,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={"Anton": AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False)},
        estop_status_word=0x55,
        params={"P": 6.3},
    )
    router.ingest_device_telemetry([dev_snap])
    core_snap = TelemetrySnapshot(
        tick=2,
        t_s=0.1,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=1.0, vel=0.1, enabled=True, fault=False),
            "Debby": AxisTelemetry(pos=2.0, vel=0.2, enabled=False, fault=False),
        },
    )
    router.publish_ui_snapshot(core_snap)
    got = s.snaps[0]
    assert got.axis_estop_status_word.get("Anton") == 0x55
    assert got.axis_params.get("Anton") == {"P": 6.3}
