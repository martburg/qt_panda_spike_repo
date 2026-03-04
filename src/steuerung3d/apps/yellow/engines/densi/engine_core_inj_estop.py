"""Injected E-Stop + ladder helpers for DenSiEngine.

This is the authoritative DenSi ladder emulation (Qt-free).
"""

from __future__ import annotations

from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ...domain.estop_facts import (
    decode_estop_word,
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)
from .estop_fsm import (
    apply_estop_state_machine,
    compute_estop_edge_and_update_state as _compute_estop_edge_and_update_state,
    derive_estop_inputs as _derive_estop_inputs,
    sync_reset_able_bit as _sync_reset_able_bit,
)
from .types import EStopState, L0Sub, L0Top


class DenSiInjectedEStopMixin:
    # ---------------------------------------------------------------------
    # injected estop / ladder
    # ---------------------------------------------------------------------

    def _ensure_inj_bits(self) -> dict[str, bool]:
        if self.inj_bits is None:
            self.inj_bits = {k: False for k in ESTOP_SPECS.keys()}
        return self.inj_bits

    def reset_to_fault_state(self) -> None:
        """Start in a FAULT state: break OK chain but allow immediate EStopReset."""
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
        """Derive ResetAble from trip-cause bits."""
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

    def derive_estop_inputs(self) -> tuple[int, bool, bool]:
        return _derive_estop_inputs(int(self.inj_estop_word))

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

    def apply_safety_and_refresh_estop(self) -> tuple[int, dict[str, bool], bool]:
        """Apply ladder + refresh packed estop word."""
        self.apply_estop_state_machine()
        self._update_display_grace_tracking()
        changed = bool(self.sync_reset_able_bit())
        word = int(self.inj_estop_word)
        bits = decode_estop_word(int(word))

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
