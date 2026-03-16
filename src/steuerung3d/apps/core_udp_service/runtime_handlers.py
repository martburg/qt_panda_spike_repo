from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Protocol

from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot, apply_measured_snapshot
from steuerung3d.protocol.axis_router import AxisRouter
from steuerung3d.protocol.udp_channels import UdpIntentIn
from steuerung3d.protocol.udp_plc_channels import UdpPlcTelemetryIn
from steuerung3d.util.heartbeat import ChangeTracker

from .reporter import emit_birds_eye_status, log_periodic_heartbeat


class _SnapshotFanoutLike(Protocol):
    def publish_telemetry(self, snap: TelemetrySnapshot) -> None: ...


class _ControlContextOutLike(Protocol):
    def publish_control_context(self, ctx: ControlContext) -> None: ...


class _StatusLike(Protocol):
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
        estop_reset_by_axis, param_ops_by_axis = self.compute_one_shots_by_axis(
            state, self.axis_ids
        )
        sent = self.router.publish_command_frames(
            cmd_frame,
            estop_reset_by_axis=estop_reset_by_axis,
            param_ops_by_axis=param_ops_by_axis,
        )
        self.stats["cmd_out"] += max(1, sent)
        self.last_seen["cmd_ts"] = time.monotonic()

    def _ingest_device_telemetry(self, state: MachineState) -> None:
        snaps = self.dev_telem_in.drain_telemetry(limit=50)
        if snaps:
            self.stats["dev_telem_in"] += len(snaps)
            self.last_seen["dev_telem_ts"] = time.monotonic()
            self.router.ingest_device_telemetry(snaps)
            for snap in snaps:
                apply_measured_snapshot(state, snap)
            self.log.debug(
                "rx dev telem: %d (last estop=%s fault=%s tick=%s)",
                len(snaps),
                snaps[-1].estop,
                snaps[-1].fault,
                snaps[-1].tick,
            )
            return
        self.log.debug("rx dev telem: 0")

    def _apply_mode(self, state: MachineState, dt: float) -> None:
        try:
            self.apply_mode_aggregation(state, router=self.router, axis_ids=self.axis_ids, dt=dt)
        except Exception:
            self.log.exception("core mode aggregation failed")

    def _emit_heartbeat(self, state: MachineState) -> None:
        now = time.monotonic()
        if now - self.t_last_report >= 1.0:
            log_periodic_heartbeat(
                log=self.log,
                now=now,
                t0=self.t0,
                state=state,
                stats=self.stats,
                last_seen=self.last_seen,
            )
            self.t_last_report = now

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
    c2_telem_outs: list[object]
    control_context_out: _ControlContextOutLike
    stats: Dict[str, int]
    last_seen: Dict[str, Any]
    status: _StatusLike | None
    state: MachineState
    last_intents_meta: Dict[str, Any]
    log: logging.Logger

    state_ch: ChangeTracker = field(default_factory=ChangeTracker)
    lt_last_ui_log_s_by_axis: dict[str, float] = field(default_factory=dict)
    context_seq: int = 0

    def _log_state_changes(self, snap: TelemetrySnapshot) -> None:
        try:
            mode_v = str(getattr(snap, "core_mode", ""))
            estop_v = bool(getattr(snap, "estop", False))
            fault_v = bool(getattr(snap, "fault", False))
            rig_v = str(getattr(snap, "rig_mode", ""))
            if (
                self.state_ch.changed("core_mode", mode_v)
                or self.state_ch.changed("estop", estop_v)
                or self.state_ch.changed("fault", fault_v)
                or self.state_ch.changed("rig_mode", rig_v)
            ):
                self.log.info(
                    "state: core_mode=%s estop=%s fault=%s rig_mode=%s",
                    mode_v,
                    estop_v,
                    fault_v,
                    rig_v,
                )
            claims = tuple(sorted(dict(getattr(self.state, "axis_claims", {}) or {}).items()))
            if self.state_ch.changed("claims", claims):
                self.log.info("claims: %s", dict(claims))
            pe = bool(getattr(self.state, "param_edit_active", False))
            pg = str(getattr(self.state, "param_edit_group", ""))
            if self.state_ch.changed("param_edit", (pe, pg)):
                self.log.info("param_edit: active=%s group=%s", pe, pg)
        except Exception:
            pass

    def _publish_ui_and_c2(self, snap: TelemetrySnapshot) -> None:
        if not self.args.ui_telem_disable:
            self.router.publish_ui_snapshot(snap)
        if self.c2_fanout is not None:
            self.c2_fanout.publish_telemetry(snap)
            self.stats["c2_telem_out"] += max(1, len(self.c2_telem_outs))
            self.last_seen["c2_telem_ts"] = time.monotonic()

    def _log_lifetick(self, snap: TelemetrySnapshot) -> None:
        for axis_id in self.axis_ids:
            try:
                ax = dict(getattr(snap, "axes", {}) or {}).get(axis_id)
                dev_tick = getattr(ax, "device_tick", None)
                now_s = time.monotonic()
                last_s = float(self.lt_last_ui_log_s_by_axis.get(axis_id, 0.0))
                if dev_tick is not None and (now_s - last_s) >= 0.5:
                    self.lt_last_ui_log_s_by_axis[axis_id] = now_s
                    self.log.debug(
                        "LIFETICK Core tx UI telem: axis=%s device_tick=%s", axis_id, int(dev_tick)
                    )
            except Exception:
                pass

    def _update_ui_stats(self, snap: TelemetrySnapshot) -> None:
        if self.args.ui_telem_disable:
            return
        ui_mode = str(getattr(self.args, "ui_telem_mode", "per_axis") or "per_axis").strip().lower()
        n_ui = (
            len(getattr(self.router, "ui_telem_fanout", []) or [])
            if ui_mode == "fanout"
            else len(self.axis_ids)
        )
        self.stats["ui_telem_out"] += max(1, n_ui)
        self.last_seen["ui_telem_ts"] = time.monotonic()
        self.log.debug("tx ui telem: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)

    def _publish_control_context(self) -> None:
        self.context_seq += 1
        mode = str(getattr(self.state, "control_mode", "") or "independent_axes")
        input_mapping = {
            "independent_axes": "axis_rate",
            "sync_kinematic_jog": "cartesian_xyz",
            "goto_pose": "pose_speed",
            "follow_path": "path_speed_trim",
        }.get(mode, "axis_rate")
        self.control_context_out.publish_control_context(
            ControlContext(
                seq=int(self.context_seq),
                mode=mode
                if mode in {"independent_axes", "sync_kinematic_jog", "goto_pose", "follow_path"}
                else "independent_axes",
                selected_target_kind="axis",
                input_mapping=input_mapping,
                motion_enabled=True,
            )
        )

    def _emit_birds_eye(self, snap: TelemetrySnapshot) -> None:
        emit_birds_eye_status(
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
