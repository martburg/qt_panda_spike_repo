from __future__ import annotations

import pytest

from steuerung3d.apps.yellow.domain.estop_facts import (
    encode_estop_word,
    estop_cause_keys,
    estop_ok_keys,
)
from steuerung3d.apps.yellow.engines.densi.engine import DenSiEngine
from steuerung3d.core.command_frame import AxisSetpoint, CommandFrame


def _arm_engine(engine: DenSiEngine) -> None:
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
    engine.brake_switch_s = 0.0
    engine.brake_handoff_grace_s = 0.0
    engine.inj_estop_word = int(encode_estop_word(bits))


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


@pytest.mark.integration
def test_densi_engine_plc_vel_cmd_loop() -> None:
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
    _arm_engine(eng)

    eng.state.params.update({"VelMax": 2.0, "AccMove": 0.5, "UserMax": 300.0, "UserMin": 0.0})

    for tick in range(5):
        eng.step(frames=[_cmd(vel=2.0, tick=tick + 1)], now_ns=0)

    ax = eng.state.axes["Anton"]
    assert ax.pos > 0.0
    assert ax.vel <= 0.5 + 1e-6
