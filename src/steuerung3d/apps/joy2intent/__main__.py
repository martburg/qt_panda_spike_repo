from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from dataclasses import replace

from steuerung3d.util.log_context import install_log_context
from steuerung3d.util.heartbeat import Heartbeat, ChangeTracker

from steuerung3d.core.status import StatusEmitter

from steuerung3d.protocol.udp_channels import UdpRawControlsIn, UdpIntentOut
from steuerung3d.protocol.raw_controls import RawControls

from .config import load_joy2intent_config
from .state import JoyState
from .mapping import JoyBindings, JoyLimits, JoyRig, synthesize_intents
from steuerung3d.core.intents import JogCartesian, JogWinch

log = logging.getLogger("joy2intent")


def main() -> int:
    ap = argparse.ArgumentParser(prog="steuerung3d.apps.joy2intent")
    ap.add_argument("--config", default="configs/joy2intent_gamepad.toml")
    ap.add_argument("--raw-in", default=None, help="Override RawControls UDP bind host:port")
    ap.add_argument("--intent-out", default=None, help="Override Intent UDP target host:port")
    ap.add_argument(
        "--winches",
        default=None,
        help="Override winch list as comma-separated axis ids (e.g. Anton,Debby,Cecil,Burt)",
    )
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    install_log_context(role="joy2intent")

    status = StatusEmitter.from_env(default_service="joy2intent")

    cfg = load_joy2intent_config(Path(args.config))

    # Stack profiles may own infrastructure wiring (ports / axis list). Allow explicit overrides.
    def _parse_hostport(s: str) -> tuple[str, int]:
        host, port = s.rsplit(":", 1)
        return host.strip(), int(port)

    if args.raw_in:
        cfg = replace(cfg, raw_in=_parse_hostport(str(args.raw_in)))
    if args.intent_out:
        cfg = replace(cfg, intent_out=_parse_hostport(str(args.intent_out)))
    if args.winches:
        winches = [w.strip() for w in str(args.winches).split(",") if w.strip()]
        if winches:
            cfg = replace(cfg, winches=winches)

    raw_in = UdpRawControlsIn.bind(cfg.raw_in)
    intent_out = UdpIntentOut.connect(cfg.intent_out)

    st = JoyState(mode=cfg.default_mode)
    rig = JoyRig(winches=cfg.winches)
    bind = JoyBindings(
        axes=cfg.axes,
        buttons=cfg.buttons,
        select_buttons=list(cfg.select_buttons or []),
        invert=cfg.invert,
        deadzone=cfg.deadzone,
        expo=cfg.expo,
    )
    lim = JoyLimits(
        max_winch_mps=cfg.max_winch_mps,
        fine_scale=cfg.fine_scale,
        max_v=cfg.manual_max_v,
    )

    dt = 1.0 / max(1.0, cfg.tick_hz)
    next_t = time.monotonic()
    last_rx_ns: int | None = None
    sent_stale_zero = False

    hb = Heartbeat("joy2intent", interval_s=1.0)
    ch = ChangeTracker()

    log.info(
        "joy2intent started mode=%s raw_in=%s intent_out=%s tick_hz=%.1f stale_after_ms=%d",
        st.mode, cfg.raw_in, cfg.intent_out, cfg.tick_hz, cfg.stale_after_ms,
    )

    while True:
        now_ns = time.monotonic_ns()

        # Drain input; keep only newest sample
        rcs = raw_in.drain_raw_controls(limit=50)
        rc: RawControls | None = rcs[-1] if rcs else None

        # Heartbeat counters
        hb.inc("rx", len(rcs))

        if last_rx_ns is not None:
            hb.set("age_ms", int((now_ns - last_rx_ns) / 1_000_000.0))
        hb.set("mode", getattr(st, "mode", "?"))

        if rc is not None:
            last_rx_ns = now_ns
            sent_stale_zero = False
            intents = synthesize_intents(st, rc, bind, rig, lim)

            # Minimal "what changed" logs (no spam)
            try:
                pressed = {i for i, v in enumerate(rc.buttons) if v}
            except Exception:
                pressed = set()
            dm_btn = bind.buttons.get("deadman")
            deadman = (dm_btn is not None) and (dm_btn in pressed)
            if ch.changed("deadman", bool(deadman)):
                log.info("deadman=%s", bool(deadman))

            # selection (setup_manual): log when selection changes
            try:
                sel = []
                for i, b in enumerate(bind.select_buttons or []):
                    if b in pressed and i < len(rig.winches):
                        sel.append(rig.winches[i])
                if ch.changed("selected", tuple(sel)):
                    log.info("selected=%s", list(sel))
            except Exception:
                pass

            hb.inc("intent", len(intents))
            for it in intents:
                intent_out.publish_intent(it)
        else:
            # stale watchdog: if input stream dies, stop motion once
            if last_rx_ns is not None:
                age_ms = (now_ns - last_rx_ns) / 1_000_000.0
                if age_ms > cfg.stale_after_ms and not sent_stale_zero:
                    # Emit stop for both domains; core will ignore the one that doesn't match current mode
                    intent_out.publish_intent(JogCartesian(vx=0.0, vy=0.0, vz=0.0))
                    # Stop any winches that were actively driven last tick.
                    if rig.winches and st.prev_active_winch_idxs:
                        for idx in sorted(st.prev_active_winch_idxs):
                            if 0 <= idx < len(rig.winches):
                                intent_out.publish_intent(JogWinch(winch_id=rig.winches[idx], rate=0.0))
                        st.prev_active_winch_idxs.clear()
                    else:
                        # Fallback (legacy single-select)
                        wid = rig.winches[st.selected_winch_idx] if rig.winches else "WINCH"
                        intent_out.publish_intent(JogWinch(winch_id=wid, rate=0.0))
                    sent_stale_zero = True
                    log.warning("raw input stale (age_ms=%.1f) -> emitted stop", age_ms)

        # Structured birds-eye status (side-channel; does not affect PLC packets)
        if status is not None:
            age_ms_f: float | None = None
            if last_rx_ns is not None:
                age_ms_f = (now_ns - last_rx_ns) / 1_000_000.0
            stale = (age_ms_f is not None) and (age_ms_f > cfg.stale_after_ms)
            level = 'WARN' if stale else 'OK'
            age_ms_i = int(age_ms_f) if age_ms_f is not None else None
            status.emit_every(
                0.5,
                level=level,
                summary=f"mode={st.mode} age_ms={age_ms_i if age_ms_i is not None else 'NA'} stale_stop={sent_stale_zero}",
                mode=st.mode,
                age_ms=age_ms_i,
                stale_stop=sent_stale_zero,
                raw_in=f"{cfg.raw_in[0]}:{cfg.raw_in[1]}",
                intent_out=f"{cfg.intent_out[0]}:{cfg.intent_out[1]}",
                winches=list(rig.winches),
            )

        # Periodic summary
        hb.emit(log)

        next_t += dt
        sleep_s = next_t - time.monotonic()
        if sleep_s > 0:
            time.sleep(sleep_s)
        else:
            next_t = time.monotonic()

    # unreachable
    # return 0


if __name__ == "__main__":
    raise SystemExit(main())
