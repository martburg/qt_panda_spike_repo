"""Qt-free runtime seam for DenSi.

Responsibilities:
- Drain CommandFrame input.
- Call DenSiEngine.
- Publish telemetry snapshots.
- Emit non-UI logs/heartbeat/status.

UI rendering stays in the controller until Patch 6.
"""

from __future__ import annotations

import logging

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat

from ..engines.densi.engine import DenSiEngine
from ..engines.densi.inputs import DensiInputs
from ..engines.densi.viewmodel import DensiViewModel
from .densi_runtime_debug import step_lifetick_debug
from .densi_runtime_status import emit_status, publish_telemetry_and_heartbeat
from .densi_runtime_tick import edge_log_cmd_changes, handle_gui_not_halt_cmd
from .densi_runtime_types import DensiRuntimeResult
from .densi_runtime_ui_actions import apply_ui_actions
from .densi_runtime_viewmodel import compute_densi_view_model


class DensiRuntime:
    """Qt-free runtime orchestrator for DenSi."""

    def __init__(
        self,
        *,
        engine: DenSiEngine,
        command_in,
        telemetry_out,
        hb: Heartbeat,
        ch: ChangeTracker,
        status=None,
        dbg_rl=None,
        axis_ids: list[str],
        stale_after_ms: int,
        log: logging.Logger,
        action_in=None,
    ) -> None:
        self.engine = engine
        self.command_in = command_in
        self.telemetry_out = telemetry_out
        self._hb = hb
        self._ch = ch
        self._status = status
        self._dbg_rl = dbg_rl
        self._axis_ids = list(axis_ids or [])
        self._stale_after_ms = int(stale_after_ms)
        self._log = log
        self.action_in = action_in

        self._last_cmd: CommandFrame | None = None
        self._last_cmd_ns: int | None = None
        self._seen_first_cmd: bool = False
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False
        self._force_refresh_checkboxes: bool = False
        self._lt_last_telem_log_s: float = 0.0
        self._lt_last_cmd_log_s: float = 0.0
        self._lt_last_echo_by_axis: dict[str, int | None] = {}

    def collect_inputs(self, *, now_ns: int) -> DensiInputs:
        from ..engines.densi.inputs import DensiEstopToggle, DensiUiInputs

        frames = self.command_in.drain_command_frames(limit=100)
        ui = DensiUiInputs()
        if self.action_in is not None:
            try:
                for action in list(self.action_in.drain_actions(limit=100) or []):
                    name = str(getattr(action, "action", "") or "")
                    if name == "estart":
                        ui.es_start_clicked = True
                    elif name == "resync":
                        ui.diag_resync_clicked = True
                    elif name == "chk_es_taster":
                        ui.estop_bit_toggles.append(
                            DensiEstopToggle(key="taster", checked=bool(getattr(action, "value", False)))
                        )
            except Exception:
                self._log.debug("remote actions drain failed", exc_info=True)
        return DensiInputs(frames=list(frames), now_ns=int(now_ns), ui=ui)

    def tick(self, *, inputs: DensiInputs) -> DensiRuntimeResult:
        frames = list(inputs.frames or [])
        now_ns = int(inputs.now_ns)
        self._apply_ui_actions(inputs)
        if frames:
            self._last_cmd = frames[-1]
            self._last_cmd_ns = int(now_ns)
            self._seen_first_cmd = True
            self._hb.inc("cmd_rx", len(frames))
            self._log.debug(
                "rx cmd: tick=%s estop_reset=%s fault=%s core_mode=%s",
                getattr(self._last_cmd, "tick", None),
                getattr(self._last_cmd, "estop_reset", None),
                getattr(self._last_cmd, "fault", None),
                getattr(self._last_cmd, "core_mode", None),
            )

        res = self.engine.step(frames=frames, now_ns=int(now_ns))
        self._last_cmd = res.last_cmd
        self._last_cmd_ns = res.last_cmd_ns
        self._seen_first_cmd = bool(getattr(self.engine, "seen_first_cmd", False))

        self._step_lifetick_debug(now_ns=now_ns, last_cmd=self._last_cmd)
        self._edge_log_cmd_changes(self._last_cmd)
        self._handle_gui_not_halt_cmd(self._last_cmd)

        snap = TelemetrySnapshot.from_state(self.engine.state)
        self.telemetry_out.publish_telemetry(snap)
        self._publish_telemetry_and_heartbeat(snap, now_ns)

        vm = self._compute_view_model(
            now_ns=now_ns,
            tick_result=res,
            snap=snap,
            last_cmd=self._last_cmd,
            last_cmd_ns=self._last_cmd_ns,
            seen_first_cmd=self._seen_first_cmd,
        )
        self._force_refresh_checkboxes = False

        return DensiRuntimeResult(
            frames=list(frames),
            tick_result=res,
            snap=snap,
            view_model=vm,
            last_cmd=self._last_cmd,
            last_cmd_ns=self._last_cmd_ns,
            seen_first_cmd=self._seen_first_cmd,
            cmd_rx_count=len(frames),
        )

    @staticmethod
    def normalize_result(res: DensiRuntimeResult) -> dict:
        snap = res.snap
        return {
            "cmd_rx_count": int(res.cmd_rx_count),
            "last_cmd_tick": getattr(res.last_cmd, "tick", None),
            "seen_first_cmd": bool(res.seen_first_cmd),
            "tick": int(getattr(snap, "tick", 0) or 0),
            "core_mode": str(getattr(snap, "core_mode", "") or ""),
            "estop": bool(getattr(snap, "estop", False)),
            "fault": bool(getattr(snap, "fault", False)),
            "estop_word": int(getattr(snap, "estop_status_word", 0) or 0),
        }

    def _edge_log_cmd_changes(self, cmd: CommandFrame | None) -> None:
        edge_log_cmd_changes(self, cmd)

    def _handle_gui_not_halt_cmd(self, cmd: CommandFrame | None) -> None:
        handle_gui_not_halt_cmd(self, cmd)

    def _publish_telemetry_and_heartbeat(self, snap: TelemetrySnapshot, now_ns: int) -> None:
        publish_telemetry_and_heartbeat(self, snap, now_ns)

    def _emit_status(self, now_ns: int) -> None:
        emit_status(self, now_ns)

    def _step_lifetick_debug(self, *, now_ns: int, last_cmd: CommandFrame | None) -> None:
        step_lifetick_debug(self, now_ns=now_ns, last_cmd=last_cmd)

    def _apply_ui_actions(self, inputs: DensiInputs) -> None:
        apply_ui_actions(self, inputs)

    def _compute_view_model(
        self,
        *,
        now_ns: int,
        tick_result,
        snap: TelemetrySnapshot,
        last_cmd: CommandFrame | None,
        last_cmd_ns: int | None,
        seen_first_cmd: bool,
    ) -> DensiViewModel:
        return compute_densi_view_model(
            engine=self.engine,
            axis_ids=list(self._axis_ids or []),
            force_refresh_checkboxes=bool(self._force_refresh_checkboxes),
            now_ns=int(now_ns),
            tick_result=tick_result,
            snap=snap,
            last_cmd=last_cmd,
            last_cmd_ns=last_cmd_ns,
            seen_first_cmd=bool(seen_first_cmd),
        )
