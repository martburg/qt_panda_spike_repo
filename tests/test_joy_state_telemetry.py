from __future__ import annotations

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.core_mode import CoreMode
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.intents import JoyStateUpdate
from steuerung3d.core.joy_state import JoyState
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.transport import InMemTransport


def test_joy_state_update_reaches_snapshot() -> None:
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    bus = InMemTransport()
    snaps: list[TelemetrySnapshot] = []

    bus.publish_intent(JoyStateUpdate(deadman=True, soll_speed=-0.75, selected_axes=("Anton",)))

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=bus.drain_intents,
        handle_intent=apply_intent,
        on_snapshot=snaps.append,
    )

    eng.step_once()
    assert len(snaps) == 1
    joy = snaps[0].joy
    assert joy.deadman is True
    assert joy.selected_axes == ("Anton",)
    assert joy.select_hip is True
    assert abs(joy.soll_speed - (-0.75)) < 1e-6


def test_joy_state_defaults_when_absent() -> None:
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    snaps: list[TelemetrySnapshot] = []

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=lambda: [],
        handle_intent=apply_intent,
        on_snapshot=snaps.append,
    )

    eng.step_once()
    assert len(snaps) == 1
    assert snaps[0].joy == JoyState()


def test_snapshot_includes_core_mode() -> None:
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    st.core_mode = CoreMode.ARMED
    snaps: list[TelemetrySnapshot] = []

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=lambda: [],
        handle_intent=apply_intent,
        on_snapshot=snaps.append,
    )

    eng.step_once()
    assert len(snaps) == 1
    assert snaps[0].core_mode == CoreMode.ARMED.value
