from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import PairFacts, PairRef
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import build_pair_status
from steuerung3d.apps.yellow.panels.supervisor.supervisor_detail_vm import (
    build_supervisor_detail_vm,
)


def _status(**overrides: object):
    facts = PairFacts(
        attached=True,
        stale=False,
        fault=False,
        estop_reset_input=False,
        estart_input=True,
        chk_es_taster_input=False,
        brake_grace_active=False,
        ready_actual=False,
        deadman_active=False,
        live_motion_active=False,
        param_edit_active=False,
        position=1.5,
        velocity=0.25,
        banner_estate="IDLE",
    )
    facts = PairFacts(**(facts.__dict__ | dict(overrides)))
    ref = PairRef(pair_id="p1", axis_id="Anton", densi_id="d1", hip_id="h1")
    return build_pair_status(ref, facts)


def test_detail_vm_returns_none_for_missing_selection() -> None:
    assert build_supervisor_detail_vm(None) is None


def test_detail_vm_contains_expected_metadata_and_inputs() -> None:
    vm = build_supervisor_detail_vm(_status())
    assert vm is not None
    assert vm.title == "p1"
    assert vm.phase_text == "Idle"
    labels = {field.label: field.value for field in vm.fields}
    assert labels["Axis"] == "Anton"
    assert labels["Banner estate"] == "IDLE"
    assert labels["EStart input"] == "On"
    assert "Check EsTaster" in vm.available_actions
