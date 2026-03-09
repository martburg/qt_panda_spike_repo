from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from steuerung3d.apps.joy2intent.config import load_joy2intent_config
from steuerung3d.apps.joy2intent.mapping import JoyBindings, JoyLimits, JoyRig, synthesize_intents
from steuerung3d.apps.joy2intent.state import JoyState
from steuerung3d.core.control_context import ControlContext
from steuerung3d.core.intents import EnableAxis, JogWinch, JoyStateUpdate, LocalAxisManualRequest
from steuerung3d.protocol.raw_controls import RawControls


@dataclass(frozen=True)
class _JoyReport:
    axes: Sequence[float]
    buttons: Sequence[int]


class _TestJoyState(JoyState):
    pass


def _rc(*, axes: list[float] | None = None, pressed: Iterable[int] = ()) -> _JoyReport:
    axes = axes or []
    btns = [0] * 16
    for i in pressed:
        if 0 <= i < len(btns):
            btns[i] = 1
    _ = RawControls(t_ns=123, src="test", axes=axes, buttons=btns)
    return _JoyReport(axes=tuple(axes), buttons=tuple(btns))


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


def _lim_from_config(tmp_path: Path) -> JoyLimits:
    """Load the canonical joy2intent service config and override max_winch_mps.

    This test deliberately forces a non-default value so we can detect accidental
    fallback to hard-coded defaults.
    """
    src = Path("configs/services/joy2intent.toml")
    raw_text = src.read_text(encoding="utf-8")

    # Force an obviously-non-default limit.
    raw_text = re.sub(
        r"(?m)^max_winch_mps\s*=\s*[0-9.]+\s*$",
        "max_winch_mps = 1.234",
        raw_text,
    )

    cfg_path = tmp_path / "joy2intent.test.toml"
    cfg_path.write_text(raw_text, encoding="utf-8")

    cfg = load_joy2intent_config(cfg_path)

    # Sanity check that we really used the overridden value.
    assert abs(cfg.max_winch_mps - 1.234) < 1e-12
    assert cfg.fine_scale > 0.0

    return JoyLimits(
        max_winch_mps=float(cfg.max_winch_mps),
        fine_scale=float(cfg.fine_scale),
    )


def test_single_winch_without_explicit_select_emits_no_enable_or_jog(tmp_path: Path) -> None:
    st = _TestJoyState()
    bind = JoyBindings(
        axes={"manual_jog": 1},
        buttons={"deadman": 5, "select_hip": 3},
        select_buttons=[0, 1, 2, 3],
        invert={"manual_jog": False},
        deadzone=0.05,
        expo=1.5,
    )
    rig = JoyRig(winches=["Anton"])
    lim = _lim_from_config(tmp_path)

    rc = _rc(axes=[0.0, 0.8], pressed=(5, 3))
    intents = synthesize_intents(st, rc, bind, rig, lim)

    assert not any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in intents)
    assert not any(
        isinstance(i, JogWinch) and i.winch_id == "Anton" and i.rate > 0.0 for i in intents
    )


def test_setup_manual_multi_select_targets_all_selected_lanes(tmp_path: Path) -> None:
    st = _TestJoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim_from_config(tmp_path)

    # deadman + select 0 & 2, manual_jog axis positive
    rc = _rc(axes=[0.0, 0.6], pressed=(5, 0, 2))
    intents = synthesize_intents(st, rc, bind, rig, lim)

    # Multi-lane selection: every selected lane should receive enable/jog intents.
    enables = [i for i in intents if isinstance(i, EnableAxis) and i.enable]
    jugs = [i for i in intents if isinstance(i, JogWinch)]

    assert {e.axis_id for e in enables} == {"Anton", "Cecil"}
    assert {j.winch_id for j in jugs} == {"Anton", "Cecil"}
    joy = next(i for i in intents if isinstance(i, JoyStateUpdate))
    assert set(joy.selected_axes) == {"Anton", "Cecil"}

    # Rate should be scaled by max_winch_mps
    for j in jugs:
        assert j.rate > 0
        assert j.rate <= lim.max_winch_mps


def test_deadman_release_disables_previously_enabled_winches(tmp_path: Path) -> None:
    st = _TestJoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim_from_config(tmp_path)

    # First tick: enable Anton (select 0) with deadman
    rc1 = _rc(axes=[0.0, 0.3], pressed=(5, 0))
    intents1 = synthesize_intents(st, rc1, bind, rig, lim)
    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in intents1)

    # Next tick: deadman released -> should disable Anton
    rc2 = _rc(axes=[0.0, 0.3], pressed=(0,))  # selection still held, but deadman off
    intents2 = synthesize_intents(st, rc2, bind, rig, lim)

    disables = [i for i in intents2 if isinstance(i, EnableAxis) and (not i.enable)]
    assert {d.axis_id for d in disables} == {"Anton"}


def test_deadman_hold_repeats_enable_keepalive(tmp_path: Path) -> None:
    """EnableAxis(True) must be re-emitted while deadman is held.

    This acts as a keepalive so that if the first EnableAxis was dropped by
    core safety gating (e.g. core still FAULT/IDLE during bring-up), the axis
    will still become enabled once the core transitions to LIVE.
    """

    st = _TestJoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim_from_config(tmp_path)

    rc = _rc(axes=[0.0, 0.3], pressed=(5, 0))
    intents1 = synthesize_intents(st, rc, bind, rig, lim)
    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in intents1)

    # Same inputs, next tick: keepalive enable should still be present.
    intents2 = synthesize_intents(st, rc, bind, rig, lim)
    assert any(isinstance(i, EnableAxis) and i.axis_id == "Anton" and i.enable for i in intents2)


def test_fine_button_scales_rate(tmp_path: Path) -> None:
    st = _TestJoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim_from_config(tmp_path)

    # same stick, same selection, compare with/without fine
    rc_fast = _rc(axes=[0.0, 1.0], pressed=(5, 0))
    intents_fast = synthesize_intents(st, rc_fast, bind, rig, lim)
    rate_fast = next(
        i.rate for i in intents_fast if isinstance(i, JogWinch) and i.winch_id == "Anton"
    )

    rc_fine = _rc(axes=[0.0, 1.0], pressed=(5, 0, 7))
    intents_fine = synthesize_intents(st, rc_fine, bind, rig, lim)
    rate_fine = next(
        i.rate for i in intents_fine if isinstance(i, JogWinch) and i.winch_id == "Anton"
    )

    assert rate_fine == rate_fast * lim.fine_scale


def test_contextual_independent_axes_emits_local_axis_manual_request(tmp_path: Path) -> None:
    st = _TestJoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim_from_config(tmp_path)
    rc = _rc(axes=[0.0, 0.6], pressed=(5, 0, 2))
    ctx = ControlContext(mode="independent_axes", input_mapping="axis_rate", motion_enabled=True)

    intents = synthesize_intents(st, rc, bind, rig, lim, control_context=ctx)

    req = next(i for i in intents if isinstance(i, LocalAxisManualRequest))
    assert set(req.axis_ids) == {"Anton", "Cecil"}
    assert req.enable is True
    assert req.rate > 0.0
    assert not any(isinstance(i, EnableAxis) and i.enable for i in intents)
    assert not any(isinstance(i, JogWinch) for i in intents)


def test_contextual_independent_axes_deadman_release_emits_only_local_stop(tmp_path: Path) -> None:
    st = _TestJoyState()
    bind = _bind()
    rig = _rig()
    lim = _lim_from_config(tmp_path)
    ctx = ControlContext(mode="independent_axes", input_mapping="axis_rate", motion_enabled=True)

    intents1 = synthesize_intents(
        st, _rc(axes=[0.0, 0.4], pressed=(5, 0)), bind, rig, lim, control_context=ctx
    )
    assert any(isinstance(i, LocalAxisManualRequest) and i.enable for i in intents1)

    intents2 = synthesize_intents(
        st, _rc(axes=[0.0, 0.4], pressed=(0,)), bind, rig, lim, control_context=ctx
    )
    req = next(i for i in intents2 if isinstance(i, LocalAxisManualRequest))
    assert req.enable is False
    assert req.rate == 0.0
    assert req.axis_ids == ("Anton",)
    assert not any(isinstance(i, EnableAxis) for i in intents2)
    assert not any(isinstance(i, JogWinch) for i in intents2)
