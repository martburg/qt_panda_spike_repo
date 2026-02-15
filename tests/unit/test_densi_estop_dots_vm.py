from __future__ import annotations

from steuerung3d.apps.yellow.panels.densi_estop_dots_vm import compute_densi_estop_dots_vm


def test_estop_dots_cause_and_header_brake_grace() -> None:
    bits = {
        "taster": True,
        "ready": False,
        # master is a TRIP CAUSE key: green when inactive (False), red when active (True)
        "master": False,
        "brk1_ok": False,
        "brk2_ok": False,
    }

    # No grace: brakes displayed bad
    vm = compute_densi_estop_dots_vm(bits=bits, taster=True, ready=False, within_brake_grace=False)
    assert vm.header["dotHdrFbt"] == "good"
    assert vm.header["dotHdrReady"] == "warn"
    assert vm.header["dotHdrBrake1"] == "bad"
    assert vm.header["dotHdrBrake2"] == "bad"
    assert vm.dots["dotMaster"] == "good"

    # With grace: brakes displayed good even if raw bits are false
    vm2 = compute_densi_estop_dots_vm(bits=bits, taster=True, ready=False, within_brake_grace=True)
    assert vm2.header["dotHdrBrake1"] == "good"
    assert vm2.header["dotHdrBrake2"] == "good"
