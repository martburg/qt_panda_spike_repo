from __future__ import annotations

import pytest

from steuerung3d.apps.yellow.domain.estop_facts import (
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)
from steuerung3d.apps.yellow.engines.densi.engine import DenSiEngine
from steuerung3d.apps.yellow.engines.densi.types import EStopState
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame


def _cmd(*, vel: float, tick: int) -> CommandFrame:
    return CommandFrame(
        tick=tick,
        t_s=0.0,
        estop=False,
        fault=False,
        core_mode="IDLE",
        axes={"Anton": AxisSetpoint(enable=True, vel=float(vel))},
        lifetick_echo={"Anton": int(tick) & 0xFFFF},
    )


def _set_bits_ok_ready(engine: DenSiEngine) -> None:
    bits = engine._ensure_inj_bits()
    for k in list(bits.keys()):
        bits[k] = False
    for k in estop_ok_keys():
        bits[k] = True
    for k in estop_cause_keys():
        bits[k] = False
    bits["taster"] = True
    bits["schuetz"] = True
    bits["ready"] = True
    bits["brk1_ok"] = True
    bits["brk2_ok"] = True
    engine.inj_estop_word = int(encode_estop_word(bits))


@pytest.mark.integration
def test_cut_markers_latch_on_ok_chain_fault_edge() -> None:
    """Contract: OK-chain faults must latch/freeze CutPos/CutVel/CutTime.

    This covers the non-trip path: no explicit ESTOP1/2/master/... trip bit set,
    but one required OK bit drops.
    """
    eng = DenSiEngine.build_default(
        axis_ids=["Anton"],
        dt_s=0.1,
        normalize_pos_chain=lambda v: v,
        normalize_guider_range=lambda v: v,
        enforce_pos_chain=lambda v: v,
        enforce_guider_minmax=lambda v: v,
        lifetick_stale_after_ticks_active=50,
        lifetick_stale_after_ticks_idle=50,
    )
    eng.state.params.update({"VelMax": 2.0, "AccMove": 0.5, "UserMax": 300.0, "UserMin": 0.0})

    _set_bits_ok_ready(eng)

    # Focused test: bypass full boot workflow.
    eng.estate = EStopState.IDLE
    eng.state.estop = False
    eng.prev_estop_state = False

    # Arm live cut tracking (mimics HiP ReSync).
    eng.arm_cut_follow_live()

    # Baseline cut markers are updated from actual pos/vel in IDLE.
    ax = eng.state.axes["Anton"]
    ax.pos = 1.0
    ax.vel = 0.2
    eng.update_cut_follow_live()
    assert float(eng.state.params.get("CutPos", 0.0) or 0.0) == 1.0

    # Introduce an OK-chain fault (no trip causes asserted).
    bits = eng._ensure_inj_bits()
    bits["kw30_ok"] = False
    eng.inj_estop_word = int(encode_estop_word(bits))

    # Tick -> should enter E-Stop and latch cut markers.
    r = eng.step(frames=[_cmd(vel=2.0, tick=10)], now_ns=0)
    assert r.estop_edge is True

    latched_cutpos = float(eng.state.params.get("CutPos", 0.0) or 0.0)
    assert latched_cutpos == 1.0

    # Further ticks (still faulted) must not mutate CutPos.
    for tick in range(11, 15):
        eng.state.axes["Anton"].pos += 10.0
        r2 = eng.step(frames=[_cmd(vel=2.0, tick=tick)], now_ns=0)
        assert bool(r2.estop_bits.get("kw30_ok", True)) is False
        assert float(eng.state.params.get("CutPos", 0.0) or 0.0) == latched_cutpos
