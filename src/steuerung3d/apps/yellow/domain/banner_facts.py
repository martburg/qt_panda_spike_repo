# src/steuerung3d/apps/yellow/domain/banner_facts.py
"""Qt-free banner estate decoding facts.

NOTE:
    This module is kept for backwards compatibility with the Yellow UI.
    The core UDP service also needs the same decoding, so the canonical
    implementation now lives in :mod:`steuerung3d.protocol.banner_estate`.
"""

from __future__ import annotations

from steuerung3d.protocol.banner_estate import (  # re-export
    BANNER_DYNAMIC_EXCLUDE,
    derive_banner_estate_from_word,
)
