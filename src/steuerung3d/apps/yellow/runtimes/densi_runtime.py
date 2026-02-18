"""Qt-free runtime seam for DenSi.

Responsibilities:
- Drain CommandFrame input.
- Call DenSiEngine.
- Publish telemetry snapshots.
- Emit non-UI logs/heartbeat/status.

UI rendering stays in the controller until Patch 6.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import List

from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.util.heartbeat import Heartbeat, ChangeTracker
from steuerung3d.util.ratelimit import rl_log_exc

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except Exception:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from ..engines.densi_engine import DenSiEngine, DenSiTickResult
from ..engines.densi_inputs import DensiInputs
from ..engines.densi_viewmodel import DensiViewModel
from ..panels.densi_banner_vm import compute_densi_banner_vm
from ..panels.densi_cut_markers_vm import compute_densi_cut_markers_vm
from ..panels.densi_estop_dots_vm import compute_densi_estop_dots_vm
from ..panels.densi_header_online_vm import compute_densi_header_online_vm
from ..panels.densi_lifetick_vm import compute_densi_lifetick_vm
from ..panels.densi_readouts_vm import compute_densi_readouts_vm
from ..panels.densi_taster_edge_state import TasterEdgeState, update_taster_edge_state, within_brake_grace


@dataclass(frozen=True)
class DensiRuntimeResult:
    frames: List[CommandFrame]
    tick_result: DenSiTickResult
    snap: TelemetrySnapshot
    view_model: DensiViewModel
    last_cmd: CommandFrame | None
    last_cmd_ns: int | None
    seen_first_cmd: bool
    cmd_rx_count: int


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
                "rx cmd: tick=%s estop_reset=%s fault=%s mode=%s",
                getattr(self._last_cmd, "tick", None),
                getattr(self._last_cmd, "estop_reset", None),
                getattr(self._last_cmd, "fault", None),
                getattr(self._last_cmd, "mode", None),
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
            "mode": str(getattr(snap, "mode", "") or ""),
            "estop": bool(getattr(snap, "estop", False)),
            "fault": bool(getattr(snap, "fault", False)),
            "estop_word": int(getattr(snap, "estop_status_word", 0) or 0),
        }

    def _edge_log_cmd_changes(self, cmd: CommandFrame | None) -> None:
        try:
            if self._ch.changed("cmd_mode", str(getattr(cmd, "mode", ""))):
                self._log.info("cmd_mode=%s", getattr(cmd, "mode", ""))
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
        if self._ch.changed("mode", str(getattr(snap, "mode", ""))):
            self._log.info("mode=%s", getattr(snap, "mode", ""))
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
        self._hb.set("mode", str(getattr(snap, "mode", "")))
        self._hb.set("estop", bool(getattr(snap, "estop", False)))
        self._hb.set("fault", bool(getattr(snap, "fault", False)))
        if self._axis_ids:
            self._hb.set("axis", self._axis_ids[0])
        if self._last_cmd_ns is not None:
            self._hb.set("cmd_age_ms", int((int(now_ns) - int(self._last_cmd_ns)) / 1_000_000.0))
        self._hb.emit(self._log)
        self._last_mode = str(getattr(self._last_cmd, "mode", "") or "")
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
        if not self._status:
            return

        age_ms: float | None
        if self._last_cmd_ns is None:
            age_ms = None
        else:
            age_ms = (int(now_ns) - int(self._last_cmd_ns)) / 1_000_000.0

        stale = (age_ms is None) or (age_ms >= float(self._stale_after_ms))
        level = "ERR" if (self._last_estop or self._last_fault) else ("WARN" if stale else "OK")
        axis = self._axis_ids[0] if self._axis_ids else ""
        mode = self._last_mode or ""
        online = bool(self._seen_first_cmd) and (not stale)
        age_disp = "NA" if age_ms is None else f"{age_ms:.0f}"
        summary = f"axis={axis or '-'} mode={mode or '-'} online={int(online)} age_ms={age_disp}"

        try:
            self._status.emit_every(
                level=level,
                summary=summary,
                fields={
                    "axis": axis,
                    "mode": mode,
                    "online": bool(online),
                    "age_ms": (-1 if age_ms is None else float(age_ms)),
                    "stale": bool(stale),
                    "estop": bool(self._last_estop),
                    "fault": bool(self._last_fault),
                    "tick": int(getattr(self.engine.state, "tick", 0) or 0),
                },
            )
        except Exception:
            rl_log_exc("densi.status.emit", "DenSi status emission failed", logger=self._log)

    @staticmethod
    def _lt_should_log(now_s: float, last_log_s: float, interval_s: float = 1.0) -> bool:
        try:
            return (float(now_s) - float(last_log_s)) >= float(interval_s)
        except Exception:
            return True

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

            if self._lt_should_log(now_s, self._lt_last_cmd_log_s):
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
            if self._lt_should_log(now_s, self._lt_last_cmd_log_s):
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
                    self._hb.set("cmd_age_ms", int((int(now_ns) - int(self._last_cmd_ns)) / 1_000_000.0))

            if self._axis_ids and _axis_id == self._axis_ids[0] and self._lt_should_log(now_s, self._lt_last_telem_log_s):
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
                self._log.info("inject: SET ALL bits (word=0x%08X)", int(self.engine.inj_estop_word))
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
                self._log.info("inject estop %s=%s (word=0x%08X)", t.key, t.checked, int(self.engine.inj_estop_word))
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
        axis_id = self._axis_ids[0] if self._axis_ids else ""

        header_online = compute_densi_header_online_vm(
            seen_first_cmd=bool(seen_first_cmd),
            now_ns=int(now_ns),
            last_cmd_ns=last_cmd_ns,
            good_max_s=1.0,
        )

        lifetick_vm = compute_densi_lifetick_vm(state=self.engine.state, axis_id=axis_id)
        readouts_vm = compute_densi_readouts_vm(state=self.engine.state, axis_id=axis_id, last_cmd=last_cmd)

        # Cut markers: compute VM + apply effects (state.params + engine token)
        try:
            now_token = self.engine._now_token()  # pylint: disable=protected-access
        except Exception:
            now_token = ""
        cut_vm = compute_densi_cut_markers_vm(
            cut_valid=bool(getattr(self.engine, "cut_valid", False)),
            estop_now=bool(getattr(self.engine.state, "estop", False)),
            now_token=str(now_token),
            systemtime_tok=str(getattr(self.engine, "systemtime_tok", "") or "") or None,
            systemtime_param=str(self.engine.state.params.get("SystemTime", "") or "") or None,
            cut_pos_m=float(getattr(self.engine, "cut_pos_m", 0.0) or 0.0) if bool(getattr(self.engine, "cut_valid", False)) else None,
            cut_vel_mps=float(getattr(self.engine, "cut_vel_mps", 0.0) or 0.0) if bool(getattr(self.engine, "cut_valid", False)) else None,
            pos_m=float(readouts_vm.pos_m) if readouts_vm is not None else None,
        )
        if cut_vm.effects.systemtime_tok is not None:
            self.engine.systemtime_tok = cut_vm.effects.systemtime_tok
            self.engine.state.params["SystemTime"] = cut_vm.effects.systemtime_tok
        if cut_vm.effects.posdiff_for is not None:
            try:
                self.engine.state.params["PosDiffFor"] = float(cut_vm.effects.posdiff_for)
            except Exception:
                pass

        # Estop dots + banner (display grace tracking)
        bits = dict(getattr(tick_result, "estop_bits", {}) or {})
        taster = bool(bits.get("taster", False))
        ready = bool(bits.get("ready", False))

        prev = bool(getattr(self.engine, "taster_prev_disp", taster))
        pressed_s = getattr(self.engine, "taster_pressed_s", None)
        st0 = TasterEdgeState(prev=prev, pressed_s=pressed_s if pressed_s is None else float(pressed_s))
        st1 = update_taster_edge_state(state=st0, taster=taster, now_s=float(time.monotonic()))
        self.engine.taster_prev_disp = bool(st1.prev)
        self.engine.taster_pressed_s = st1.pressed_s

        within_grace = within_brake_grace(
            state=st1,
            now_s=float(time.monotonic()),
            grace_s=float(getattr(self.engine, "brake_handoff_grace_s", 2.0)),
        )

        banner_vm = compute_densi_banner_vm(estop_word=int(tick_result.estop_word), within_brake_grace=within_grace)
        estop_dots_vm = compute_densi_estop_dots_vm(
            bits=bits,
            taster=taster,
            ready=ready,
            within_brake_grace=within_grace,
        )

        return DensiViewModel(
            header_online=header_online,
            banner=banner_vm,
            estop_dots=estop_dots_vm,
            readouts=readouts_vm,
            cut_markers=cut_vm,
            lifetick=lifetick_vm,
            estop_word=int(tick_result.estop_word),
            refresh_checkboxes=bool(getattr(tick_result, "reset_able_changed", False)) or bool(self._force_refresh_checkboxes),
            applied_param_values=dict(getattr(tick_result, "applied_param_values", {}) or {}),
        )
