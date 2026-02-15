from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.apps.yellow.controllers.ui_estop import (
    age_to_online_state,
    compute_estop_dot_state,
    compute_estop_dot_states,
    compute_header_estop_dot_states,
)


@dataclass(frozen=True)
class _Spec:
    key: str
    dot: str | None


CAUSE = {"master", "estop1"}
OK = {"kw30_ok", "sps_ok"}


def test_age_to_online_state_three_level() -> None:
    assert age_to_online_state(age=0.0, good_max=30.0, warn_max=500.0) == "good"
    assert age_to_online_state(age=30.0, good_max=30.0, warn_max=500.0) == "good"
    assert age_to_online_state(age=31.0, good_max=30.0, warn_max=500.0) == "warn"
    assert age_to_online_state(age=500.0, good_max=30.0, warn_max=500.0) == "warn"
    assert age_to_online_state(age=501.0, good_max=30.0, warn_max=500.0) == "bad"


def test_age_to_online_state_two_level() -> None:
    assert age_to_online_state(age=0.5, good_max=1.0, warn_max=None) == "good"
    assert age_to_online_state(age=1.0, good_max=1.0, warn_max=None) == "good"
    assert age_to_online_state(age=1.1, good_max=1.0, warn_max=None) == "warn"


def test_compute_estop_dot_state_buckets() -> None:
    # brake dots depend on caller policy
    assert (
        compute_estop_dot_state(
            key="brk1_ok",
            value=True,
            taster=False,
            brake_ok_display=lambda raw: raw,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "good"
    )
    assert (
        compute_estop_dot_state(
            key="brk2_ok",
            value=False,
            taster=True,
            brake_ok_display=lambda raw: raw,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "bad"
    )

    # brk2kb_ok is raw
    assert (
        compute_estop_dot_state(
            key="brk2kb_ok",
            value=True,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "good"
    )
    assert (
        compute_estop_dot_state(
            key="brk2kb_ok",
            value=False,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "bad"
    )

    # cause keys: red when active
    assert (
        compute_estop_dot_state(
            key="master",
            value=True,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "bad"
    )
    assert (
        compute_estop_dot_state(
            key="master",
            value=False,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "good"
    )

    # ok keys: green when ok
    assert (
        compute_estop_dot_state(
            key="kw30_ok",
            value=True,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "good"
    )
    assert (
        compute_estop_dot_state(
            key="kw30_ok",
            value=False,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "bad"
    )

    # other keys: amber only when asserted
    assert (
        compute_estop_dot_state(
            key="pos_win",
            value=True,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        == "warn"
    )
    assert (
        compute_estop_dot_state(
            key="pos_win",
            value=False,
            taster=False,
            brake_ok_display=None,
            cause_keys=CAUSE,
            ok_keys=OK,
        )
        is None
    )


def test_compute_estop_dot_states_roundtrip() -> None:
    specs = [
        _Spec("brk1_ok", "dotBrk1"),
        _Spec("master", "dotMaster"),
        _Spec("kw30_ok", "dotKw30"),
        _Spec("pos_win", "dotPosWin"),
        _Spec("unused", None),
    ]
    bits = {"brk1_ok": True, "master": False, "kw30_ok": True, "pos_win": False}

    out = compute_estop_dot_states(
        bits=bits,
        taster=False,
        specs=specs,
        brake_ok_display=lambda raw: raw,
        cause_keys=CAUSE,
        ok_keys=OK,
    )
    assert out["dotBrk1"] == "good"
    assert out["dotMaster"] == "good"  # cause key false -> good
    assert out["dotKw30"] == "good"
    assert out["dotPosWin"] is None


def test_compute_header_estop_dot_states() -> None:
    out = compute_header_estop_dot_states(
        taster=True,
        ready=False,
        brk1_raw=True,
        brk2_raw=False,
        brake_ok_display=lambda raw: raw,
    )
    assert out["dotHdrFbt"] == "good"
    assert out["dotHdrReady"] == "warn"
    assert out["dotHdrBrake1"] == "good"
    assert out["dotHdrBrake2"] == "bad"
