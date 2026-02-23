from __future__ import annotations

from dataclasses import dataclass
from typing import List

from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame, ParamWriteOp
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot
from steuerung3d.protocol.axis_router import AxisRouter


@dataclass
class _CmdSink:
    frames: List[CommandFrame]
    def publish_command_frame(self, frame: CommandFrame) -> None:
        self.frames.append(frame)


@dataclass
class _TelemSink:
    snaps: List[TelemetrySnapshot]
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None:
        self.snaps.append(snap)


def test_router_reduces_multi_axis_command_frame_and_lifetick_echo():
    axis_ids = ["X", "Y"]
    x_out, y_out = _CmdSink([]), _CmdSink([])
    t_x, t_y = _TelemSink([]), _TelemSink([])

    router = AxisRouter(
        axis_ids=axis_ids,
        dev_cmd_out_by_axis={"X": x_out, "Y": y_out},
        ui_telem_out_by_axis={"X": t_x, "Y": t_y},
    )

    frame = CommandFrame(
        tick=10,
        t_s=0.2,
        estop=False,
        fault=False,
        mode="LIVE",
        axes={
            "X": AxisSetpoint(enable=True, vel=2.0),
            "Y": AxisSetpoint(enable=False, vel=4.0),
        },
        lifetick_echo={"X": 123, "Y": 456},
        estop_reset=False,
        param_ops=[],
    )

    sent = router.publish_command_frames(
        frame,
        estop_reset_by_axis={"X": True, "Y": False},
        param_ops_by_axis={
            "X": [ParamWriteOp(group="pos", values={"a": 1.0})],
            "Y": [],
        },
    )

    assert sent == 2
    assert len(x_out.frames) == 1
    assert len(y_out.frames) == 1

    fx, fy = x_out.frames[0], y_out.frames[0]
    assert list(fx.axes.keys()) == ["X"]
    assert list(fy.axes.keys()) == ["Y"]
    assert fx.lifetick_echo == {"X": 123}
    assert fy.lifetick_echo == {"Y": 456}
    assert fx.estop_reset is True
    assert fy.estop_reset is False
    assert len(fx.param_ops) == 1
    assert fy.param_ops == []


def test_router_slices_ui_snapshot_and_pins_device_scoped_fields():
    axis_ids = ["X", "Y"]
    x_out, y_out = _CmdSink([]), _CmdSink([])
    t_x, t_y = _TelemSink([]), _TelemSink([])

    router = AxisRouter(
        axis_ids=axis_ids,
        dev_cmd_out_by_axis={"X": x_out, "Y": y_out},
        ui_telem_out_by_axis={"X": t_x, "Y": t_y},
    )

    # Ingest a device telemetry that only reports axis X.
    dev_snap_x = TelemetrySnapshot(
        tick=1,
        t_s=0.02,
        mode="LIVE",
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={"X": AxisTelemetry(pos=0.0, vel=0.0, enabled=True, fault=False)},
        rig_mode="DISCOVERY",
        densis={},
        estop_status_word=0x55,
        param_edit_active=True,
        param_edit_group="guider",
        params={"p": 12.5},
        core_acks=[],
        param_commit_req_id="r1",
        param_commit_group="g1",
        param_commit_status="ok",
        param_commit_age_ticks=2,
        param_commit_unmatched=["u"],
    )
    router.ingest_device_telemetry([dev_snap_x])

    # Core snapshot has both axes, but should be sliced per axis.
    core_snap = TelemetrySnapshot(
        tick=2,
        t_s=0.04,
        mode="LIVE",
        core_mode="LIVE",
        estop=False,
        fault=False,
        axes={
            "X": AxisTelemetry(pos=1.0, vel=0.1, enabled=True, fault=False),
            "Y": AxisTelemetry(pos=2.0, vel=0.2, enabled=False, fault=False),
        },
        rig_mode="DISCOVERY",
        densis={},
        estop_status_word=0,
        param_edit_active=False,
        param_edit_group="",
        params={},
        core_acks=[],
        param_commit_req_id="",
        param_commit_group="",
        param_commit_status="idle",
        param_commit_age_ticks=0,
        param_commit_unmatched=[],
    )

    sent = router.publish_ui_snapshot(core_snap)
    assert sent == 2
    assert len(t_x.snaps) == 1
    assert len(t_y.snaps) == 1

    sx, sy = t_x.snaps[0], t_y.snaps[0]
    assert list(sx.axes.keys()) == ["X"]
    assert list(sy.axes.keys()) == ["Y"]

    # X gets pinned fields from device telemetry cache.
    assert sx.estop_status_word == 0x55
    assert sx.param_edit_active is True
    assert sx.param_edit_group == "guider"
    assert sx.params == {"p": 12.5}
    assert sx.param_commit_req_id == "r1"
    assert sx.param_commit_status == "ok"

    # Y has no device cache yet; should fall back to core snapshot fields.
    assert sy.estop_status_word == 0
    assert sy.param_edit_active is False
    assert sy.params == {}