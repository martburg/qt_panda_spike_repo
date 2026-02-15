from __future__ import annotations

from steuerung3d.apps.yellow.panels.densi_banner_vm import compute_densi_banner_vm
from steuerung3d.protocol.estop_bits import ESTOP_CAUSE_KEYS, ESTOP_OK_KEYS, encode_estop_word


def _base_bits() -> dict[str, bool]:
    # "healthy" defaults: all OK-chain bits asserted, all trip causes inactive
    b: dict[str, bool] = {k: True for k in ESTOP_OK_KEYS}
    b.update({k: False for k in ESTOP_CAUSE_KEYS})
    return b


def test_banner_estate_ladder_states() -> None:
    # ESTOP when word=0
    vm0 = compute_densi_banner_vm(estop_word=0, within_brake_grace=False)
    assert vm0.estate == "ESTOP"

    # IDLE: schuetz=1, taster=0, brakes OK, no trip causes
    bits = _base_bits()
    bits.update({"schuetz": True, "taster": False, "brk1_ok": True, "brk2_ok": True})
    w_idle = encode_estop_word(bits)
    vm_idle = compute_densi_banner_vm(estop_word=w_idle, within_brake_grace=False)
    assert vm_idle.estate == "IDLE"

    # ARMED: taster=1 but brakes not yet OK, within grace
    bits = _base_bits()
    bits.update({"schuetz": True, "taster": True, "brk1_ok": False, "brk2_ok": False})
    w_armed = encode_estop_word(bits)
    vm_armed = compute_densi_banner_vm(estop_word=w_armed, within_brake_grace=True)
    assert vm_armed.estate == "ARMED"

    # READY: taster=1 and brakes OK
    bits = _base_bits()
    bits.update({"schuetz": True, "taster": True, "brk1_ok": True, "brk2_ok": True})
    w_ready = encode_estop_word(bits)
    vm_ready = compute_densi_banner_vm(estop_word=w_ready, within_brake_grace=False)
    assert vm_ready.estate == "READY"
