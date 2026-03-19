from __future__ import annotations

import logging
import os
import subprocess
import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from steuerung3d.core.intents import ReleaseAxis, ReleaseAxisLease
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.udp_channels import (
    UdpIntentOut as UdpIntentOut,
    UdpTelemetryIn as UdpTelemetryIn,
)

from .actions_transport import (
    UdpDensiActionIn as UdpDensiActionIn,
    UdpDensiActionOut as UdpDensiActionOut,
)
from .engine import SupervisorEngine
from .gui.window import SupervisorWindow
from .models import SupervisorProfile
from .runtime_process_support import (
    launch_children,
    launch_hip_child,
    refresh_hip_processes,
    terminate_children,
    terminate_hip_children,
)
from .runtime_smoke_action_support import (
    bind_smoke_action_input,
    close_smoke_action_input,
    ingest_smoke_actions,
)
from .runtime_transport_support import (
    close_transports,
    ingest_telemetry,
    init_transports,
    publish_outbound,
)

log = logging.getLogger("supervisor")


class SupervisorRuntime(QObject):
    def __init__(self, profile: SupervisorProfile) -> None:
        super().__init__()
        self.profile = profile
        self.engine = SupervisorEngine(profile)
        self._children: list[subprocess.Popen[str]] = []
        self._hip_children: dict[str, list[subprocess.Popen[str]]] = {}
        self._merged_snapshot: TelemetrySnapshot | None = None
        self._axes_by_unit_id = {axis.unit_id: axis for axis in profile.axes}
        self.telemetry_in: UdpTelemetryIn
        self.intent_out: UdpIntentOut
        self.action_outs_by_unit_id: dict[str, UdpDensiActionOut]
        self._smoke_action_in: UdpDensiActionIn | None = None

        self._init_transports()
        self._init_window_and_signals()
        self._init_timer()

    def start(self) -> int:
        self._launch_children()
        self._timer.start(int(self.profile.cycle_ms))
        if bool(self.profile.gui):
            self.window.show()
        return 0

    def tick(self) -> None:
        self._refresh_hip_processes()
        self._ingest_telemetry()
        self._ingest_smoke_actions()
        self._apply_window_snapshot()
        self._publish_outbound()

    def open_hip_for_axis(self, unit_id: str) -> None:
        axis = self._axes_by_unit_id.get(str(unit_id))
        if axis is None:
            return

        cmd_text = str(axis.hip_launch).strip()
        if not cmd_text:
            try:
                self.window.status_label.setText(
                    f"{self.engine.snapshot().status_text} | hip: no launch for {axis.axis_id}"
                )
            except Exception:
                pass
            return

        env_overrides: dict[str, str] = {}
        smoke_addr = self._hip_smoke_control_addr_for_unit_id(axis.unit_id)
        if smoke_addr:
            env_overrides["STEUERUNG3D_HIP_SMOKE_CONTROL_IN"] = smoke_addr
        child = launch_hip_child(cmd_text=cmd_text, env_overrides=env_overrides or None)
        self._hip_children.setdefault(axis.unit_id, []).append(child)
        self.engine.set_hip_open_count(axis.unit_id, len(self._hip_children.get(axis.unit_id, [])))

    def _hip_smoke_control_addr_for_unit_id(self, unit_id: str) -> str:
        base_raw = str(os.environ.get("STEUERUNG3D_SUPERVISOR_HIP_SMOKE_BASE", "") or "").strip()
        if not base_raw:
            return ""
        try:
            base = int(base_raw)
        except ValueError:
            return ""
        for idx, axis in enumerate(self.profile.axes):
            if str(axis.unit_id) == str(unit_id):
                return f"127.0.0.1:{base + idx}"
        return ""

    def _refresh_hip_processes(self) -> None:
        refresh_hip_processes(
            profile=self.profile,
            hip_children=self._hip_children,
            set_hip_open_count=self.engine.set_hip_open_count,
            release_hip_authority=self._release_hip_authority,
            axes_by_unit_id=self._axes_by_unit_id,
        )

    def shutdown(self) -> None:
        self._terminate_children()
        self._terminate_hip_children()
        self._close_transports()

    def _init_transports(self) -> None:
        self.telemetry_in, self.intent_out, self.action_outs_by_unit_id = init_transports(
            profile=self.profile
        )
        self._smoke_action_in = bind_smoke_action_input(bind_action_in=UdpDensiActionIn.bind)

    def _init_window_and_signals(self) -> None:
        self.window = SupervisorWindow()
        self.window.reset_estop_clicked.connect(self.engine.queue_reset_estop)
        self.window.estart_clicked.connect(self.engine.queue_estart)
        self.window.resync_clicked.connect(self.engine.queue_resync)
        self.window.recover_clicked.connect(self._on_recover_clicked)
        self.window.chk_es_taster_changed.connect(self.engine.set_chk_requested)
        self.window.unit_selected_changed.connect(self.engine.set_selected)
        self.window.open_hip_clicked.connect(self.open_hip_for_axis)

    def _init_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)

    def _ingest_telemetry(self) -> None:
        merged = ingest_telemetry(
            telemetry_in=self.telemetry_in, merged_snapshot=self._merged_snapshot
        )
        if merged is self._merged_snapshot:
            return
        self._merged_snapshot = merged
        if merged is None:
            return
        self.engine.ingest(merged)

    def _ingest_smoke_actions(self) -> None:
        ingest_smoke_actions(
            smoke_action_in=self._smoke_action_in,
            engine=self.engine,
            open_hip_for_axis=self.open_hip_for_axis,
        )

    def _apply_window_snapshot(self) -> None:
        snapshot = self.engine.snapshot()
        self.window.apply_snapshot(snapshot)

    def _publish_outbound(self) -> None:
        publish_outbound(
            outbound=self.engine.consume_outbound(),
            intent_out=self.intent_out,
            action_outs_by_unit_id=self.action_outs_by_unit_id,
        )

    def _terminate_children(self) -> None:
        terminate_children(children=self._children)

    def _terminate_hip_children(self) -> None:
        terminate_hip_children(hip_children=self._hip_children)

    def _close_transports(self) -> None:
        close_transports(
            telemetry_in=self.telemetry_in,
            intent_out=self.intent_out,
            action_outs_by_unit_id=self.action_outs_by_unit_id,
        )
        close_smoke_action_input(self._smoke_action_in)
        self._smoke_action_in = None

    def _launch_children(self) -> None:
        self._children.extend(launch_children(profile=self.profile))

    def _on_recover_clicked(self) -> None:
        self.engine.queue_recover()
        self.window.show_recover_placeholder()
        self.engine.clear_recover_requested()

    def _release_hip_authority(self, axis_id: str, hip_id: str) -> None:
        try:
            self.intent_out.publish_intent(ReleaseAxis(axis_id=str(axis_id), hip_id=str(hip_id)))
        except Exception:
            log.exception("failed to release axis claim for axis=%s hip=%s", axis_id, hip_id)
        try:
            self.intent_out.publish_intent(
                ReleaseAxisLease(axis_id=str(axis_id), hip_id=str(hip_id))
            )
        except Exception:
            log.exception("failed to release axis lease for axis=%s hip=%s", axis_id, hip_id)


def run_app(profile: SupervisorProfile) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    rt = SupervisorRuntime(profile)
    app.aboutToQuit.connect(rt.shutdown)
    rt.start()
    return app.exec()
