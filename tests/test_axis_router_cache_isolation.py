from __future__ import annotations

from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.axis_router import AxisRouter
from tests.test_axis_router import _CmdSink, _TelemSink


def test_axis_router_slice_keeps_device_caches_axis_local() -> None:
    router = AxisRouter(
        axis_ids=["Anton", "Debby"],
        dev_cmd_out_by_axis={"Anton": _CmdSink([]), "Debby": _CmdSink([])},
        ui_telem_out_by_axis={"Anton": _TelemSink([]), "Debby": _TelemSink([])},
    )

    router.ingest_device_telemetry(
        [
            TelemetrySnapshot(
                tick=1,
                t_s=0.0,
                core_mode="LIVE",
                estop=False,
                fault=False,
                axes={"Anton": object()},
                estop_status_word=0x11,
                params={"p": 1.0},
            ),
            TelemetrySnapshot(
                tick=1,
                t_s=0.0,
                core_mode="LIVE",
                estop=False,
                fault=False,
                axes={"Debby": object()},
                estop_status_word=0x22,
                params={"p": 2.0},
            ),
        ]
    )

    snap = TelemetrySnapshot(
        tick=2,
        t_s=0.1,
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={"Anton": object(), "Debby": object()},
        estop_status_word=0x99,
        params={"fallback": 0.0},
    )

    anton = router.slice_snapshot_for_axis(snap, "Anton")
    debby = router.slice_snapshot_for_axis(snap, "Debby")

    assert anton.estop_status_word == 0x11
    assert debby.estop_status_word == 0x22
    assert anton.params == {"p": 1.0}
    assert debby.params == {"p": 2.0}
