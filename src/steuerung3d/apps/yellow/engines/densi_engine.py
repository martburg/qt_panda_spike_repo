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

from dataclasses import dataclass, replace
from datetime import datetime
import time
from typing import Callable

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.protocol.estop_bits import (
    ESTOP_SPECS,
    ESTOP_CAUSE_KEYS,
    ESTOP_OK_KEYS,
    decode_estop_word,
    encode_estop_word,
)

from .densi_types import EStopState, L0Top, L0Sub
from ..panels.densi_param_ops_core import apply_densi_param_ops
from ..controllers.ui_banner import BANNER_DYNAMIC_EXCLUDE, derive_banner_estate_from_word



@dataclass
class DenSiTickResult:
    """Result of one DenSi engine tick."""

    cmd_rx_count: int
    last_cmd: CommandFrame
    last_cmd_ns: int | None

    l0_top: L0Top
    l0_sub: L0Sub

    reset_able: bool
    ready_for_sollvel: bool
    moving: bool

    estop_word: int
    estop_bits: dict[str, bool]
    estop_edge: bool

    applied_param_values: dict[str, float]

    # UI nicety: controller can choose whether to refresh estop checkboxes.
    # Legacy behavior refreshed checkboxes only when ResetAble toggled.
    reset_able_changed: bool = False


@dataclass
class DenSiEngine:
    """Qt-free DenSi engine (single-axis for now)."""

    axis_ids: list[str]
    tb: Timebase
    state: MachineState
    device: SimDevice

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

    # param ops hooks (controller supplies: keep semantics)
    normalize_pos_chain: Callable[[dict[str, float]], dict[str, float]] | None = None
    normalize_guider_range: Callable[[dict[str, float]], dict[str, float]] | None = None
    enforce_pos_chain: Callable[[dict[str, float]], dict[str, float]] | None = None
    enforce_guider_minmax: Callable[[dict[str, float]], dict[str, float]] | None = None

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
            normalize_pos_chain=normalize_pos_chain,
            normalize_guider_range=normalize_guider_range,
            enforce_pos_chain=enforce_pos_chain,
            enforce_guider_minmax=enforce_guider_minmax,
        )
        eng.reset_to_fault_state()
        eng.prev_estop_state = bool(getattr(eng.state, "estop", False))
        return eng

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
        `time.monotonic()` just like the legacy controller implementation.
        """
        try:
            if self.taster_pressed_s is None:
                return False
            return (time.monotonic() - float(self.taster_pressed_s)) < float(self.brake_handoff_grace_s)
        except Exception:
            return False

    def ensure_last_cmd(self) -> CommandFrame:
        if self.last_cmd is None:
            self.last_cmd = CommandFrame(
                tick=int(self.state.tick),
                t_s=float(self.state.t_s),
                estop=False,
                fault=False,
                mode=self.state.mode,
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
          - Trip-causes NOT asserted at startup (no explicit cause latched): ESTOP_CAUSE_KEYS => False
          - Status/OK chain broken (red): ESTOP_OK_KEYS => False
          - ResetAble is derived from trip-cause bits and becomes True when causes are clear.
        """
        bits = self._ensure_inj_bits()

        # default everything False
        for k in list(bits.keys()):
            bits[k] = False

        # Trip causes clear at startup (no explicit cause latched)
        for k in ESTOP_CAUSE_KEYS:
            bits[k] = False

        # Break the OK chain (red)
        for k in ESTOP_OK_KEYS:
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

        # Cut markers (latched on E-Stop entry)
        self.cut_valid = False
        self.cut_pos_m = 0.0
        self.cut_vel_mps = 0.0
        self.cut_time_s = 0.0
        self.systemtime_tok = ""
        self.prev_estop_state = bool(getattr(self.state, "estop", False))

        # Derived/latches
        self.estop_latched = False
        self.safety_ok = True

        # Display grace mirrors (used by VM for banner/brake dots)
        self.taster_prev_disp = False
        self.taster_pressed_s = None

    def apply_go_state(self) -> None:
        """Set injected bits to a stable 'GO' state (no flash)."""
        bits = self._ensure_inj_bits()
        for k in list(bits.keys()):
            bits[k] = False

        for k in ESTOP_OK_KEYS:
            bits[k] = True
        for k in ESTOP_CAUSE_KEYS:
            bits[k] = False

        self.inj_estop_word = int(encode_estop_word(bits))
        self.estop_latched = False

    def apply_post_reset_state(self) -> None:
        """Clear initial FAULT latch, but remain not-ready until Taster + delay."""
        bits = self._ensure_inj_bits()
        for k in list(bits.keys()):
            bits[k] = False

        for k in ESTOP_OK_KEYS:
            bits[k] = True
        for k in ESTOP_CAUSE_KEYS:
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
        if "reset_able" not in bits:
            return False

        trip_causes = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)

        # Only surface ResetAble while we are in ESTOP.
        try:
            estate = derive_banner_estate_from_word(
                int(self.inj_estop_word),
                within_brake_grace=self.within_brake_grace_disp,
            )
        except Exception:
            estate = "ESTOP"
        in_estop = (estate == "ESTOP")

        desired = (not trip_causes) and bool(in_estop)
        if bool(bits.get("reset_able", False)) == bool(desired):
            return False

        bits["reset_able"] = bool(desired)
        self.inj_estop_word = int(encode_estop_word(bits))
        return True
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
        schuetz = bool(bits.get("schuetz", False))
        taster = bool(bits.get("taster", False))

        # Track taster edge in device timebase (deterministic)
        if taster and (not bool(self.taster_prev)):
            self.taster_rise_t_s = float(self.state.t_s)
        if not taster:
            self.taster_rise_t_s = None
        self.taster_prev = bool(taster)

        elapsed: float | None = None
        if self.taster_rise_t_s is not None:
            try:
                elapsed = float(self.state.t_s) - float(self.taster_rise_t_s)
            except Exception:
                elapsed = None

        brake_switch_s = float(self.brake_switch_s)
        grace_s = float(self.brake_handoff_grace_s)

        # Desired brake OK-for-mode
        if bool(self.estop_latched) or (not schuetz):
            desired_brk_ok = (not taster)
        else:
            if not taster:
                desired_brk_ok = True
            else:
                desired_brk_ok = (elapsed is not None) and (elapsed >= brake_switch_s)

        for k in ("brk1_ok", "brk2_ok"):
            if k in bits and bool(bits.get(k, False)) != bool(desired_brk_ok):
                # respect override
                if k == "brk1_ok" and bool(self.brake_override_b1):
                    continue
                if k == "brk2_ok" and bool(self.brake_override_b2):
                    continue
                bits[k] = bool(desired_brk_ok)

        # Trip evaluation
        trip_cause = any(bool(bits.get(k, False)) for k in ESTOP_CAUSE_KEYS)
        ok_keys = [k for k in ESTOP_OK_KEYS if (k not in BANNER_DYNAMIC_EXCLUDE) and (k not in ("brk1_ok", "brk2_ok"))]
        ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)

        brk_ok = bool(bits.get("brk1_ok", True)) and bool(bits.get("brk2_ok", True))
        if taster:
            brake_trip = (not brk_ok) and ((elapsed is None) or (elapsed >= grace_s))
        else:
            brake_trip = (not brk_ok)

        trip_active = trip_cause or ok_chain_fault or brake_trip or (not bool(self.safety_ok))

        if trip_active:
            self.estop_latched = True
            if bool(bits.get("ready", False)):
                bits["ready"] = False
            if bool(bits.get("schuetz", False)):
                bits["schuetz"] = False
            self.drive_ready = False
            self.estate = EStopState.ESTOP
        else:
            if not schuetz:
                self.estate = EStopState.ESTOP
            elif not taster:
                self.estate = EStopState.IDLE
            else:
                self.estate = EStopState.READY if brk_ok else EStopState.ARMED

            desired_ready = (self.estate == EStopState.READY)
            if "ready" in bits and bool(bits.get("ready", False)) != bool(desired_ready):
                bits["ready"] = bool(desired_ready)
            self.drive_ready = bool(desired_ready)

        self.inj_estop_word = int(encode_estop_word(bits))

    # ---------------------------------------------------------------------
    # cut markers
    # ---------------------------------------------------------------------

    def clear_cut_markers(self, *, reset_prev: bool = False) -> None:
        self.cut_valid = False
        self.cut_pos_m = 0.0
        self.cut_vel_mps = 0.0
        self.cut_time_s = 0.0
        if reset_prev:
            self.prev_estop_state = bool(getattr(self.state, "estop", False))

        try:
            self.state.params["CutPos"] = 0.0
            self.state.params["CutVel"] = 0.0
            self.state.params["CutTime"] = 0.0
            self.state.params["PosDiffFor"] = 0.0
        except Exception:
            pass

    # ---------------------------------------------------------------------
    # legacy/diagnostic meta helpers
    # ---------------------------------------------------------------------

    @staticmethod
    def _make_drive_status_word(
        *,
        output_powered: bool,
        amp_ready: bool,
        referenced: bool,
        in_position: bool,
        brake_lifted: bool,
        fault: bool,
        zustand: int,
    ) -> int:
        w = 0
        if output_powered:
            w |= 1 << 0
        if amp_ready:
            w |= 1 << 1
        if referenced:
            w |= 1 << 2
        if in_position:
            w |= 1 << 3
        if brake_lifted:
            w |= 1 << 4
        if fault:
            w |= 1 << 5
        w |= (int(zustand) & 0xFF) << 8
        return int(w)

    def update_drive_status_words(self) -> None:
        bits = decode_estop_word(int(self.inj_estop_word))
        taster = bool(bits.get("taster", False))

        for _axis_id, ax in self.state.axes.items():
            vel = float(getattr(ax, "vel", 0.0) or 0.0)
            in_pos = abs(vel) < 1e-3

            if bool(self.state.estop):
                main = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=True, zustand=14,
                )
                slave = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=True, zustand=14,
                )
            elif self.drive_ready and taster:
                main = self._make_drive_status_word(
                    output_powered=True, amp_ready=True, referenced=True, in_position=in_pos,
                    brake_lifted=True, fault=False, zustand=10,
                )
                slave = self._make_drive_status_word(
                    output_powered=True, amp_ready=True, referenced=True, in_position=in_pos,
                    brake_lifted=True, fault=False, zustand=5,
                )
            else:
                main = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=False, zustand=0,
                )
                slave = self._make_drive_status_word(
                    output_powered=False, amp_ready=False, referenced=False, in_position=False,
                    brake_lifted=False, fault=False, zustand=0,
                )

            ax.meta["status_word"] = int(main)
            ax.meta["guide_status_word"] = int(slave)

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
        word = int(self.inj_estop_word)
        reset_able = bool(self._reset_able_from_estop_word(word))
        ready_for_sollvel = bool(self._ready_from_estop_word(word))
        return word, reset_able, ready_for_sollvel

    @staticmethod
    def _reset_able_from_estop_word(word: int) -> bool:
        try:
            bits = decode_estop_word(int(word))
            return bool(bits.get("reset_able", False))
        except Exception:
            return False

    @staticmethod
    def _ready_from_estop_word(word: int) -> bool:
        try:
            bits = decode_estop_word(int(word))
            return bool(bits.get("ready", False))
        except Exception:
            return False

    def compute_moving_guard(self) -> bool:
        axis_id0 = self.axis_ids[0] if self.axis_ids else ""
        ax0 = self.state.axes.get(axis_id0) if axis_id0 else None
        try:
            return bool(ax0 is not None and abs(float(getattr(ax0, "vel", 0.0) or 0.0)) > 1e-3)
        except Exception:
            return False

    def handle_estop_reset_cmd(self, reset_able: bool) -> None:
        cmd = self.ensure_last_cmd()
        if self.l0_top == L0Top.CONNECTED and bool(getattr(cmd, "estop_reset", False)) and bool(reset_able):
            self.l0_sub = L0Sub.RESETTING_ESTOP

        if self.l0_sub == L0Sub.RESETTING_ESTOP:
            self.apply_post_reset_state()
            # remain in EStop workflow: keep cut markers frozen until HiP ReSync
            self.es_start_armed = False
            # one-shot
            self.l0_sub = L0Sub.IDLE

    def handle_resync_cmd(self) -> None:
        cmd = self.ensure_last_cmd()
        if self.l0_top == L0Top.CONNECTED and bool(getattr(cmd, "resync", False)):
            self.clear_cut_markers(reset_prev=True)

    def apply_param_ops(self, ready_for_sollvel: bool, moving: bool) -> dict[str, float]:
        cmd = self.ensure_last_cmd()
        allow_param_ops = (
            self.l0_top == L0Top.CONNECTED
            and (not bool(ready_for_sollvel))
            and (not bool(moving))
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
        changed = bool(self.sync_reset_able_bit())
        word = int(self.inj_estop_word)
        bits = decode_estop_word(int(word))
        return word, bits, changed

    def compute_estop_edge_and_update_state(self, estop_word: int) -> bool:
        # EStop ladder is authoritative
        self.state.estop = bool(self.estate == EStopState.ESTOP)
        self.state.estop_status_word = int(estop_word)
        # latch on entry
        return bool(self.state.estop) and (not bool(self.prev_estop_state))

    def step_plant_with_clamp(self) -> None:
        cmd = self.ensure_last_cmd()
        cmd_for_plant = cmd
        if (not self.drive_ready) or bool(self.state.estop):
            cmd_for_plant = replace(
                cmd,
                axes={a: AxisSetpoint(enable=False, vel=0.0) for a in self.axis_ids},
            )
        self.device.step(self.state, cmd_for_plant, float(self.tb.dt_s))

    def maybe_latch_cut_markers(self, estop_edge: bool) -> None:
        if bool(estop_edge) and (not bool(self.cut_valid)):
            axis_id = self.axis_ids[0] if self.axis_ids else ""
            ax0 = self.state.axes.get(axis_id) if axis_id else None
            if ax0 is not None:
                self.cut_valid = True
                self.cut_pos_m = float(getattr(ax0, "pos", 0.0) or 0.0)
                self.cut_vel_mps = float(getattr(ax0, "vel", 0.0) or 0.0)
                self.cut_time_s = float(getattr(self.state, "t_s", 0.0) or 0.0)
                self.systemtime_tok = self._now_token()

                try:
                    self.state.params["SystemTime"] = self.systemtime_tok
                except Exception:
                    pass

                try:
                    self.state.params["CutPos"] = float(self.cut_pos_m)
                    self.state.params["CutVel"] = float(self.cut_vel_mps)
                    self.state.params["CutTime"] = float(self.cut_time_s)
                    self.state.params["PosDiffFor"] = 0.0
                except Exception:
                    pass

    def apply_estop_clamp_to_state(self) -> None:
        if bool(self.state.estop):
            for ax in self.state.axes.values():
                ax.enabled = False
                ax.vel = 0.0

    def advance_tick(self) -> None:
        self.state.tick += 1
        self.state.t_s += float(self.tb.dt_s)
        self.prev_estop_state = bool(self.state.estop)

    def step(self, *, frames: list[CommandFrame], now_ns: int) -> DenSiTickResult:
        cmd_rx_count = self.rx_command_frames(frames, now_ns=int(now_ns))
        cmd = self.ensure_last_cmd()

        self.update_l0_connection_state(int(now_ns))

        _estop_word0, reset_able, ready_for_sollvel = self.derive_estop_inputs()
        moving = self.compute_moving_guard()

        self.handle_estop_reset_cmd(reset_able)
        self.handle_resync_cmd()

        applied = self.apply_param_ops(ready_for_sollvel=ready_for_sollvel, moving=moving)

        estop_word, bits, reset_able_changed = self.apply_safety_and_refresh_estop()
        estop_edge = self.compute_estop_edge_and_update_state(estop_word)

        self.step_plant_with_clamp()
        self.maybe_latch_cut_markers(estop_edge)
        self.apply_estop_clamp_to_state()
        self.advance_tick()

        # phase 7 (non-Qt semantics): lifetick + status words
        self.step_lifetick()
        self.update_drive_status_words()

        return DenSiTickResult(
            cmd_rx_count=cmd_rx_count,
            last_cmd=cmd,
            last_cmd_ns=self.last_cmd_ns,
            l0_top=self.l0_top,
            l0_sub=self.l0_sub,
            reset_able=bool(reset_able),
            ready_for_sollvel=bool(ready_for_sollvel),
            moving=bool(moving),
            estop_word=int(estop_word),
            estop_bits=dict(bits),
            estop_edge=bool(estop_edge),
            applied_param_values=dict(applied),
            reset_able_changed=bool(reset_able_changed),
        )
