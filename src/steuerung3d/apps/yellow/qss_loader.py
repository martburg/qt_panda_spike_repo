from __future__ import annotations

from pathlib import Path


def load_base_qss() -> str:
    """Load the base Yellow QSS from the assets directory."""
    qss_path = Path(__file__).resolve().parent / "assets" / "yellow.qss"
    return qss_path.read_text(encoding="utf-8")
