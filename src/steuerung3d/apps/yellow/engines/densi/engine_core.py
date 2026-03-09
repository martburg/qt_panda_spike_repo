"""Qt-free DenSi engine.

This module intentionally keeps the *public* DenSiEngine surface stable, while
splitting implementation details into focused mixin modules.

Semantics note:
  - This split is a structural refactor only. Tick behavior is still implemented
    by :mod:`step_impl` and must remain unchanged.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState

from .engine_core_clock import DenSiClockMixin
from .engine_core_cut import DenSiCutMarkersMixin
from .engine_core_inj_estop import DenSiInjectedEStopMixin
from .engine_core_meta import DenSiMetaMixin
from .engine_core_pipeline import DenSiPipelineMixin
from .types import EStopState, L0Sub, L0Top


@dataclass
class DenSiEngine(
    DenSiClockMixin,
    DenSiInjectedEStopMixin,
    DenSiCutMarkersMixin,
    DenSiMetaMixin,
    DenSiPipelineMixin,
):
    """Qt-free DenSi engine (single-axis for now)."""

    axis_ids: list[str]
    tb: Timebase
    state: MachineState
    device: SimDevice

    # clock (injectable for deterministic tests)
    now_s: Callable[[], float] = time.monotonic

    # connection
    disconnect_after_s: float = 2.0
    seen_first_cmd: bool = False
    last_cmd: CommandFrame | None = None
    last_cmd_ns: int | None = None
    l0_top: L0Top = L0Top.START
    l0_sub: L0Sub = L0Sub.IDLE

    # injected estop
    inj_bits: dict[str, bool] | None = None
    inj_estop_word: int = 0

    # ladder state
    taster_prev: bool = False
    taster_rise_t_s: float | None = None

    # display grace tracking (legacy: uses time.monotonic seconds)
    taster_prev_disp: bool = False
    taster_pressed_s: float | None = None
    drive_ready: bool = False
    estate: EStopState = EStopState.ESTOP
    brake_switch_s: float = 1.5
    brake_handoff_grace_s: float = 2.0
    es_start_armed: bool = False
    estop_latched: bool = False
    safety_ok: bool = True

    # per-brake override (simulate one brake fault)
    brake_override_b1: bool = False
    brake_override_b2: bool = False

    # cut markers
    cut_valid: bool = False
    cut_pos_m: float = 0.0
    cut_vel_mps: float = 0.0
    cut_time_s: float = 0.0
    systemtime_tok: str = ""
    prev_estop_state: bool = False

    # After HiP ReSync, CutPos/CutVel follow actual pos/vel until an E-Stop cause hits.
    cut_follow_live: bool = False

    # Cut markers should latch on "cause became active" (trip bits / OK-chain fault),
    # not on state.estop edge alone (state.estop can be true during startup / not-armed).
    prev_cause_active: bool = False
    cause_active: bool = False
    cause_edge: bool = False

    # stop metrics (coastdown distance after E-Stop edge)
    stop_valid: bool = False
    stop_pos_m: float = 0.0
    stop_time_s: float = 0.0
    posdiff_stop_m: float = 0.0

    # param ops hooks (controller supplies: keep semantics)
    normalize_pos_chain: Callable[[dict[str, float]], dict[str, float]] | None = None
    normalize_guider_range: Callable[[dict[str, float]], dict[str, float]] | None = None
    enforce_pos_chain: Callable[[dict[str, float]], dict[str, float]] | None = None
    enforce_guider_minmax: Callable[[dict[str, float]], dict[str, float]] | None = None

    # PLC-faithful vel_cmd behavior tuning
    lifetick_stale_after_ticks_active: int = 50
    lifetick_stale_after_ticks_idle: int = 500

    @classmethod
    def build_default(
        cls,
        *,
        axis_ids: list[str],
        dt_s: float,
        normalize_pos_chain,
        normalize_guider_range,
        enforce_pos_chain,
        enforce_guider_minmax,
        lifetick_stale_after_ticks_active: int | None = None,
        lifetick_stale_after_ticks_idle: int | None = None,
        now_s: Callable[[], float] | None = None,
    ) -> "DenSiEngine":
        """Construct an engine with default SimDevice/plant and seeded params."""

        # Imports kept local to avoid heavy module graphs at import time.
        from .types import EStopState, L0Sub, L0Top

        tb = Timebase(dt_s=float(dt_s))
        state = MachineState()
        for a in axis_ids:
            state.ensure_axis(a)
        device = SimDevice(plant=SimAxisPlant())
        eng = cls(
            axis_ids=list(axis_ids),
            tb=tb,
            state=state,
            device=device,
            now_s=(now_s or time.monotonic),
            normalize_pos_chain=normalize_pos_chain,
            normalize_guider_range=normalize_guider_range,
            enforce_pos_chain=enforce_pos_chain,
            enforce_guider_minmax=enforce_guider_minmax,
            lifetick_stale_after_ticks_active=int(lifetick_stale_after_ticks_active)
            if lifetick_stale_after_ticks_active is not None
            else 50,
            lifetick_stale_after_ticks_idle=int(lifetick_stale_after_ticks_idle)
            if lifetick_stale_after_ticks_idle is not None
            else 500,
        )
        eng.l0_top = L0Top.START
        eng.l0_sub = L0Sub.IDLE
        eng.estate = EStopState.ESTOP
        eng.reset_to_fault_state()
        eng._seed_default_params()
        eng.prev_estop_state = bool(getattr(eng.state, "estop", False))
        return eng

    def _seed_default_params(self) -> None:
        from .param_defaults import apply_densi_param_defaults

        try:
            self.state.params["SystemTime"] = self._now_token()
        except Exception:
            pass

        # Defaults expected by UI + protocol contract tests
        apply_densi_param_defaults(self.state.params)

        # Reflect initial L0 state
        try:
            self.state.params["DenSiL0Top"] = getattr(self.l0_top, "name", str(self.l0_top))
            self.state.params["DenSiL0Sub"] = getattr(self.l0_sub, "name", str(self.l0_sub))
        except Exception:
            pass
