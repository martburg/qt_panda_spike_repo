from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.models import ControlSource, PairFacts, PairRef
from steuerung3d.apps.yellow.engines.supervisor.pair_derivation import build_pair_status
from steuerung3d.apps.yellow.engines.supervisor.reset_estop import (
    evaluate_reset_estop_eligibility,
    issue_reset_estop_for_pair,
)


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
        position=0.0,
        velocity=0.0,
        banner_estate="",
    )
    facts = PairFacts(**(facts.__dict__ | dict(overrides)))
    ref = PairRef(pair_id="p1", axis_id="Anton", densi_id="d1", hip_id="h1")
    return build_pair_status(ref, facts)


def test_single_pair_reset_estop_success() -> None:
    status = _status()
    eligibility = evaluate_reset_estop_eligibility(status)
    assert eligibility.eligible is True
    result = issue_reset_estop_for_pair(status=status, source=ControlSource.GUI)
    assert result.issued is True
    assert result.reason == ""


def test_reset_estop_blocked_due_to_state() -> None:
    status = _status(estart_input=True)
    eligibility = evaluate_reset_estop_eligibility(status)
    assert eligibility.eligible is False
    assert eligibility.reason == "pair not in reset-estop-capable phase"
    result = issue_reset_estop_for_pair(status=status, source=ControlSource.GUI)
    assert result.issued is False
    assert result.reason == "pair not in reset-estop-capable phase"
