from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

from steuerung3d.adapters.sim.axis_plant import SimAxisPlant
from steuerung3d.adapters.sim.device import SimDevice
from steuerung3d.common.timebase import Timebase
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.recording import JsonlReader
from steuerung3d.protocol.transport import InMemTransport

from steuerung3d.config.replay_player_config import load_replay_player_config


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Steuerung3D replay player (deterministic log replay)")
    p.add_argument("logfile", type=Path, help="Path to JSONL log file")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("configs/replay_player.toml"),
        help="Path to TOML config (default: configs/replay_player.toml)",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    cfg = load_replay_player_config(args.config)

    path = args.logfile
    r = JsonlReader(path)

    intents_by_tick: Dict[int, List] = defaultdict(list)
    telemetry_by_tick: Dict[int, TelemetrySnapshot] = {}
    command_by_tick: Dict[int, CommandFrame] = {}

    max_tick = 0
    for tick, intent in r.iter_intents():
        t = int(tick) if tick is not None else 0
        intents_by_tick[t].append(intent)

    for snap in r.iter_telemetry():
        telemetry_by_tick[snap.tick] = snap
        max_tick = max(max_tick, snap.tick)

    # Optional: deep debugging stream (command frames)
    if bool(cfg.replay.compare_command_frames):
        for cf in r.iter_command_frames():
            command_by_tick[cf.tick] = cf

    transport = InMemTransport()
    tb = Timebase(dt_s=float(cfg.app.dt_s))
    st = MachineState()

    # derive axis set from recorded telemetry
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

    device = SimDevice(SimAxisPlant())

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

    while st.tick < max_tick:
        current_tick = st.tick

        for intent in intents_by_tick.get(current_tick, []):
            transport.publish_intent(intent)

        eng.step_once()

        if last_snap is not None and last_snap.tick in telemetry_by_tick:
            ref = telemetry_by_tick[last_snap.tick]
            if not _telemetry_close(last_snap, ref, eps=float(cfg.replay.eps)):
                mismatches += 1
                print(f"[mismatch] tick={last_snap.tick}")

        if command_by_tick and last_cmd is not None and last_cmd.tick in command_by_tick:
            ref_cf = command_by_tick[last_cmd.tick]
            if not _command_frame_close(last_cmd, ref_cf, eps=float(cfg.replay.eps)):
                cmd_mismatches += 1
                print(f"[cmd mismatch] tick={last_cmd.tick}")

    if command_by_tick:
        print(f"Replay done. ticks={st.tick}, telem_mismatches={mismatches}, cmd_mismatches={cmd_mismatches}")
    else:
        print(f"Replay done. ticks={st.tick}, mismatches={mismatches}")
    return 0


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
