from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import PairFacts, PairPhase
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import derive_pair_phase


def _facts(**overrides: object) -> PairFacts:
    base = PairFacts(
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
        banner_estate="ESTOP",
    )
    return PairFacts(**(base.__dict__ | dict(overrides)))


def test_pair_phase_offline_has_priority() -> None:
    assert derive_pair_phase(_facts(stale=True, fault=True, attached=True)) == PairPhase.OFFLINE


def test_pair_phase_unattached_before_attached_flow() -> None:
    assert derive_pair_phase(_facts(attached=False)) == PairPhase.UNATTACHED


def test_pair_phase_attached_is_default_attached_phase() -> None:
    assert derive_pair_phase(_facts()) == PairPhase.ATTACHED


def test_pair_phase_idles_when_estart_input_seen() -> None:
    assert derive_pair_phase(_facts(estart_input=True)) == PairPhase.IDLE


def test_pair_phase_armed_when_chk_es_taster_input_seen() -> None:
    assert derive_pair_phase(_facts(chk_es_taster_input=True)) == PairPhase.ARMED


def test_pair_phase_brake_grace_overrides_armed() -> None:
    assert (
        derive_pair_phase(_facts(chk_es_taster_input=True, brake_grace_active=True))
        == PairPhase.BRAKE_GRACE
    )


def test_pair_phase_ready_overrides_brake_grace() -> None:
    assert derive_pair_phase(_facts(ready_actual=True, brake_grace_active=True)) == PairPhase.READY


def test_pair_phase_live_overrides_ready() -> None:
    assert derive_pair_phase(_facts(live_motion_active=True, ready_actual=True)) == PairPhase.LIVE


def test_pair_phase_fault_overrides_non_offline_attached_states() -> None:
    assert (
        derive_pair_phase(_facts(fault=True, live_motion_active=True, ready_actual=True))
        == PairPhase.FAULT
    )


def test_pair_phase_does_not_depend_on_banner_estate_text() -> None:
    assert derive_pair_phase(_facts(estart_input=True, banner_estate="ESTOP")) == PairPhase.IDLE
    assert derive_pair_phase(_facts(banner_estate="READY")) == PairPhase.ATTACHED
