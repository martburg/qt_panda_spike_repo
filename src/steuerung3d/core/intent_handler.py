from __future__ import annotations

"""Intent application (public entry points).

This module intentionally stays small.
Implementation details live in :mod:`steuerung3d.core.intent_handler_impl`.

Lane 1 refactor: no semantic changes; public imports stay stable.
"""

from steuerung3d.core.intent_handler_impl import apply_intent, enforce_core_mode_actions

__all__ = ["apply_intent", "enforce_core_mode_actions"]
