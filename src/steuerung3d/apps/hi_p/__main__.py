from __future__ import annotations

import argparse
import sys

import logging
from pathlib import Path

from steuerung3d.util.log_context import install_log_context
from steuerung3d.config.toml_loader import load_toml

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window
from steuerung3d.apps.yellow.controllers.hip_controller import HiPController
#from steuerung3d.protocol.transport import InMemTransport
from steuerung3d.protocol.udp_channels import UdpIntentOut, UdpTelemetryIn
# and import HiPController directly if you changed controllers/__init__.py:
from steuerung3d.apps.yellow.controllers.hip_controller import HiPController

log = logging.getLogger("hi_p")


def _load_config(path: str | None) -> dict:
    if not path:
        return {}
    try:
        return dict(load_toml(Path(path)))
    except Exception:
        return {}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", choices=("ip", "pilot", "ft"), default="ip")
    ap.add_argument("--axis", default="", help="Optional: pin this HiP window to a single axis id.")
    ap.add_argument(
        "--telem-in",
        default="127.0.0.1:51002",
        help="TelemetryIn bind address host:port (default 127.0.0.1:51002).",
    )
    ap.add_argument(
        "--intent-out",
        default="127.0.0.1:51001",
        help="IntentOut target host:port (default 127.0.0.1:51001).",
    )
    ap.add_argument("--config", default="", help="TOML config path for HiP runtime.")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    install_log_context(role="hi_p", axis=(args.axis or ""))
    log.info("log level = %s", args.log_level.upper())
    cfg = _load_config(args.config or None)
    engine_cfg = cfg.get("engine", {}) or {}
    shadow_mode = str(engine_cfg.get("shadow_mode", "old") or "old").strip().lower()
    if shadow_mode not in ("old", "shadow", "new"):
        shadow_mode = "old"
    def _parse_hostport(s: str, default_host: str = "127.0.0.1"):
        s = (s or "").strip()
        if s.count(":") == 0:
            return (default_host, int(s))
        h, p = s.rsplit(":", 1)
        h = h.strip() or default_host
        return (h, int(p))

    intent_out_addr = _parse_hostport(args.intent_out)
    telem_in_addr = _parse_hostport(args.telem_in)

    log.info("HI-P target IntentOut=%s  bind TelemetryIn=%s", intent_out_addr, telem_in_addr)


    app = QApplication(sys.argv)
    win = build_yellow_window(role="ip")

    intent_out = UdpIntentOut.connect(intent_out_addr)
    telemetry_in = UdpTelemetryIn.bind(telem_in_addr)

    ctl = HiPController(
        win=win,
        intent_out=intent_out,
        telemetry_in=telemetry_in,
        shadow_mode=shadow_mode,
    )
    axis_label = (str(args.axis).strip() or "*")
    if str(args.axis).strip():
        ctl.set_fixed_axis(str(args.axis).strip(), lock_combo=True)
    # Make the window self-identifying (axis + ports) to reduce integration confusion.
    try:
        win.setWindowTitle(
            f"HMI – HiP ({axis_label})  telem-in={telem_in_addr[0]}:{telem_in_addr[1]}  intent->{intent_out_addr[0]}:{intent_out_addr[1]}"
        )
    except Exception:
        pass
    ctl.start_polling(period_ms=50)

    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
