"""Injected E-Stop + ladder helpers for DenSiEngine.

This is the authoritative DenSi ladder emulation (Qt-free).
"""

from __future__ import annotations

from typing import cast

from steuerung3d.protocol.estop_bits import ESTOP_SPECS

from ...domain.estop_facts import (
    decode_estop_word,
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)
from .engine_host_protocols import DenSiEngineHost
from .estop_fsm import (
    apply_estop_state_machine,
    compute_estop_edge_and_update_state as _compute_estop_edge_and_update_state,
    derive_estop_inputs as _derive_estop_inputs,
    sync_reset_able_bit as _sync_reset_able_bit,
)
from .types import EStopState, L0Sub, L0Top


class DenSiInjectedEStopMixin:
    def _host(self) -> DenSiEngineHost:
        return cast(DenSiEngineHost, self)

    # ---------------------------------------------------------------------
    # injected estop / ladder
    # ---------------------------------------------------------------------

    def _ensure_inj_bits(self) -> dict[str, bool]:
        host = self._host()
        if host.inj_bits is None:
            host.inj_bits = {k: False for k in ESTOP_SPECS.keys()}
        return host.inj_bits

    def reset_to_fault_state(self) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        cause_keys = estop_cause_keys()
        ok_keys = estop_ok_keys()

        for k in list(bits.keys()):
            bits[k] = False
        for k in cause_keys:
            bits[k] = False
        for k in ok_keys:
            bits[k] = False
        bits["reset_able"] = False

        host.inj_estop_word = int(encode_estop_word(bits))
        host.sync_reset_able_bit()

        host.taster_prev = False
        host.taster_rise_t_s = None
        host.drive_ready = False
        host.estate = EStopState.ESTOP
        host.es_start_armed = False
        host.brake_override_b1 = False
        host.brake_override_b2 = False
        host.cut_valid = True
        host.cut_pos_m = 0.0
        host.cut_vel_mps = 0.0
        host.cut_time_s = 0.0
        host.systemtime_tok = ""
        host.prev_estop_state = bool(getattr(host.state, "estop", False))
        host.prev_cause_active = False
        host.cause_edge = False
        host.stop_valid = False
        host.stop_pos_m = 0.0
        host.stop_time_s = 0.0
        host.posdiff_stop_m = 0.0
        host.estop_latched = False
        host.safety_ok = True
        host.taster_prev_disp = False
        host.taster_pressed_s = None

    def apply_go_state(self) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        cause_keys = estop_cause_keys()
        ok_keys = estop_ok_keys()
        for k in list(bits.keys()):
            bits[k] = False
        for k in ok_keys:
            bits[k] = True
        for k in cause_keys:
            bits[k] = False
        host.inj_estop_word = int(encode_estop_word(bits))
        host.estop_latched = False

    def apply_post_reset_state(self) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        cause_keys = estop_cause_keys()
        ok_keys = estop_ok_keys()
        for k in list(bits.keys()):
            bits[k] = False
        for k in ok_keys:
            bits[k] = True
        for k in cause_keys:
            bits[k] = False
        for k in ("ready", "taster", "schuetz", "brk1_ok", "brk2_ok"):
            if k in bits:
                bits[k] = False
        if "reset_able" in bits:
            bits["reset_able"] = False

        host.inj_estop_word = int(encode_estop_word(bits))
        host.estop_latched = False
        host.taster_prev = False
        host.taster_rise_t_s = None
        host.drive_ready = False
        host.es_start_armed = False
        host.brake_override_b1 = False
        host.brake_override_b2 = False

    def sync_reset_able_bit(self) -> bool:
        host = self._host()
        bits = self._ensure_inj_bits()
        changed, new_word = _sync_reset_able_bit(
            inj_bits=bits,
            inj_estop_word=int(host.inj_estop_word),
            within_brake_grace=host.within_brake_grace_disp,
        )
        host.inj_estop_word = int(new_word)
        return bool(changed)

    def inject_estop_bit(self, key: str, checked: bool) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        if key not in bits:
            return
        if key in ("brk1_ok", "brk2_ok"):
            desired = bool(host.drive_ready)
            if bool(checked) != bool(desired):
                if key == "brk1_ok":
                    host.brake_override_b1 = True
                else:
                    host.brake_override_b2 = True
        bits[key] = bool(checked)
        host.inj_estop_word = int(encode_estop_word(bits))
        host.sync_reset_able_bit()

    def set_all_estop_bits(self) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        for k in list(bits.keys()):
            bits[k] = True
        host.inj_estop_word = int(encode_estop_word(bits))
        host.sync_reset_able_bit()

    def clear_all_estop_bits(self) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        for k in list(bits.keys()):
            bits[k] = False
        host.inj_estop_word = int(encode_estop_word(bits))
        host.sync_reset_able_bit()

    def press_es_start(self) -> None:
        host = self._host()
        if bool(host.estop_latched):
            return
        bits = self._ensure_inj_bits()
        host.es_start_armed = True
        bits["schuetz"] = True
        if bool(bits.get("taster", False)):
            host.taster_rise_t_s = float(host.state.t_s)
        host.inj_estop_word = int(encode_estop_word(bits))

    def apply_estop_state_machine(self) -> None:
        host = self._host()
        bits = self._ensure_inj_bits()
        axis_id = host.axis_ids[0] if host.axis_ids else ""
        ax0 = host.state.axes.get(axis_id) if axis_id else None
        speed_abs_mps = abs(float(getattr(ax0, "vel", 0.0) or 0.0)) if ax0 is not None else 0.0
        stop_eps_mps = 1e-3
        (
            host.inj_estop_word,
            host.taster_prev,
            host.taster_rise_t_s,
            host.drive_ready,
            host.estate,
            host.estop_latched,
        ) = apply_estop_state_machine(
            inj_bits=bits,
            state_t_s=float(host.state.t_s),
            brake_switch_s=float(host.brake_switch_s),
            brake_handoff_grace_s=float(host.brake_handoff_grace_s),
            estop_latched=bool(host.estop_latched),
            safety_ok=bool(host.safety_ok),
            taster_prev=bool(host.taster_prev),
            taster_rise_t_s=host.taster_rise_t_s,
            drive_ready=bool(host.drive_ready),
            estate=host.estate,
            speed_abs_mps=float(speed_abs_mps),
            stop_eps_mps=float(stop_eps_mps),
            brake_override_b1=bool(host.brake_override_b1),
            brake_override_b2=bool(host.brake_override_b2),
        )

    def derive_estop_inputs(self) -> tuple[int, bool, bool]:
        host = self._host()
        return _derive_estop_inputs(int(host.inj_estop_word))

    def handle_estop_reset_cmd(self, reset_able: bool) -> None:
        host = self._host()
        cmd = host.ensure_last_cmd()
        if (
            host.l0_top == L0Top.CONNECTED
            and bool(getattr(cmd, "estop_reset", False))
            and bool(reset_able)
        ):
            host.l0_sub = L0Sub.RESETTING_ESTOP

        if host.l0_sub == L0Sub.RESETTING_ESTOP:
            host.apply_post_reset_state()
            host.es_start_armed = False
            host.l0_sub = L0Sub.IDLE

    def apply_safety_and_refresh_estop(self) -> tuple[int, dict[str, bool], bool]:
        host = self._host()
        host.apply_estop_state_machine()
        host._update_display_grace_tracking()
        changed = bool(host.sync_reset_able_bit())
        word = int(host.inj_estop_word)
        bits = decode_estop_word(int(word))

        trip_cause = any(bool(bits.get(k, False)) for k in estop_cause_keys())
        ok_keys = [k for k in estop_ok_keys() if k not in ("brk1_ok", "brk2_ok")]
        ok_chain_fault = any(not bool(bits.get(k, True)) for k in ok_keys)
        cause_active = bool(trip_cause) or bool(ok_chain_fault)

        host.cause_edge = bool(cause_active) and (not bool(host.prev_cause_active))
        host.prev_cause_active = bool(cause_active)
        return word, bits, changed

    def compute_estop_edge_and_update_state(self, estop_word: int) -> bool:
        host = self._host()
        return _compute_estop_edge_and_update_state(
            estate=host.estate,
            prev_estop_state=bool(host.prev_estop_state),
            estop_word=int(estop_word),
            state=host.state,
        )
