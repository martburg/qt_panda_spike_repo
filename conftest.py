"""Pytest helper.

This repo uses a src/ layout. When running tests without installing the package,
we add ./src to sys.path so `import steuerung3d` works.

If you prefer, you can instead do: `python -m pip install -e .`
"""

from __future__ import annotations

import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))
