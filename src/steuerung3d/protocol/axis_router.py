from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from steuerung3d.core.axis_id import normalize_axis_id
from steuerung3d.core.command_frame import CommandFrame, ParamOp
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.telemetry import TelemetrySnapshot

from .axis_router_cache import ingest_device_telemetry as _ingest_device_telemetry
from .axis_router_command import publish_command_frames as _publish_command_frames
from .axis_router_publish import publish_ui_snapshot as _publish_ui_snapshot
from .axis_router_snapshot import (
    fanout_snapshot_with_axis_caches as _fanout_snapshot_with_axis_caches,
    project_joy_for_axis as _project_joy_for_axis,
    slice_snapshot_for_axis as _slice_snapshot_for_axis,
)
from .axis_router_types import CommandFrameSink, TelemetrySink, empty_telemetry_sinks


@dataclass
class AxisRouter:
    """Strict per-axis routing and slicing."""

    axis_ids: Sequence[str]
    dev_cmd_out_by_axis: Mapping[str, CommandFrameSink]
    ui_telem_out_by_axis: Mapping[str, TelemetrySink]
    ui_telem_fanout: list[TelemetrySink] = field(default_factory=empty_telemetry_sinks)

    last_dev_params_by_axis: dict[str, dict[str, float]] = field(default_factory=lambda: {})
    last_dev_estop_word_by_axis: dict[str, int] = field(default_factory=lambda: {})
    last_dev_param_edit_active_by_axis: dict[str, bool] = field(default_factory=lambda: {})
    last_dev_param_edit_group_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_plc_uplink_fields_by_axis: dict[str, dict[str, str]] = field(
        default_factory=lambda: {}
    )
    last_dev_plc_uplink_tail_by_axis: dict[str, dict[str, str]] = field(default_factory=lambda: {})
    last_dev_param_commit_req_id_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_param_commit_group_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_param_commit_status_by_axis: dict[str, str] = field(default_factory=lambda: {})
    last_dev_param_commit_age_ticks_by_axis: dict[str, int] = field(default_factory=lambda: {})
    last_dev_param_commit_unmatched_by_axis: dict[str, list[str]] = field(
        default_factory=lambda: {}
    )

    def __post_init__(self) -> None:
        self.axis_ids = [
            normalize_axis_id(a) for a in (self.axis_ids or []) if normalize_axis_id(a)
        ]
        self.dev_cmd_out_by_axis = {
            normalize_axis_id(k): v
            for k, v in dict(self.dev_cmd_out_by_axis or {}).items()
            if normalize_axis_id(k)
        }
        self.ui_telem_out_by_axis = {
            normalize_axis_id(k): v
            for k, v in dict(self.ui_telem_out_by_axis or {}).items()
            if normalize_axis_id(k)
        }
        self.ui_telem_fanout = list(self.ui_telem_fanout or [])

    def publish_command_frames(
        self,
        cmd_frame: CommandFrame,
        *,
        estop_reset_by_axis: Mapping[str, bool] | None = None,
        param_ops_by_axis: Mapping[str, list[ParamOp]] | None = None,
    ) -> int:
        return _publish_command_frames(
            self,
            cmd_frame,
            estop_reset_by_axis=estop_reset_by_axis,
            param_ops_by_axis=param_ops_by_axis,
        )

    def ingest_device_telemetry(self, snaps: Sequence[TelemetrySnapshot]) -> None:
        _ingest_device_telemetry(self, snaps)

    def slice_snapshot_for_axis(self, snap: TelemetrySnapshot, axis_id: str) -> TelemetrySnapshot:
        return _slice_snapshot_for_axis(self, snap, axis_id)

    def _project_joy_for_axis(self, snap: TelemetrySnapshot, axis_id: str) -> JoyState:
        return _project_joy_for_axis(snap, axis_id)

    def fanout_snapshot_with_axis_caches(self, snap: TelemetrySnapshot) -> TelemetrySnapshot:
        return _fanout_snapshot_with_axis_caches(self, snap)

    def publish_ui_snapshot(self, snap: TelemetrySnapshot) -> int:
        return _publish_ui_snapshot(self, snap)
