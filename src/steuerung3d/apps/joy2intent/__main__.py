from __future__ import annotations

import argparse

from steuerung3d.util.app_bootstrap import bootstrap_logging

from .runtime import run
from .startup import load_runtime


def main() -> int:
    ap = argparse.ArgumentParser(prog="steuerung3d.apps.joy2intent")
    ap.add_argument("--config", default="configs/services/joy2intent.toml")
    ap.add_argument("--raw-in", default=None, help="Override RawControls UDP bind host:port")
    ap.add_argument("--intent-out", default=None, help="Override Intent UDP target host:port")
    ap.add_argument("--log-level", default="info", choices=("debug", "info", "warning", "error"))
    args = ap.parse_args()

    bootstrap_logging(role="joy2intent", log_level=args.log_level)
    runtime = load_runtime(
        config_path=str(args.config), raw_in=args.raw_in, intent_out=args.intent_out
    )
    return int(run(runtime))


if __name__ == "__main__":
    raise SystemExit(main())
