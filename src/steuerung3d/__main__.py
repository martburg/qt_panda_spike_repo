"""Package entry point.

This makes `python -m steuerung3d ...` the unified CLI.
"""

from __future__ import annotations

from steuerung3d.cli.__main__ import main

if __name__ == "__main__":
    raise SystemExit(main())
