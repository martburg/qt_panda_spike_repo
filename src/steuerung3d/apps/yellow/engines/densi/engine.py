"""Qt-free DenSi engine.

Goal: keep DenSi semantics (protocol + ladder + clamping) out of the Qt controller.
The controller remains responsible for:
- UI rendering
- transport (CommandFrame RX, Telemetry publish)
- logging/heartbeat

The engine owns:
- injected EStop bits/word + ladder state
- L0 connection state
- plant stepping + clamp policy
- cut marker latching
- legacy lifetick + status words meta fields
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ...domain.estop_facts import (
    decode_estop_word,
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)
from .cut_markers import (
    clear_cut_markers as _clear_cut_markers,
    maybe_latch_cut_markers as _maybe_latch_cut_markers,
)
from .engine_types import DenSiTickResult
from .estop_fsm import (
    apply_estop_state_machine,
    compute_estop_edge_and_update_state as _compute_estop_edge_and_update_state,
    derive_estop_inputs as _derive_estop_inputs,
    sync_reset_able_bit as _sync_reset_able_bit,
)
from .motion_clamp import apply_estop_clamp_to_state, compute_moving_guard
from .param_defaults import apply_densi_param_defaults
from .param_ops import apply_densi_param_ops
from .plc_anton_vel_cmd import step_plc_anton_vel_cmd
from .resync import handle_resync_cmd as _handle_resync_cmd
from .setpoint_semantics import normalize_cmd_for_plant
from .step_impl import step as _step
from .types import EStopState, L0Sub, L0Top


@dataclass
class DenSiEngine:
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
        eng.reset_to_fault_state()
        eng._seed_default_params()
        eng.prev_estop_state = bool(getattr(eng.state, "estop", False))
        return eng

    def _seed_default_params(self) -> None:
        try:
            self.state.params["SystemTime"] = self._now_token()
        except Exception:
            pass

        # Defaults expected by UI + protocol contract tests
        apply_densi_param_defaults(self.state.params)

        # Reflect initial L0 state
        try:
            self.state.params["DenSiL0Top"] = self.l0_top.name
            self.state.params["DenSiL0Sub"] = self.l0_sub.name
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _now_token() -> str:
        """DenSi wallclock token: 'DD-MM-YYYY HH:MM:SS 123 ms'."""
        now = datetime.now()
        ms = int(now.microsecond // 1000)
        return now.strftime("%d-%m-%Y %H:%M:%S ") + f"{ms:03d} ms"

    def within_brake_grace_disp(self) -> bool:
        """UI-display grace helper (monotonic time).

        The UI banner/dots show a short grace interval after the *taster* rises,
        during which the brake feedback may still be in the previous state.

        This is intentionally display-only (non-deterministic) and uses
        `self.now_s()` (injectable clock), matching legacy monotonic seconds by default.
        """
        try:
            if self.taster_pressed_s is None:
                return False
            return (float(self.now_s()) - float(self.taster_pressed_s)) < float(
                self.brake_handoff_grace_s
            )
        except Exception:
            return False

    def _update_display_grace_tracking(self) -> None:
        """Update display-only brake grace tracking.

        Uses an injectable monotonic-seconds clock (`now_s`) so tests can
        be deterministic. This is UI nicety only; it must not affect the
        authoritative ladder timing.
        """
        try:
            bits = self._ensure_inj_bits()
            taster = bool(bits.get("taster", False))
            if taster and not bool(self.taster_prev_disp):
                self.taster_pressed_s = float(self.now_s())
            if not taster:
                self.taster_pressed_s = None
            self.taster_prev_disp = bool(taster)
        except Exception:
            return

    def ensure_last_cmd(self) -> CommandFrame:
        if self.last_cmd is None:
            self.last_cmd = CommandFrame(
                tick=int(self.state.tick),
                t_s=float(self.state.t_s),
                estop=False,
                fault=False,
                core_mode=getattr(self.state, "core_mode", ""),
                axes={},
                estop_reset=False,
            )
        return self.last_cmd

    # ---------------------------------------------------------------------
    # injected estop / ladder
    # ---------------------------------------------------------------------

    def _ensure_inj_bits(self) -> dict[str, bool]:
        if self.inj_bits is None:
            self.inj_bits = {k: False for k in ESTOP_SPECS.keys()}
        return self.inj_bits

    def reset_to_fault_state(self) -> None:
        """Start in a FAULT state: break OK chain but allow immediate EStopReset.

        Legacy-compatible policy:
          - Trip-causes NOT asserted at startup (no explicit cause latched): cause keys => False
          - Status/OK chain broken (red): OK chain keys => False
          - ResetAble is derived from trip-cause bits and becomes True when causes are clear.
        """
        bits = self._ensure_inj_bits()
        cause_keys = estop_cause_keys()
        ok_keys = estop_ok_keys()

        # default everything False
        for k in list(bits.keys()):
            bits[k] = False

        # Trip causes clear at startup (no explicit cause latched)
        for k in cause_keys:
            bits[k] = False

        # Break the OK chain (red)
        for k in ok_keys:
            bits[k] = False

        # ResetAble derived; seed as False then sync
        bits["reset_able"] = False

        self.inj_estop_word = int(encode_estop_word(bits))
        self.sync_reset_able_bit()

        # Startup / SafetyPLC handoff emulation
        self.taster_prev = False
        self.taster_rise_t_s = None
        self.drive_ready = False
        self.estate = EStopState.ESTOP
        self.es_start_armed = False

        # Per-brake override (simulate one brake fault)
        self.brake_override_b1 = False
        self.brake_override_b2 = False

        # Cut markers baseline (visible in IDLE/ESTOP; starts at 0 until HiP ReSync arms live tracking)
        self.cut_valid = True
        self.cut_pos_m = 0.0
        self.cut_vel_mps = 0.0
        self.cut_time_s = 0.0
        self.systemtime_tok = ""
        self.prev_estop_state = bool(getattr(self.state, "estop", False))
        self.prev_cause_active = False
        self.cause_edge = False

        # Stop metrics (latched when coastdown reaches v~=0)
        self.stop_valid = False
        self.stop_pos_m = 0.0
        self.stop_time_s = 0.0
        self.posdiff_stop_m = 0.0

        # Derived/latches
        self.estop_latched = False
        self.safety_ok = True

        # Display grace mirrors (used by VM for banner/brake dots)
        self.taster_prev_disp = False
        self.taster_pressed_s = None

    def apply_go_state(self) -> None:
        """Set injected bits to a stable 'GO' state (no flash)."""
        bits = self._ensure_inj_bits()
        cause_keys = estop_cause_keys()
        ok_keys = estop_ok_keys()
        for k in list(bits.keys()):
            bits[k] = False

        for k in ok_keys:
            bits[k] = True
        for k in cause_keys:
            bits[k] = False

        self.inj_estop_word = int(encode_estop_word(bits))
        self.estop_latched = False

    def apply_post_reset_state(self) -> None:
        """Clear initial FAULT latch, but remain not-ready until Taster + delay."""
        bits = self._ensure_inj_bits()
        cause_keys = estop_cause_keys()
        ok_keys = estop_ok_keys()
        for k in list(bits.keys()):
            bits[k] = False

        for k in ok_keys:
            bits[k] = True
        for k in cause_keys:
            bits[k] = False

        # Post-reset we are *not* yet ready: operator must press the Taster and wait a bit.
        for k in ("ready", "taster", "schuetz", "brk1_ok", "brk2_ok"):
            if k in bits:
                bits[k] = False

        # consume ResetAble (mimics PLC behavior)
        if "reset_able" in bits:
            bits["reset_able"] = False

        self.inj_estop_word = int(encode_estop_word(bits))
        self.estop_latched = False

        # Reset ladder timers/derived readiness
        self.taster_prev = False
        self.taster_rise_t_s = None
        self.drive_ready = False
        self.es_start_armed = False
        self.brake_override_b1 = False
        self.brake_override_b2 = False

    def sync_reset_able_bit(self) -> bool:
        """Derive ResetAble from trip-cause bits.

        Returns True if packed word changed.
        """
        bits = self._ensure_inj_bits()
        changed, new_word = _sync_reset_able_bit(
            inj_bits=bits,
            inj_estop_word=int(self.inj_estop_word),
            within_brake_grace=self.within_brake_grace_disp,
        )
        self.inj_estop_word = int(new_word)
        return bool(changed)

    def inject_estop_bit(self, key: str, checked: bool) -> None:
        """UI-driven diagnostic override for E-Stop bits."""
        bits = self._ensure_inj_bits()
        if key not in bits:
            return

        # User-driven diagnostic override for brake feedback bits.
        if key in ("brk1_ok", "brk2_ok"):
            desired = bool(getattr(self, "drive_ready", False))
            if bool(checked) != bool(desired):
                if key == "brk1_ok":
                    self.brake_override_b1 = True
                else:
                    self.brake_override_b2 = True

        bits[key] = bool(checked)
        self.inj_estop_word = int(encode_estop_word(bits))
        self.sync_reset_able_bit()

    def set_all_estop_bits(self) -> None:
        bits = self._ensure_inj_bits()
        for k in list(bits.keys()):
            bits[k] = True
        self.inj_estop_word = int(encode_estop_word(bits))
        self.sync_reset_able_bit()

    def clear_all_estop_bits(self) -> None:
        bits = self._ensure_inj_bits()
        for k in list(bits.keys()):
            bits[k] = False
        self.inj_estop_word = int(encode_estop_word(bits))
        self.sync_reset_able_bit()

    def press_es_start(self) -> None:
        """Simulate SafetyPLC Start (ESStart) -> sets schuetz=1."""
        if bool(self.estop_latched):
            return

        bits = self._ensure_inj_bits()
        self.es_start_armed = True
        bits["schuetz"] = True
        if bool(bits.get("taster", False)):
            self.taster_rise_t_s = float(self.state.t_s)
        self.inj_estop_word = int(encode_estop_word(bits))

    def apply_estop_state_machine(self) -> None:
        """Authoritative ESTOP/IDLE/ARMED/READY ladder + brake timing."""
        bits = self._ensure_inj_bits()

        # For STOPPING -> ESTOP transition we need the current (actual) speed.
        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        speed_abs_mps = abs(float(getattr(ax0, "vel", 0.0) or 0.0)) if ax0 is not None else 0.0
        stop_eps_mps = 1e-3
        (
            self.inj_estop_word,
            self.taster_prev,
            self.taster_rise_t_s,
            self.drive_ready,
            self.estate,
            self.estop_latched,
        ) = apply_estop_state_machine(
            inj_bits=bits,
            state_t_s=float(self.state.t_s),
            brake_switch_s=float(self.brake_switch_s),
            brake_handoff_grace_s=float(self.brake_handoff_grace_s),
            estop_latched=bool(self.estop_latched),
            safety_ok=bool(self.safety_ok),
            taster_prev=bool(self.taster_prev),
            taster_rise_t_s=self.taster_rise_t_s,
            drive_ready=bool(self.drive_ready),
            estate=self.estate,
            speed_abs_mps=float(speed_abs_mps),
            stop_eps_mps=float(stop_eps_mps),
            brake_override_b1=bool(self.brake_override_b1),
            brake_override_b2=bool(self.brake_override_b2),
        )

    # ---------------------------------------------------------------------
    # cut markers
    # ---------------------------------------------------------------------

    def clear_cut_markers(self, *, reset_prev: bool = False) -> None:
        (
            self.cut_valid,
            self.cut_pos_m,
            self.cut_vel_mps,
            self.cut_time_s,
            self.systemtime_tok,
            self.prev_estop_state,
        ) = _clear_cut_markers(
            state=self.state,
            reset_prev=bool(reset_prev),
            prev_estop_state=bool(self.prev_estop_state),
        )

        # Stop metrics are cleared on ReSync together with the cut markers.
        self.stop_valid = False
        self.stop_pos_m = 0.0
        self.stop_time_s = 0.0
        self.posdiff_stop_m = 0.0

        # ReSync / clear also resets the cause edge detector.
        self.prev_cause_active = False
        self.cause_edge = False

    def arm_cut_follow_live(self) -> None:
        """Arm live cut baseline tracking (HiP ReSync).

        Policy:
        - CutPos/CutVel start tracking the actual axis pos/vel every tick.
        - When an E-Stop *cause* becomes active, the cut markers freeze at that moment.
        - Stop metrics are cleared.
        """
        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        pos = float(getattr(ax0, "pos", 0.0) or 0.0) if ax0 is not None else 0.0
        vel = float(getattr(ax0, "vel", 0.0) or 0.0) if ax0 is not None else 0.0

        self.cut_follow_live = True
        self.cut_valid = True
        self.cut_pos_m = pos
        self.cut_vel_mps = vel
        self.cut_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
        self.systemtime_tok = self._now_token()

        # Clear stop metrics on ReSync.
        self.stop_valid = False
        self.stop_pos_m = 0.0
        self.stop_time_s = 0.0
        self.posdiff_stop_m = 0.0

        # Reset cause-edge detector so the next real cause edge will freeze markers.
        self.prev_cause_active = False
        self.cause_edge = False

        try:
            self.state.params["SystemTime"] = self.systemtime_tok
            self.state.params["CutPos"] = float(self.cut_pos_m)
            self.state.params["CutVel"] = float(self.cut_vel_mps)
            self.state.params["CutTime"] = float(self.cut_time_s)
            # PosDiffFor is reserved for CutMarker diff (pos - CutPos).
            self.state.params["PosDiffFor"] = 0.0
            self.state.params["PosDiffStop"] = 0.0
        except Exception:
            pass


    def update_cut_follow_live(self) -> None:
        """If armed, keep CutPos/CutVel tracking actual axis pos/vel.

        Stops updating automatically once an E-Stop *cause* becomes active.
        """
        if not bool(self.cut_follow_live):
            return
        if bool(getattr(self, "cause_active", False)):
            # Freeze at the moment a cause hits.
            self.cut_follow_live = False
            return

        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        if ax0 is None:
            return

        self.cut_valid = True
        self.cut_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
        self.cut_vel_mps = float(getattr(ax0, "vel", 0.0) or 0.0)
        self.cut_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
        self.systemtime_tok = self._now_token()

        try:
            self.state.params["SystemTime"] = self.systemtime_tok
            self.state.params["CutPos"] = float(self.cut_pos_m)
            self.state.params["CutVel"] = float(self.cut_vel_mps)
            self.state.params["CutTime"] = float(self.cut_time_s)
        except Exception:
            pass


    # ---------------------------------------------------------------------
    # legacy/diagnostic meta helpers
    # ---------------------------------------------------------------------

    def step_lifetick(self) -> None:
        """Update legacy device_tick/lifetick meta fields.

        Uses last_cmd.lifetick_echo map if available.
        """
        inc_ms = max(1, int(round(self.tb.dt_s * 1000.0)))
        echo_map = {}
        if self.last_cmd is not None:
            try:
                echo_map = dict(getattr(self.last_cmd, "lifetick_echo", {}) or {})
            except Exception:
                echo_map = {}

        for axis_id, ax in self.state.axes.items():
            prev = int(ax.meta.get("device_tick", 0)) & 0xFFFF
            dev_tick = (prev + inc_ms) & 0xFFFF
            ax.meta["device_tick"] = int(dev_tick)
            ax.meta["lifetick_tx"] = int(dev_tick)
            try:
                ax.meta["lifetick_rx"] = int(echo_map.get(axis_id, 0) or 0)
            except Exception:
                ax.meta["lifetick_rx"] = 0
            ax.meta["timetick_ms"] = int(inc_ms)

    # ---------------------------------------------------------------------
    # step pipeline
    # ---------------------------------------------------------------------

    def rx_command_frames(self, frames: list[CommandFrame], now_ns: int) -> int:
        if frames:
            self.last_cmd = frames[-1]
            self.last_cmd_ns = int(now_ns)
            self.seen_first_cmd = True
        return int(len(frames))

    def update_l0_connection_state(self, now_ns: int) -> None:
        if not bool(self.seen_first_cmd):
            self.l0_top = L0Top.START
            self.l0_sub = L0Sub.IDLE
        else:
            if self.last_cmd_ns is not None:
                age_s = (int(now_ns) - int(self.last_cmd_ns)) / 1e9
                if age_s > float(self.disconnect_after_s):
                    self.l0_top = L0Top.START
                    self.l0_sub = L0Sub.IDLE
                else:
                    self.l0_top = L0Top.CONNECTED
            else:
                self.l0_top = L0Top.CONNECTED

        try:
            self.state.params["DenSiL0Top"] = self.l0_top.name
            self.state.params["DenSiL0Sub"] = self.l0_sub.name
        except Exception:
            pass

    def derive_estop_inputs(self) -> tuple[int, bool, bool]:
        return _derive_estop_inputs(int(self.inj_estop_word))

    def compute_moving_guard(self) -> bool:
        return compute_moving_guard(state=self.state, axis_ids=list(self.axis_ids))

    def handle_estop_reset_cmd(self, reset_able: bool) -> None:
        cmd = self.ensure_last_cmd()
        if (
            self.l0_top == L0Top.CONNECTED
            and bool(getattr(cmd, "estop_reset", False))
            and bool(reset_able)
        ):
            self.l0_sub = L0Sub.RESETTING_ESTOP

        if self.l0_sub == L0Sub.RESETTING_ESTOP:
            self.apply_post_reset_state()
            # remain in EStop workflow: keep cut markers frozen until HiP ReSync
            self.es_start_armed = False
            # one-shot
            self.l0_sub = L0Sub.IDLE

    def handle_resync_cmd(self) -> None:
        cmd = self.ensure_last_cmd()
        _handle_resync_cmd(
            cmd=cmd,
            l0_top=self.l0_top,
            clear_cut_markers=lambda reset_prev: self.clear_cut_markers(reset_prev=reset_prev),
            arm_cut_follow_live=self.arm_cut_follow_live,
        )

    def apply_param_ops(self, ready_for_sollvel: bool, moving: bool) -> dict[str, float]:
        cmd = self.ensure_last_cmd()
        allow_param_ops = (
            self.l0_top == L0Top.CONNECTED and (not bool(ready_for_sollvel)) and (not bool(moving))
        )

        res = apply_densi_param_ops(
            state=self.state,
            param_ops=getattr(cmd, "param_ops", []) or [],
            allow=allow_param_ops,
            normalize_pos_chain=self.normalize_pos_chain,
            normalize_guider_range=self.normalize_guider_range,
            enforce_pos_chain=self.enforce_pos_chain,
            enforce_guider_minmax=self.enforce_guider_minmax,
        )
        return dict(res.applied_values or {})

    def apply_safety_and_refresh_estop(self) -> tuple[int, dict[str, bool], bool]:
        """Apply ladder + refresh packed estop word.

        Returns (word, bits, reset_able_changed).
        """
        self.apply_estop_state_machine()
        self._update_display_grace_tracking()
        changed = bool(self.sync_reset_able_bit())
        word = int(self.inj_estop_word)
        bits = decode_estop_word(int(word))

        # "Cause active" matches the operator mental model:
        # - any trip bit set OR
        # - any required OK bit unset
        # We use the *edge* of this to latch CutPos/CutVel, because state.estop can be
        # true for non-cause reasons (e.g., startup / schuetz off).
        # Include OK-chain faults as a cause: losing a required OK bit must latch
        # CutPos/CutVel/CutTime just like trip bits do.
        trip_cause = any(bool(bits.get(k, False)) for k in estop_cause_keys())
        ok_keys = [k for k in estop_ok_keys() if k not in ("brk1_ok", "brk2_ok")]
        ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)
        cause_active = bool(trip_cause) or bool(ok_chain_fault)

        self.cause_edge = bool(cause_active) and (not bool(self.prev_cause_active))
        self.prev_cause_active = bool(cause_active)
        return word, bits, changed

    def compute_estop_edge_and_update_state(self, estop_word: int) -> bool:
        # EStop ladder is authoritative
        return _compute_estop_edge_and_update_state(
            estate=self.estate,
            prev_estop_state=bool(self.prev_estop_state),
            estop_word=int(estop_word),
            state=self.state,
        )

    def step_plant_with_clamp(self) -> None:
        # PLC-faithful DenSi behavior (Anton): see docs/anton_vel_cmd_implementation_step.md
        # Goals: deterministic gating, ramping, soft-limit braking, and PID trim overlay.
        cmd = self.ensure_last_cmd()
        cmd_for_plant = normalize_cmd_for_plant(
            cmd,
            state=self.state,
            dt_s=float(self.tb.dt_s),
            axis_ids=list(self.axis_ids),
            drive_ready=bool(self.drive_ready),
        )
        params = dict(getattr(self.state, "params", {}) or {})
        ramp_mode_ok = bool(int(params.get("RampModeOk", params.get("DriveModeOk", 1)) or 0))
        deadman_active = bool(getattr(getattr(self.state, "joy", None), "deadman", False))

        step_plc_anton_vel_cmd(
            state=self.state,
            cmd=cmd_for_plant,
            dt_s=float(self.tb.dt_s),
            axis_ids=list(self.axis_ids),
            ready_for_sollvel=bool(self.drive_ready),
            lifetick_stale_after_ticks_active=int(self.lifetick_stale_after_ticks_active),
            lifetick_stale_after_ticks_idle=int(self.lifetick_stale_after_ticks_idle),
            deadman_active=bool(deadman_active),
            ramp_mode_ok=bool(ramp_mode_ok),
        )

    def maybe_latch_cut_markers(self, estop_edge: bool) -> None:
        (
            self.cut_valid,
            self.cut_pos_m,
            self.cut_vel_mps,
            self.cut_time_s,
            self.systemtime_tok,
        ) = _maybe_latch_cut_markers(
            state=self.state,
            axis_ids=list(self.axis_ids),
            estop_edge=bool(estop_edge),
            cut_valid=bool(self.cut_valid),
            now_token=self._now_token,
            cut_pos_m=float(self.cut_pos_m),
            cut_vel_mps=float(self.cut_vel_mps),
            cut_time_s=float(self.cut_time_s),
            systemtime_tok=str(self.systemtime_tok or ""),
        )

    def maybe_latch_stop_metrics(self) -> None:
        """Latch stop distance once the coastdown reaches v~=0.

        Semantic intent (Lane 2): When an E-Stop trip occurs, commanded speed is
        dropped to zero immediately, while the simulated plant decelerates with
        Dcc. We record CutPos/CutVel at the moment the E-Stop is entered and
        then compute PosDiffStop = (pos_stop - CutPos) once the axis stops.
        """

        if (not bool(self.cut_valid)) or bool(self.stop_valid):
            return
        if self.estate != EStopState.STOPPING:
            return

        axis_id = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id) if axis_id else None
        if ax0 is None:
            return

        v = float(getattr(ax0, "vel", 0.0) or 0.0)
        if abs(v) > 1e-3:
            return

        self.stop_valid = True
        self.stop_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
        self.stop_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
        self.posdiff_stop_m = float(self.stop_pos_m) - float(self.cut_pos_m)

        try:
            self.state.params["PosDiffStop"] = float(self.posdiff_stop_m)
            # Keep Hip/legacy panels consistent: PosDiffFor is what they display.
            self.state.params["PosDiffFor"] = float(self.posdiff_stop_m)
        except Exception:
            pass

    def apply_estop_clamp_to_state(self) -> None:
        apply_estop_clamp_to_state(state=self.state)

    def advance_tick(self) -> None:
        self.state.tick += 1
        self.state.t_s += float(self.tb.dt_s)
        self.prev_estop_state = bool(self.state.estop)

    def step(self, *, frames: list[CommandFrame], now_ns: int) -> DenSiTickResult:
        return _step(engine=self, frames=frames, now_ns=now_ns)
