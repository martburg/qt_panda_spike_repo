from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

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
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = load_joy2intent_config(Path(args.config))

    raw_in = UdpRawControlsIn.bind(cfg.raw_in)
    intent_out = UdpIntentOut.connect(cfg.intent_out)

    st = JoyState(mode=cfg.default_mode)
    rig = JoyRig(winches=cfg.winches)
    bind = JoyBindings(
        axes=cfg.axes,
        buttons=cfg.buttons,
        invert=cfg.invert,
        deadzone=cfg.deadzone,
        expo=cfg.expo,
    )
    lim = JoyLimits(
        max_winch_mps=cfg.max_winch_mps,
        fine_scale=cfg.fine_scale,
        max_v=cfg.max_v,
    )

    dt = 1.0 / max(1.0, cfg.tick_hz)
    next_t = time.monotonic()
    last_rx_ns: int | None = None
    sent_stale_zero = False

    log.info(
        "joy2intent started mode=%s raw_in=%s intent_out=%s tick_hz=%.1f stale_after_ms=%d",
        st.mode, cfg.raw_in, cfg.intent_out, cfg.tick_hz, cfg.stale_after_ms,
    )

    while True:
        now_ns = time.monotonic_ns()

        # Drain input; keep only newest sample
        rcs = raw_in.drain_raw_controls(limit=50)
        rc: RawControls | None = rcs[-1] if rcs else None

        if rc is not None:
            last_rx_ns = now_ns
            sent_stale_zero = False
            intents = synthesize_intents(rc, st, rig, bind, lim)
            for it in intents:
                intent_out.publish_intent(it)
        else:
            # stale watchdog: if input stream dies, stop motion once
            if last_rx_ns is not None:
                age_ms = (now_ns - last_rx_ns) / 1_000_000.0
                if age_ms > cfg.stale_after_ms and not sent_stale_zero:
                    # Emit stop for both domains; core will ignore the one that doesn't match current mode
                    intent_out.publish_intent(JogCartesian(vx=0.0, vy=0.0, vz=0.0))  # type: ignore[name-defined]
                    # Stop any winches that were actively driven last tick.
                    if rig.winches and st.prev_active_winch_idxs:
                        for idx in sorted(st.prev_active_winch_idxs):
                            if 0 <= idx < len(rig.winches):
                                intent_out.publish_intent(JogWinch(winch_id=rig.winches[idx], rate=0.0))  # type: ignore[name-defined]
                        st.prev_active_winch_idxs.clear()
                    else:
                        # Fallback (legacy single-select)
                        wid = rig.winches[st.selected_winch_idx] if rig.winches else "WINCH"
                        intent_out.publish_intent(JogWinch(winch_id=wid, rate=0.0))      # type: ignore[name-defined]
                    sent_stale_zero = True

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
