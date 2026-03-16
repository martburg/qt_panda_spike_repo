from __future__ import annotations

import logging
import os
import shlex
import subprocess
import sys

from PySide6.QtCore import QObject, QTimer
from PySide6.QtWidgets import QApplication

from steuerung3d.core.net import parse_hostport
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn

from .actions_transport import UdpDensiActionOut
from .engine import SupervisorEngine
from .gui.window import SupervisorWindow
from .merge import merge_snapshots
from .models import SupervisorProfile

log = logging.getLogger("supervisor")


class SupervisorRuntime(QObject):
    def __init__(self, profile: SupervisorProfile) -> None:
        super().__init__()
        self.profile = profile
        self.engine = SupervisorEngine(profile)
        self.telemetry_in = UdpTelemetryIn.bind(parse_hostport(profile.telem_in))
        self.intent_out = UdpIntentOut.connect(parse_hostport(profile.intent_out))
        self.action_outs = {
            axis.unit_id: UdpDensiActionOut.connect(parse_hostport(axis.densi_action_out))
            for axis in profile.axes
            if axis.densi_action_out
        }
        self.window = SupervisorWindow()
        self._merged_snapshot = None

        self.window.reset_estop_clicked.connect(self.engine.queue_reset_estop)
        self.window.estart_clicked.connect(self.engine.queue_estart)
        self.window.resync_clicked.connect(self.engine.queue_resync)
        self.window.recover_clicked.connect(self._on_recover_clicked)
        self.window.chk_es_taster_changed.connect(self.engine.set_chk_requested)
        self.window.pair_selected_changed.connect(self.engine.set_selected)
        self.window.open_hip_clicked.connect(self.open_hip_for_axis)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.tick)

        self._children: list[subprocess.Popen[str]] = []
        self._hip_children: dict[str, list[subprocess.Popen[str]]] = {}

    def start(self) -> int:
        self._launch_children()
        self._timer.start(int(self.profile.cycle_ms))
        if bool(self.profile.gui):
            self.window.show()
        return 0

    def tick(self) -> None:
        self._refresh_hip_processes()
        snaps = self.telemetry_in.drain_telemetry(limit=50)
        if snaps:
            self._merged_snapshot = merge_snapshots(self._merged_snapshot, snaps)
            self.engine.ingest(self._merged_snapshot)

        snapshot = self.engine.snapshot()
        self.window.apply_snapshot(snapshot)

        outbound = self.engine.consume_outbound()
        for intent in outbound.intents:
            try:
                self.intent_out.publish_intent(intent)
            except Exception:
                log.exception("failed to publish intent %r", intent)

        for pair_id, actions in outbound.densi_actions.items():
            tx = self.action_outs.get(pair_id)
            if tx is None:
                continue
            for action in actions:
                try:
                    tx.publish_action(action)
                except Exception:
                    log.exception("failed to publish densi action %s -> %s", pair_id, action)

    def open_hip_for_axis(self, unit_id: str) -> None:
        axis = next((axis for axis in self.profile.axes if axis.unit_id == str(unit_id)), None)
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

        env = dict(os.environ)
        argv = shlex.split(cmd_text)
        child = subprocess.Popen(argv, cwd=os.getcwd(), env=env, text=True)
        self._hip_children.setdefault(axis.unit_id, []).append(child)
        self.engine.set_hip_open_count(axis.unit_id, len(self._hip_children.get(axis.unit_id, [])))

    def _refresh_hip_processes(self) -> None:
        for unit_id, children in list(self._hip_children.items()):
            alive = [child for child in children if child.poll() is None]
            if alive:
                self._hip_children[unit_id] = alive
            else:
                self._hip_children.pop(unit_id, None)
            self.engine.set_hip_open_count(unit_id, len(alive))

    def shutdown(self) -> None:
        for child in self._children:
            try:
                child.terminate()
            except Exception:
                pass

        for children in self._hip_children.values():
            for child in children:
                try:
                    child.terminate()
                except Exception:
                    pass

        try:
            self.telemetry_in.rx.link.close()
        except Exception:
            pass

        try:
            self.intent_out.tx.link.close()
        except Exception:
            pass

        for tx in self.action_outs.values():
            try:
                tx.tx.link.close()
            except Exception:
                pass

    def _launch_children(self) -> None:
        if self.profile.launch_stack:
            cmd = [
                sys.executable,
                "-m",
                "steuerung3d",
                "up",
                "--profile",
                self.profile.launch_stack,
            ]
            self._children.append(subprocess.Popen(cmd, cwd=os.getcwd(), text=True))
            return

        env = dict(os.environ)
        for axis in self.profile.axes:
            for cmd_text in (axis.hip_launch, axis.densi_launch):
                if not cmd_text:
                    continue
                argv = shlex.split(cmd_text)
                self._children.append(subprocess.Popen(argv, cwd=os.getcwd(), env=env, text=True))

    def _on_recover_clicked(self) -> None:
        self.engine.queue_recover()
        self.window.show_recover_placeholder()
        self.engine.clear_recover_requested()


def run_app(profile: SupervisorProfile) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    rt = SupervisorRuntime(profile)
    app.aboutToQuit.connect(rt.shutdown)
    rt.start()
    return app.exec()
