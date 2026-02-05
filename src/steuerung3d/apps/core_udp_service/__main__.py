from __future__ import annotations

import time
import logging

import argparse
import signal
from typing import Tuple, List

from steuerung3d.util.log_context import install_log_context
from steuerung3d.util.heartbeat import Heartbeat, ChangeTracker

from steuerung3d.core.status import StatusEmitter

from steuerung3d.common.timebase import Timebase
from steuerung3d.core.engine import CoreEngine
from steuerung3d.core.intent_handler import apply_intent
from steuerung3d.core.command_frame import CommandFrame
from steuerung3d.core.state import MachineState
from steuerung3d.core.telemetry import TelemetrySnapshot, apply_measured_snapshot
from steuerung3d.protocol.core_runner import CoreRunner
from steuerung3d.protocol.axis_router import AxisRouter
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
    install_log_context(role="core")
    log.info("log level = %s", args.log_level.upper())

    # Optional structured heartbeat (supervisor birds-eye). Controlled by env:
    #   ST3D_STATUS_OUT, ST3D_STACK_NAME, ST3D_SERVICE_NAME, ST3D_INSTANCE
    status = StatusEmitter.from_env(default_service="core")

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

    # Track key state transitions (avoid log spam while still giving operators context).
    state_ch = ChangeTracker()

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

    # Router centralizes strict per-axis shaping (commands + UI snapshots)
    # and holds device-scoped caches used for axis-pinned UI values.

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

    router = AxisRouter(
        axis_ids=axis_ids,
        dev_cmd_out_by_axis=axis_cmd_outs,
        ui_telem_out_by_axis=axis_ui_outs,
    )

    def drain_intents():
        ints = op_intent_in.drain_intents(limit=200)
        if ints:
            stats["intents_in"] += len(ints)
            last_seen["intent_ts"] = time.monotonic()
            log.debug("rx intents: %d (last=%s)", len(ints), type(ints[-1]).__name__)
        return ints

    def device_step(state, cmd_frame, dt):
        nonlocal t_last_report

        # Per-axis command routing (no broadcast). Router reduces multi-axis frames.
        multi_axis = len(axis_ids) > 1
        if multi_axis:
            estop_reset_by_axis = dict(getattr(state, "estop_reset_req_by_axis", {}) or {})
            param_ops_by_axis = {k: list(v) for k, v in dict(getattr(state, "pending_param_ops_by_axis", {}) or {}).items()}
        else:
            axis0 = axis_ids[0]
            estop_reset_by_axis = {
                axis0: bool(dict(getattr(state, "estop_reset_req_by_axis", {}) or {}).get(axis0, False) or getattr(state, "estop_reset_req", False))
            }
            per_axis_ops = list(dict(getattr(state, "pending_param_ops_by_axis", {}) or {}).get(axis0, []))
            global_ops = list(getattr(state, "pending_param_ops", []) or [])
            param_ops_by_axis = {axis0: (per_axis_ops or global_ops)}

        sent = router.publish_command_frames(
            cmd_frame,
            estop_reset_by_axis=estop_reset_by_axis,
            param_ops_by_axis=param_ops_by_axis,
        )
        stats["cmd_out"] += max(1, sent)
        last_seen["cmd_ts"] = time.monotonic()

        snaps = dev_telem_in.drain_telemetry(limit=50)
        if snaps:
            stats["dev_telem_in"] += len(snaps)
            last_seen["dev_telem_ts"] = time.monotonic()
            # Update axis-scoped caches from all received device snapshots.
            router.ingest_device_telemetry(snaps)
            # Device-side measured telemetry can arrive from multiple sources
            # (e.g. one DenSi process per axis). Apply *all* snapshots so each
            # axis' measured/meta fields get updated, instead of only the most
            # recent datagram.
            for snap in snaps:
                apply_measured_snapshot(state, snap)
            log.debug(
                "rx dev telem: %d (last estop=%s fault=%s tick=%s)",
                len(snaps),
                snaps[-1].estop,
                snaps[-1].fault,
                snaps[-1].tick,
            )
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
                "HB t=%.1fs mode=%s rig=%s estop=%s fault=%s claims=%d | intents=%d(age=%s) dev_telem=%d(age=%s) cmd_out=%d(age=%s) ui_telem_out=%d(age=%s)",
                now - t0,
                getattr(getattr(state, "mode", ""), "value", getattr(state, "mode", "")),
                getattr(state, "rig_mode", "DISCOVERY"),
                bool(getattr(state, "estop", False)),
                bool(getattr(state, "fault", False)),
                len(dict(getattr(state, "axis_claims", {}) or {})),
                stats["intents_in"], "n/a" if age_int is None else f"{age_int:.2f}s",
                stats["dev_telem_in"], "n/a" if age_dev is None else f"{age_dev:.2f}s",
                stats["cmd_out"], "n/a" if age_cmd is None else f"{age_cmd:.2f}s",
                stats["ui_telem_out"], "n/a" if age_ui is None else f"{age_ui:.2f}s",
            )
            t_last_report = now

    # Lifetick tracing: log Core->UI device tick at most every 0.5s per axis.
    _lt_last_ui_log_s_by_axis: dict[str, float] = {}

    def on_snapshot(snap: TelemetrySnapshot):
        # Log key state changes once (helps a lot during field debugging).
        try:
            mode_v = str(getattr(snap, "mode", ""))
            estop_v = bool(getattr(snap, "estop", False))
            fault_v = bool(getattr(snap, "fault", False))
            rig_v = str(getattr(snap, "rig_mode", ""))
            if (
                state_ch.changed("mode", mode_v)
                or state_ch.changed("estop", estop_v)
                or state_ch.changed("fault", fault_v)
                or state_ch.changed("rig_mode", rig_v)
            ):
                log.info("state: mode=%s estop=%s fault=%s rig_mode=%s", mode_v, estop_v, fault_v, rig_v)

            claims = tuple(sorted(dict(getattr(st, "axis_claims", {}) or {}).items()))
            if state_ch.changed("claims", claims):
                log.info("claims: %s", dict(claims))

            pe = bool(getattr(st, "param_edit_active", False))
            pg = str(getattr(st, "param_edit_group", ""))
            if state_ch.changed("param_edit", (pe, pg)):
                log.info("param_edit: active=%s group=%s", pe, pg)
        except Exception:
            pass

        # One HiP per axis: send a *sliced* snapshot to each UI target.
        router.publish_ui_snapshot(snap)

        # LIFETICK trace: Core -> HiP (TelemetrySnapshot.axes[axis].device_tick)
        for axis_id in axis_ids:
            try:
                ax = dict(getattr(snap, "axes", {}) or {}).get(axis_id)
                dev_tick = getattr(ax, "device_tick", None)
                now_s = time.monotonic()
                last_s = float(_lt_last_ui_log_s_by_axis.get(axis_id, 0.0))
                if dev_tick is not None and (now_s - last_s) >= 0.5:
                    _lt_last_ui_log_s_by_axis[axis_id] = now_s
                    log.debug("LIFETICK Core tx UI telem: axis=%s device_tick=%s", axis_id, int(dev_tick))
            except Exception:
                pass

        stats["ui_telem_out"] += max(1, len(axis_ids))
        last_seen["ui_telem_ts"] = time.monotonic()

        log.debug("tx ui telem: tick=%s estop=%s fault=%s", snap.tick, snap.estop, snap.fault)

        # Structured heartbeat for supervisor birds-eye (PLC telemetry remains unchanged).
        if status is not None:
            try:
                now = time.monotonic()
                age_int = None if last_seen["intent_ts"] is None else (now - float(last_seen["intent_ts"]))
                age_dev = None if last_seen["dev_telem_ts"] is None else (now - float(last_seen["dev_telem_ts"]))
                age_cmd = None if last_seen["cmd_ts"] is None else (now - float(last_seen["cmd_ts"]))
                age_ui  = None if last_seen["ui_telem_ts"] is None else (now - float(last_seen["ui_telem_ts"]))

                estop_v = bool(getattr(snap, "estop", False))
                fault_v = bool(getattr(snap, "fault", False))
                mode_v = getattr(getattr(snap, "mode", ""), "value", getattr(snap, "mode", ""))

                # Simple policy: ERR on estop/fault; WARN on stale inputs; else OK.
                stale = False
                for a in (age_int, age_dev):
                    if a is not None and a > 2.0:
                        stale = True
                level = "ERR" if (estop_v or fault_v) else ("WARN" if stale else "OK")

                summary = (
                    f"tick={int(getattr(snap, 'tick', 0))} mode={mode_v} "
                    f"estop={int(estop_v)} fault={int(fault_v)} "
                    f"age_int_ms={-1 if age_int is None else int(age_int*1000)} "
                    f"age_dev_ms={-1 if age_dev is None else int(age_dev*1000)}"
                )

                # Discovered devices (REAL) or spawned sims (SIM): expose as fields so the
                # supervisor can provision a HiP pool in REAL mode.
                try:
                    densis = getattr(snap, "densis", {}) or {}
                    devices = sorted([str(k) for k in densis.keys()])
                except Exception:
                    devices = []

                status.emit_every(
                    level=level,
                    summary=summary,
                    fields={
                        "tick": int(getattr(snap, "tick", 0) or 0),
                        "mode": str(mode_v),
                        "estop": estop_v,
                        "fault": fault_v,
                        "devices": devices[:32],
                        "devices_n": len(devices),
                        "age_int_ms": None if age_int is None else age_int * 1000.0,
                        "age_dev_ms": None if age_dev is None else age_dev * 1000.0,
                        "age_cmd_ms": None if age_cmd is None else age_cmd * 1000.0,
                        "age_ui_ms": None if age_ui is None else age_ui * 1000.0,
                    },
                )
            except Exception:
                pass

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