from __future__ import annotations

from steuerung3d.apps.yellow.engines.supervisor.kinematics_simple import OnePairOneDofKinematics
from steuerung3d.apps.yellow.engines.supervisor.models import (
    PairFacts,
    PairRef,
    SupervisorMember,
    SupervisorSpec,
)
from steuerung3d.apps.yellow.engines.supervisor.runtime import SupervisorRuntime


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
        position=0.0,
        velocity=0.0,
        banner_estate="",
    )
    return PairFacts(**(base.__dict__ | dict(overrides)))


def _runtime() -> SupervisorRuntime:
    spec = SupervisorSpec(
        supervisor_id="sup-1",
        name="Sup",
        members=(
            SupervisorMember(member_id="pair:a", member_kind="pair", target_id="a", order_key=0),
            SupervisorMember(member_id="pair:b", member_kind="pair", target_id="b", order_key=1),
            SupervisorMember(member_id="pair:c", member_kind="pair", target_id="c", order_key=2),
        ),
    )
    pair_refs = {
        "a": PairRef(pair_id="a", axis_id="A", densi_id="dA", hip_id="hA"),
        "b": PairRef(pair_id="b", axis_id="B", densi_id="dB", hip_id="hB"),
        "c": PairRef(pair_id="c", axis_id="C", densi_id="dC", hip_id="hC"),
    }
    return SupervisorRuntime(spec=spec, pair_refs=pair_refs, kinematics=OnePairOneDofKinematics({}))


def test_batch_reset_estop_partially_eligible() -> None:
    runtime = _runtime()
    facts = {
        "a": _facts(),
        "b": _facts(estop_reset_input=True),
        "c": _facts(estart_input=True),
    }
    batch_result, updated = runtime.issue_reset_estop_batch(
        pair_ids=["a", "b", "c"],
        facts_by_pair_id=facts,
    )
    assert batch_result.issued_pair_ids == ("a",)
    assert batch_result.blocked_pair_ids == ("b", "c")
    reasons = {result.pair_id: result.reason for result in batch_result.results}
    assert reasons["b"] == "estop reset already present"
    assert reasons["c"] == "pair not in reset-estop-capable phase"
    assert updated["a"].estop_reset_input is True
    assert updated["b"].estop_reset_input is True
    assert updated["c"].estop_reset_input is False


def test_unknown_pair_id_is_reported_blocked() -> None:
    runtime = _runtime()
    facts = {"a": _facts(), "b": _facts(), "c": _facts()}
    batch_result, _ = runtime.issue_reset_estop_batch(pair_ids=["z"], facts_by_pair_id=facts)
    assert len(batch_result.results) == 1
    assert batch_result.results[0].pair_id == "z"
    assert batch_result.results[0].issued is False
    assert batch_result.results[0].reason == "unknown pair id"
