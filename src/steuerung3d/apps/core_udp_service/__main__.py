from __future__ import annotations

import time
import logging

import argparse
import signal
from typing import Tuple, List

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot, apply_measured_snapshot
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.udp_channels import (
    UdpIntentIn, UdpTelemetryOut,
    UdpTelemetryIn, UdpCommandOut,
)

log = logging.getLogger("core_udp_service")


def _show_fatal_modal(msg: str, *, title: str = "Steuerung3D – Core") -> None:
    """Best-effort modal error dialog (Windows-friendly). Falls back to stderr."""
    try:
        import tkinter as _tk
        from tkinter import messagebox as _mb
        r = _tk.Tk()
        r.withdraw()
        _mb.showerror(title, msg)
        try:
            r.destroy()
        except Exception:
            pass
    except Exception:
        # Headless or tkinter unavailable
        pass
    try:
        import sys as _sys
        print(msg, file=_sys.stderr)
    except Exception:
        pass


def _fatal(msg: str) -> int:
    _show_fatal_modal(msg)
    log.error(msg)
    return 2


def _parse_hostport(s: str, default_host: str = "127.0.0.1") -> Tuple[str, int]:
    s = (s or "").strip()
    if not s:
        raise ValueError("empty host:port")
    if s.count(":") == 0:
        return (default_host, int(s))
    host, port_s = s.rsplit(":", 1)
    host = host.strip() or default_host
    return (host, int(port_s))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    ap.add_argument("--dt", type=float, default=0.02, help="Core tick (s)")
    ap.add_argument(
        "--axis",
        action="append",
        # Important: for action='append', argparse will *append to the default*.
        # Using a non-empty default would silently inject an extra axis (e.g. 'X')
        # and break strict per-axis routing.
        default=[],
        help="Axis ids to initialize in core state (repeatable). Example: --axis Anton --axis Debby",
    )
    ap.add_argument(
        "--dev-cmd-target",
        action="append",
        default=[],
        help=(
            "Device CommandOut target(s) as host:port. Repeatable. "
            "If not provided, defaults to 127.0.0.1:52001. "
            "One target per axis (no broadcast)."
        ),
    )
    ap.add_argument(
        "--dev-cmd-base",
        default=None,
        help="Convenience: base port for Device CommandOut targets (e.g. 52001).",
    )
    ap.add_argument(
        "--dev-cmd-count",
        type=int,
        default=0,
        help="Convenience: number of Device CommandOut targets to generate from base port.",
    )

    ap.add_argument(
        "--dev-telem-in",
        default="127.0.0.1:52002",
        help=(
            "Device TelemetryIn bind host:port (default 127.0.0.1:52002). "
            "Tip: choose a port that does not overlap your --dev-cmd-base..range."
        ),
    )

    # UI telemetry targets (one HiP per axis; no broadcast)
    ap.add_argument(
        "--ui-telem-target",
        action="append",
        default=[],
        help=(
            "UI TelemetryOut target(s) as host:port. Repeatable. "
            "If not provided, defaults to 127.0.0.1:51002. "
            "Strict mode: one target per axis (no broadcast)."
        ),
    )
    ap.add_argument(
        "--ui-telem-base",
        default=None,
        help="Convenience: base port for UI TelemetryOut broadcast (e.g. 51002).",
    )
    ap.add_argument(
        "--ui-telem-count",
        type=int,
        default=0,
        help="Convenience: number of UI TelemetryOut targets to generate from base port.",
    )
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log.info("log level = %s", args.log_level.upper())

    # --- UDP endpoints ---
    op_intent_in = UdpIntentIn.bind(("127.0.0.1", 51001))

    # UI telemetry targets
    ui_telem_targets: List[Tuple[str, int]] = []
    for s in args.ui_telem_target:
        ui_telem_targets.append(_parse_hostport(s))
    if args.ui_telem_base is not None and int(args.ui_telem_count) > 0:
        base = int(str(args.ui_telem_base).strip())
        for i in range(int(args.ui_telem_count)):
            ui_telem_targets.append(("127.0.0.1", base + i))
    if not ui_telem_targets:
        ui_telem_targets = [("127.0.0.1", 51002)]
    op_telem_outs = [UdpTelemetryOut.connect(t) for t in ui_telem_targets]

    dev_telem_bind = _parse_hostport(args.dev_telem_in)
    dev_telem_in = UdpTelemetryIn.bind(dev_telem_bind)

    # Device command broadcast targets (N DenSi apps each binding a unique command port)
    dev_cmd_targets: List[Tuple[str, int]] = []
    for s in args.dev_cmd_target:
        dev_cmd_targets.append(_parse_hostport(s))

    if args.dev_cmd_base is not None and int(args.dev_cmd_count) > 0:
        base = int(str(args.dev_cmd_base).strip())
        for i in range(int(args.dev_cmd_count)):
            dev_cmd_targets.append(("127.0.0.1", base + i))

        # Guard against accidental port overlap (common on Windows).
        if dev_telem_bind[0] == "127.0.0.1" and dev_telem_bind[1] in range(base, base + int(args.dev_cmd_count)):
            return _fatal(
                f"dev telemetry bind port {dev_telem_bind[1]} overlaps dev-cmd ports {base}..{base + int(args.dev_cmd_count) - 1}. "
                f"Pick a different --dev-telem-in (e.g. 127.0.0.1:{base + 100}) or shift --dev-cmd-base."
            )

    if not dev_cmd_targets:
        # Default only for single-axis convenience. Multi-axis requires explicit per-axis targets.
        if len([a for a in args.axis if a and str(a).strip()]) <= 1:
            dev_cmd_targets = [("127.0.0.1", 52001)]
        else:
            dev_cmd_targets = []

    dev_cmd_outs = [UdpCommandOut.connect(t) for t in dev_cmd_targets]

    stats = {
        "intents_in": 0,
        "dev_telem_in": 0,
        "ui_telem_out": 0,
        "cmd_out": 0,
    }
    last_seen = {
        "intent_ts": None,
        "dev_telem_ts": None,
        "ui_telem_ts": None,
        "cmd_ts": None,
    }
    t0 = time.monotonic()
    t_last_report = t0

    log.info("=== core_udp_service starting ===")
    log.info("Operator: IntentIn  bind=%s", ("127.0.0.1", 51001))
    if len(ui_telem_targets) == 1:
        log.info("Operator: TelemetryOut target=%s", ui_telem_targets[0])
    else:
        log.info("Operator: TelemetryOut targets=%s", ui_telem_targets)
    if len(dev_cmd_targets) == 1:
        log.info("Device:   CommandOut target=%s", dev_cmd_targets[0])
    else:
        log.info("Device:   CommandOut targets=%s", dev_cmd_targets)
    log.info("Device:   TelemetryIn bind=%s", dev_telem_bind)

    # --- core state ---
    tb = Timebase(dt_s=args.dt)
    log.info("timebase dt = %.4fs", tb.dt_s)

    st = MachineState()
    axis_ids = [a.strip() for a in args.axis if a and a.strip()]
    if not axis_ids:
        axis_ids = ["X"]

    # Track last device-scoped values so UI telemetry can be axis-pinned
    # (each DenSi/PLC reports only its own params/estop word).
    last_dev_params_by_axis: dict[str, dict[str, float]] = {}
    last_dev_estop_word_by_axis: dict[str, int] = {}
    last_dev_param_edit_active_by_axis: dict[str, bool] = {}
    last_dev_param_edit_group_by_axis: dict[str, str] = {}

    # Per-axis param commit state (comes from DenSi/PLC telemetry). Without this cache,
    # in multi-axis mode the last received device snapshot would overwrite the commit
    # fields, causing other HiPs to time out while waiting for their own commit ack.
    last_dev_param_commit_req_id_by_axis: dict[str, str] = {}
    last_dev_param_commit_group_by_axis: dict[str, str] = {}
    last_dev_param_commit_status_by_axis: dict[str, str] = {}
    last_dev_param_commit_age_ticks_by_axis: dict[str, int] = {}
    last_dev_param_commit_unmatched_by_axis: dict[str, list[str]] = {}

    # Enforce uniqueness while preserving order; duplicates are almost always
    # a configuration mistake (and are disastrous with strict per-axis routing).
    seen = set()
    dupes = []
    uniq: List[str] = []
    for a in axis_ids:
        k = a
        if k in seen:
            dupes.append(k)
            continue
        seen.add(k)
        uniq.append(k)
    if dupes:
        return _fatal(
            "Duplicate --axis entries are not allowed (strict per-axis routing).\n\n"
            f"Axes provided: {axis_ids}\n"
            f"Duplicates: {sorted(set(dupes))}"
        )
    axis_ids = uniq
    # --- strict per-axis device command routing ---
    # We do NOT support broadcast device commands, because PLC code is frozen.
    if len(axis_ids) > 1:
        if len(dev_cmd_targets) != len(axis_ids):
            msg = (
                "Multi-axis run requires one --dev-cmd-target per axis (no broadcast).\n\n"
                f"Axes ({len(axis_ids)}): {', '.join(axis_ids)}\n"
                f"Targets provided ({len(dev_cmd_targets)}): {dev_cmd_targets}\n\n"
                "Fix: provide N targets, e.g.\n"
                "  --dev-cmd-target 172.16.17.1:50010 --dev-cmd-target 172.16.17.2:50010 ...\n"
                "or use a local sim range, e.g.\n"
                f"  --dev-cmd-base 52001 --dev-cmd-count {len(axis_ids)}\n\n"
                "Note: --dev-telem-in must NOT overlap the dev-cmd port range."
            )
            return _fatal(msg)
    else:
        # single-axis: ensure exactly one target
        if len(dev_cmd_targets) != 1:
            msg = (
                "Single-axis run requires exactly one --dev-cmd-target.\n\n"
                f"Axis: {axis_ids[0] if axis_ids else 'X'}\n"
                f"Targets provided ({len(dev_cmd_targets)}): {dev_cmd_targets}"
            )
            return _fatal(msg)

    # Map axis_id -> CommandOut transport (order matters).
    axis_cmd_outs = {axis_id: dev_cmd_outs[i] for i, axis_id in enumerate(axis_ids)}

    # --- strict per-axis UI telemetry routing ---
    if len(axis_ids) > 1:
        if len(ui_telem_targets) != len(axis_ids):
            msg = (
                "Multi-axis run requires one UI telemetry target per axis (no broadcast).\n\n"
                f"Axes ({len(axis_ids)}): {', '.join(axis_ids)}\n"
                f"UI Telemetry targets provided ({len(ui_telem_targets)}): {ui_telem_targets}\n\n"
                "Fix: provide N targets, e.g.\n"
                "  --ui-telem-target 127.0.0.1:51002 --ui-telem-target 127.0.0.1:51003 ...\n"
                "or use a local range, e.g.\n"
                f"  --ui-telem-base 51002 --ui-telem-count {len(axis_ids)}\n"
            )
            return _fatal(msg)
    else:
        if len(ui_telem_targets) != 1:
            msg = (
                "Single-axis run requires exactly one UI telemetry target.\n\n"
                f"Axis: {axis_ids[0] if axis_ids else 'X'}\n"
                f"Targets provided ({len(ui_telem_targets)}): {ui_telem_targets}"
            )
            return _fatal(msg)

    axis_ui_outs = {axis_id: op_telem_outs[i] for i, axis_id in enumerate(axis_ids)}
    for a in axis_ids:
        st.ensure_axis(a)
        st.ensure_axis_cmd(a)

    def drain_intents():
        ints = op_intent_in.drain_intents(limit=200)
        if ints:
            stats["intents_in"] += len(ints)
            last_seen["intent_ts"] = time.monotonic()
            log.debug("rx intents: %d (last=%s)", len(ints), type(ints[-1]).__name__)
        return ints

    def device_step(state, cmd_frame, dt):
        nonlocal t_last_report

        # Per-axis command routing (no broadcast).
        multi_axis = len(axis_ids) > 1
        for axis_id in axis_ids:
            sp = cmd_frame.axes.get(axis_id)
            if sp is None:
                # Defensive: axis missing from frame; skip.
                continue

            frame_axis = CommandFrame(
                tick=cmd_frame.tick,
                t_s=cmd_frame.t_s,
                estop=cmd_frame.estop,
                fault=cmd_frame.fault,
                mode=cmd_frame.mode,
                axes={axis_id: sp},
                estop_reset=(
                    bool(getattr(state, "estop_reset_req_by_axis", {}).get(axis_id, False))
                    if multi_axis
                    else bool(getattr(state, "estop_reset_req_by_axis", {}).get(axis_id, False) or getattr(state, "estop_reset_req", False))
                ),
                param_ops=(
                    list(getattr(state, "pending_param_ops_by_axis", {}).get(axis_id, []))
                    if multi_axis
                    else (list(getattr(state, "pending_param_ops_by_axis", {}).get(axis_id, [])) or list(getattr(state, "pending_param_ops", [])))
                ),
            )
            axis_cmd_outs[axis_id].publish_command_frame(frame_axis)

        stats["cmd_out"] += max(1, len(axis_ids))
        last_seen["cmd_ts"] = time.monotonic()

        snaps = dev_telem_in.drain_telemetry(limit=50)
        if snaps:
            stats["dev_telem_in"] += len(snaps)
            last_seen["dev_telem_ts"] = time.monotonic()
            # Update axis-scoped caches from all received device snapshots.
            for s in snaps:
                try:
                    k = None
                    axes_keys = list(getattr(s, "axes", {}).keys())
                    if len(axes_keys) == 1:
                        k = str(axes_keys[0])
                    elif len(axes_keys) > 1:
                        # If ever multi-axis, ignore (should not happen for DenSi/PLC)
                        k = None
                    if k:
                        last_dev_estop_word_by_axis[k] = int(getattr(s, "estop_status_word", 0))
                        last_dev_params_by_axis[k] = dict(getattr(s, "params", {}) or {})
                        last_dev_param_edit_active_by_axis[k] = bool(getattr(s, "param_edit_active", False))
                        last_dev_param_edit_group_by_axis[k] = str(getattr(s, "param_edit_group", ""))

                        # Param commit state is also device-scoped.
                        last_dev_param_commit_req_id_by_axis[k] = str(getattr(s, "param_commit_req_id", ""))
                        last_dev_param_commit_group_by_axis[k] = str(getattr(s, "param_commit_group", ""))
                        last_dev_param_commit_status_by_axis[k] = str(getattr(s, "param_commit_status", "idle"))
                        last_dev_param_commit_age_ticks_by_axis[k] = int(getattr(s, "param_commit_age_ticks", 0))
                        last_dev_param_commit_unmatched_by_axis[k] = list(getattr(s, "param_commit_unmatched", []) or [])
                except Exception:
                    pass
            # Keep existing core measured-state application (axes/pos/vel/enabled/fault).
            apply_measured_snapshot(state, snaps[-1])
            log.debug("rx dev telem: %d (estop=%s fault=%s tick=%s)",
                      len(snaps), snaps[-1].estop, snaps[-1].fault, snaps[-1].tick)
        else:
            log.debug("rx dev telem: 0")

        log.debug("tx cmd frame: tick=%s estop=%s fault=%s mode=%s",
                  cmd_frame.tick, cmd_frame.estop, cmd_frame.fault, cmd_frame.mode)

        now = time.monotonic()
        if now - t_last_report >= 1.0:
            age_int = None if last_seen["intent_ts"] is None else now - last_seen["intent_ts"]
            age_dev = None if last_seen["dev_telem_ts"] is None else now - last_seen["dev_telem_ts"]
            age_cmd = None if last_seen["cmd_ts"] is None else now - last_seen["cmd_ts"]
            age_ui  = None if last_seen["ui_telem_ts"] is None else now - last_seen["ui_telem_ts"]

            log.info(
                "HB t=%.1fs intents=%d(age=%s) dev_telem=%d(age=%s) cmd_out=%d(age=%s) ui_telem_out=%d(age=%s)",
                now - t0,
                stats["intents_in"], "n/a" if age_int is None else f"{age_int:.2f}s",
                stats["dev_telem_in"], "n/a" if age_dev is None else f"{age_dev:.2f}s",
                stats["cmd_out"], "n/a" if age_cmd is None else f"{age_cmd:.2f}s",
                stats["ui_telem_out"], "n/a" if age_ui is None else f"{age_ui:.2f}s",
            )
            t_last_report = now

    def _slice_for_axis(snap: TelemetrySnapshot, axis_id: str) -> TelemetrySnapshot:
        ax_t = dict(getattr(snap, "axes", {})).get(axis_id)
        axes = {axis_id: ax_t} if ax_t is not None else {}
        densis = dict(getattr(snap, "densis", {}))
        densis_one = {axis_id: densis[axis_id]} if axis_id in densis else {}

        return TelemetrySnapshot(
            tick=int(getattr(snap, "tick", 0)),
            t_s=float(getattr(snap, "t_s", 0.0)),
            mode=str(getattr(snap, "mode", "")),
            estop=bool(getattr(snap, "estop", False)),
            fault=bool(getattr(snap, "fault", False)),
            axes=axes,
            rig_mode=str(getattr(snap, "rig_mode", "DISCOVERY")),
            densis=densis_one,
            estop_status_word=int(last_dev_estop_word_by_axis.get(axis_id, int(getattr(snap, "estop_status_word", 0)))),
            param_edit_active=bool(last_dev_param_edit_active_by_axis.get(axis_id, bool(getattr(snap, "param_edit_active", False)))),
            param_edit_group=str(last_dev_param_edit_group_by_axis.get(axis_id, str(getattr(snap, "param_edit_group", "")))),
            params=dict(last_dev_params_by_axis.get(axis_id, dict(getattr(snap, "params", {})) or {})),
            core_acks=list(getattr(snap, "core_acks", [])),
            param_commit_req_id=str(last_dev_param_commit_req_id_by_axis.get(axis_id, str(getattr(snap, "param_commit_req_id", "")))),
            param_commit_group=str(last_dev_param_commit_group_by_axis.get(axis_id, str(getattr(snap, "param_commit_group", "")))),
            param_commit_status=str(last_dev_param_commit_status_by_axis.get(axis_id, str(getattr(snap, "param_commit_status", "idle")))),
            param_commit_age_ticks=int(last_dev_param_commit_age_ticks_by_axis.get(axis_id, int(getattr(snap, "param_commit_age_ticks", 0)))),
            param_commit_unmatched=list(last_dev_param_commit_unmatched_by_axis.get(axis_id, list(getattr(snap, "param_commit_unmatched", [])) or [])),
        )

    def on_snapshot(snap: TelemetrySnapshot):
        # One HiP per axis: send a *sliced* snapshot to each UI target.
        for axis_id in axis_ids:
            tx = axis_ui_outs.get(axis_id)
            if tx is None:
                continue
            tx.publish_telemetry(_slice_for_axis(snap, axis_id))

        stats["ui_telem_out"] += max(1, len(axis_ids))
        last_seen["ui_telem_ts"] = time.monotonic()

        log.debug("tx ui telem: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)

    eng = CoreEngine(
        timebase=tb,
        state=st,
        drain_intents=drain_intents,
        handle_intent=apply_intent,
        device_step=device_step,
        on_snapshot=on_snapshot,
    )

    runner = CoreRunner(engine=eng, realtime=True)
    runner.start()
    try:
        while runner.is_alive():
            runner.join(timeout=0.25)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt: stopping core runner...")
        runner.stop()
        runner.join(timeout=2.0)
        log.info("core runner stopped")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())