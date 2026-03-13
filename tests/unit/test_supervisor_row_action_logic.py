from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import PairFacts, PairRef
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import build_pair_status
from steuerung3d.apps.yellow.panels.supervisor.supervisor_presenter import derive_row_action_flags


def _status(**overrides: object):
    facts = PairFacts(
        attached=True,
        stale=False,
        fault=False,
        estop_reset_input=False,
        estart_input=False,
        chk_es_taster_input=False,
        brake_grace_active=False,
        ready_actual=False,
        deadman_active=False,
        live_motion_active=False,
        param_edit_active=False,
        position=1.0,
        velocity=0.0,
        banner_estate="",
    )
    facts = PairFacts(**(facts.__dict__ | dict(overrides)))
    ref = PairRef(pair_id="p1", axis_id="Anton", densi_id="d1", hip_id="h1")
    return build_pair_status(ref, facts)


def test_attached_enables_reset_and_edit() -> None:
    flags = derive_row_action_flags(_status())
    assert flags.can_reset_estop is True
    assert flags.can_edit_parameters is True
    assert flags.can_check_es_taster is False


def test_idle_enables_check_and_edit() -> None:
    flags = derive_row_action_flags(_status(estart_input=True))
    assert flags.can_check_es_taster is True
    assert flags.can_edit_parameters is True
    assert flags.can_reset_estop is False


def test_editing_mode_enables_write_and_cancel() -> None:
    flags = derive_row_action_flags(_status(estart_input=True, param_edit_active=True))
    assert flags.can_write_parameters is True
    assert flags.can_cancel_edit is True
    assert flags.can_edit_parameters is False


def test_fault_disables_operational_actions() -> None:
    flags = derive_row_action_flags(_status(fault=True, estart_input=True))
    assert flags.can_reset_estop is False
    assert flags.can_check_es_taster is False
    assert flags.can_edit_parameters is False


def test_row_can_remove_member_when_present() -> None:
    flags = derive_row_action_flags(_status())
    assert flags.can_remove_member is True
