from __future__ import annotations

from typing import Sequence

from steuerung3d.apps.yellow.engines.hip.engine import HipEngine
from steuerung3d.core.intents import EchoLifeTick, Intent
from steuerung3d.core.telemetry import AxisTelemetry, TelemetrySnapshot


def _single_echo(intents: Sequence[Intent]) -> EchoLifeTick:
    echoes = [intent for intent in intents if isinstance(intent, EchoLifeTick)]
    assert len(echoes) == 1
    return echoes[0]


def _snap() -> TelemetrySnapshot:
    return TelemetrySnapshot(
        tick=1,
        t_s=0.01,
        core_mode="IDLE",
        estop=False,
        fault=False,
        axes={
            "Anton": AxisTelemetry(pos=0.0, vel=0.0, enabled=False, fault=False, device_tick=101),
            "Debby": AxisTelemetry(pos=0.0, vel=0.0, enabled=False, fault=False, device_tick=202),
        },
    )


def test_hip_echoes_only_selected_axis() -> None:
    intents, echo_map = HipEngine._compute_lifetick_echo_intents(
        snap=_snap(),
        hip_id="hip_anton",
        selected_axis="Anton",
        last_lifetick_echo_sent={},
    )
    echo = _single_echo(intents)
    assert echo.axis_id == "Anton"
    assert echo.value == 101
    assert echo_map == {"Anton": 101}


def test_hip_emits_no_echo_without_selected_axis() -> None:
    intents, echo_map = HipEngine._compute_lifetick_echo_intents(
        snap=_snap(),
        hip_id="hip_anton",
        selected_axis="",
        last_lifetick_echo_sent={},
    )
    assert intents == []
    assert echo_map == {}
