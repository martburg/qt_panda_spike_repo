from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path



def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Qt + Panda3D integration spike")
    parser.add_argument(
        "--backend",
        choices=("native", "offscreen"),
        default="native",
        help="Viewport backend to run",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument(
        "--pick-log",
        default="pick_diagnostics.jsonl",
        help="Path to the JSONL file that receives per-click pick diagnostics when --pick-debug is enabled",
    )
    parser.add_argument(
        "--pick-debug",
        action="store_true",
        help="Enable pick diagnostics logging and debug hit markers",
    )
    parser.add_argument(
        "--show-dome",
        action="store_true",
        help="Render the camera-centered debug dome",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    ns = parser.parse_args(argv)

    from PySide6.QtWidgets import QApplication

    from .ui.main_window import MainWindow

    app = QApplication.instance() or QApplication([])
    window = MainWindow(
        backend_name=ns.backend,
        pick_log_path=Path(ns.pick_log),
        pick_debug=bool(ns.pick_debug),
        show_dome=bool(ns.show_dome),
    )
    window.resize(max(640, ns.width), max(480, ns.height))
    window.show()
    return app.exec()
