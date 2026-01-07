from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.recording import JsonlReader
from steuerung3d.protocol.transport import InMemTransport

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice

def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python -m apps.replay_player <logfile.jsonl>")
        return 2

    path = Path(sys.argv[1])
    r = JsonlReader(path)

    intents_by_tick: Dict[int, List] = defaultdict(list)
    telemetry_by_tick: Dict[int, TelemetrySnapshot] = {}
    command_by_tick: Dict[int, CommandFrame] = {}

    max_tick = 0
    for tick, intent in r.iter_intents():
        # if tick is missing, treat as tick 0
        t = int(tick) if tick is not None else 0
        intents_by_tick[t].append(intent)

    for snap in r.iter_telemetry():
        telemetry_by_tick[snap.tick] = snap
        max_tick = max(max_tick, snap.tick)

    # Optional: deep debugging stream (command frames)
    for cf in r.iter_command_frames():
        command_by_tick[cf.tick] = cf

    # Recreate a fresh core
    transport = InMemTransport()
    tb = Timebase(dt_s=0.01)
    st = MachineState()
    # v0.1: derive axis set from recorded telemetry (more robust than hardcoding X)
    if telemetry_by_tick:
        first = telemetry_by_tick[min(telemetry_by_tick.keys())]
        for axis_id in first.axes.keys():
            st.ensure_axis(axis_id)
    else:
        st.ensure_axis("X")

    last_snap: Optional[TelemetrySnapshot] = None
    last_cmd: Optional[CommandFrame] = None

    def on_snapshot(snap: TelemetrySnapshot) -> None:
        nonlocal last_snap
        last_snap = snap

    def on_command_frame(cf: CommandFrame) -> None:
        nonlocal last_cmd
        last_cmd = cf

    plant = SimAxisPlant()
    device = SimDevice(plant)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=transport.drain_intents,
        handle_intent=apply_intent,
        device_step=device.step,
        on_command_frame=on_command_frame,
        on_snapshot=on_snapshot,
    )

    mismatches = 0
    cmd_mismatches = 0

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

        # Deep debugging: compare command frames if present in the log.
        if last_cmd is not None and last_cmd.tick in command_by_tick:
            ref_cf = command_by_tick[last_cmd.tick]
            if not _command_frame_close(last_cmd, ref_cf):
                cmd_mismatches += 1
                print(f"[cmd mismatch] tick={last_cmd.tick}")

    if command_by_tick:
        print(f"Replay done. ticks={st.tick}, telem_mismatches={mismatches}, cmd_mismatches={cmd_mismatches}")
    else:
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


def _command_frame_close(a: CommandFrame, b: CommandFrame, eps: float = 1e-9) -> bool:
    if a.tick != b.tick or a.mode != b.mode or a.estop != b.estop or a.fault != b.fault:
        return False
    if set(a.axes.keys()) != set(b.axes.keys()):
        return False
    for k in a.axes:
        aa = a.axes[k]
        bb = b.axes[k]
        if aa.enable != bb.enable:
            return False
        if abs(aa.vel - bb.vel) > eps:
            return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
