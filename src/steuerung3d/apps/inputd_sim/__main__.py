from __future__ import annotations

import argparse
import logging
from pathlib import Path

from steuerung3d.util.app_bootstrap import bootstrap_logging

from .config import load_inputd_sim_config
from .runtime import run

log = logging.getLogger("inputd_sim")


def main() -> int:
    ap = argparse.ArgumentParser(prog="steuerung3d.apps.inputd_sim")
    ap.add_argument("--config", default="configs/services/inputd_sim_smoke.toml")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    bootstrap_logging(role="inputd_sim", log_level=args.log_level)
    cfg = load_inputd_sim_config(Path(args.config))

    log.info(
        "inputd_sim starting out=%s tick_hz=%.1f control_in=%s scenario=%s",
        cfg.out_addr,
        cfg.tick_hz,
        cfg.control_in_addr,
        cfg.scenario_path,
    )

    try:
        return run(cfg)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
