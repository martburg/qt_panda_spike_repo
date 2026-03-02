from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.recording import JsonlReader
from steuerung3d.protocol.transport import InMemTransport


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m apps.replay_player <logfile.jsonl>")
        return 2

    path = Path(sys.argv[1])
    r = JsonlReader(path)

    intents_by_tick: Dict[int, List] = defaultdict(list)
    telemetry_by_tick: Dict[int, TelemetrySnapshot] = {}

    max_tick = 0
    for tick, intent in r.iter_intents():
        # if tick is missing, treat as tick 0
        t = int(tick) if tick is not None else 0
        intents_by_tick[t].append(intent)

    for snap in r.iter_telemetry():
        telemetry_by_tick[snap.tick] = snap
        max_tick = max(max_tick, snap.tick)

    # Recreate a fresh core
    transport = InMemTransport()
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    st.ensure_axis("X")  # v0.1: we assume X exists; later: load config

    last_snap: Optional[TelemetrySnapshot] = None

    def on_snapshot(snap: TelemetrySnapshot) -> None:
        nonlocal last_snap
        last_snap = snap

    plant = SimAxisPlant()
    device = SimDevice(plant)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_snapshot=on_snapshot,
    )

    mismatches = 0

    # Deterministic replay loop:
    # intents are injected at the *start* of step when state.tick == recorded_tick
    while st.tick < max_tick:
        current_tick = st.tick

        for intent in intents_by_tick.get(current_tick, []):
            transport.publish_intent(intent)

        eng.step_once()

        # compare after step (snap tick == st.tick)
        if last_snap is not None and last_snap.tick in telemetry_by_tick:
            ref = telemetry_by_tick[last_snap.tick]
            if not _telemetry_close(last_snap, ref):
                mismatches += 1
                print(f"[mismatch] tick={last_snap.tick}")

    print(f"Replay done. ticks={st.tick}, mismatches={mismatches}")
    return 0


def _plant_integrate_x(state: MachineState, dt: float) -> None:
    # v0.1: same "plant" used in dev_stack: integrate vel into pos
    ax = state.axes.get("X")
    if ax is None:
        return
    ax.pos += ax.vel * dt


def _telemetry_close(a: TelemetrySnapshot, b: TelemetrySnapshot, eps: float = 1e-9) -> bool:
    if a.tick != b.tick or a.mode != b.mode or a.estop != b.estop or a.fault != b.fault:
        return False
    if set(a.axes.keys()) != set(b.axes.keys()):
        return False
    for k in a.axes:
        aa = a.axes[k]
        bb = b.axes[k]
        if aa.enabled != bb.enabled or aa.fault != bb.fault:
            return False
        if abs(aa.pos - bb.pos) > eps:
            return False
        if abs(aa.vel - bb.vel) > eps:
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
