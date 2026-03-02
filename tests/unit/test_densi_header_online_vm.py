from __future__ import annotations

from steuerung3d.apps.yellow.panels.densi.densi_header_online_vm import (
    compute_densi_header_online_vm,
)


def test_header_online_dot_off_until_first_cmd() -> None:
    vm = compute_densi_header_online_vm(
        seen_first_cmd=False, now_ns=1_000_000_000, last_cmd_ns=None
    )
    assert vm.dot_state is None


def test_header_online_dot_good_then_warn() -> None:
    # Age 0.5s -> good
    vm1 = compute_densi_header_online_vm(
        seen_first_cmd=True, now_ns=2_000_000_000, last_cmd_ns=1_500_000_000, good_max_s=1.0
    )
    assert vm1.dot_state == "good"

    # Age 2s -> warn (warn_max=None -> never bad)
    vm2 = compute_densi_header_online_vm(
        seen_first_cmd=True, now_ns=3_000_000_000, last_cmd_ns=1_000_000_000, good_max_s=1.0
    )
    assert vm2.dot_state == "warn"
