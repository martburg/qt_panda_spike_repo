from __future__ import annotations

from steuerung3d.apps.yellow.panels.hip.hip_banner_vm import compute_hip_banner_vm
from steuerung3d.apps.yellow.panels.hip.hip_header_dots_vm import compute_hip_header_dots_vm
from steuerung3d.apps.yellow.panels.hip.hip_estop_vm import compute_hip_estop_vm
from steuerung3d.apps.yellow.domain.ui_estop import infer_estop_profile


def test_hip_banner_vm_shapes() -> None:
    vm = compute_hip_banner_vm(estop_word=0, within_brake_grace=False)
    assert vm.estate
    assert vm.bg
    assert vm.fg


def test_hip_header_dots_vm_passes_online_state() -> None:
    vm = compute_hip_header_dots_vm(
        online_state="good",
        taster=False,
        ready=True,
        brk1_raw=True,
        brk2_raw=True,
        brake_ok_display=lambda v: bool(v),
    )
    assert vm.online_state == "good"


def test_hip_estop_vm_reset_enabled_and_profile() -> None:
    logical = {
        "reset_able": True,
        "ready": True,
        "brk1_ok": True,
        "brk2_ok": True,
    }
    profile = infer_estop_profile(logical)
    vm = compute_hip_estop_vm(
        logical=logical,
        taster=False,
        attached=True,
        brake_ok_display=lambda v: bool(v),
        profile=profile,
        prev_profile=str(profile),
    )
    assert vm.reset_enabled is True
    assert vm.profile_changed is False
