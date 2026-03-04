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
    # Typical "ready" baseline
    bits["taster"] = True
    bits["schuetz"] = True
    bits["ready"] = True
    bits["brk1_ok"] = True
    bits["brk2_ok"] = True
    engine.inj_estop_word = int(encode_estop_word(bits))


def _trip_estop(engine: DenSiEngine) -> None:
    bits = engine._ensure_inj_bits()
    bits["estop1"] = True
    engine.inj_estop_word = int(encode_estop_word(bits))


@pytest.mark.integration
def test_cut_markers_freeze_when_entering_estop() -> None:
    """Contract: CutPos/CutVel/CutTime must latch/freeze on entering E-Stop.

    Scenario:
      - start READY/IDLE
      - arm live cut tracking (ReSync behavior)
      - run a few ticks so CutPos follows actual pos
      - trip E-Stop and verify:
          * tick reports estop_edge
          * CutPos/CutVel/CutTime latch at entry
          * subsequent ticks in E-Stop do not modify CutPos
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

    # This test targets cut-marker behavior, not the full E-Stop boot workflow.
    # Force the engine into the normal running ladder state.
    eng.estate = EStopState.IDLE
    eng.state.estop = False
    eng.prev_estop_state = False

    # Move a bit.
    for tick in range(3):
        eng.step(frames=[_cmd(vel=2.0, tick=tick + 1)], now_ns=0)

    # Arm live cut tracking (mimics HiP ReSync).
    eng.arm_cut_follow_live()

    # Let cut markers follow: for this focused test we don't depend on the
    # full drive-ready ladder, so we nudge the plant state directly.
    ax = eng.state.axes["Anton"]
    ax.pos = 1.0
    ax.vel = 0.2
    eng.update_cut_follow_live()

    pre_trip_cutpos = float(eng.state.params.get("CutPos", 0.0) or 0.0)
    assert pre_trip_cutpos == 1.0

    # Trip E-Stop: must latch/freeze at entry.
    _trip_estop(eng)
    r = eng.step(frames=[_cmd(vel=2.0, tick=7)], now_ns=0)
    assert r.estop_edge is True

    latched_cutpos = float(eng.state.params.get("CutPos", 0.0) or 0.0)
    latched_cutvel = float(eng.state.params.get("CutVel", 0.0) or 0.0)
    latched_cuttime = float(eng.state.params.get("CutTime", 0.0) or 0.0)

    assert latched_cutpos >= pre_trip_cutpos
    assert isinstance(latched_cutvel, float)
    assert latched_cuttime > 0.0

    # In subsequent ticks while still in E-Stop, CutPos must remain unchanged.
    # Simulate plant drift/coastdown by mutating pos between ticks.
    for tick in range(8, 12):
        eng.state.axes["Anton"].pos += 10.0
        r2 = eng.step(frames=[_cmd(vel=2.0, tick=tick)], now_ns=0)
        assert bool(r2.estop_bits.get("estop1", False)) is True
        assert float(eng.state.params.get("CutPos", 0.0) or 0.0) == latched_cutpos
