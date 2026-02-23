from __future__ import annotations

from typing import Iterable

from steuerung3d.apps.joy2intent.mapping import JoyBindings, JoyLimits, JoyRig, synthesize_intents
from steuerung3d.apps.joy2intent.state import JoyState
from steuerung3d.core.intents import EnableAxis, JogWinch
from steuerung3d.protocol.raw_controls import RawControls


def _rc(*, axes: list[float] | None = None, pressed: Iterable[int] = ()) -> RawControls:
    axes = axes or []
    btns = [0] * 16
    for i in pressed:
        if 0 <= i < len(btns):
            btns[i] = 1
    return RawControls(t_ns=123, src="test", axes=axes, buttons=btns)


def _bind() -> JoyBindings:
    return JoyBindings(
        axes={"manual_jog": 1},
        buttons={"deadman": 5, "fine": 7},
        select_buttons=[0, 1, 2, 3],
        invert={"manual_jog": False},
        deadzone=0.05,
        expo=1.5,
    )


def _rig() -> JoyRig:
    return JoyRig(winches=["Anton", "Debby", "Cecil", "Burt"])


def _lim() -> JoyLimits:
    return JoyLimits(max_winch_mps=0.3, fine_scale=0.2)


def test_single_winch_select_hip_fallback_emits_enable_and_jog() -> None:
    st = JoyState()
    bind = JoyBindings(
        axes={"manual_jog": 1},
        buttons={"deadman": 5, "select_hip": 3},
        select_buttons=[0, 1, 2, 3],
        invert={"manual_jog": False},
        deadzone=0.05,
        expo=1.5,
    )
    rig = JoyRig(winches=["Anton"])
    lim = _lim()

    rc = _rc(axes=[0.0, 0.8], pressed=(5, 3))
    intents = synthesize_intents(st, rc, bind, rig, lim)

    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in intents)
    assert any(isinstance(i, JogWinch) and i.winch_id == "Anton" and i.rate > 0.0 for i in intents)


def test_setup_manual_multi_select_targets_single_lowest_index() -> None:
    st = JoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim()

    # deadman + select 0 & 2, manual_jog axis positive
    rc = _rc(axes=[0.0, 0.6], pressed=(5, 0, 2))
    intents = synthesize_intents(st, rc, bind, rig, lim)

    # Legacy arbitration: even if multiple select buttons are held, only one
    # winch is targeted (lowest index wins).
    enables = [i for i in intents if isinstance(i, EnableAxis) and i.enable]
    jugs = [i for i in intents if isinstance(i, JogWinch)]

    assert {e.axis_id for e in enables} == {"Anton"}
    assert {j.winch_id for j in jugs} == {"Anton"}

    # Rate should be scaled by max_winch_mps
    for j in jugs:
        assert j.rate > 0
        assert j.rate <= lim.max_winch_mps


def test_deadman_release_disables_previously_enabled_winches() -> None:
    st = JoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim()

    # First tick: enable Anton (select 0) with deadman
    rc1 = _rc(axes=[0.0, 0.3], pressed=(5, 0))
    intents1 = synthesize_intents(st, rc1, bind, rig, lim)
    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in intents1)

    # Next tick: deadman released -> should disable Anton
    rc2 = _rc(axes=[0.0, 0.3], pressed=(0,))  # selection still held, but deadman off
    intents2 = synthesize_intents(st, rc2, bind, rig, lim)

    disables = [i for i in intents2 if isinstance(i, EnableAxis) and (not i.enable)]
    assert {d.axis_id for d in disables} == {"Anton"}


def test_fine_button_scales_rate() -> None:
    st = JoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim()

    # same stick, same selection, compare with/without fine
    rc_fast = _rc(axes=[0.0, 1.0], pressed=(5, 0))
    intents_fast = synthesize_intents(st, rc_fast, bind, rig, lim)
    rate_fast = next(i.rate for i in intents_fast if isinstance(i, JogWinch) and i.winch_id == "Anton")

    rc_fine = _rc(axes=[0.0, 1.0], pressed=(5, 0, 7))
    intents_fine = synthesize_intents(st, rc_fine, bind, rig, lim)
    rate_fine = next(i.rate for i in intents_fine if isinstance(i, JogWinch) and i.winch_id == "Anton")

    assert rate_fine == rate_fast * lim.fine_scale
