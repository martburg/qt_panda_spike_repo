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
import time

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import ChangeTracker, Heartbeat

from .runtime_kernel import compute_health, emit_runtime_status, with_health_fields
from .runtime_utils import (
    should_interval_log,
)

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from ..engines.densi.engine import DenSiEngine
from ..engines.densi.engine_types import DenSiTickResult
from ..engines.densi.inputs import DensiInputs
from ..engines.densi.viewmodel import DensiViewModel
from .densi_runtime_types import DensiRuntimeResult
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

        self._last_cmd: CommandFrame | None = None
        self._last_cmd_ns: int | None = None
        self._seen_first_cmd: bool = False
        self._last_mode: str = ""
        self._last_estop: bool = False
        self._last_fault: bool = False

        self._force_refresh_checkboxes: bool = False

        # Lifetick tracing / log throttling
        self._lt_last_telem_log_s: float = 0.0
        self._lt_last_cmd_log_s: float = 0.0
        self._lt_last_echo_by_axis: dict[str, int | None] = {}

    def collect_inputs(self, *, now_ns: int) -> DensiInputs:
        frames = self.command_in.drain_command_frames(limit=100)
        return DensiInputs(frames=list(frames), now_ns=int(now_ns))

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
        try:
            if self._ch.changed("cmd_core_mode", str(getattr(cmd, "core_mode", ""))):
                self._log.info("cmd_core_mode=%s", getattr(cmd, "core_mode", ""))
            if self._ch.changed("cmd_estop_reset", bool(getattr(cmd, "estop_reset", False))):
                self._log.info("cmd_estop_reset=%s", bool(getattr(cmd, "estop_reset", False)))
        except Exception:
            pass

    def _handle_gui_not_halt_cmd(self, cmd: CommandFrame | None) -> None:
        try:
            if self._ch.changed("cmd_gui_not_halt", bool(getattr(cmd, "gui_not_halt", False))):
                self._log.info("gui_not_halt=%s", bool(getattr(cmd, "gui_not_halt", False)))
        except Exception:
            pass

    def _publish_telemetry_and_heartbeat(self, snap: TelemetrySnapshot, now_ns: int) -> None:
        if self._ch.changed("core_mode", str(getattr(snap, "core_mode", ""))):
            self._log.info("core_mode=%s", getattr(snap, "core_mode", ""))
        if self._ch.changed("estop", bool(getattr(snap, "estop", False))):
            self._log.info(
                "estop=%s word=%s",
                bool(getattr(snap, "estop", False)),
                hex(int(getattr(snap, "estop_status_word", 0))),
            )
        if self._ch.changed("fault", bool(getattr(snap, "fault", False))):
            self._log.info("fault=%s", bool(getattr(snap, "fault", False)))

        # Heartbeat summary (1 Hz)
        self._hb.inc("telem_tx", 1)
        self._hb.set("tick", int(getattr(snap, "tick", 0)))
        self._hb.set("core_mode", str(getattr(snap, "core_mode", "")))
        self._hb.set("estop", bool(getattr(snap, "estop", False)))
        self._hb.set("fault", bool(getattr(snap, "fault", False)))
        if self._axis_ids:
            self._hb.set("axis", self._axis_ids[0])
        if self._last_cmd_ns is not None:
            self._hb.set("cmd_age_ms", int((int(now_ns) - int(self._last_cmd_ns)) / 1_000_000.0))
        self._hb.emit(self._log)
        self._last_mode = str(getattr(self._last_cmd, "core_mode", "") or "")
        self._last_estop = bool(getattr(self._last_cmd, "estop", False))
        self._last_fault = bool(getattr(self._last_cmd, "fault", False))
        self._emit_status(now_ns)

        if self._log.isEnabledFor(logging.DEBUG) and self._dbg_rl is not None:
            try:
                now_s = time.monotonic()
                if self._dbg_rl.due(now_s):
                    self._dbg_rl.mark(now_s)
                    try:
                        dt = None
                        if getattr(self.engine.state, "axes", None):
                            ax0 = next(iter(self.engine.state.axes.values()))
                            dt = ax0.meta.get("device_tick")
                    except Exception:
                        dt = None
                    self._log.debug("device_tick=%s", dt)
                    self._log.debug(
                        "tx telem: tick=%s estop=%s fault=%s estop_word=%s",
                        snap.tick,
                        snap.estop,
                        snap.fault,
                        hex(snap.estop_status_word),
                    )
            except Exception:
                pass

    def _emit_status(self, now_ns: int) -> None:
        # Status emitters may legitimately be falsey (e.g. a test stub that
        # defines __bool__). Only skip emission when we truly don't have one.
        if self._status is None:
            return

        h = compute_health(
            now_ns=int(now_ns),
            last_rx_ns=self._last_cmd_ns,
            stale_after_ms=self._stale_after_ms,
            seen_first_rx=bool(self._seen_first_cmd),
            estop=bool(self._last_estop),
            fault=bool(self._last_fault),
        )
        axis = self._axis_ids[0] if self._axis_ids else ""
        mode = self._last_mode or ""
        online = bool(getattr(h, "online", False))
        cmd = self._last_cmd
        cmd_mode = str(getattr(cmd, "core_mode", "") or "") if cmd is not None else ""
        cmd_intent = bool(getattr(cmd, "intent", False)) if cmd is not None else False
        cmd_enable = False
        cmd_vel = 0.0
        try:
            if cmd is not None and axis:
                sp = (getattr(cmd, "axes", {}) or {}).get(axis)
                if sp is not None:
                    cmd_enable = bool(getattr(sp, "enable", False))
                    cmd_vel = float(getattr(sp, "vel", 0.0) or 0.0)
        except Exception:
            cmd_enable = False
            cmd_vel = 0.0

        ready_for_sollvel = bool(getattr(self.engine, "drive_ready", False))
        estop_now = bool(getattr(self.engine.state, "estop", False))
        fault_now = bool(getattr(self.engine.state, "fault", False))

        vel_applied = 0.0
        pos_applied = 0.0
        lifetick_age_ticks = None
        try:
            ax = (getattr(self.engine.state, "axes", {}) or {}).get(axis)
            if ax is not None:
                vel_applied = float(getattr(ax, "vel", 0.0) or 0.0)
                pos_applied = float(getattr(ax, "pos", 0.0) or 0.0)
                lifetick_age_ticks = int(getattr(ax, "meta", {}).get("plc_lifetick_age_ticks", 0))
        except Exception:
            vel_applied = 0.0
            pos_applied = 0.0
            lifetick_age_ticks = None

        summary = (
            f"densi axis={axis or '-'} ctrl={int(cmd_enable)} "
            f"soll={cmd_vel:+.2f} ready={int(ready_for_sollvel)} "
            f"estop={int(estop_now)} applied={vel_applied:+.2f}"
        )

        fields = with_health_fields(
            {
                "component": "densi",
                "axis": axis,
                "core_mode": mode,
                "online": bool(online),
                "tick": int(getattr(self.engine.state, "tick", 0) or 0),
                "last_cmd_rx_age_ms": (
                    -1 if getattr(h, "age_ms", None) is None else float(getattr(h, "age_ms", 0.0))
                ),
                "cmd_core_mode": str(cmd_mode),
                "cmd_intent": bool(cmd_intent),
                "cmd_enable": bool(cmd_enable),
                "cmd_vel": float(cmd_vel),
                "ready_for_sollvel": bool(ready_for_sollvel),
                "vel_applied": float(vel_applied),
                "pos": float(pos_applied),
                "lifetick_age_ticks": lifetick_age_ticks,
            },
            health=h,
            estop=bool(estop_now),
            fault=bool(fault_now),
        )

        emit_runtime_status(
            self._status,
            level=str(getattr(h, "level", "") or ""),
            summary=summary,
            fields=fields,
            log=self._log,
            exc_tag="densi.status.emit",
            exc_msg="DenSi status emission failed",
        )

    def _step_lifetick_debug(self, *, now_ns: int, last_cmd: CommandFrame | None) -> None:
        now_s = time.monotonic()
        _echo_map = getattr(last_cmd, "lifetick_echo", {}) if last_cmd is not None else {}

        # LIFETICK (core -> DenSi): log echo changes immediately; otherwise throttle.
        if last_cmd is not None and self._axis_ids:
            for axis_id in self._axis_ids:
                echo_val = dict(_echo_map).get(axis_id, None)
                prev = self._lt_last_echo_by_axis.get(axis_id)
                if prev != echo_val:
                    self._lt_last_echo_by_axis[axis_id] = echo_val
                    self._log.debug(
                        "LIFETICK DenSi rx cmd echo: axis=%s value=%s cmd_tick=%s",
                        axis_id,
                        echo_val,
                        getattr(last_cmd, "tick", None),
                    )

            if should_interval_log(now_s, self._lt_last_cmd_log_s):
                axis0 = self._axis_ids[0]
                self._log.debug(
                    "DenSi rx cmd: tick=%s lifetick_echo[%s]=%s (map=%s)",
                    getattr(last_cmd, "tick", None),
                    axis0,
                    dict(_echo_map).get(axis0, None),
                    _echo_map,
                )
                self._lt_last_cmd_log_s = now_s
        else:
            if should_interval_log(now_s, self._lt_last_cmd_log_s):
                self._log.debug("DenSi rx cmd: <no cmd yet>")
                self._lt_last_cmd_log_s = now_s

        for _axis_id, _ax in self.engine.state.axes.items():
            tx = int(_ax.meta.get("lifetick_tx", 0) or 0) & 0xFFFF
            rx = int(_ax.meta.get("lifetick_rx", 0) or 0) & 0xFFFF
            diff = (tx - rx) & 0xFFFF

            if self._axis_ids and _axis_id == self._axis_ids[0]:
                self._hb.set("tx", int(tx))
                self._hb.set("rx", int(rx))
                self._hb.set("diff", int(diff))
                if self._last_cmd_ns is not None:
                    self._hb.set(
                        "cmd_age_ms", int((int(now_ns) - int(self._last_cmd_ns)) / 1_000_000.0)
                    )

            if (
                self._axis_ids
                and _axis_id == self._axis_ids[0]
                and should_interval_log(now_s, self._lt_last_telem_log_s)
            ):
                self._lt_last_telem_log_s = now_s
                self._log.debug(
                    "LIFETICK DenSi device: axis=%s tx=%d rx=%d diff=%d",
                    _axis_id,
                    tx,
                    rx,
                    diff,
                )

    def _apply_ui_actions(self, inputs: DensiInputs) -> None:
        ui = inputs.ui
        if ui is None:
            return

        if ui.es_start_clicked:
            try:
                self.engine.press_es_start()
                self._log.info("ESStart pressed")
                self._force_refresh_checkboxes = True
            except Exception:
                pass

        if ui.estop_all_set_clicked:
            try:
                self.engine.set_all_estop_bits()
                self._log.info(
                    "inject: SET ALL bits (word=0x%08X)", int(self.engine.inj_estop_word)
                )
                self._force_refresh_checkboxes = True
            except Exception:
                pass

        if ui.estop_all_clear_clicked:
            try:
                self.engine.apply_go_state()
                self._log.info("inject: GO state (word=0x%08X)", int(self.engine.inj_estop_word))
                self._force_refresh_checkboxes = True
            except Exception:
                pass

        for t in list(ui.estop_bit_toggles or []):
            try:
                self.engine.inject_estop_bit(str(t.key), bool(t.checked))
                self._log.info(
                    "inject estop %s=%s (word=0x%08X)",
                    t.key,
                    t.checked,
                    int(self.engine.inj_estop_word),
                )
                self._force_refresh_checkboxes = True
            except Exception:
                pass

        if ui.diag_resync_clicked:
            try:
                self.engine.clear_cut_markers(reset_prev=True)
            except Exception:
                pass

    def _compute_view_model(
        self,
        *,
        now_ns: int,
        tick_result: DenSiTickResult,
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
