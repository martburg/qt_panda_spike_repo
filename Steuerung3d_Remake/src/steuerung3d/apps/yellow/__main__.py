from __future__ import annotations

import sys
import argparse

from PySide6.QtWidgets import QApplication

from steuerung3d.apps.yellow.ui_shell import build_yellow_window


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--role", choices=("ip", "cfc"), default="ip")
    args = p.parse_args()

    app = QApplication(sys.argv)
    win = build_yellow_window(role=args.role)
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
