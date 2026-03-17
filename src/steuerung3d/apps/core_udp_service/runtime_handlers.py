from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Protocol

from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.udp_channels import UdpIntentIn
from steuerung3d.protocol.udp_plc_channels import UdpPlcTelemetryIn
from steuerung3d.util.heartbeat import ChangeTracker

from .runtime_device_step_support import (
    apply_mode_aggregation,
    emit_heartbeat,
    ingest_device_telemetry,
    publish_commands,
)
from .runtime_snapshot_support import (
    emit_birds_eye,
    log_lifetick,
    log_state_changes,
    publish_control_context,
    publish_ui_and_c2,
    update_ui_stats,
)


class _SnapshotFanoutLike(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...


class _ControlContextOutLike(Protocol):
    def publish_control_context(self, ctx: ControlContext) -> None: ...


class StatusLike(Protocol):
    def emit_every(self, *, level: str, summary: str, fields: dict[str, object]) -> None: ...


def build_intent_drain(
    *,
    op_intent_in: UdpIntentIn,
    stats: Dict[str, int],
    last_seen: Dict[str, Any],
    last_intents_meta: Dict[str, Any],
    log: logging.Logger,
) -> Callable[[], list[Any]]:
    def drain_intents() -> list[Any]:
        ints = op_intent_in.drain_intents(limit=200)
        if ints:
            stats["intents_in"] += len(ints)
            last_seen["intent_ts"] = time.monotonic()
            try:
                last_intents_meta["count"] = int(len(ints))
                last_intents_meta["types"] = sorted({type(i).__name__ for i in ints})
            except Exception:
                last_intents_meta["count"] = int(len(ints))
                last_intents_meta["types"] = []
            log.debug("rx intents: %d (last=%s)", len(ints), type(ints[-1]).__name__)
        return list(ints)

    return drain_intents


@dataclass
class DeviceStepper:
    router: AxisRouter
    axis_ids: list[str]
    dev_telem_in: UdpPlcTelemetryIn
    stats: Dict[str, int]
    last_seen: Dict[str, Any]
    t0: float
    apply_mode_aggregation: Callable[..., None]
    compute_one_shots_by_axis: Callable[..., Any]
    log: logging.Logger

    t_last_report: float = field(default_factory=time.monotonic)

    def _publish_commands(self, state: MachineState, cmd_frame: Any) -> None:
        publish_commands(
            router=self.router,
            axis_ids=self.axis_ids,
            state=state,
            cmd_frame=cmd_frame,
            stats=self.stats,
            last_seen=self.last_seen,
            compute_one_shots_by_axis=self.compute_one_shots_by_axis,
        )

    def _ingest_device_telemetry(self, state: MachineState) -> None:
        ingest_device_telemetry(
            dev_telem_in=self.dev_telem_in,
            router=self.router,
            state=state,
            stats=self.stats,
            last_seen=self.last_seen,
            log=self.log,
        )

    def _apply_mode(self, state: MachineState, dt: float) -> None:
        apply_mode_aggregation(
            apply_mode_aggregation_fn=self.apply_mode_aggregation,
            state=state,
            router=self.router,
            axis_ids=self.axis_ids,
            dt=dt,
            log=self.log,
        )

    def _emit_heartbeat(self, state: MachineState) -> None:
        self.t_last_report = emit_heartbeat(
            now=time.monotonic(),
            t_last_report=self.t_last_report,
            t0=self.t0,
            state=state,
            stats=self.stats,
            last_seen=self.last_seen,
            log=self.log,
        )

    def __call__(self, state: MachineState, cmd_frame: Any, dt: float) -> None:
        self._publish_commands(state, cmd_frame)
        self._ingest_device_telemetry(state)
        self._apply_mode(state, dt)
        self.log.debug(
            "tx cmd frame: tick=%s estop=%s fault=%s core_mode=%s",
            cmd_frame.tick,
            cmd_frame.estop,
            cmd_frame.fault,
            cmd_frame.core_mode,
        )
        self._emit_heartbeat(state)


@dataclass
class SnapshotHandler:
    router: AxisRouter
    axis_ids: list[str]
    args: Any
    c2_fanout: _SnapshotFanoutLike | None
    c2_telem_outs: Sequence[object]
    control_context_out: _ControlContextOutLike
    stats: Dict[str, int]
    last_seen: Dict[str, Any]
    status: StatusLike | None
    state: MachineState
    last_intents_meta: Dict[str, Any]
    log: logging.Logger

    state_ch: ChangeTracker = field(default_factory=ChangeTracker)
    lt_last_ui_log_s_by_axis: dict[str, float] = field(default_factory=dict)
    context_seq: int = 0

    def _log_state_changes(self, snap: TelemetrySnapshot) -> None:
        log_state_changes(snap=snap, state=self.state, state_ch=self.state_ch, log=self.log)

    def _publish_ui_and_c2(self, snap: TelemetrySnapshot) -> None:
        publish_ui_and_c2(
            snap=snap,
            args=self.args,
            router=self.router,
            c2_fanout=self.c2_fanout,
            c2_telem_outs=self.c2_telem_outs,
            stats=self.stats,
            last_seen=self.last_seen,
        )

    def _log_lifetick(self, snap: TelemetrySnapshot) -> None:
        log_lifetick(
            snap=snap,
            axis_ids=self.axis_ids,
            lt_last_ui_log_s_by_axis=self.lt_last_ui_log_s_by_axis,
            log=self.log,
        )

    def _update_ui_stats(self, snap: TelemetrySnapshot) -> None:
        update_ui_stats(
            snap=snap,
            args=self.args,
            router=self.router,
            axis_ids=self.axis_ids,
            stats=self.stats,
            last_seen=self.last_seen,
            log=self.log,
        )

    def _publish_control_context(self) -> None:
        self.context_seq = publish_control_context(
            state=self.state,
            control_context_out=self.control_context_out,
            context_seq=self.context_seq,
        )

    def _emit_birds_eye(self, snap: TelemetrySnapshot) -> None:
        emit_birds_eye(
            status=self.status,
            snap=snap,
            state=self.state,
            router=self.router,
            axis_ids=self.axis_ids,
            last_intents_meta=self.last_intents_meta,
            last_seen=self.last_seen,
        )

    def __call__(self, snap: TelemetrySnapshot) -> None:
        self._log_state_changes(snap)
        self._publish_ui_and_c2(snap)
        self._log_lifetick(snap)
        self._update_ui_stats(snap)
        self._publish_control_context()
        self._emit_birds_eye(snap)
