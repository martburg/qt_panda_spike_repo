from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from steuerung3d.config.log_viewer_config import LogViewerConfig, load_log_viewer_config
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.telemetry import TelemetrySnapshot
from steuerung3d.protocol.recording import JsonlReader


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Steuerung3D log viewer (commanded vs measured per tick)"
    )
    p.add_argument("logfile", type=Path, help="Path to JSONL session log")
    p.add_argument(
        "--config",
        type=Path,
        default=Path("configs/log_viewer.toml"),
        help="Path to TOML config (default: configs/log_viewer.toml)",
    )
    p.add_argument("--from-tick", type=int, default=None, help="First tick to show (inclusive)")
    p.add_argument("--to-tick", type=int, default=None, help="Last tick to show (inclusive)")
    p.add_argument("--every", type=int, default=None, help="Only show every Nth tick (after filtering)")
    p.add_argument(
        "--axes",
        type=str,
        default=None,
        help="Comma-separated axis ids to display (default: all in log)",
    )
    p.add_argument("--no-pos", action="store_true", help="Do not print measured position columns")
    p.add_argument("--csv", dest="as_csv", action="store_true", help="Output CSV instead of table")
    p.add_argument("--show-intents", action="store_true", help="Include intent count per tick")
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    cfg: LogViewerConfig = load_log_viewer_config(args.config)

    path = args.logfile
    r = JsonlReader(path)

    telem_by_tick: Dict[int, TelemetrySnapshot] = {}
    cmd_by_tick: Dict[int, CommandFrame] = {}
    intent_count_by_tick: Dict[int, int] = {}

    for tick, _intent in r.iter_intents():
        t = int(tick) if tick is not None else 0
        intent_count_by_tick[t] = intent_count_by_tick.get(t, 0) + 1

    for snap in r.iter_telemetry():
        telem_by_tick[snap.tick] = snap

    for cf in r.iter_command_frames():
        cmd_by_tick[cf.tick] = cf

    if not telem_by_tick and not cmd_by_tick:
        print("No telemetry or command_frame records found.")
        return 2

    all_ticks = sorted(set(telem_by_tick.keys()) | set(cmd_by_tick.keys()))
    if not all_ticks:
        print("No records found.")
        return 2

    # Resolve tick range: CLI overrides config
    tick_from = args.from_tick if args.from_tick is not None else cfg.view.from_tick
    tick_to = args.to_tick if args.to_tick is not None else cfg.view.to_tick
    every = args.every if args.every is not None else cfg.view.every

    # Determine axes list
    axes: List[str]
    if args.axes:
        axes = [a.strip() for a in args.axes.split(",") if a.strip()]
    elif cfg.view.axes:
        axes = list(cfg.view.axes)
    else:
        # derive from first telemetry/command record
        sample_axes = set()
        if telem_by_tick:
            sample_axes |= set(next(iter(telem_by_tick.values())).axes.keys())
        if cmd_by_tick:
            sample_axes |= set(next(iter(cmd_by_tick.values())).axes.keys())
        axes = sorted(sample_axes) if sample_axes else ["X"]

    rows = []
    for t in all_ticks:
        if tick_from is not None and t < tick_from:
            continue
        if tick_to is not None and t > tick_to:
            continue
        rows.append(t)

    if every and every > 1:
        rows = rows[::every]

    show_pos = bool(cfg.view.show_pos) and (not args.no_pos)

    if args.as_csv:
        _print_csv(rows, axes, telem_by_tick, cmd_by_tick, intent_count_by_tick, show_pos, args.show_intents)
    else:
        _print_table(rows, axes, telem_by_tick, cmd_by_tick, intent_count_by_tick, show_pos, args.show_intents)

    return 0


def _print_csv(
    ticks: Sequence[int],
    axes: Sequence[str],
    telem_by_tick: Dict[int, TelemetrySnapshot],
    cmd_by_tick: Dict[int, CommandFrame],
    intent_count_by_tick: Dict[int, int],
    show_pos: bool,
    show_intents: bool,
) -> None:
    header = ["tick", "t_s", "core_mode", "estop", "fault"]
    if show_intents:
        header.append("intents")
    for a in axes:
        header += [f"cmd.{a}.enable", f"cmd.{a}.vel", f"meas.{a}.enable", f"meas.{a}.vel"]
        if show_pos:
            header.append(f"meas.{a}.pos")

    w = csv.writer(_stdout())
    w.writerow(header)

    for t in ticks:
        snap = telem_by_tick.get(t)
        cf = cmd_by_tick.get(t)

        # Prefer telemetry for shared fields; fallback to command frame.
        t_s = snap.t_s if snap else (cf.t_s if cf else 0.0)
        mode = snap.core_mode if snap else (cf.core_mode if cf else "")
        estop = snap.estop if snap else (cf.estop if cf else False)
        fault = snap.fault if snap else (cf.fault if cf else False)

        row = [t, f"{t_s:.6f}", mode, int(estop), int(fault)]
        if show_intents:
            row.append(intent_count_by_tick.get(t, 0))

        for a in axes:
            c = cf.axes.get(a) if cf else None
            m = snap.axes.get(a) if snap else None
            row += [
                (int(c.enable) if c else ""),
                (f"{c.vel:.6f}" if c else ""),
                (int(m.enabled) if m else ""),
                (f"{m.vel:.6f}" if m else ""),
            ]
            if show_pos:
                row.append(f"{m.pos:.6f}" if m else "")
        w.writerow(row)


def _print_table(
    ticks: Sequence[int],
    axes: Sequence[str],
    telem_by_tick: Dict[int, TelemetrySnapshot],
    cmd_by_tick: Dict[int, CommandFrame],
    intent_count_by_tick: Dict[int, int],
    show_pos: bool,
    show_intents: bool,
) -> None:
    # Simple fixed-width table (no external deps).
    cols = ["tick", "t_s", "core_mode", "E", "F"]
    if show_intents:
        cols.append("I")
    for a in axes:
        cols += [f"{a}:cEn", f"{a}:cVel", f"{a}:mEn", f"{a}:mVel"]
        if show_pos:
            cols.append(f"{a}:mPos")

    def fmt_bool(b: bool) -> str:
        return "1" if b else "0"

    lines: List[List[str]] = []
    for t in ticks:
        snap = telem_by_tick.get(t)
        cf = cmd_by_tick.get(t)

        t_s = snap.t_s if snap else (cf.t_s if cf else 0.0)
        mode = snap.core_mode if snap else (cf.core_mode if cf else "")
        estop = snap.estop if snap else (cf.estop if cf else False)
        fault = snap.fault if snap else (cf.fault if cf else False)

        row = [str(t), f"{t_s:.3f}", mode, fmt_bool(estop), fmt_bool(fault)]
        if show_intents:
            row.append(str(intent_count_by_tick.get(t, 0)))

        for a in axes:
            c = cf.axes.get(a) if cf else None
            m = snap.axes.get(a) if snap else None
            row += [
                (fmt_bool(c.enable) if c else ""),
                (f"{c.vel:.3f}" if c else ""),
                (fmt_bool(m.enabled) if m else ""),
                (f"{m.vel:.3f}" if m else ""),
            ]
            if show_pos:
                row.append(f"{m.pos:.3f}" if m else "")
        lines.append(row)

    widths = [len(c) for c in cols]
    for row in lines:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))

    def join_row(row: Sequence[str]) -> str:
        return " ".join(cell.rjust(widths[i]) for i, cell in enumerate(row))

    print(join_row(cols))
    print(" ".join("-" * w for w in widths))
    for row in lines:
        print(join_row(row))


def _stdout():
    import sys
    return sys.stdout


if __name__ == "__main__":
    raise SystemExit(main())
