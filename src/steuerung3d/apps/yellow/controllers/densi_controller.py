# src/steuerung3d/apps/yellow/controllers/densi_controller.py
"""DenSi (device-side simulator) controller.

Orchestration only:
- read command frames
- read UI inputs
- call DensiRuntime
- publish telemetry
- apply DensiViewModel
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace

from PySide6.QtWidgets import QWidget

# Optional structured status heartbeat (used by stack supervisor birds-eye)
try:
    from steuerung3d.core.status import StatusEmitter  # type: ignore
except ImportError:  # pragma: no cover
    StatusEmitter = None  # type: ignore

from ..binders.densi_qt_binder import DenSiQtBinder
from ..domain import estop_facts
from ..engines.densi.engine import DenSiEngine
from ..engines.densi.inputs import DensiUiInputs
from ..ports import CommandIn, TelemetryOut
from ..qtutil.bindings import YellowBindings
from ..qtutil.perf_watchdog import PerfWatchdog
from ..runtimes.densi_runtime import DensiRuntime
from .controller_utils import bump_soft_error, init_observability, start_poll_timer

log = logging.getLogger("den_si")


@dataclass
class DenSiController:
    win: QWidget
    command_in: CommandIn
    telemetry_out: TelemetryOut
    axis_ids: list[str]

    wire_proto: str = "json"  # json|plc
    dt_s: float = 0.01
    stale_after_ms: int = 500
    action_in: object | None = None

    def __post_init__(self) -> None:
        # Soft-error counters for swallowed exceptions (binder/UI)
        self._soft_errors: dict[str, int] = {}
        """Bind widgets and initialize the DenSi device-side simulator."""
        self._init_wire_proto_and_ui()
        self._init_observability()
        self._init_state_and_sim()

        self._runtime = DensiRuntime(
            engine=self.engine,
            command_in=self.command_in,
            telemetry_out=self.telemetry_out,
            hb=self._hb,
            ch=self._ch,
            status=self._status,
            dbg_rl=self._dbg_rl,
            axis_ids=list(self.axis_ids),
            stale_after_ms=int(self.stale_after_ms),
            log=log,
            action_in=self.action_in,
        )
        self._wd = PerfWatchdog(log, name="den_si")

        # --- Qt binder (UI-only)
        self._binder = DenSiQtBinder(self.win, log, axis_ids=list(self.axis_ids))
        self._binder.init_fixed_axis()
        self._binder.lock_param_ui_device_side()
        self._binder.reset_ui_startup()

        # Seed params from UI if available (merge into defaults)
        try:
            seed = self._binder.seed_params_from_ui()
            if seed:
                self.state.params.update(dict(seed))
        except Exception:
            bump_soft_error(self._soft_errors, "binder.seed_params_from_ui")

        try:
            self._binder.init_estop_checkboxes(estop_word=int(self.engine.inj_estop_word))
        except Exception:
            bump_soft_error(self._soft_errors, "binder.init_estop_checkboxes")

    # ------------------------------------------------------------------
    # Initialization helpers
    # ------------------------------------------------------------------

    def _init_wire_proto_and_ui(self) -> None:
        self.wire_proto = (getattr(self, "wire_proto", "json") or "json").strip().lower()
        self.ui = YellowBindings.from_window(self.win)

    def _init_observability(self) -> None:
        self._hb, self._ch, self._status, self._dbg_rl = init_observability(
            "den_si",
            status_emitter_cls=StatusEmitter,
            status_default_service="den_si",
            dbg_rl_interval_s=1.0,
        )

    def _init_state_and_sim(self) -> None:
        self._disconnect_after_s = 2.0

        self.engine = DenSiEngine.build_default(
            axis_ids=list(self.axis_ids),
            dt_s=float(self.dt_s),
            normalize_pos_chain=self._normalize_pos_chain,
            normalize_guider_range=self._normalize_guider_range,
            enforce_pos_chain=self._enforce_pos_chain,
            enforce_guider_minmax=self._enforce_guider_minmax,
        )
        self.engine.disconnect_after_s = float(self._disconnect_after_s)

        # Backwards-compat aliases (tests and runtime use these attributes)
        self.state = self.engine.state
        self.device = self.engine.device
        self.tb = self.engine.tb

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._timer = start_poll_timer(
            self.win, period_ms=int(self.dt_s * 1000), callback=self.step_once
        )

    def step_once(self) -> None:
        with self._wd.tick():
            now_ns = int(time.monotonic_ns())
            inputs = self._runtime.collect_inputs(now_ns=now_ns)
            try:
                ui_inputs = self._binder.read_inputs()
                merged_ui = self._merge_ui_inputs(inputs.ui, ui_inputs.ui)
                inputs = replace(inputs, ui=merged_ui)
            except Exception:
                bump_soft_error(self._soft_errors, "binder.read_inputs")
            runtime_res = self._runtime.tick(inputs=inputs)

            try:
                self._binder.apply(runtime_res.view_model)
            except Exception:
                bump_soft_error(self._soft_errors, "binder.apply")

            self._emit_birdseye(runtime_res)

    def _emit_birdseye(self, runtime_res) -> None:
        status = getattr(self, "_status", None)
        if status is None:
            return

        soft = dict(getattr(self, "_soft_errors", {}) or {})
        soft_total = int(sum(int(v) for v in soft.values()))
        level = "WARN" if soft_total else "OK"

        dev_id = ""
        try:
            dev_id = str(getattr(getattr(self, "device", None), "device_id", "") or "")
        except Exception:
            dev_id = ""

        axes = []
        try:
            axes = list(getattr(getattr(runtime_res, "snap", None), "axes", {}) or {})
        except Exception:
            axes = []

        summary = f"den_si dev={dev_id or '-'} axes={len(axes)} soft_err={soft_total}"
        fields = {
            "component": "den_si",
            "device_id": dev_id,
            "axes_count": int(len(axes)),
            "soft_errors_total": soft_total,
            "soft_errors_by_key": {str(k): int(v) for k, v in soft.items()},
        }
        try:
            status.emit_every(level=level, summary=summary, fields=fields)
        except Exception:
            return

    @staticmethod
    def _merge_ui_inputs(
        remote_ui: DensiUiInputs | None, local_ui: DensiUiInputs | None
    ) -> DensiUiInputs:
        remote = remote_ui or DensiUiInputs()
        local = local_ui or DensiUiInputs()
        return DensiUiInputs(
            es_start_clicked=bool(remote.es_start_clicked or local.es_start_clicked),
            estop_reset_clicked=bool(remote.estop_reset_clicked or local.estop_reset_clicked),
            estop_all_set_clicked=bool(remote.estop_all_set_clicked or local.estop_all_set_clicked),
            estop_all_clear_clicked=bool(
                remote.estop_all_clear_clicked or local.estop_all_clear_clicked
            ),
            diag_resync_clicked=bool(remote.diag_resync_clicked or local.diag_resync_clicked),
            estop_bit_toggles=[
                *list(remote.estop_bit_toggles or []),
                *list(local.estop_bit_toggles or []),
            ],
        )

    # ------------------------------------------------------------------
    # Static helpers (tests depend on these)
    # ------------------------------------------------------------------

    @staticmethod
    def _reset_able_from_estop_word(word: int) -> bool:
        """Return the reset_able bit, which is packed into EStopStatusWord."""
        return bool(estop_facts.reset_able_from_word(int(word)))

    @staticmethod
    def _ready_from_estop_word(word: int) -> bool:
        """Return the READY indicator from EStopStatusWord."""
        return bool(estop_facts.ready_from_word(int(word)))

    # ------------------------------------------------------------------
    # Param normalization helpers (engine hooks)
    # ------------------------------------------------------------------

    def _normalize_pos_chain(self, values: dict[str, float]) -> dict[str, float]:
        return self._coerce_pos_chain(values)

    def _normalize_guider_range(self, values: dict[str, float]) -> dict[str, float]:
        return self._coerce_guider_range(values)

    def _enforce_pos_chain(self, vals: dict[str, float]) -> dict[str, float]:
        return self._coerce_pos_chain(vals)

    def _enforce_guider_minmax(self, vals: dict[str, float]) -> dict[str, float]:
        return self._coerce_guider_range(vals)

    @staticmethod
    def _coerce_pos_chain(values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        keys = ("HardMax", "UserMax", "UserMin", "HardMin")
        if not all(k in v for k in keys):
            return v

        hard_max = float(v["HardMax"])
        user_max = float(v["UserMax"])
        user_min = float(v["UserMin"])
        hard_min = float(v["HardMin"])

        if hard_max < hard_min:
            hard_max, hard_min = hard_min, hard_max

        user_max = max(hard_min, min(hard_max, user_max))
        user_min = max(hard_min, min(user_max, user_min))

        v["HardMax"] = hard_max
        v["HardMin"] = hard_min
        v["UserMax"] = user_max
        v["UserMin"] = user_min
        return v

    @staticmethod
    def _coerce_guider_range(values: dict[str, float]) -> dict[str, float]:
        v = dict(values)
        if "PosMin" not in v or "PosMax" not in v:
            return v
        pos_min = float(v["PosMin"])
        pos_max = float(v["PosMax"])
        if pos_min > pos_max:
            pos_min, pos_max = pos_max, pos_min
        if pos_min == pos_max:
            pos_max = pos_min + (1e-6 * (abs(pos_min) + 1.0))
        v["PosMin"] = pos_min
        v["PosMax"] = pos_max
        return v
