from __future__ import annotations

from steuerung3d.apps.yellow.panels.densi.densi_cut_markers_vm import (
    compute_densi_cut_markers_vm,
)


def test_cut_markers_token_advances_only_when_not_estop() -> None:
    # Not latched, not estop: token advances to now_token
    vm = compute_densi_cut_markers_vm(
        cut_valid=False,
        estop_now=False,
        now_token="T1",
        systemtime_tok=None,
        systemtime_param=None,
        cut_pos_m=None,
        cut_vel_mps=None,
        pos_m=None,
    )
    assert vm.cut_time_text == "T1"
    assert vm.effects.systemtime_tok == "T1"

    # Not latched, estop: token stays at old (systemtime_tok) and does not advance
    vm2 = compute_densi_cut_markers_vm(
        cut_valid=False,
        estop_now=True,
        now_token="T2",
        systemtime_tok="T1",
        systemtime_param=None,
        cut_pos_m=None,
        cut_vel_mps=None,
        pos_m=None,
    )
    assert vm2.cut_time_text == "T1"
    assert vm2.effects.systemtime_tok is None


def test_cut_markers_posdiff_effect_when_latched() -> None:
    vm = compute_densi_cut_markers_vm(
        cut_valid=True,
        estop_now=True,
        now_token="IGNORED",
        systemtime_tok="Tfreeze",
        systemtime_param=None,
        cut_pos_m=1.0,
        cut_vel_mps=0.5,
        pos_m=1.25,
    )
    assert vm.effects.posdiff_for is not None
    assert abs(float(vm.effects.posdiff_for) - 0.25) < 1e-9
